# Data Model

All telemetry in PC Diagnostic flows through a small set of frozen dataclasses defined
in `src/pc_diagnostic/models.py`. This document explains each model, why it's shaped
the way it is, and the naming conventions that hold everything together.

---

## Core Types

### MetricUnit (Enum)

A closed set of physical units. Unlike metric names (which are open strings), units
change rarely and benefit from type safety — an enum prevents bugs where one provider
reports bytes and another reports megabytes for the same metric.

```python
class MetricUnit(Enum):
    PERCENT       = "PERCENT"
    BYTES         = "BYTES"
    BYTES_PER_SEC = "BYTES_PER_SEC"
    HERTZ         = "HERTZ"
    CELSIUS       = "CELSIUS"
    RPM           = "RPM"
    COUNT         = "COUNT"
    SECONDS       = "SECONDS"
    INFO          = "INFO"    # metadata / static specs
    VOLTS         = "VOLTS"
```

### MetricReading (frozen dataclass)

The single most important type in the system. Every reading, from every provider,
on every OS, fits this shape:

| Field    | Type              | Purpose                                | Example                          |
|----------|-------------------|----------------------------------------|----------------------------------|
| `metric` | `str`             | Canonical dot-separated name           | `"cpu.utilization.total"`        |
| `value`  | `float`           | The measurement                        | `47.3`                           |
| `unit`   | `MetricUnit`      | What the number means                  | `MetricUnit.PERCENT`             |
| `source` | `str`             | Which provider produced this           | `"psutil"`                       |
| `tags`   | `dict[str, str]`  | Dimensional metadata (default `{}`)    | `{"core": "0", "disk": "sda"}`   |

#### Why these fields?

- **`metric` is a string, not an enum.** New providers define new metrics. An enum
  forces updating a central file every time — a coupling magnet. Strings with a
  dot-separated convention give structure without rigidity.

- **`tags` instead of dedicated fields.** The same shape describes
  `cpu.utilization.per_core` (tag: `core=0`) and `disk.io.read_bytes`
  (tag: `device=sda`). Without tags, the schema either explodes with nullable fields
  or forces different reading types per metric category. This is the
  dimensional-metrics pattern (à la Prometheus / StatsD).

- **`source` as a string.** Lets the dashboard trace where a number came from.
  Essential when the same metric (e.g., `cpu.temperature`) might come from
  multiple providers on different OSes.

- **No `timestamp` on individual readings.** The timestamp lives on the `Snapshot`.
  All readings in a tick share one timestamp, avoiding clock drift within a tick.

### Snapshot (frozen dataclass)

One tick's worth of data:

```python
@dataclass(frozen=True)
class Snapshot:
    timestamp: float           # time.time(), epoch seconds
    readings: list[MetricReading]
```

The readings list is **flat** (not nested by category) because:
- The cache doesn't need to understand metric semantics — it just stores snapshots
- Grouping/filtering is a read-time concern (the dashboard decides layout)
- Flat is simpler to serialize, validate, and iterate

### CacheHealth (frozen dataclass)

An observability hook for diagnosing the collector's health:

| Field          | Type    | What it tells you                        |
|----------------|---------|------------------------------------------|
| `size`         | `int`   | How many snapshots are cached            |
| `max_size`     | `int`   | The deque's maxlen                       |
| `last_updated` | `float` | Timestamp of the most recent push        |
| `age_s`        | `float` | Seconds since the last push (staleness)  |

`age_s` is how the system detects a dead collector. If it exceeds a threshold
(e.g., 2s for the dashboard, 5x tick interval as a general rule), something is wrong.

---

## Metric Naming Convention

All metric names follow a dot-separated hierarchy:

```
<category>.<measurement>[.<qualifier>]
```

### Registered Metrics

| Metric Name                  | Unit            | Tags                           | Source   |
|------------------------------|-----------------|--------------------------------|----------|
| `cpu.utilization.total`      | PERCENT         | —                              | psutil   |
| `cpu.utilization.per_core`   | PERCENT         | `core=N`                       | psutil   |
| `cpu.frequency.current`      | HERTZ           | —                              | psutil   |
| `memory.total`               | BYTES           | —                              | psutil   |
| `memory.used`                | BYTES           | —                              | psutil   |
| `memory.available`           | BYTES           | —                              | psutil   |
| `memory.utilization`         | PERCENT         | —                              | psutil   |
| `disk.usage.used`            | BYTES           | `device=X`, `mountpoint=Y`     | psutil   |
| `disk.io.read_bytes`         | BYTES_PER_SEC   | `device=X`                     | psutil   |
| `disk.io.write_bytes`        | BYTES_PER_SEC   | `device=X`                     | psutil   |
| `network.io.bytes_sent`      | BYTES_PER_SEC   | `interface=X`                  | psutil   |
| `network.io.bytes_recv`      | BYTES_PER_SEC   | `interface=X`                  | psutil   |
| `process.cpu_percent`        | PERCENT         | `pid=N`, `name=X`, `type=Y`   | psutil   |
| `process.memory.used`        | BYTES           | `pid=N`, `name=X`, `type=Y`   | psutil   |
| `system.info.cpu_model`      | INFO            | `value=<model string>`         | psutil   |
| `system.info.os_version`     | INFO            | `value=<os string>`            | psutil   |
| `system.info.total_memory`   | INFO            | `value=<bytes string>`         | psutil   |
| `system.temperature.cpu`     | CELSIUS         | `sensor=X`, `identifier=Y`    | lhm/smc  |
| `system.temperature.gpu`     | CELSIUS         | `sensor=X`, `identifier=Y`    | lhm/smc  |
| `system.fan.speed`           | RPM             | `sensor=X`                     | lhm/smc  |
| `system.voltage.cpu`         | VOLTS           | `sensor=X`, `identifier=Y`    | lhm      |
| `system.uptime`              | SECONDS         | —                              | stub     |

### Static Specs Convention

Static system specs (CPU model, OS version, RAM capacity) use `unit=INFO` with
`value=0.0` and carry the actual data in `tags["value"]`. This is slightly awkward
for a time-series schema, but the simplicity of one schema everywhere is worth it.
The dashboard filters `unit=INFO` readings and renders them differently.

### Process Type Tags

Process readings use a `type` tag to differentiate between top-CPU and top-memory
process lists:
- `type=cpu_top` — processes sorted by CPU usage (top 5)
- `type=mem_top` — processes sorted by memory usage (top 5)

This allows the dashboard to render two separate ranked tables from the same
metric name.
