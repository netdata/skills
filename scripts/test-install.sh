#!/usr/bin/env bash
# Smoke test the install flow: copy the repo into a clean temp dir, simulate
# a client-agnostic "skills install" by dropping the tree into a target
# directory, then assert the shape clients expect is present.
#
# This is not a network install; it validates the payload the repo presents.
# A real agentskills.io install fetches from GitHub; that cannot be exercised
# without a real remote.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "[install-test] temp dir: $TMP_DIR"
cp -R "$REPO_ROOT" "$TMP_DIR/netdata-skills"
cd "$TMP_DIR/netdata-skills"

FAIL=0
assert() {
  local desc="$1"
  local path="$2"
  if [ -e "$path" ]; then
    echo "[PASS] $desc"
  else
    echo "[FAIL] $desc: missing $path"
    FAIL=1
  fi
}

echo "[install-test] checking top-level layout"
assert "package.json present"             package.json
assert "LICENSE present"                  LICENSE
assert "README present"                   README.md
assert "CLAUDE.md bridge file"            CLAUDE.md
assert "AGENTS.md bridge file"            AGENTS.md
assert "plugin.json for Claude Code"      .claude-plugin/plugin.json
assert "skills directory"                 skills
assert "validator script"                 scripts/validate.py

echo "[install-test] checking Tier 1 skills"
for s in netdata-otel-setup netdata-instrumentation netdata-collector-config netdata-mcp-integration netdata-migration; do
  assert "tier1 skill: $s/SKILL.md"       "skills/$s/SKILL.md"
  assert "tier1 skill: $s/README.md"      "skills/$s/README.md"
  assert "tier1 skill: $s/rules/"         "skills/$s/rules"
done

echo "[install-test] checking at least 10 tier2 skills"
t2=$(find skills -maxdepth 1 -type d -name 'troubleshoot-*' | wc -l)
if [ "$t2" -ge 10 ]; then
  echo "[PASS] tier2 skill count: $t2"
else
  echo "[FAIL] tier2 skill count: $t2 (< 10)"
  FAIL=1
fi

echo "[install-test] running validator against installed tree"
if python3 scripts/validate.py > /dev/null; then
  echo "[PASS] validator exits 0 on installed tree"
else
  echo "[FAIL] validator exits non-zero on installed tree"
  FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
  echo "[install-test] FAIL"
  exit 1
fi

echo "[install-test] PASS"
exit 0
