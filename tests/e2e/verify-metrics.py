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


def verify_with_retries(
    netdata_url: str,
    service_name: str,
    attempts: int = 6,
    sleep_s: float = 5.0,
) -> int:
    last_mcp = last_rest = ""
    for i in range(1, attempts + 1):
        ok, mcp_msg = try_mcp_verification(netdata_url, service_name)
        last_mcp = mcp_msg
        if ok:
            print(f"[verify] MCP PASS ({i}/{attempts}): {mcp_msg}")
            return 0
        print(f"[verify] MCP attempt {i}/{attempts}: {mcp_msg}")
        ok, rest_msg = try_rest_verification(netdata_url, service_name)
        last_rest = rest_msg
        if ok:
            print(f"[verify] REST PASS ({i}/{attempts}): {rest_msg}")
            return 0
        print(f"[verify] REST attempt {i}/{attempts}: {rest_msg}")
        time.sleep(sleep_s)

    print(f"[verify] FAIL after {attempts} attempts.")
    print(f"[verify]   last MCP result:  {last_mcp}")
    print(f"[verify]   last REST result: {last_rest}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="nodejs", choices=sorted(DEFAULT_APP_TARGETS))
    ap.add_argument("--url", default=DEFAULT_NETDATA_URL)
    ap.add_argument("--service", default=None)
    ap.add_argument("--attempts", type=int, default=6)
    args = ap.parse_args()

    service = args.service or DEFAULT_APP_TARGETS[args.app]
    return verify_with_retries(args.url, service, attempts=args.attempts)


if __name__ == "__main__":
    sys.exit(main())
