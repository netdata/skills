#!/usr/bin/env python3
"""Generate Tier 2 troubleshoot-<tech> skills from Netdata operator playbooks.

The playbooks live outside the repo at `../_reference/netdata-playbooks/` on
the build machine. They are the authoritative operator knowledge source;
this script distils each one into a skill that a coding agent can trigger
on symptom keywords and then route to MCP queries.

Each generated skill contains:
- A SKILL.md with dynamic frontmatter, mental-model summary, failure
  archetypes, and an MCP verification section.
- One rule file per signal domain ("Availability", "Performance", etc.).

Run from the repo root:

    python scripts/generate-troubleshoot-skills.py

The script is idempotent: it overwrites the generated files each run.
Existing hand-written skills under `skills/troubleshoot-*/` will be
overwritten, so do not hand-edit those files. If a playbook needs a
hand-written skill, remove it from the playbooks dir first.
"""

from __future__ import annotations

import pathlib
import re
import sys
import textwrap

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAYBOOKS_DIR = REPO_ROOT.parent / "_reference" / "netdata-playbooks"
NETDATA_DIR = REPO_ROOT.parent / "_reference" / "netdata"
GO_COLLECTORS_DIR = NETDATA_DIR / "src" / "go" / "plugin" / "go.d" / "collector"
SKILLS_DIR = REPO_ROOT / "skills"

TROUBLESHOOT_PREFIX = "troubleshoot-"

# Explicit playbook-slug -> Netdata collector-dir mapping. Anything not
# listed here falls through to the generic "discover via list_metrics"
# guidance. Keep this list in sync with the playbooks directory.
PLAYBOOK_TO_COLLECTOR: dict[str, str] = {
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
    # kafka: no native Go collector. Agents typically scrape via the
    # Prometheus JMX exporter; contexts are prom-style and cannot be
    # enumerated statically. Skill falls back to discovery guidance.
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

# Domain-name keywords that group Netdata contexts by playbook domain.
# Lookup is case-insensitive. A context matches a domain if any keyword
# appears in the context's name, description, or one of its dimensions.
# The 'default' bucket catches whatever did not match elsewhere.
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "availability": (
        "uptime", "ping", "status", "up", "down", "reachability",
        "connection", "connected", "health", "alive",
    ),
    "connectivity": (
        "connection", "client", "net", "bandwidth", "bytes",
        "packets", "socket", "listen",
    ),
    "throughput": (
        "commands", "ops", "operations", "requests", "calls",
        "queries", "rate", "processed", "throughput", "traffic",
    ),
    "latency": (
        "latency", "duration", "time", "slow", "wait",
    ),
    "errors": (
        "error", "failed", "rejected", "dropped", "fail",
        "timeout", "denied", "retries",
    ),
    "resource": (
        "memory", "cpu", "ratio", "usage", "pool", "heap",
        "buffer", "cache", "allocated", "rss", "fragmentation",
    ),
    "storage": (
        "disk", "io", "rdb", "aof", "persistence", "save",
        "writeback", "space", "volume", "fs",
    ),
    "replication": (
        "master", "replica", "slave", "replication", "cluster",
        "follower", "leader", "link",
    ),
    "keyspace": (
        "keys", "keyspace", "database", "eviction", "expire",
        "expiration", "expired",
    ),
    "queue": (
        "queue", "consumer", "producer", "message", "publish",
        "delivery", "backlog", "lag",
    ),
}

DOMAIN_HEADER_RE = re.compile(
    r"^(?:\*\*DOMAIN:\s*(?P<bold_domain>[^*]+?)\*\*"
    r"|#{3,4}\s*DOMAIN:\s*(?P<named>.+?)"
    r"|#{4}\s+(?!SIGNAL\b|Signal\s+\d|PATTERN\b)(?P<keyword>[A-Z][A-Z0-9 &/\-]{2,}))\s*$",
    re.MULTILINE,
)
SIGNAL_HEADER_RE = re.compile(
    r"(?:^\*\*SIGNAL:\s*(?P<bold>.+?)\*\*|^#{3,5}\s*SIGNAL:\s*(?P<hash>.+?))"
    r"(?:\s*\[(?P<sev>HIGH|MEDIUM|LOW|MED)\])?\s*$",
    re.MULTILINE,
)
SECTION0_RE = re.compile(r"^#{2,3}\s*SECTION\s*0\s*.*?$", re.MULTILINE)
SECTION1_RE = re.compile(r"^#{2,3}\s*SECTION\s*1\s*.*?$", re.MULTILINE)
SECTION2_RE = re.compile(r"^#{2,3}\s*SECTION\s*2\s*.*?$", re.MULTILINE)
FAILURE_HEADER_RE = re.compile(
    r"(?i)(?:\*\*|#{2,5}\s+)(?:characteristic\s+)?failure\s+archetypes[:.]?",
)


