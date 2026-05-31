# python.d and charts.d modules

`python.d.plugin` (Python) and `charts.d.plugin` (Bash) are
orchestrated frameworks. Each hosts many modules and speaks the line
protocol to Netdata on their behalf, so a module writes only the
collect-and-return logic, not its own process loop.

Treat both as legacy. Most former Python and Bash modules have been
replaced by go.d equivalents, and Netdata steers new core
contributions to Go. The surviving python.d modules on master are
only `am2320`, `go_expvar`, `haproxy`, `pandas`, and `traefik`;
`charts.d` is down to `apcupsd`, `libreswan`, `opensips`, `sensors`,
and `example`. Use these frameworks to extend or fix a module that
already lives here, or for a community module that leans on a
language-specific library. For a new standalone collector, prefer a
raw external plugin
([`external-plugin-protocol.md`](./external-plugin-protocol.md)).

Sources:
`src/collectors/python.d.plugin/python.d.conf`,
`src/collectors/charts.d.plugin/charts.d.conf`,
`docs/developer-and-contributor-corner/python-collector.txt`.
Community modules go to
[`netdata/community`](https://github.com/netdata/community).

## python.d

### Layout and enabling

A module `<module>` is the file
`src/collectors/python.d.plugin/<module>/<module>.chart.py`, with a
sibling YAML config `<module>.conf`. Enable it in `python.d.conf`
(`<module>: yes`). The whole plugin can be turned off in
`netdata.conf` with `python.d = no` under `[plugins]`. Source:
`src/collectors/python.d.plugin/README.md`.

The `example` module was removed from master, so copy a surviving
module like `am2320` as a starting point. Source:
`src/collectors/python.d.plugin/am2320/am2320.chart.py`.

### Framework base classes

All under
`src/collectors/python.d.plugin/python_modules/bases/FrameworkServices`.
Pick the base that matches your data source:

- `SimpleService`: root prototype; subclass when you collect data
  yourself. You implement `get_data()`.
- `UrlService`: scrape an HTTP/HTTPS endpoint; reads `url`, auth, and
  `tls_*` from config.
- `SocketService`: raw TCP/UDP or Unix-socket protocols.
- `ExecutableService`: parse the stdout of a command.
- `LogService`: tail a log file, returning only new lines.
- `MySQLService`: run a dict of queries against MySQL/MariaDB.

### The idiom

Two module-level globals plus a `Service` subclass:

- `ORDER`: list of chart ids in display order.
- `CHARTS`: dict mapping each chart id to `options` and `lines`.
  - `options` is positional: `[None, title, units, family, context,
    charttype]`.
  - each `lines` entry is `[id, name, algorithm, multiplier,
    divisor]` (trailing items optional).
- `Service` sets `self.order = ORDER` and `self.definitions = CHARTS`
  in `__init__`, and implements `get_data()` returning a dict of
  `{dimension_id: value}` or `None` on failure.

The dict keys returned by `get_data()` must match the `lines` ids.
Minimal module, following the `am2320` shape:

```python
# example.chart.py
# SPDX-License-Identifier: GPL-3.0-or-later

import random

from bases.FrameworkServices.SimpleService import SimpleService

ORDER = [
    'random',
]

CHARTS = {
    'random': {
        # [None, title, units, family, context, charttype]
        'options': [None, 'Random Numbers', 'value', 'random', 'example.random', 'line'],
        'lines': [
            # [id, name, algorithm, multiplier, divisor]
            ['random1', 'first',  'absolute'],
            ['random2', 'second', 'absolute'],
        ],
    },
}


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = CHARTS

    def check(self):
        return True

    def get_data(self):
        try:
            return {
                'random1': random.randint(0, 100),
                'random2': random.randint(0, 100),
            }
        except (OSError, RuntimeError) as error:
            self.error(error)
            return None
```

Per-job config keys every module supports: `name`, `update_every`,
`priority`, `penalty`, `autodetection_retry`. Source:
`src/collectors/python.d.plugin/python_modules/bases/FrameworkServices/SimpleService.py`,
`src/collectors/python.d.plugin/am2320/am2320.conf`.

## charts.d (Bash)

### Layout and enabling

A module `X` is the script `X.chart.sh` in the charts.d directory,
with an optional `X.conf` (itself a sourced Bash script). Enable it
in `charts.d.conf` with `X="yes"`. Use `X="force"` only for stock
modules whose `X_check` may fail on a host that lacks the target; for
your own working module, `X="yes"` is what enables it (`force` alone
will not). All functions and globals must be prefixed with `X_`.
charts.d is not installed by default with native packages; it needs
the `netdata-plugin-chartsd` package. Source:
`src/collectors/charts.d.plugin/README.md`.

### The contract: three functions

- `X_check`: return 0 if the collector can run, 1 to disable it. Run
  once.
- `X_create`: print `CHART` and `DIMENSION` lines. Run once after
  `check` succeeds.
- `X_update`: print `BEGIN` / `SET` / `END` lines. Run every
  interval. It receives one argument, the microseconds since its last
  run, which you append to each `BEGIN` line.

There is no required `X_get`; modules often define one as an internal
helper. charts.d provides `require_cmd` (for use in `check`) and
`fixid` (sanitize a string into a valid id; do not call it in
`update`).

Minimal module, following the real `example.chart.sh`:

```bash
# no shebang: this file is sourced by charts.d.plugin
# SPDX-License-Identifier: GPL-3.0-or-later
# shellcheck shell=bash

example_update_every=
example_priority=150000

example_value1=
example_value2=

# internal helper, not part of the contract
example_get() {
  example_value1=$RANDOM
  example_value2=$RANDOM
  return 0
}

example_check() {
  example_get || return 1
  return 0
}

example_create() {
  cat << EOF
CHART example.random '' "Random Numbers" "value" random example.random line $((example_priority)) $example_update_every '' '' 'example'
DIMENSION random1 '' absolute 1 1
DIMENSION random2 '' absolute 1 1
EOF
  return 0
}

# $1 is the microseconds since the last run
example_update() {
  example_get || return 1
  cat << VALUESEOF
BEGIN example.random $1
SET random1 = $example_value1
SET random2 = $example_value2
END
VALUESEOF
  return 0
}
```

Source:
`src/collectors/charts.d.plugin/example/example.chart.sh`.

Mind the `CHART` positional fields: `CHART type.id name title units
family context charttype ...`. The chart id and the context are
different fields. Set the context (7th field) to a meaningful value
such as `example.random`, not a bare word. Netdata groups, charts,
and verifies by context, so when you confirm the collector over MCP
you filter on the context, not the chart id. Netdata's stock
`example.chart.sh` uses a bare `random` context, which is why this
example overrides it. See
[`external-plugin-protocol.md`](./external-plugin-protocol.md) for the
full field reference.

### Performance caveat

`charts.d.plugin` calls each module's `X_update` sequentially, so a
slow module delays the others. This is a reason to prefer Go for
anything latency-sensitive or high-cardinality. Source:
`src/collectors/charts.d.plugin/README.md`.

## References

- python.d README:
  `src/collectors/python.d.plugin/README.md`
- charts.d README:
  `src/collectors/charts.d.plugin/README.md`
- The chart line protocol (shared by both frameworks):
  [`external-plugin-protocol.md`](./external-plugin-protocol.md)
