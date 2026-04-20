#!/usr/bin/env python3
"""Dump the skill index and prompts in the shape the description-eval
agent expects. Prints paste-ready inputs so a reviewer can run the
eval inside any Claude Code, Cursor, or Codex session (an external
LLM is required; this script does not call out to an LLM itself).

Outputs:
- ``skill_index.tsv``   tab-separated (skill_name, description)
- ``prompts.json``      [{"prompt", "expected"}, ...] from
                        ``prompts.yaml``

Usage::

    python tests/eval/run-description-eval.py [--out-dir DIR]

The reviewer feeds both files to an LLM along with the prompt
template below, then pastes the resulting JSON back into
``LAST_EVAL_RESULTS.json`` for the record.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
PROMPTS_FILE = REPO_ROOT / "tests" / "eval" / "prompts.yaml"


AGENT_PROMPT_TEMPLATE = """\
You are evaluating whether a Netdata Agent Skills pack's skill
descriptions are sharp enough to route user prompts to the correct
skill. Your only evidence per prompt is each skill's name and
`description` frontmatter field. You may NOT read SKILL.md bodies or
rule files.

Read the skill index from {index_path} (tab-separated:
name<TAB>description, one skill per row) and the prompts from
{prompts_path} (JSON array, each with `prompt` and `expected`).

For each of the {n_prompts} prompts, pick ONE skill using ONLY the
index. Write results as a JSON array to `eval_results.json`, each
entry with: `prompt`, `expected`, `picked`, `match`, `reasoning`.

At the end, print: (a) N/N match count, (b) per-prompt mismatch list
if any, (c) 3 description-sharpening recommendations.
"""


def load_skill_index(skills_dir: pathlib.Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end == -1:
            continue
        fm_raw = text[4:end]
        try:
            fm = yaml.safe_load(fm_raw) or {}
        except yaml.YAMLError:
            continue
        name = fm.get("name") or d.name
        desc = fm.get("description") or ""
        rows.append((name, desc))
    return rows


def load_prompts(prompts_file: pathlib.Path) -> list[dict[str, str]]:
    data = yaml.safe_load(prompts_file.read_text(encoding="utf-8")) or {}
    out: list[dict[str, str]] = []
    for _bucket, entries in data.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict) or "prompt" not in e:
                continue
            out.append({
                "prompt": e["prompt"],
                "expected": e.get("expected_skill", ""),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/tmp")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = load_skill_index(SKILLS_DIR)
    prompts = load_prompts(PROMPTS_FILE)

    index_path = out_dir / "skill_index.tsv"
    index_path.write_text(
        "\n".join(f"{n}\t{d}" for n, d in index) + "\n",
        encoding="utf-8",
    )

    prompts_path = out_dir / "prompts.json"
    prompts_path.write_text(
        json.dumps(prompts, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[eval] {len(index)} skills written to {index_path}")
    print(f"[eval] {len(prompts)} prompts written to {prompts_path}")
    print()
    print("Paste the following into a fresh agent session:")
    print("-" * 60)
    print(AGENT_PROMPT_TEMPLATE.format(
        index_path=str(index_path),
        prompts_path=str(prompts_path),
        n_prompts=len(prompts),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
