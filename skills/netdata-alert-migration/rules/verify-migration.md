# Verifying the migration

A translated alert is not done until it has loaded into a real Netdata
health engine, attached to its chart, parsed its expression, and
evaluated. Netdata skips a health entity that fails to parse rather
than failing the reload, so a silent omission looks like success.
Always verify.

When a Netdata MCP server is connected, the agent runs this loop
itself and reports the result. Do not hand the user a checklist.

## Load the alerts

Place the files under `/etc/netdata/health.d/` and reload without
restarting:

```bash
sudo netdatacli reload-health
```

(`sudo killall -USR2 netdata` is the equivalent signal.) Source:
`src/health/REFERENCE.md`.

## Stage 1: confirm each alert loaded and parsed

Over MCP, the relevant tools are `list_running_alerts` (every alert,
including CLEAR, that is attached and evaluating), `list_raised_alerts`
(only WARNING/CRITICAL right now), and `list_alert_transitions`
(state-change history).

1. **Loaded and attached.** Call `list_running_alerts` and confirm
   each translated alert is present and not in `UNINITIALIZED` or
   `UNDEFINED` state. A missing alert means a parse or attach failure.

   ```text
   Use list_running_alerts. Confirm an alert named "myapp_queue_backlog"
   is present and its status is CLEAR, WARNING, or CRITICAL (not
   UNINITIALIZED or UNDEFINED).
   ```

2. **Parsed expression.** Cross-check against the REST health API,
   which returns both the original and the parsed (re-parenthesized)
   expression:

   ```bash
   curl -s 'http://localhost:19999/api/v1/alarms?all' \
     | jq '.alarms | to_entries[]
            | select(.value.name=="myapp_queue_backlog")
            | {status, active, warn:.value.warn, warn_parsed:.value.warn_parsed}'
   ```

   `active: true` means it attached to a chart. A populated
   `warn_parsed`/`crit_parsed` proves the expression parsed. The
   status enum is `CLEAR`, `WARNING`, `CRITICAL`, `UNINITIALIZED`,
   `UNDEFINED`, `REMOVED`. Source: `src/web/api/v1/api_v1_alarms.c`.

3. **Variables resolve.** If status is `UNDEFINED`, a referenced
   variable or dimension is wrong. Check what the chart exposes:

   ```bash
   curl -s 'http://localhost:19999/api/v1/alarm_variables?chart=CHART_ID'
   ```

## Stage 2: confirm it evaluates correctly (trigger and revert)

Loading is not correctness. Confirm the alert actually fires on the
condition it is meant to catch. Temporarily lower the threshold so the
current value crosses it, reload, and watch the transition.

1. Edit the alert to a threshold the live value exceeds, e.g.
   `warn: $this > 0`, and `netdatacli reload-health`.
2. Confirm it raised:

   ```text
   Use list_raised_alerts and confirm "myapp_queue_backlog" is now WARNING.
   ```

   or over REST, read `status` from `/api/v1/alarms`, or the
   transition from `/api/v1/alarm_log?chart=CHART_ID`
   (`status`/`old_status`).
3. Confirm the transition was recorded:

   ```text
   Use list_alert_transitions and confirm a CLEAR to WARNING transition
   for "myapp_queue_backlog".
   ```

4. Restore the real threshold and `netdatacli reload-health` again.

This proves the alert binds to the right dimension, the `lookup`
returns a sane value, and the comparison fires in the expected
direction (a counter charted as a level, or an inverted threshold, is
caught here).

## When an alert does not appear

The reload skips a bad entity rather than failing, so check the daemon
log for the parse error:

```bash
journalctl -u netdata | grep -i "Health configuration"
```

On non-systemd or older hosts, look in `/var/log/netdata/` (the
daemon/error log). The message names the file and line. Source:
`src/health/health_config.c`. Common causes:

- `on:` names a context/chart that does not exist (metric not
  collected): the alert never attaches. Collect the metric first.
- a dimension in `lookup ... of` does not exist on the chart: status
  `UNDEFINED`. Confirm dimension names with `alarm_variables`.
- a chart id with `-` or `=` referenced without the `${...}` brace
  form in an expression: parse error.
- `families:` / `charts:` lines, or a misspelled key: ignored or
  rejected.

## Iterate until correct

Re-run Stage 1 and Stage 2 after each fix. The migration is complete
when every translated alert is present, attached, parsed, and has
demonstrated the expected transition, and every rule that stays on
`vmalert` is listed with its reason.

## References

- Health REST API source: `src/web/api/v1/api_v1_alarms.c`.
- MCP alert tools: the `netdata-mcp-integration` skill.
- Health reference: `src/health/REFERENCE.md`.