def load_collector_contexts(playbook_slug: str) -> list[dict]:
    """Return a list of real Netdata contexts for this playbook's tech.

    Each entry is ``{name, description, unit, scope, dimensions}``. An
    empty list means we have no mapping for this tech or the metadata
    file is missing. Callers fall back to generic discovery guidance.
    """
    coll = PLAYBOOK_TO_COLLECTOR.get(playbook_slug)
    if not coll:
        return []
    md_path = GO_COLLECTORS_DIR / coll / "metadata.yaml"
    if not md_path.is_file():
        return []
    try:
        data = yaml.safe_load(md_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    out: list[dict] = []
    for mod in data.get("modules", []) or []:
        metrics_block = mod.get("metrics") or {}
        for scope in metrics_block.get("scopes", []) or []:
            scope_name = scope.get("name") or "global"
            for m in scope.get("metrics", []) or []:
                name = (m.get("name") or "").strip()
                if not name or "." not in name:
                    continue
                dims = [
                    (d.get("name") or "").strip()
                    for d in (m.get("dimensions") or [])
                    if isinstance(d, dict) and d.get("name")
                ]
                out.append({
                    "name": name,
                    "description": (m.get("description") or "").strip(),
                    "unit": (m.get("unit") or "").strip(),
                    "scope": scope_name,
                    "dimensions": dims,
                })
    return out


def _domain_keywords(domain_name: str) -> set[str]:
    """Map a playbook domain name to a keyword set for context matching.

    Uses the domain name itself plus any preset bucket whose label
    appears in the name. Falls back to the name's own tokens so
    unrecognized domains still pick up obvious name matches.
    """
    dn = domain_name.lower()
    keys: set[str] = set()
    # Always include the tokens in the domain name itself.
    for tok in re.split(r"[^a-z0-9]+", dn):
        if len(tok) >= 4:
            keys.add(tok)
    # Pull in preset bucket keywords for any bucket whose label is
    # referenced in the domain name.
    for bucket, words in DOMAIN_KEYWORDS.items():
        if bucket in dn:
            keys.update(words)
    return keys


def classify_contexts_by_domain(
    contexts: list[dict],
    domains: list[tuple[str, list[tuple[str, str]]]],
) -> dict[str, list[dict]]:
    """Return ``{domain_name: [context, ...]}`` plus a synthetic
    ``"__unmatched__"`` bucket for contexts that did not key into any
    domain.

    Matching is keyword overlap between the context (name, description,
    dimensions) and each domain's keyword set. Contexts may appear in
    more than one domain if they match multiple.
    """
    buckets: dict[str, list[dict]] = {name: [] for name, _ in domains}
    unmatched: list[dict] = []
    domain_keys = {name: _domain_keywords(name) for name, _ in domains}
    for ctx in contexts:
        haystack = " ".join([
            ctx["name"].lower(),
            ctx["description"].lower(),
            " ".join(ctx.get("dimensions", [])).lower(),
        ])
        matched_any = False
        for name, keys in domain_keys.items():
            if any(kw in haystack for kw in keys):
                buckets[name].append(ctx)
                matched_any = True
        if not matched_any:
            unmatched.append(ctx)
    buckets["__unmatched__"] = unmatched
    return buckets


def fmt_context_table(contexts: list[dict], limit: int = 12) -> str:
    """Render a compact Markdown list of contexts. Used inside rule files
    and under the SKILL.md verification block.
    """
    if not contexts:
        return ""
    lines: list[str] = []
    for ctx in contexts[:limit]:
        dims = ctx.get("dimensions") or []
        dim_hint = ""
        if dims:
            visible = ", ".join(d for d in dims[:6] if d and "dimension per" not in d)
            if visible:
                dim_hint = f" Dimensions: {visible}."
        desc = trim(ctx["description"], 120) if ctx["description"] else ""
        unit = f" ({ctx['unit']})" if ctx["unit"] else ""
        suffix = f"{desc}{unit}.{dim_hint}" if desc else f"Netdata context.{dim_hint}"
        lines.append(wrap_line(f"- `{ctx['name']}`: ", suffix.strip()))
    return "\n".join(lines)


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def read_playbooks() -> list[pathlib.Path]:
    if not PLAYBOOKS_DIR.exists():
        sys.stderr.write(
            f"Playbooks dir not found: {PLAYBOOKS_DIR}\n"
            "Clone the reference repo into the workspace before running.\n"
        )
        sys.exit(2)
    return sorted(p for p in PLAYBOOKS_DIR.glob("*.md") if p.is_file())


def extract_title(text: str, filename: str) -> str:
    # Try the first PLAYBOOK: line (SECTION 0 style H2 or H3).
    for line in text.splitlines():
        m = re.match(
            r"^#{1,3}\s*PLAYBOOK:\s*Monitoring\s+(.+?)\s*$", line.strip()
        )
        if m:
            return m.group(1).strip()
        m = re.match(
            r"^#\s*Consolidated\s+Operational\s+Playbook:\s*(.+?)\s*$",
            line.strip(),
        )
        if m:
            return m.group(1).strip()
    # Fallback: prettified filename.
    stem = pathlib.Path(filename).stem
    return stem.replace("-", " ").title()


def extract_section(text: str, start_re: re.Pattern[str], stop_re: re.Pattern[str] | None) -> str:
    start = start_re.search(text)
    if not start:
        return ""
    start_idx = start.end()
    if stop_re is None:
        return text[start_idx:].strip()
    stop = stop_re.search(text, start_idx)
    end_idx = stop.start() if stop else len(text)
    return text[start_idx:end_idx].strip()


def first_paragraphs(section: str, n: int = 2) -> str:
    """Return the first N non-empty paragraphs of a section."""
    paras: list[str] = []
    buf: list[str] = []
    for line in section.splitlines():
        if not line.strip():
            if buf:
                paras.append(" ".join(buf).strip())
                buf = []
                if len(paras) >= n:
                    break
        else:
            if line.lstrip().startswith(("#", "**Deployment", "**Resources", "**Characteristic")):
                if buf:
                    paras.append(" ".join(buf).strip())
                    buf = []
                break
            buf.append(line.strip())
    if buf and len(paras) < n:
        paras.append(" ".join(buf).strip())
    return "\n\n".join(paras)


def extract_failure_archetypes(section0: str) -> list[str]:
    m = FAILURE_HEADER_RE.search(section0)
    if not m:
        return []
    tail = section0[m.end() :]
    # Stop at the next bold subheading or H3/H4.
    stop = re.search(r"\n\*\*[^*]+\*\*\s*\n|\n#{2,4}\s", tail)
    block = tail[: stop.start() if stop else len(tail)]
    items = re.findall(
        r"^\s*\d+\.\s+\*\*(.+?)\*\*[:.]\s*(.+?)\s*$",
        block,
        re.MULTILINE,
    )
    if not items:
        items = re.findall(
            r"^\s*\d+\.\s+\*\*(.+?)\*\*\s*(.*?)$",
            block,
            re.MULTILINE,
        )
    out = []
    for title, body in items:
        title = sanitize(title.strip().rstrip(".:").strip())
        body = body.strip()
        body = re.sub(r"\s+", " ", body)
        if body.startswith("\u2014") or body.startswith("-"):
            body = body[1:].strip()
        body = sanitize(body)
        out.append((title, body))
    return out  # type: ignore[return-value]


def extract_domains(section1: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return [(domain_name, [(signal_name, severity), ...]), ...]."""
    domains: list[tuple[str, list[tuple[str, str]]]] = []
    matches = list(DOMAIN_HEADER_RE.finditer(section1))
    for i, m in enumerate(matches):
        raw_name = (
            m.group("bold_domain")
            or m.group("named")
            or m.group("keyword")
            or ""
        )
        name = raw_name.strip().rstrip(".").title()
        if not name:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section1)
        block = section1[start:end]
        signals: list[tuple[str, str]] = []
        for sm in SIGNAL_HEADER_RE.finditer(block):
            sig_name = (sm.group("bold") or sm.group("hash") or "").strip().rstrip(":.")
            sev = (sm.group("sev") or "").strip() or "MED"
            signals.append((sig_name, sev))
        if signals:
            domains.append((name, signals))
    return domains


def top_symptoms(failures: list[tuple[str, str]]) -> list[str]:
    if not failures:
        return []
    # Take up to 5 archetypes; more archetypes in the description sharpen
    # activation matching against real user phrasings (for example,
    # replication-lag prompts for MySQL hit archetype #5).
    return [t.lower() for t, _ in failures[:5]]


def _oxford_join(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} or {items[1]}"
    return ", ".join(items[:-1]) + f", or {items[-1]}"


def fmt_description(tech: str, symptoms: list[str], domains: list[tuple[str, list[tuple[str, str]]]]) -> str:
    if symptoms:
        sym_clause = _oxford_join(symptoms)
    elif domains:
        dom_names = [d.lower() for d, _ in domains[:4]]
        sym_clause = f"{_oxford_join(dom_names)} degradation"
    else:
        sym_clause = f"{tech} operational issues"
    key_metrics = []
    for _name, signals in domains[:3]:
        for sig, _sev in signals[:2]:
            key_metrics.append(sanitize(sig).lower())
    metrics_clause = ", ".join(key_metrics[:5]) if key_metrics else f"{tech} health signals"
    desc = (
        f"Use when diagnosing issues with {tech}: {sym_clause}. Queries "
        f"Netdata via MCP for {metrics_clause}, applies the diagnostic "
        f"tree from the Netdata operator playbook, and recommends "
        f"remediation."
    )
    if len(desc) > 1020:
        desc = desc[:1017] + "..."
    return desc


def fmt_skill_md(
    tech: str,
    slug: str,
    section0_intro: str,
    failures: list[tuple[str, str]],
    domains: list[tuple[str, list[tuple[str, str]]]],
    tags: list[str],
    contexts: list[dict] | None = None,
) -> str:
    contexts = contexts or []
    symptoms = top_symptoms(failures)
    desc = fmt_description(tech, symptoms, domains)

    # Frontmatter built manually, no textwrap.
    # YAML-quote the description: it contains colons that would otherwise
    # be parsed as mapping separators.
    desc_quoted = desc.replace("\\", "\\\\").replace('"', '\\"')
    fm_lines = [
        "---",
        f"name: {slug}",
        f'description: "{desc_quoted}"',
        "version: 0.1.0",
        "author: Netdata",
        "license: Apache-2.0",
        "tags:",
    ]
    for t in tags:
        fm_lines.append(f"  - {t}")
    fm_lines.append("---")
    fm = "\n".join(fm_lines)

    # When to use: failure archetypes become triggers plus always-on generic triggers.
    triggers_lines: list[str] = []
    if failures:
        for title, body in failures[:6]:
            triggers_lines.append(
                wrap_line(f"- **{title}**: ", trim(body, 280))
            )
    triggers_lines.append(
        wrap_line(
            "- ",
            f"Any time the user reports a {tech} service behaving outside "
            "its expected envelope (elevated errors, latency, saturation, "
            "resource exhaustion, or unexpected restarts).",
        )
    )
    triggers_lines.append(
        wrap_line(
            "- ",
            f"An on-call engineer is paging on a Netdata alert tied to a "
            f"{tech} instance and wants a structured triage path.",
        )
    )

    # Key facts: architecture summary + more body.
    key_facts = []
    key_facts.append(
        f"This skill wraps the Netdata operator playbook for {tech}. It "
        "does not replace the playbook; it routes a coding agent through "
        "MCP queries against the same signals the playbook relies on."
    )
    if section0_intro:
        for para in section0_intro.split("\n\n")[:2]:
            p = re.sub(r"\s+", " ", para).strip()
            if p and not p.startswith("**"):
                key_facts.append(trim(p, 400))
    if domains:
        dnames = ", ".join(sanitize(n) for n, _ in domains[:6])
        key_facts.append(
            f"The playbook decomposes {tech} health into {len(domains)} "
            f"signal domains: {dnames}. Each domain maps to one rule "
            "file in this skill."
        )
    if failures:
        key_facts.append(
            f"Dominant failure archetypes the playbook calls out: "
            + "; ".join(t for t, _ in failures[:5])
            + "."
        )
    key_facts.append(
        "Netdata observes the signals listed in the rule files via its "
        "native collectors, plus any OpenTelemetry-shipped metrics that "
        f"your {tech} instrumentation adds. Both paths end at the same "
        "MCP query surface."
    )
    if contexts:
        ctx_prefixes = sorted({c["name"].split(".", 1)[0] for c in contexts})
        prefix_list = ", ".join(f"`{p}.*`" for p in ctx_prefixes[:4])
        key_facts.append(
            f"Netdata's {PLAYBOOK_TO_COLLECTOR.get(slug.replace(TROUBLESHOOT_PREFIX, ''), tech)} "
            f"collector emits {len(contexts)} context(s) under "
            f"{prefix_list}. The rule files enumerate which contexts "
            "surface which domain; the Verification section below names "
            "the load-bearing ones explicitly."
        )

    # Step by step: use failure archetypes as ordered triage.
    def _step(idx: int, body: str) -> str:
        return wrap_line(f"{idx}. ", body)

    steps_lines = []
    steps_lines.append(
        _step(
            1,
            f"Confirm the {tech} service is up. Query Netdata via MCP "
            "with `list_nodes` and filter by the host running the target. "
            "A missing node means the symptom is at the network or "
            "orchestrator layer, not inside the service.",
        )
    )
    steps_lines.append(
        _step(
            2,
            "Pull the last 15 minutes of signals for the target. Use "
            "`query_metrics` against the contexts listed in the domain "
            "rule files. Run `find_anomalous_metrics` in parallel over "
            "the same window; anomalies frame which rule file to read "
            "first.",
        )
    )
    for idx, (title, body) in enumerate(failures[:5], start=3):
        steps_lines.append(
            _step(
                idx,
                f"Check for **{title}**. {trim(body, 400)} "
                "Inspect the rule file whose signals move first for "
                "this mode.",
            )
        )
    next_idx = len(steps_lines) + 1
    steps_lines.append(
        _step(
            next_idx,
            "Correlate with host-level signals "
            "(`system.cpu.utilization`, `system.memory.usage`, "
            "`system.disk.io_time`). Many service-level failures have a "
            "host-resource precursor.",
        )
    )
    steps_lines.append(
        _step(
            next_idx + 1,
            "Apply the remediation hinted at in the matching rule file "
            "or the operator playbook. Re-run the MCP queries from the "
            "Verification section to confirm the signals returned to "
            "expected ranges. A fix that does not move the signal back "
            "is not a fix.",
        )
    )
    steps_block = "\n".join(steps_lines)

    # Common mistakes.
    mistakes_lines = [
        wrap_line(
            "- ",
            f"Treating {tech} as a generic HTTP or process health check. "
            f"{tech} has specific failure archetypes (see Key facts) that "
            "generic checks miss.",
        ),
        wrap_line(
            "- ",
            "Stopping at the first anomalous metric. Several archetypes "
            "produce correlated spikes; use `find_correlated_metrics` to "
            "widen the search before concluding a root cause.",
        ),
        wrap_line(
            "- ",
            "Quoting percentile latency without the sample count. Low "
            "traffic plus a single slow request moves p99 by seconds.",
        ),
        wrap_line(
            "- ",
            "Reading dashboards for a window shorter than the failure's "
            "fingerprint. Slow-brew failures (queue growth, bloat, "
            "memory fragmentation) need 30+ minutes of data to see the "
            "trend.",
        ),
        wrap_line(
            "- ",
            "Skipping the host-level correlation. A process-level fix "
            "for a noisy-neighbour problem does not hold.",
        ),
        wrap_line(
            "- ",
            "Assuming alert thresholds are tuned for your workload. "
            f"Tune against observed {tech} traffic before escalating an "
            "alert configuration issue.",
        ),
    ]
    mistakes_block = "\n".join(mistakes_lines)

    # Verification: real MCP queries with actual Netdata context names.
    ctx_prefixes = sorted({c["name"].split(".", 1)[0] for c in contexts})
    primary_prefix = ctx_prefixes[0] if ctx_prefixes else ""

    # Pick the load-bearing contexts by giving availability/errors first,
    # then throughput and resource. This biases Verification toward the
    # handful of contexts most likely to move in an incident.
    priority_buckets = ("availability", "errors", "throughput", "resource")
    chosen: list[dict] = []
    seen_names: set[str] = set()
    if contexts:
        bmap = classify_contexts_by_domain(contexts, [(b, []) for b in priority_buckets])
        for bucket in priority_buckets:
            for ctx in bmap.get(bucket, []):
                if ctx["name"] not in seen_names:
                    chosen.append(ctx)
                    seen_names.add(ctx["name"])
                if len(chosen) >= 6:
                    break
            if len(chosen) >= 6:
                break
        # Backfill if buckets missed; keep within 6.
        for ctx in contexts:
            if len(chosen) >= 6:
                break
            if ctx["name"] not in seen_names:
                chosen.append(ctx)
                seen_names.add(ctx["name"])

    if chosen:
        context_list_str = ", ".join(f"`{c['name']}`" for c in chosen)
        prefix_clause = (
            f"list_metrics filtered by q=\"{primary_prefix}\" "
            f"(returns every {primary_prefix}.* context Netdata sees)"
        ) if primary_prefix else "list_metrics with no filter"
        probe_query = (
            f"query_metrics with contexts=[{', '.join(c['name'] for c in chosen)}] "
            "and relative_window=-30m"
        )
        anomaly_query = (
            "find_anomalous_metrics filtered by node=<host> and "
            f"context_pattern=\"{primary_prefix}.*\""
        ) if primary_prefix else (
            "find_anomalous_metrics filtered by node=<host>"
        )
        verification_intro = wrap_plain(
            f"Run these MCP queries against the Netdata instance that "
            f"sees the {tech} service. Every context listed below is a "
            "real Netdata chart name; the agent does not need to guess."
        )
        verification_body = wrap_plain(
            "A clean result means every context is within its expected "
            "band and the `find_anomalous_metrics` list is empty or "
            "contains only already-acknowledged items. If the fix was "
            "real, re-running the same queries 10 minutes after "
            "applying it will show a clean result. If it does not, "
            "revert and look deeper."
        )
        verification_block = (
            f"{verification_intro}\n\n"
            "```text\n"
            f"1. {prefix_clause}\n"
            f"2. {probe_query}\n"
            f"3. {anomaly_query}\n"
            "```\n\n"
            "Load-bearing contexts for this service:\n\n"
            f"{fmt_context_table(chosen)}\n\n"
            f"{verification_body}"
        )
    else:
        # Fallback for techs without a Netdata-native collector mapping.
        verification_intro = wrap_plain(
            f"Netdata does not ship a native collector for {tech}; "
            "discovery is dynamic. Run these MCP queries against the "
            f"Netdata instance that sees the {tech} service."
        )
        verification_body = wrap_plain(
            "If list_metrics returns nothing for this service, "
            "instrumentation or scraping has not been set up yet. See "
            "skills/netdata-otel-setup/ or the relevant Netdata "
            "collector config reference."
        )
        verification_block = (
            f"{verification_intro}\n\n"
            "```text\n"
            f"1. list_metrics with q=\"{slugify(tech)}\" to discover "
            "contexts\n"
            "2. query_metrics for each returned context over the last "
            "30 minutes\n"
            "3. find_anomalous_metrics scoped to the service or host\n"
            "```\n\n"
            f"{verification_body}"
        )

    # References: one per domain file.
    ref_lines = []
    for name, _ in domains:
        fname = f"{slugify(name)}.md"
        ref_lines.append(f"- [`rules/{fname}`](./rules/{fname})")
    if not ref_lines:
        ref_lines.append("- [`rules/overview.md`](./rules/overview.md)")
    ref_block = "\n".join(ref_lines)

    example_ctx = chosen[0]["name"] if chosen else f"{slugify(tech)}.*"
    discover_filter = (
        f"list_metrics with q=\"{primary_prefix}\"" if primary_prefix
        else f"list_metrics with q=\"{slugify(tech)}\""
    )
    mcp_tips = (
        "### Handy MCP call templates\n\n"
        "```text\n"
        f"# Discover metrics from {tech}\n"
        f"{discover_filter}\n"
        "\n"
        "# Pull a specific context over the last window\n"
        f"query_metrics with context=\"{example_ctx}\", relative_window=-15m\n"
        "\n"
        "# Rank anomalies for the service or host\n"
        "find_anomalous_metrics with node=<host> and context_pattern=\""
        + (f"{primary_prefix}.*" if primary_prefix else f"{slugify(tech)}.*")
        + "\"\n"
        "\n"
        "# Correlate a known problem context with others\n"
        "find_correlated_metrics around the incident window\n"
        "\n"
        "# Show current alert state\n"
        "list_raised_alerts scoped to the node\n"
        "```\n"
    )

    key_facts_block = "\n".join(wrap_line("- ", f) for f in key_facts)

    fix_misdiagnosis_intro = wrap_plain(
        f"If signals drift back into the anomalous range within 30 "
        f"minutes of a remediation, the cause was deeper than the "
        f"applied change. Typical misdiagnoses for {tech}:"
    )
    fix_misdiagnosis_bullets = "\n".join([
        wrap_line(
            "- ",
            "Host-resource pressure masquerading as application bug.",
        ),
        wrap_line(
            "- ",
            "Dependent service (DB, cache, upstream) causing a "
            "secondary symptom in the instrumented service.",
        ),
        wrap_line(
            "- ",
            "Configuration change that was never reloaded (some "
            "subsystems only pick up config on full restart).",
        ),
    ])
    fix_escalation = wrap_plain(
        "Escalate by widening the query window: 2-6 hours instead of "
        "15 minutes. Slow-moving causes are invisible at triage window "
        "sizes."
    )

    references_extra = "\n".join([
        wrap_line(
            "- ",
            "Netdata operator playbook: the authoritative source "
            "material this skill summarizes.",
        ),
        wrap_line(
            "- ",
            "`skills/netdata-mcp-integration/` for the transport setup.",
        ),
        wrap_line(
            "- ",
            "`skills/netdata-otel-setup/` if additional application "
            "signals are needed beyond what Netdata collects natively.",
        ),
    ])

    body = (
        f"# Troubleshoot {tech}\n\n"
        "## When to use this skill\n\n"
        + "\n".join(triggers_lines)
        + "\n\n"
        "## Key facts\n\n"
        + key_facts_block
        + "\n\n"
        "## Step-by-step\n\n"
        + steps_block
        + "\n\n"
        + mcp_tips
        + "\n"
        "## Common mistakes\n\n"
        + mistakes_block
        + "\n\n"
        "## Verification\n\n"
        + verification_block
        + "\n\n"
        "### When the fix does not hold\n\n"
        + fix_misdiagnosis_intro
        + "\n\n"
        + fix_misdiagnosis_bullets
        + "\n\n"
        + fix_escalation
        + "\n\n"
        "## References\n\n"
        + ref_block
        + "\n"
        + references_extra
        + "\n"
    )
    return fm + "\n\n" + body


def fmt_domain_rule(
    tech: str,
    slug_domain: str,
    domain_name: str,
    signals: list[tuple[str, str]],
    section_text: str,
    matched_contexts: list[dict] | None = None,
) -> str:
    matched_contexts = matched_contexts or []
    # Pull first paragraph under each signal as a short blurb.
    signal_blocks = []
    for sig_name, sev in signals:
        # Match either **SIGNAL: name** or #### SIGNAL: name variants.
        pattern = re.compile(
            rf"(?:\*\*SIGNAL:\s*{re.escape(sig_name)}\*\*|"
            rf"^#{{3,5}}\s*SIGNAL:\s*{re.escape(sig_name)}).*?$",
            re.MULTILINE,
        )
        m = pattern.search(section_text)
        blurb = ""
        source = ""
        if m:
            tail = section_text[m.end() :]
            stop = SIGNAL_HEADER_RE.search(tail)
            chunk = tail[: stop.start() if stop else len(tail)]
            w = re.search(
                r"WHAT IT IS:?\s*\n(.+?)(?:\n\n|\nSOURCE|\nHOW TO|$)",
                chunk,
                re.DOTALL,
            )
            if w:
                blurb = re.sub(r"\s+", " ", w.group(1)).strip()
            else:
                paras = [p.strip() for p in chunk.split("\n\n") if p.strip()]
                blurb = trim(re.sub(r"\s+", " ", paras[0]), 300) if paras else ""
            s = re.search(r"SOURCE:?\s*\n(.+?)(?:\n\n|\nHOW TO|$)", chunk, re.DOTALL)
            if s:
                source = re.sub(r"\s+", " ", s.group(1)).strip()

        signal_blocks.append((sig_name, sev, blurb, source))

    domain_name = sanitize(domain_name)
    lines: list[str] = []
    lines.append(f"# {tech}: {domain_name} signals")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(wrap_plain(
        f"Signals in the {domain_name} domain for {tech}, as defined in "
        "the Netdata operator playbook. Each signal includes a short "
        "description, the collection source, and a hint for the MCP "
        "query pattern that surfaces it. Use this file during a triage "
        "pass to decide which signal to pull first."
    ))
    lines.append("")
    lines.append("## Severity legend")
    lines.append("")
    lines.append("- **HIGH**: first-class paging target. Short time to impact.")
    lines.append("- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.")
    lines.append("- **LOW**: context only. Useful for RCA, not for alerting.")
    lines.append("")
    lines.append("## Signals")
    lines.append("")
    if signal_blocks:
        for sig_name, sev, blurb, source in signal_blocks:
            lines.append(f"### {sanitize(sig_name)} [{sev}]")
            lines.append("")
            if blurb:
                lines.append(wrap_plain(trim(blurb, 500)))
            else:
                lines.append(wrap_plain(
                    f"See the {tech} operator playbook for the full "
                    "definition of this signal."
                ))
            lines.append("")
            if source:
                lines.append(wrap_plain(
                    f"Collection source: {trim(source, 300)}"
                ))
                lines.append("")
            lines.append(wrap_plain(
                "MCP query: pull this signal with `query_metrics` and "
                "check the last 15 to 30 minutes against expected bands. "
                "Cross-reference with `find_anomalous_metrics` scoped to "
                "the same context. Use `find_correlated_metrics` if the "
                "signal has moved but the obvious cause is not visible."
            ))
            lines.append("")
    else:
        lines.append(wrap_plain(
            f"No structured signal list was extracted from the playbook "
            f"for the {domain_name} domain. Fall back to the MCP "
            "discovery pattern: run `list_metrics` filtered by the "
            f"{tech} service and inspect anything with matching keywords."
        ))
        lines.append("")

    lines.append("## Triage order within this domain")
    lines.append("")
    lines.append(wrap_plain(
        "Investigate HIGH-severity signals first, then MEDIUM, then "
        "LOW. HIGH-severity signals have the shortest time to impact; "
        "a confirmed HIGH anomaly usually justifies paging. When two "
        "HIGH signals move together, treat them as one incident until "
        "`find_correlated_metrics` rules out shared cause."
    ))
    lines.append("")
    lines.append("## Common false positives")
    lines.append("")
    lines.append(wrap_line("- ",
        "A single stale data point from a collector restart triggers "
        "many signals briefly. Re-query after 30 seconds before "
        "escalating."
    ))
    lines.append(wrap_line("- ",
        "Short bursts under 60 seconds rarely warrant action unless "
        "paired with a confirmed business impact."
    ))
    lines.append(wrap_line("- ",
        "Comparing against yesterday's baseline on a post-deploy day "
        "produces false anomalies. Compare against the pre-deploy "
        "baseline."
    ))
    lines.append(wrap_line("- ",
        "Collector-visible percentile latency with < 100 samples per "
        "minute is noise. Require a minimum sample count before acting."
    ))
    lines.append("")
    lines.append("## Remediation pointers")
    lines.append("")
    lines.append(wrap_plain(
        "Remediation for signals in this domain is tech-specific and "
        "typically covered in the operator playbook's SECTION 3 "
        "(Failure Patterns) or SECTION 4 (Runbooks). Before applying a "
        "change:"
    ))
    lines.append("")
    lines.append(wrap_line("1. ",
        "Run the MCP verification queries to record the current state."
    ))
    lines.append(wrap_line("2. ",
        "Apply the smallest remediation that addresses the confirmed "
        "cause. Config changes before restarts; restarts before "
        "rollbacks."
    ))
    lines.append(wrap_line("3. ",
        "Re-run the same MCP queries after the remediation settles. "
        "Recording before/after numbers is how a runbook entry gets "
        "sharpened over time."
    ))
    lines.append("")

    # Netdata contexts section: real chart names from metadata.yaml,
    # pre-filtered to this domain. Empty block means we either have no
    # Netdata collector mapping (e.g. Kafka) or the keyword filter
    # matched nothing in this domain; the MCP examples below fall back
    # to discovery-style calls in that case.
    lines.append(f"## Netdata contexts that surface {domain_name}")
    lines.append("")
    if matched_contexts:
        lines.append(wrap_plain(
            "These are the real Netdata chart contexts the native "
            f"collector emits for {tech}. Use these names verbatim in "
            "`query_metrics` calls."
        ))
        lines.append("")
        lines.append(fmt_context_table(matched_contexts))
        lines.append("")
    else:
        lines.append(wrap_plain(
            f"No Netdata-native contexts were classified into the "
            f"{domain_name} domain for {tech}. Use discovery-style MCP "
            "calls below, or consult the full context list in SKILL.md."
        ))
        lines.append("")

    lines.append("## MCP query examples for this domain")
    lines.append("")
    lines.append("```text")
    if matched_contexts:
        names = [c["name"] for c in matched_contexts[:6]]
        lines.append("# Pull every context in this domain at once")
        lines.append(
            f"query_metrics with contexts=[{', '.join(names)}] "
            "and relative_window=-30m"
        )
        lines.append("")
        prefix = matched_contexts[0]["name"].split(".", 1)[0]
        lines.append("# Rank anomalies that match this domain")
        lines.append(
            f"find_anomalous_metrics with node=<host> and "
            f"context_pattern=\"{prefix}.*\""
        )
        lines.append("")
        lines.append("# Correlate a problem context with others outside the domain")
        lines.append(
            f"find_correlated_metrics around the incident window, "
            f"anchor_context=\"{matched_contexts[0]['name']}\""
        )
    else:
        lines.append("# Discover contexts for this service")
        lines.append(
            f"list_metrics with q=\"{slugify(tech)}\""
        )
        lines.append("")
        lines.append("# Rank anomalies on the host running this service")
        lines.append(
            f"find_anomalous_metrics with node=<host>"
        )
    lines.append("```")
    lines.append("")
    lines.append("## When to escalate out of this skill")
    lines.append("")
    lines.append(wrap_plain(
        "If none of the signals in this domain move during the "
        "incident, the root cause is elsewhere. Typical re-routing:"
    ))
    lines.append("")
    lines.append(wrap_line("- ",
        "Host-resource domain: load, CPU, memory, disk, network "
        "saturation"
    ))
    lines.append(wrap_line("- ",
        "Dependency domain: the service's upstream or downstream "
        "(database, cache, queue) is the actual source"
    ))
    lines.append(wrap_line("- ",
        "Orchestrator domain: Kubernetes or systemd lifecycle events "
        "rather than application misbehavior"
    ))
    lines.append(wrap_line("- ",
        "Alert engine domain: a misconfigured alert threshold triggered "
        "a false-positive incident"
    ))
    lines.append("")

    return "\n".join(lines)


# Playbook text sometimes uses marketing-adjacent words the repo style
# guide bans. Swap them for neutral equivalents as the text flows into
# the generator. Keep this map in sync with BANNED_PHRASES in
# scripts/validate.py; entries here exist because playbook prose has
# historically tripped the validator on at least one technology.
BANNED_PHRASE_REPLACEMENTS = [
    ("cutting-edge", "current"),
    ("game-changing", "meaningful"),
    ("delve into", "work through"),
    ("dive in", "start"),
    ("I'd love to", ""),
    ("seamlessly", "cleanly"),
    ("leverage", "use"),
    ("robustly", "reliably"),
    ("robust", "reliable"),
    ("powerful", "strong"),
    ("genuinely", ""),
]


def sanitize(s: str) -> str:
    """Strip style-banned characters from extracted playbook text."""
    # An em-dash in the middle of a clause becomes a semicolon-like break.
    # Before a descriptor it becomes a colon; pattern-matching is tricky, so
    # use semicolon which reads well in most contexts.
    s = s.replace(" \u2014 ", "; ")  # spaced em-dash -> semicolon
    s = s.replace("\u2014", "; ")     # any remaining em-dash
    s = s.replace("\u2013", "-")      # en-dash
    s = s.replace(" \u2192 ", " then ")  # ' -> '  (unicode arrow) -> 'then'
    s = s.replace("\u2192", " then ")   # bare arrow
    s = s.replace("\u21d2", " then ")   # double arrow
    s = re.sub(r"(?<!-)--(?!-)", " -", s)  # double-hyphen -> single
    # Replace banned phrases before collapsing whitespace.
    for bad, good in BANNED_PHRASE_REPLACEMENTS:
        s = re.sub(
            rf"\b{re.escape(bad)}\b",
            good,
            s,
            flags=re.IGNORECASE,
        )
    # Collapse the resulting doubled punctuation.
    s = re.sub(r";\s*;", ";", s)
    s = re.sub(r"\s+;", ";", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def trim(s: str, n: int) -> str:
    s = sanitize(s)
    if len(s) <= n:
        return s
    return s[: n - 3].rstrip() + "..."


def wrap_line(prefix: str, body: str, width: int = 100) -> str:
    """Wrap `prefix + body` so every line stays <= width. Continuation lines
    are indented by the visual width of the prefix so Markdown list rendering
    is preserved (bullet and numbered lists both recognize hanging indent)."""
    body = sanitize(body)
    indent = " " * len(prefix)
    return textwrap.fill(
        prefix + body,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
        initial_indent="",
        subsequent_indent=indent,
    )


def wrap_plain(body: str, width: int = 100) -> str:
    """Wrap a standalone paragraph at `width` characters."""
    body = sanitize(body)
    return textwrap.fill(
        body,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )


def write_if_changed(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def clean_old_generated() -> None:
    if not SKILLS_DIR.exists():
        return
    for d in SKILLS_DIR.iterdir():
        if d.is_dir() and d.name.startswith(TROUBLESHOOT_PREFIX):
            # Remove the whole directory to avoid stale rule files.
            for child in sorted(d.rglob("*"), key=lambda p: (p.is_file(), str(p)), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            d.rmdir()


def generate() -> int:
    playbooks = read_playbooks()
    print(f"Found {len(playbooks)} playbooks.")
    clean_old_generated()

    made = 0
    for pb in playbooks:
        text = pb.read_text(encoding="utf-8")
        tech = extract_title(text, pb.name)
        pb_slug = slugify(pb.stem)
        slug = f"{TROUBLESHOOT_PREFIX}{pb_slug}"

        section0 = extract_section(text, SECTION0_RE, SECTION1_RE)
        section1 = extract_section(text, SECTION1_RE, SECTION2_RE)

        failures = extract_failure_archetypes(section0) or []
        domains = extract_domains(section1)
        intro = first_paragraphs(section0, n=2)

        tags = [
            "netdata",
            "troubleshoot",
            "mcp",
            pb_slug,
        ]

        # Pull real Netdata contexts for this tech from the collector
        # metadata.yaml. Empty list means no native collector mapping;
        # the skill then teaches discovery-style MCP calls.
        contexts = load_collector_contexts(pb_slug)
        context_buckets = classify_contexts_by_domain(contexts, domains)

        skill_text = fmt_skill_md(
            tech, slug, intro, failures, domains, tags, contexts=contexts,
        )

        skill_dir = SKILLS_DIR / slug
        write_if_changed(skill_dir / "SKILL.md", skill_text)
        write_if_changed(
            skill_dir / "README.md",
            f"# {slug}\n\nTroubleshooting skill for {tech}. See "
            f"[SKILL.md](./SKILL.md).\n",
        )

        if domains:
            for name, signals in domains:
                dslug = slugify(name)
                matched = context_buckets.get(name, [])
                rule = fmt_domain_rule(
                    tech, dslug, name, signals, section1,
                    matched_contexts=matched,
                )
                write_if_changed(skill_dir / "rules" / f"{dslug}.md", rule)
            # If we have contexts that did not bucket into any playbook
            # domain, emit an extra rule file so they are not lost. This
            # is intentionally a single catch-all domain, not per-scope.
            unmatched = context_buckets.get("__unmatched__", [])
            if unmatched:
                rule = fmt_domain_rule(
                    tech, "other-contexts", "Other Netdata Contexts",
                    [], section1, matched_contexts=unmatched,
                )
                write_if_changed(
                    skill_dir / "rules" / "other-contexts.md", rule,
                )
        else:
            rule = fmt_domain_rule(
                tech, "overview", "Overview", [], section0 or "",
                matched_contexts=contexts,
            )
            write_if_changed(skill_dir / "rules" / "overview.md", rule)

        made += 1

    print(f"Generated {made} troubleshoot-* skills.")
    return 0


if __name__ == "__main__":
    sys.exit(generate())
