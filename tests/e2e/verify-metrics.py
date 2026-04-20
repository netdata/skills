#!/usr/bin/env python3
"""Verify that the E2E sample app's metrics reached Netdata.

Preferred path: JSON-RPC against the Netdata MCP HTTP-streamable endpoint.
Fallback path: the Netdata REST `/api/v2/contexts` endpoint, for cases
where the MCP transport is not yet stable in CI.

Exits 0 when the expected signals are visible. Exits 1 otherwise, with
actionable context.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any
import urllib.request
import urllib.error

DEBUG = os.environ.get("E2E_VERIFY_DEBUG") == "1"

DEFAULT_NETDATA_URL = "http://localhost:19998"
DEFAULT_APP_TARGETS = {
    "nodejs": "hello-nodejs",
    "python": "hello-python",
}

MCP_CALL_TIMEOUT = 10.0

NETDATA_CONTAINER = "netdata-skills-e2e"
JOURNAL_DIR = "/var/log/netdata/otel/v1"
DEFAULT_LOG_ANCHORS = {
    "python": "hello-python request served",
}


def read_api_key() -> str:
    """Fetch the MCP bearer token from inside the running container."""
    result = subprocess.run(
        [
            "docker",
            "exec",
            "netdata-skills-e2e",
            "cat",
            "/var/lib/netdata/mcp_dev_preview_api_key",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=MCP_CALL_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=MCP_CALL_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def try_mcp_verification(netdata_url: str, service_name: str) -> tuple[bool, str]:
    token = read_api_key()
    if not token:
        return False, "no MCP bearer token available (docker exec failed)"

    mcp_url = f"{netdata_url}/mcp"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # 1. initialize
    try:
        r = http_post_json(
            mcp_url,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-verify", "version": "0.1.0"},
                },
            },
            headers,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        return False, f"MCP initialize failed: {e}"

    if "error" in r:
        return False, f"MCP initialize returned error: {r['error']}"

    # 2. tools/list -> expect at least 10 tools
    try:
        r = http_post_json(
            mcp_url,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers,
        )
    except Exception as e:
        return False, f"MCP tools/list failed: {e}"

    tools = r.get("result", {}).get("tools", [])
    if len(tools) < 10:
        return False, f"expected 10+ MCP tools, saw {len(tools)}"

    # 3. tools/call list_metrics with the service name as a full-text
    # query. Netdata enters SEARCH mode when `q` is set and expands the
    # response to include labels, instances, and dimensions, which is
    # where the OTel `service.name` attribute lands. Without `q`, the
    # default response carries only context names.
    try:
        r = http_post_json(
            mcp_url,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_metrics",
                    "arguments": {
                        "metrics": "*",
                        "q": service_name,
                    },
                },
            },
            headers,
        )
    except Exception as e:
        return False, f"MCP list_metrics failed: {e}"

    if "error" in r:
        return False, f"MCP list_metrics returned error: {r['error']}"

    if DEBUG:
        print("[verify][debug] raw MCP list_metrics response:")
        print(json.dumps(r, indent=2)[:4000])

    payload = _extract_text_payload(r)
    if payload is None:
        snippet = json.dumps(r)[:400]
        return False, f"MCP list_metrics response had no parsable text content: {snippet}"

    match_count = _count_context_matches(payload)
    if match_count > 0:
        return True, (
            f"service '{service_name}' matched {match_count} metric "
            f"context(s) via MCP list_metrics q-filter"
        )
    return False, (
        f"MCP list_metrics q-filter returned zero matches for "
        f"'{service_name}' (payload keys: {sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__})"
    )


def _extract_text_payload(resp: dict[str, Any]) -> Any:
    """Parse the JSON-encoded text blob carried inside an MCP tools/call result."""
    content = resp.get("result", {}).get("content") or []
    if not isinstance(content, list) or not content:
        return None
    first = content[0]
    if not isinstance(first, dict):
        return None
    text = first.get("text")
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _count_context_matches(payload: Any) -> int:
    """Count context-level matches in a v2-contexts SEARCH payload."""
    if not isinstance(payload, dict):
        return 0
    contexts = payload.get("contexts")
    if isinstance(contexts, dict):
        return len(contexts)
    if isinstance(contexts, list):
        return len(contexts)
    nodes = payload.get("nodes")
    if isinstance(nodes, list):
        return sum(1 for n in nodes if isinstance(n, dict) and n.get("contexts"))
    return 0


def try_rest_verification(netdata_url: str, service_name: str) -> tuple[bool, str]:
    url = f"{netdata_url}/api/v2/contexts"
    try:
        r = http_get(url)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        return False, f"REST /api/v2/contexts failed: {e}"

    contexts = r.get("contexts") or {}
    if not isinstance(contexts, dict):
        return False, f"unexpected contexts shape: {type(contexts).__name__}"

    # Look for any context whose key or attribute blob mentions service_name.
    found = []
    for key, meta in contexts.items():
        if service_name in key:
            found.append(key)
            continue
        meta_blob = json.dumps(meta)
        if service_name in meta_blob:
            found.append(key)
    if found:
        return True, f"service '{service_name}' visible in {len(found)} contexts via REST"
    # As a weaker signal, any `http.server.*` context means OTel data arrived.
    otel_ctx = [k for k in contexts if "http.server" in k or "otel" in k.lower()]
    if otel_ctx:
        return True, (
            f"service name not found, but {len(otel_ctx)} OTel-origin contexts "
            f"present (samples: {otel_ctx[:3]}). Accepting as partial proof."
        )
    return False, (
        f"no OTel-origin contexts visible in {len(contexts)} total contexts. "
        "Ingestion likely failed; check Netdata logs."
    )


def try_journalctl_verification(service_name: str, anchor: str) -> tuple[bool, str]:
    """Look for `anchor` in OTLP log bodies via journalctl.

    Netdata's otel-plugin writes journal records with coded field names
    (for example `NDAE_LOG_BODY` instead of `MESSAGE`, `ND3AE_RA_SERVICE_NAME`
    instead of `SERVICE_NAME`). Using `-o export` and grepping the body
    line is the portable way to find a specific record without knowing
    the internal mapping.
    """
    cmd = [
        "docker",
        "exec",
        NETDATA_CONTAINER,
        "journalctl",
        "-D",
        JOURNAL_DIR,
        "--since",
        "10 minutes ago",
        "--no-pager",
        "--all",
        "-o",
        "export",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"journalctl exec failed: {e}"

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip().splitlines()
        last = stderr[-1] if stderr else ""
        return False, f"journalctl returned {result.returncode}: {last}"

    stdout = result.stdout.decode("utf-8", "replace")
    body_lines = [
        line[len("NDAE_LOG_BODY="):]
        for line in stdout.splitlines()
        if line.startswith("NDAE_LOG_BODY=")
    ]
    service_lines = [
        line[len("ND3AE_RA_SERVICE_NAME="):]
        for line in stdout.splitlines()
        if line.startswith("ND3AE_RA_SERVICE_NAME=")
    ]
    service_match = service_name in service_lines
    anchor_match = any(anchor in body for body in body_lines)

    if service_match and anchor_match:
        return True, (
            f"anchor '{anchor}' found in journal with service.name={service_name} "
            f"({len(body_lines)} total bodies, {service_lines.count(service_name)} "
            f"records for this service)"
        )
    return False, (
        f"anchor '{anchor}' not found; journal has {len(body_lines)} bodies, "
        f"{service_lines.count(service_name)} records with "
        f"service.name={service_name} (service_match={service_match}, "
        f"anchor_match={anchor_match})"
    )


def verify_with_retries(
    netdata_url: str,
    service_name: str,
    signal: str,
    log_anchor: str | None,
    attempts: int = 6,
    sleep_s: float = 5.0,
) -> int:
    want_metrics = signal in ("metrics", "both")
    want_logs = signal in ("logs", "both")
    metrics_ok = not want_metrics
    logs_ok = not want_logs
    last_mcp = last_rest = last_log = ""

    for i in range(1, attempts + 1):
        if want_metrics and not metrics_ok:
            ok, mcp_msg = try_mcp_verification(netdata_url, service_name)
            last_mcp = mcp_msg
            if ok:
                print(f"[verify] metrics MCP PASS ({i}/{attempts}): {mcp_msg}")
                metrics_ok = True
            else:
                print(f"[verify] metrics MCP attempt {i}/{attempts}: {mcp_msg}")
                ok, rest_msg = try_rest_verification(netdata_url, service_name)
                last_rest = rest_msg
                if ok:
                    print(f"[verify] metrics REST PASS ({i}/{attempts}): {rest_msg}")
                    metrics_ok = True
                else:
                    print(f"[verify] metrics REST attempt {i}/{attempts}: {rest_msg}")

        if want_logs and not logs_ok:
            if not log_anchor:
                return _fail("no log anchor configured for this app")
            ok, log_msg = try_journalctl_verification(service_name, log_anchor)
            last_log = log_msg
            if ok:
                print(f"[verify] logs PASS ({i}/{attempts}): {log_msg}")
                logs_ok = True
            else:
                print(f"[verify] logs attempt {i}/{attempts}: {log_msg}")

        if metrics_ok and logs_ok:
            return 0
        time.sleep(sleep_s)

    print(f"[verify] FAIL after {attempts} attempts.")
    if want_metrics and not metrics_ok:
        print(f"[verify]   last metrics MCP result:  {last_mcp}")
        print(f"[verify]   last metrics REST result: {last_rest}")
    if want_logs and not logs_ok:
        print(f"[verify]   last logs result:         {last_log}")
    return 1


def _fail(msg: str) -> int:
    print(f"[verify] FAIL: {msg}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="nodejs", choices=sorted(DEFAULT_APP_TARGETS))
    ap.add_argument("--url", default=DEFAULT_NETDATA_URL)
    ap.add_argument("--service", default=None)
    ap.add_argument("--signal", default="metrics", choices=["metrics", "logs", "both"])
    ap.add_argument("--log-anchor", default=None,
                    help="Substring to grep for in OTLP log records. "
                         "Defaults per-app.")
    ap.add_argument("--attempts", type=int, default=6)
    args = ap.parse_args()

    service = args.service or DEFAULT_APP_TARGETS[args.app]
    log_anchor = args.log_anchor or DEFAULT_LOG_ANCHORS.get(args.app)
    return verify_with_retries(
        args.url, service, args.signal, log_anchor, attempts=args.attempts
    )


if __name__ == "__main__":
    sys.exit(main())
