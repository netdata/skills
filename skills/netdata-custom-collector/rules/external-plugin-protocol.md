# External plugins: collect in any language

An external plugin is any executable that prints a line protocol to
stdout. Netdata runs it, reads its output, and turns it into charts.
This is the universal path: if your language can print text on an
interval, it can feed Netdata. Use it for quick wins, for wrapping a
CLI tool, or when the data is only reachable through a library that
exists in one language.

This rule is also the canonical reference for the chart model. The Go
framework and the `python.d`/`charts.d` frameworks are conveniences
over this same protocol.

Source for everything below:
`src/plugins.d/README.md`.
(Note: the file is at `src/plugins.d/README.md`, not under
`src/collectors/`.)

## The model

- Netdata starts the plugin when it starts and expects it to run
  forever. Communication is one-way: plugin stdout to Netdata.
- The plugin's stderr is written to Netdata's error log.
- Netdata passes one command-line argument: the update interval in
  seconds. Read it from `argv[1]`. It is also in the environment as
  `NETDATA_UPDATE_EVERY`.
- Exit codes matter. Exit non-zero (or print `DISABLE`) and Netdata
  stops restarting the plugin. Exit zero and Netdata restarts it
  after a while. A plugin that exits before ever emitting a metric is
  not restarted.
- Plugins live in the `plugins.d` directory, typically
  `/usr/libexec/netdata/plugins.d`. Name them `*.plugin` by
  convention.

## The line protocol

### CHART, printed once per chart

```text
CHART type.id name title units [family [context [charttype [priority [update_every [options [plugin [module]]]]]]]]
```

Required: `type.id`, `name`, `title`, `units`. Everything from
`family` on is optional.

- `type.id` uniquely identifies the chart and is the handle used by
  `BEGIN`. The `type` prefix groups a plugin's charts into one
  dashboard menu section.
- `name` is a user-facing alias for the `id` part; pass `''` to skip.
- `title` is the text above the chart.
- `units` is the vertical-axis label; all dimensions should share it.
- `family` groups related charts into a submenu (for example one
  family per disk). Defaults to the `id` part.
- `context` is the chart template. Charts that show the same thing
  for different families share a context, and alerts attach by
  context.
- `charttype` is `line`, `area`, `stacked`, or `heatmap`. Default
  `line`.
- `priority` sorts charts, lower first. Default 1000.
- `options` include `obsolete`, `hidden`, and `store_first`.

### DIMENSION, printed once per dimension after its CHART

```text
DIMENSION id [name [algorithm [multiplier [divisor [options]]]]]
```

Required: `id` only. `id` is the key used by `SET`.

- `name` is the legend label; defaults to `id`.
- `algorithm`:
  - `absolute`: value drawn as-is. The default. Use for levels.
  - `incremental`: value is a monotonic counter; Netdata shows the
    per-second delta. Use for counters.
  - `percentage-of-absolute-row` and
    `percentage-of-incremental-row`: value as a percent of the row.
- `multiplier` and `divisor` are integers, default 1.

Avoid `.` in a dimension `id`; it breaks dotted names in some export
backends.

### BEGIN / SET / END, printed every collection cycle

```text
BEGIN type.id [microseconds]
SET id = value
END
```

- `BEGIN type.id` opens an update for that chart. The optional
  `microseconds` is the time since this chart's last update;
  supplying it improves accuracy under load. Omit it on the first
  cycle.
- `SET id = value` sets one dimension. `value` is a signed 64-bit
  integer. To skip a dimension this cycle, omit the line.
- `END` commits the values.

`SET` takes integers only. For fractional values, multiply in code
and set the dimension `divisor` to match (multiply by 1000, divisor
1000).

### Other commands

- `FLUSH` cancels an open `BEGIN` and discards values collected since
  it.
- `DISABLE` tells Netdata to stop restarting this plugin.
- `CLABEL name value source` then `CLABEL_COMMIT` attach labels to a
  chart. `VARIABLE`, `FUNCTION`, and `CONFIG` are advanced and not
  needed for a basic collector.

## The lifecycle a plugin must implement

