#!/usr/bin/env python3
"""Static validator for the netdata/skills repo.

Runs 12 checks over every SKILL.md plus one repo-wide check.

Exit 0 on success, 1 on any hard error. Warnings do not affect exit code.
"""

from __future__ import annotations

import pathlib
import re
import sys
import unicodedata

try:
    import yaml
except ImportError:
    sys.stderr.write("validate.py requires pyyaml (pip install pyyaml)\n")
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

# Netdata source tree. Optional: present on a dev machine with the
# reference clone; absent in some CI images. Context-reality checks
# silently no-op when absent.
NETDATA_DIR = REPO_ROOT.parent / "_reference" / "netdata"
GO_COLLECTORS_DIR = NETDATA_DIR / "src" / "go" / "plugin" / "go.d" / "collector"

# Keep this mapping in sync with scripts/generate-troubleshoot-skills.py.
# The validator uses it to resolve troubleshoot-<slug> to the Netdata
# collector dir whose metadata.yaml lists the real chart contexts.
TIER2_COLLECTOR_MAP: dict[str, str] = {
    "activemq": "activemq",
    "apache-httpd": "apache",
    "apache-pulsar": "pulsar",
    "bind-dns": "bind",
    "cassandra": "cassandra",
    "ceph": "ceph",
    "clickhouse": "clickhouse",
    "cockroachdb": "cockroachdb",
    "consul": "consul",
    "coredns": "coredns",
    "docker": "docker",
    "docker-engine": "docker_engine",
    "elasticsearch": "elasticsearch",
    "envoy": "envoy",
    "fluentd": "fluentd",
    "haproxy": "haproxy",
    "kubernetes-api-server": "k8s_apiserver",
    "kubernetes-cluster-state": "k8s_state",
    "kubernetes-kube-proxy": "k8s_kubeproxy",
    "kubernetes-kubelet": "k8s_kubelet",
    "logstash": "logstash",
    "lvm": "lvm",
    "memcached": "memcached",
    "microsoft-sql-server": "mssql",
    "mongodb": "mongodb",
    "mysql": "mysql",
    "nats": "nats",
    "nginx": "nginx",
    "nvidia-dcgm": "dcgm",
    "nvidia-gpu": "nvidia_smi",
    "nvme": "nvme",
    "oracle-database": "oracledb",
    "pgbouncer": "pgbouncer",
    "php-fpm": "phpfpm",
    "postfix": "postfix",
    "postgresql": "postgres",
    "proxysql": "proxysql",
    "rabbitmq": "rabbitmq",
    "redis": "redis",
    "smartctl-disk-monitoring": "smartctl",
    "tomcat": "tomcat",
    "traefik": "traefik",
    "uwsgi": "uwsgi",
    "varnish": "varnish",
    "vmware-vcsa": "vcsa",
    "vmware-vsphere": "vsphere",
    "zfs": "zfspool",
    "zookeeper": "zookeeper",
}

# Namespaces for host / system / correlation contexts that may
# legitimately appear in any rule file. A reference that matches one
# of these prefixes is accepted without checking the collector file.
# Keep tight: fabricated contexts tend to use tech-specific prefixes
# we do enumerate, not these generic ones.
ALWAYS_ALLOWED_CONTEXT_PREFIXES = {
    "system", "host", "net", "disk", "cpu", "mem",
    "app", "groups", "cgroup", "k8s", "container",
}

REQUIRED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "version",
    "author",
    "license",
    "tags",
}

REQUIRED_SECTIONS = [
    "When to use this skill",
    "Key facts",
    "Step-by-step",
    "Common mistakes",
    "Verification",
    "References",
]

BANNED_PHRASES = [
    "genuinely",
    "I'd love to",
    "dive in",
    "delve into",
    "leverage",
    "game-changing",
    "seamlessly",
    "robust",
    "powerful",
    "cutting-edge",
]

DESCRIPTION_MAX_CHARS = 1024
LINE_LENGTH_WARN = 120

EM_DASH = "\u2014"
EN_DASH = "\u2013"

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
    ".tar",
    ".gz",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".pdf",
    ".pyc",
}

EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, path: pathlib.Path, msg: str) -> None:
        self.errors.append(f"ERROR {path.relative_to(REPO_ROOT)}: {msg}")

    def warn(self, path: pathlib.Path, msg: str) -> None:
        self.warnings.append(f"WARN  {path.relative_to(REPO_ROOT)}: {msg}")

    def ok(self) -> bool:
        return not self.errors


