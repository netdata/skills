# Migrating notification routing

Alertmanager and Netdata route notifications with different models.
Netdata has two targets: per-agent notifications
(`health_alarm_notify.conf`) and Netdata Cloud. Map the customer's
Alertmanager config onto whichever fits; for label-matcher routing,
Cloud is the closer parity.

## Alertmanager in one paragraph

`vmalert` posts firing alerts to Alertmanager, which groups them
(`group_by`), routes them through a tree of `route` nodes that match
on alert labels (`matchers`), and delivers each to a `receiver`
(slack, pagerduty, email, webhook, and so on). It also throttles
(`group_wait`, `group_interval`, `repeat_interval`), suppresses with
`inhibit_rules`, and mutes with time-bounded silences. Source:
https://prometheus.io/docs/alerting/latest/configuration/

## Netdata agent notifications

The alert's `to:` line names a **role**, not a recipient. The role is
expanded to recipients per method in `health_alarm_notify.conf` (a
BASH config). Three layers:

- `SEND_<METHOD>="YES|NO"` enables a method (e.g. `SEND_SLACK`,
  `SEND_PD`, `SEND_EMAIL`).
- `DEFAULT_RECIPIENT_<METHOD>` is the fallback recipient for that
  method.
- `role_recipients_<method>[role]="..."` maps a role to recipients for
  that method.

Built-in roles: `sysadmin`, `domainadmin`, `dba`, `webmaster`,
`proxyadmin`, `sitemgr`. Add a custom role just by adding
`role_recipients_<method>[<newrole>]` entries and using `<newrole>` in
an alert's `to:`.

Per-recipient severity filters append with `|`:

```text
role_recipients_slack[dba]="#db-alerts #oncall|critical"
role_recipients_email[dba]="dba@corp.com|nowarn"
```

`|critical` sends only critical (and follow-ups until clear),
`|nowarn` drops warnings, `|noclear` drops clears. Set a recipient to
`disabled` to turn a method off for a role. Source:
`src/health/notifications/health_alarm_notify.conf`.

## Netdata Cloud notifications

Cloud centralizes notifications across all connected nodes, configured
per Space and filtered to Rooms, so it does not need per-node config.
Integrations include Email, Discord, Slack, Mattermost, RocketChat,
Telegram, Microsoft Teams, PagerDuty, Opsgenie, Amazon SNS,
ServiceNow, Splunk, Splunk VictorOps, ilert, and Webhook. Method
availability depends on the plan (Email and Discord on the free
Community plan; Slack and PagerDuty require a paid plan). Each method
configuration selects which severities to send: Critical, Warning,
Clear, Reachable, Unreachable.

**Silencing rules** are the closest analog to Alertmanager matchers
and silences. They match on Rooms, Nodes, Host Labels, Alert Name,
Alert Context, and Alert Role, and run either Immediate (until turned
off) or Scheduled (start and end time, i.e. a maintenance window).
Silencing rules require a paid plan. Source:
`docs/alerts-and-notifications/notifications/centralized-cloud-notifications/`
in the Netdata repo.

## Mapping table

| Alertmanager | Netdata agent | Netdata Cloud |
| --- | --- | --- |
| `receiver` (slack/pd/email) | a method + `role_recipients_<m>[role]` | an integration configuration |
| `route.receiver` | the alert's `to: <role>` | the method's Room filter |
| `matchers` (label routing) | none; pick the `to:` role per alert | silencing-rule criteria |
| severity routing | `|critical` / `|nowarn` per recipient | per-method severity selection |
| `silences` (time-bounded) | `disabled` recipient (permanent) | silencing rule, Scheduled mode |
| `inhibit_rules` | none | partial: silencing by context/label |
| `group_by` | none | none (flood protection only) |
| `group_wait`/`group_interval`/`repeat_interval` | `repeat:` (re-notify only) | none tunable |

## Recommendation

- **Receiver fan-out and severity throttling**: the agent role model
  reproduces this fully, free, with no Cloud dependency. Translate
  each `receiver` to a method plus `role_recipients`, and each alert's
  effective route to a `to:` role.
- **Label-matcher routing, silences, and maintenance windows**:
  Netdata Cloud is the parity target (silencing rules with
  node/context/label/name criteria and scheduled windows). Note the
  paid-plan requirement.
- **No equivalent**: `group_by`, group timing intervals, and true
  source-to-target `inhibit_rules`. State these as gaps. The closest
  partial substitutes are Cloud flood protection (not tunable) and
  Cloud silencing (suppression, not inhibition).

## References

- Alertmanager config: https://prometheus.io/docs/alerting/latest/configuration/
- Agent notifications: `src/health/notifications/health_alarm_notify.conf`
- Cloud notifications: `docs/alerts-and-notifications/notifications/` in the Netdata repo.