1. Read the update interval from `argv[1]`.
2. If you cannot collect at all, print `DISABLE` and exit 1.
3. Print every `CHART` and its `DIMENSION` lines once.
4. Loop forever: sleep the interval, collect, print `BEGIN` / `SET` /
   `END`, then flush stdout.

Flush stdout every cycle. The pipe to Netdata buffers, and without a
flush Netdata sees nothing. If you are unsure about memory leaks in a
long-running plugin, the README suggests exiting once an hour and
letting Netdata restart you.

## Minimal plugin in Bash

```bash
#!/usr/bin/env bash
# Netdata external plugin: one chart, two dimensions.
# Protocol: src/plugins.d/README.md

update_every="${1:-1}"          # argv[1] is the interval in seconds

# Definitions, printed once.
# CHART type.id name title units family context charttype priority update_every
cat <<EOF
CHART example.twovalues '' "Two Random Values" "value" random example.twovalues line 90000 ${update_every}
DIMENSION value_a 'A' absolute 1 1
DIMENSION value_b 'B' absolute 1 1
EOF

trap 'exit 0' TERM INT

while true; do
    sleep "${update_every}"
    a=$RANDOM
    b=$RANDOM
    cat <<EOF
BEGIN example.twovalues
SET value_a = ${a}
SET value_b = ${b}
END
EOF
done
```

## Minimal plugin in Python

```python
#!/usr/bin/env python3
# Netdata external plugin: one chart, two dimensions.
# Protocol: src/plugins.d/README.md
import sys
import time
import random
import signal

update_every = int(sys.argv[1]) if len(sys.argv) > 1 else 1

def out(line):
    sys.stdout.write(line + "\n")

# Definitions, printed once.
out("CHART example.twovalues '' 'Two Random Values' 'value' random "
    "example.twovalues line 90000 %d" % update_every)
out("DIMENSION value_a 'A' absolute 1 1")
out("DIMENSION value_b 'B' absolute 1 1")
sys.stdout.flush()

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

while True:
    time.sleep(update_every)
    out("BEGIN example.twovalues")
    out("SET value_a = %d" % random.randint(0, 32767))
    out("SET value_b = %d" % random.randint(0, 32767))
    out("END")
    sys.stdout.flush()          # mandatory: the pipe buffers
```

The SIGTERM trap is good practice for a clean exit; it is not part of
the protocol spec.

## Install and enable

1. Place the executable in `/usr/libexec/netdata/plugins.d/`, named
   `something.plugin`.
2. Make it executable and give it a valid shebang:

   ```bash
   sudo chmod +x /usr/libexec/netdata/plugins.d/twovalues.plugin
   ```

3. Enable it in `netdata.conf` under `[plugins]`. The per-plugin key
   is the filename without `.plugin`:

   ```text
   [plugins]
       enable running new plugins = yes
       twovalues = yes
   ```

4. Tune it per plugin with a `[plugin:NAME]` section:

   ```text
   [plugin:twovalues]
       update every = 1
       command options =
   ```

   `update every` becomes the `argv[1]` interval; `command options`
   appends arguments.

A plain Bash or Python plugin needs no special privileges, only the
executable bit. Privileged plugins (setuid or capabilities) are a
separate, advanced topic.

## Debug standalone

Run the plugin yourself to read its raw protocol output:

```bash
/usr/libexec/netdata/plugins.d/twovalues.plugin 1
```

You should see the `CHART` and `DIMENSION` block, then a `BEGIN` /
`SET` / `END` block every second. To reproduce Netdata's runtime
permissions, run it as the `netdata` user:

```bash
sudo -u netdata /usr/libexec/netdata/plugins.d/twovalues.plugin 1
```

See [`verify-a-collector.md`](./verify-a-collector.md) for the full
check.

## Raw plugin vs orchestrator

`go.d.plugin`, `python.d.plugin`, and `charts.d.plugin` are
themselves external plugins, but they are orchestrators: each hosts
many modules and speaks this protocol on their behalf, so a module
author writes only collect-and-return logic. A raw external plugin
(your own `*.plugin`) emits the protocol directly. If you are writing
a Python or Bash module inside one of those frameworks, see
[`python-and-bash-modules.md`](./python-and-bash-modules.md).

## References

- External plugins API and protocol:
  `src/plugins.d/README.md`
