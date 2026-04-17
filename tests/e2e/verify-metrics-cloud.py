#!/usr/bin/env python3
"""Verify that a service's OTel metrics are visible in Netdata Cloud.

Parallel to ``verify-metrics.py`` (which talks to a local Agent MCP),
this script queries the Netdata Cloud MCP endpoint at
``https://app.netdata.cloud/api/v1/mcp`` using a bearer token.

Typical flow:

1. A local Netdata Agent receives the sample app's OTLP metrics.
2. That Agent is claimed to a Netdata Cloud space and streams data.
3. This script hits the Cloud MCP endpoint, calls ``list_metrics``
   with a q-filter for the service name, and expects at least one
   matching context.

Required environment:

- ``NETDATA_CLOUD_API_TOKEN``   bearer token for Cloud MCP
- (optional) ``NETDATA_CLOUD_MCP_URL``
      override the endpoint; default
      ``https://app.netdata.cloud/api/v1/mcp``

Exit 0 when the service is visible in Cloud, non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
import urllib.request
import urllib.error

DEFAULT_CLOUD_MCP_URL = "https://app.netdata.cloud/api/v1/mcp"
MCP_CALL_TIMEOUT = 15.0
DEBUG = os.environ.get("E2E_VERIFY_DEBUG") == "1"


def http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=MCP_CALL_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cloud_mcp_call(
    url: str,
    token: str,
    method: str,
    params: dict[str, Any] | None = None,
    req_id: int = 1,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        payload["params"] = params
    return http_post_json(url, payload, headers)


def extract_text_payload(resp: dict[str, Any]) -> Any:
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


def count_context_matches(payload: Any) -> int:
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


def probe_once(url: str, token: str, service_name: str) -> tuple[bool, str]:
    try:
        r = cloud_mcp_call(
            url,
            token,
            "initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-verify-cloud", "version": "0.1.0"},
            },
            req_id=1,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        return False, f"Cloud MCP initialize failed: {e}"
    if "error" in r:
        return False, f"Cloud MCP initialize returned error: {r['error']}"

    try:
        r = cloud_mcp_call(
            url,
            token,
            "tools/call",
            params={
                "name": "list_metrics",
                "arguments": {"metrics": "*", "q": service_name},
            },
            req_id=2,
        )
    except Exception as e:
        return False, f"Cloud MCP list_metrics failed: {e}"
    if "error" in r:
        return False, f"Cloud MCP list_metrics returned error: {r['error']}"

    if DEBUG:
        print("[verify-cloud][debug] raw Cloud MCP list_metrics response:")
        print(json.dumps(r, indent=2)[:4000])

    payload = extract_text_payload(r)
    if payload is None:
        snippet = json.dumps(r)[:400]
        return False, f"Cloud MCP list_metrics response had no parsable text content: {snippet}"

    match_count = count_context_matches(payload)
    if match_count > 0:
        return True, (
            f"service '{service_name}' matched {match_count} metric "
            f"context(s) in Netdata Cloud"
        )
    return False, (
        f"Cloud MCP q-filter returned zero matches for "
        f"'{service_name}' (payload keys: {sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__})"
    )


def verify_with_retries(
    url: str,
    token: str,
    service_name: str,
    attempts: int = 10,
    sleep_s: float = 6.0,
) -> int:
    last = ""
    for i in range(1, attempts + 1):
        ok, msg = probe_once(url, token, service_name)
        last = msg
        if ok:
            print(f"[verify-cloud] PASS ({i}/{attempts}): {msg}")
            return 0
        print(f"[verify-cloud] attempt {i}/{attempts}: {msg}")
        time.sleep(sleep_s)
    print(f"[verify-cloud] FAIL after {attempts} attempts. Last: {last}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True, help="Service name to search for")
    ap.add_argument(
        "--url",
        default=os.environ.get("NETDATA_CLOUD_MCP_URL", DEFAULT_CLOUD_MCP_URL),
    )
    ap.add_argument(
        "--token",
        default=os.environ.get("NETDATA_CLOUD_API_TOKEN", ""),
    )
    ap.add_argument("--attempts", type=int, default=10)
    ap.add_argument("--sleep", type=float, default=6.0)
    args = ap.parse_args()

    if not args.token:
        print(
            "[verify-cloud] ERROR: no Cloud API token. "
            "Set NETDATA_CLOUD_API_TOKEN or pass --token.",
            file=sys.stderr,
        )
        return 2

    return verify_with_retries(
        args.url,
        args.token,
        args.service,
        attempts=args.attempts,
        sleep_s=args.sleep,
    )


if __name__ == "__main__":
    sys.exit(main())