def color(s: str, code: str) -> str:
    if not sys.stdout.isatty():
        return s
    return f"\033[{code}m{s}\033[0m"


def red(s: str) -> str:
    return color(s, "31")


def yellow(s: str) -> str:
    return color(s, "33")


def green(s: str) -> str:
    return color(s, "32")


def split_frontmatter(text: str) -> tuple[dict | None, str, str]:
    """Return (frontmatter_dict, body_text, raw_frontmatter_string).

    If no frontmatter, returns (None, text, '').
    If frontmatter does not parse, returns ({}, body, raw_frontmatter).
    """
    if not text.startswith("---\n"):
        return None, text, ""
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text, ""
    raw = text[4:end]
    body = text[end + 5 :]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return {}, body, raw
    if not isinstance(data, dict):
        return {}, body, raw
    return data, body, raw


def iter_skill_files() -> list[pathlib.Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def iter_rule_files() -> list[pathlib.Path]:
    """Return every rules/*.md file under every skill directory."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(SKILLS_DIR.glob("*/rules/*.md"))


def load_real_contexts_for(skill_dir: pathlib.Path) -> set[str] | None:
    """Return the set of real Netdata context names for a troubleshoot-*
    skill, or None if this skill is not a Tier 2 troubleshoot skill with
    a known collector mapping, or if the reference tree is not present.
    """
    name = skill_dir.name
    if not name.startswith("troubleshoot-"):
        return None
    tech_slug = name[len("troubleshoot-") :]
    coll = TIER2_COLLECTOR_MAP.get(tech_slug)
    if not coll:
        return None
    md = GO_COLLECTORS_DIR / coll / "metadata.yaml"
    if not md.is_file():
        return None
    try:
        data = yaml.safe_load(md.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    out: set[str] = set()
    for mod in data.get("modules", []) or []:
        for scope in (mod.get("metrics") or {}).get("scopes", []) or []:
            for m in scope.get("metrics", []) or []:
                name = (m.get("name") or "").strip()
                if name and "." in name:
                    out.add(name)
    return out


# Matches backtick-delimited inline code spans like `redis.commands` or
# `postgres.replication_slot_files`. Only multi-segment dotted names
# are considered candidates; single tokens (e.g. `INFO`) are ignored.
CONTEXT_MENTION_RE = re.compile(
    r"`([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)`"
)


def iter_repo_text_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for path in REPO_ROOT.rglob("*"):
        if path.is_dir():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        out.append(path)
    return out


def check_frontmatter(report: Report, path: pathlib.Path, fm: dict | None, raw: str) -> bool:
    if fm is None:
        report.error(path, "missing or malformed YAML frontmatter block")
        return False
    if fm == {} and raw:
        report.error(path, "frontmatter block present but did not parse as a YAML mapping")
        return False
    missing = REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
    if missing:
        report.error(path, f"frontmatter missing required keys: {sorted(missing)}")
    return not missing


def check_name_matches_folder(report: Report, path: pathlib.Path, fm: dict) -> None:
    name = fm.get("name")
    folder = path.parent.name
    if name != folder:
        report.error(
            path,
            f"frontmatter name '{name}' does not match folder name '{folder}'",
        )


def check_description(report: Report, path: pathlib.Path, fm: dict) -> None:
    desc = fm.get("description", "")
    if not isinstance(desc, str) or not desc.strip():
        report.error(path, "frontmatter description is empty")
        return
    if len(desc) > DESCRIPTION_MAX_CHARS:
        report.error(
            path,
            f"description is {len(desc)} chars; must be under {DESCRIPTION_MAX_CHARS}",
        )


def check_sections(report: Report, path: pathlib.Path, body: str) -> None:
    headings = re.findall(r"^##\s+(.+?)\s*$", body, re.MULTILINE)
    for required in REQUIRED_SECTIONS:
        if required not in headings:
            report.error(path, f"missing required H2 section: '{required}'")


def strip_code_blocks(body: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Return (body_without_code, list_of_(fence_line_number, lang, block_content)).

    Code block fences are detected with '```' at line start.
    """
    out_lines: list[str] = []
    blocks: list[tuple[int, str, str]] = []
    in_block = False
    block_buf: list[str] = []
    block_lang = ""
    block_start = 0
    for idx, line in enumerate(body.splitlines(keepends=False), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if not in_block:
                in_block = True
                block_lang = stripped[3:].strip()
                block_start = idx
                block_buf = []
            else:
                blocks.append((block_start, block_lang, "\n".join(block_buf)))
                in_block = False
                block_lang = ""
                block_buf = []
            out_lines.append("")
        elif in_block:
            block_buf.append(line)
            out_lines.append("")
        else:
            out_lines.append(line)
    if in_block:
        blocks.append((block_start, block_lang, "\n".join(block_buf)))
    return "\n".join(out_lines), blocks


def strip_inline_code(line: str) -> str:
    """Remove content inside single-backtick spans."""
    return re.sub(r"`[^`]*`", "", line)


def check_em_dashes(report: Report, path: pathlib.Path, prose: str) -> None:
    for idx, line in enumerate(prose.splitlines(), start=1):
        visible = strip_inline_code(line)
        if EM_DASH in visible:
            report.error(path, f"em-dash at line {idx}: {line.strip()[:120]}")
        if re.search(r"(?<!-)--(?!-)", visible):
            report.error(path, f"double-dash at line {idx}: {line.strip()[:120]}")


def check_banned_phrases(report: Report, path: pathlib.Path, prose: str) -> None:
    lower = prose.lower()
    for phrase in BANNED_PHRASES:
        if phrase.lower() in lower:
            report.error(path, f"banned phrase '{phrase}' found in prose")


def check_no_emoji(report: Report, path: pathlib.Path, text: str) -> None:
    for ch in text:
        if ord(ch) < 0x2600:
            continue
        cat = unicodedata.category(ch)
        if cat == "So":
            report.error(path, f"emoji or pictograph not allowed: {ch!r} (U+{ord(ch):04X})")
            return
        if 0x1F300 <= ord(ch) <= 0x1FAFF:
            report.error(path, f"emoji not allowed: {ch!r} (U+{ord(ch):04X})")
            return


def check_rule_references(report: Report, path: pathlib.Path, body: str) -> None:
    rules_dir = path.parent / "rules"
    # Match markdown links to rules/*.md (relative)
    pattern = re.compile(r"\]\(\.?/?rules/([^)\s]+\.md)\)")
    for match in pattern.finditer(body):
        target = rules_dir / match.group(1)
        if not target.exists():
            report.error(path, f"referenced rule file does not exist: rules/{match.group(1)}")


def check_code_block_languages(report: Report, path: pathlib.Path, blocks: list[tuple[int, str, str]]) -> None:
    for line_no, lang, _body in blocks:
        if not lang:
            report.error(path, f"code block at line {line_no} does not declare a language")


def check_line_length(report: Report, path: pathlib.Path, prose: str) -> None:
    for idx, line in enumerate(prose.splitlines(), start=1):
        if len(line) > LINE_LENGTH_WARN:
            report.warn(path, f"line {idx} is {len(line)} chars (> {LINE_LENGTH_WARN})")


# Built piecewise so the validator file itself does not contain the literal token.
FORBIDDEN_VENDOR_TOKEN = "".join(chr(c) for c in (100, 97, 115, 104, 48))


def check_repo_wide_forbidden_token(report: Report) -> None:
    needle = re.compile(FORBIDDEN_VENDOR_TOKEN, re.IGNORECASE)
    for path in iter_repo_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if needle.search(text):
            report.error(
                path,
                f"file contains forbidden vendor token '{FORBIDDEN_VENDOR_TOKEN}' "
                "(case-insensitive)",
            )


def validate_rule_file(report: Report, path: pathlib.Path) -> None:
    """Check a rules/*.md file for style, structure, and any fabricated
    Netdata context references.

    Rule files carry no frontmatter (they are plain Markdown). The
    checks overlap with validate_skill but the rule-file surface has
    simpler structural requirements.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error(path, f"cannot read file: {exc}")
        return

    if not re.search(r"(?m)^#\s+\S", text):
        report.error(path, "rule file has no H1 title")

    prose, blocks = strip_code_blocks(text)
    check_em_dashes(report, path, prose)
    check_banned_phrases(report, path, prose)
    check_no_emoji(report, path, text)
    check_code_block_languages(report, path, blocks)
    check_line_length(report, path, prose)

    # Tier 2 context reality: every backtick-wrapped dotted token in
    # this rule file that uses the tech's collector prefix must be a
    # real context name. Tokens under generic namespaces (system.*,
    # host.*, etc.) are always accepted.
    skill_dir = path.parent.parent
    real = load_real_contexts_for(skill_dir)
    if real is None:
        return

    tech_slug = skill_dir.name[len("troubleshoot-") :]
    coll = TIER2_COLLECTOR_MAP.get(tech_slug, "")
    prefix = coll.replace("_", "") if coll else ""

    for match in CONTEXT_MENTION_RE.finditer(text):
        token = match.group(1)
        head = token.split(".", 1)[0]
        if head in ALWAYS_ALLOWED_CONTEXT_PREFIXES:
            continue
        # Only police tokens that use this collector's prefix. Tokens
        # from unrelated namespaces (other techs cross-referenced) are
        # out of scope here; they will be validated by their own skill.
        if prefix and head != prefix and head != coll:
            continue
        if token not in real:
            report.error(
                path,
                f"context `{token}` not present in "
                f"{coll}/metadata.yaml (possibly fabricated)",
            )


def validate_tier2_has_real_contexts(
    report: Report, skill_dir: pathlib.Path,
) -> None:
    """Tier 2 skills with a collector mapping must name at least three
    real Netdata contexts across SKILL.md and rules/*.md combined.

    Placeholder-only content ("list_metrics filtered by context prefix")
    fails this check; the original bug that shipped v0.1.0 would have
    been caught here.
    """
    real = load_real_contexts_for(skill_dir)
    if not real:
        return

    seen: set[str] = set()
    for md in [skill_dir / "SKILL.md", *sorted((skill_dir / "rules").glob("*.md"))]:
        if not md.is_file():
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in CONTEXT_MENTION_RE.finditer(text):
            token = match.group(1)
            if token in real:
                seen.add(token)

    # Collectors with very small metric surfaces (LVM and Postfix at
    # the time of writing only emit 2 contexts each) get a proportional
    # threshold: cite all of them, or cite at least 3 when the collector
    # has more. Anything less looks like placeholder content.
    expected = min(3, len(real))
    if len(seen) < expected:
        report.error(
            skill_dir / "SKILL.md",
            f"Tier 2 skill names {len(seen)} real Netdata "
            f"context(s); expected at least {expected} out of "
            f"{len(real)} available (check generator output and "
            f"metadata.yaml mapping).",
        )


def validate_skill(report: Report, path: pathlib.Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error(path, f"cannot read file: {exc}")
        return

    fm, body, raw = split_frontmatter(text)
    if not check_frontmatter(report, path, fm, raw):
        return
    assert fm is not None

    check_name_matches_folder(report, path, fm)
    check_description(report, path, fm)
    check_sections(report, path, body)

    prose, blocks = strip_code_blocks(body)
    check_em_dashes(report, path, prose)
    check_banned_phrases(report, path, prose)
    check_no_emoji(report, path, text)
    check_rule_references(report, path, body)
    check_code_block_languages(report, path, blocks)
    check_line_length(report, path, prose)


def main() -> int:
    report = Report()
    skills = iter_skill_files()
    if not skills:
        report.errors.append(f"ERROR: no SKILL.md files found under {SKILLS_DIR}")
    for path in skills:
        validate_skill(report, path)

    rules = iter_rule_files()
    for path in rules:
        validate_rule_file(report, path)

    # Tier 2 realism: every troubleshoot-<tech> skill that has a known
    # Netdata collector mapping must cite at least a few real contexts.
    for skill_path in skills:
        skill_dir = skill_path.parent
        if skill_dir.name.startswith("troubleshoot-"):
            validate_tier2_has_real_contexts(report, skill_dir)

    check_repo_wide_forbidden_token(report)

    for w in report.warnings:
        print(yellow(w))
    for e in report.errors:
        print(red(e))

    summary = (
        f"{len(skills)} skills checked, "
        f"{len(rules)} rule files checked, "
        f"{len(report.errors)} errors, "
        f"{len(report.warnings)} warnings"
    )
    if report.ok():
        print(green(summary))
        return 0
    print(red(summary))
    return 1


if __name__ == "__main__":
    sys.exit(main())
