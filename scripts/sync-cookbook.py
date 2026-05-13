#!/usr/bin/env python3
"""Refresh the cookbook recipe index in netdata-collector-config.

The Netdata OTel Collector Cookbook (https://github.com/netdata/otelcol-cookbook)
is the source of truth for end-to-end Collector recipes. This script
pulls the current recipe list from that repo and reports which recipes
the skill pack already mentions, which are missing from the index, and
which references the skill pack has that no longer exist upstream.

It does not rewrite content automatically. The intent is to surface
drift between the cookbook and the skill pack so a human can decide
how to bring them back into alignment (add a new entry to the recipe
index, retire an old one, fold a new recipe pattern into receivers /
processors / exporters guidance, etc.).

Usage:

    python3 scripts/sync-cookbook.py
    python3 scripts/sync-cookbook.py --json

Exit code is 0 when the index is in sync, 1 otherwise. Use --json for
CI integration.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RECIPES_INDEX = (
    REPO_ROOT
    / "skills"
    / "netdata-collector-config"
    / "rules"
    / "recipes.md"
)

COOKBOOK_OWNER = "netdata"
COOKBOOK_REPO = "otelcol-cookbook"
COOKBOOK_API_PATH = f"repos/{COOKBOOK_OWNER}/{COOKBOOK_REPO}"
COOKBOOK_API = f"https://api.github.com/{COOKBOOK_API_PATH}"
COOKBOOK_HTML = f"https://github.com/{COOKBOOK_OWNER}/{COOKBOOK_REPO}"

# Matches a line in the recipes.md index table referencing a recipe
# directory in the cookbook by name.
INDEX_RECIPE_RE = re.compile(
    r"https://github\.com/netdata/otelcol-cookbook/tree/master/([^\s/)]+)"
)


def _github_token() -> str | None:
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        tok = os.environ.get(var)
        if tok:
            return tok
    if shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        tok = result.stdout.strip()
        return tok or None
    return None


def _api_get(path: str) -> object:
    """Fetch a GitHub API path, honoring GH_TOKEN / GITHUB_TOKEN / gh login.

    The cookbook is private at the time of writing; anonymous access
    returns 404. Authenticated access via a personal token or the
    locally configured `gh` CLI returns the real listing.
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _raw_get(path: str) -> str | None:
    """Fetch a raw file from the cookbook via the GitHub contents API.

    Uses the API rather than raw.githubusercontent.com because the
    latter does not accept the bearer token for private repos.
    """
    try:
        data = _api_get(f"{COOKBOOK_API_PATH}/contents/{path}")
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    if not isinstance(data, dict):
        return None
    encoding = data.get("encoding")
    content = data.get("content")
    if encoding != "base64" or not isinstance(content, str):
        return None
    try:
        return base64.b64decode(content).decode("utf-8", errors="replace")
    except (ValueError, binascii.Error):
        return None


def fetch_cookbook_recipes() -> list[str]:
    """Return the list of recipe directory names at the cookbook root.

    A recipe is any top-level directory (excluding things like .github
    or docs). The cookbook README itself documents this convention:
    each directory is one recipe.
    """
    entries = _api_get(f"{COOKBOOK_API_PATH}/contents")
    if not isinstance(entries, list):
        raise RuntimeError("unexpected cookbook contents shape")
    out: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "dir":
            continue
        name = entry.get("name", "")
        if not name or name.startswith("."):
            continue
        if name in {"docs", "scripts", "tests"}:
            continue
        out.append(name)
    return sorted(out)


def fetch_recipe_readme(recipe: str) -> str | None:
    """Return the first non-empty paragraph from a recipe's README, or None."""
    text = _raw_get(f"{recipe}/README.md")
    if not text:
        return None
    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        stripped = para.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return re.sub(r"\s+", " ", stripped)
    return None


def parse_indexed_recipes() -> set[str]:
    if not RECIPES_INDEX.is_file():
        return set()
    text = RECIPES_INDEX.read_text(encoding="utf-8")
    return set(INDEX_RECIPE_RE.findall(text))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable output instead of human-readable",
    )
    args = parser.parse_args(argv)

    try:
        upstream = fetch_cookbook_recipes()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        sys.stderr.write(f"failed to fetch cookbook recipes: {exc}\n")
        return 2

    indexed = parse_indexed_recipes()
    missing_locally = sorted(set(upstream) - indexed)
    stale_locally = sorted(indexed - set(upstream))

    summaries: dict[str, str | None] = {}
    if missing_locally and not args.json:
        for recipe in missing_locally:
            summaries[recipe] = fetch_recipe_readme(recipe)

    if args.json:
        payload = {
            "upstream": upstream,
            "indexed": sorted(indexed),
            "missing_locally": missing_locally,
            "stale_locally": stale_locally,
        }
        print(json.dumps(payload, indent=2))
        return 0 if not missing_locally and not stale_locally else 1

    print(f"Cookbook: {COOKBOOK_HTML}")
    print(f"Upstream recipes: {len(upstream)}")
    for recipe in upstream:
        marker = " " if recipe in indexed else "+"
        print(f"  {marker} {recipe}")
    print()
    if missing_locally:
        print("Recipes upstream but missing from the local index:")
        for recipe in missing_locally:
            summary = summaries.get(recipe) or "(no description fetched)"
            if len(summary) > 200:
                summary = summary[:197] + "..."
            print(f"  - {recipe}: {summary}")
        print()
    if stale_locally:
        print("Recipes referenced locally but no longer in the cookbook:")
        for recipe in stale_locally:
            print(f"  - {recipe}")
        print()
    if not missing_locally and not stale_locally:
        print("Index is in sync with the cookbook.")
        return 0
    print(
        "Open "
        f"{RECIPES_INDEX.relative_to(REPO_ROOT)} "
        "and update the Index table."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
