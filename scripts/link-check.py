#!/usr/bin/env python3
"""Check that every relative markdown link resolves to a real file.

External URLs (http:// and https://) are not fetched; this is a
static consistency check, not a reachability check.

Exit 0 on pass, 1 on any broken link.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
EXCLUDE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


def iter_markdown_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for path in REPO_ROOT.rglob("*.md"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:"))


def resolve(base: pathlib.Path, target: str) -> pathlib.Path:
    # Strip fragment (e.g. "#section").
    target = target.split("#", 1)[0]
    if not target:
        return base  # pure fragment link, always valid
    return (base.parent / target).resolve()


def main() -> int:
    errors: list[str] = []
    files = iter_markdown_files()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if is_external(target):
                continue
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            if not target:
                continue
            resolved = resolve(path, target)
            if not resolved.exists():
                errors.append(
                    f"BROKEN {path.relative_to(REPO_ROOT)}: -> {target}"
                )
    if errors:
        for e in errors:
            print(e)
        print(f"{len(errors)} broken links across {len(files)} files")
        return 1
    print(f"{len(files)} markdown files scanned, 0 broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
