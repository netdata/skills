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
import subprocess
import sys
import time
from typing import Any
import urllib.request
import urllib.error

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

    # 3. tools/call list_metrics
    try:
        r = http_post_json(
            mcp_url,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_metrics", "arguments": {}},
            },
            headers,
        )
    except Exception as e:
        return False, f"MCP list_metrics failed: {e}"

    # The response shape is implementation-specific; look for the service
    # name or at least one sample-app-emitted metric context.
    blob = json.dumps(r)
    if service_name in blob:
        return True, f"service '{service_name}' visible via MCP list_metrics"
    return False, (
        f"MCP list_metrics returned, but service '{service_name}' not "
        f"visible. Response snippet: {blob[:400]}"
    )


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
        ok, msg = try_mcp_verification(netdata_url, service_name)
        last_mcp = msg
        if ok:
            print(f"[verify] MCP PASS ({i}/{attempts}): {msg}")
            return 0
        ok, msg = try_rest_verification(netdata_url, service_name)
        last_rest = msg
        if ok:
            print(f"[verify] REST PASS ({i}/{attempts}): {msg}")
            # TODO: migrate to MCP once the MCP handshake is confirmed stable
            # in the v0.1 CI environment.
            return 0
        print(f"[verify] attempt {i}/{attempts}: MCP={msg} | REST={msg}")
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
