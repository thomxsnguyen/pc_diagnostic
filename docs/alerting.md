# Alerting System

The alerting system evaluates threshold rules against live telemetry and dispatches
tiered responses. This document covers the alert data model, state machine,
evaluation logic, and dispatch tiers.

All alerting code lives in `src/pc_diagnostic/alerts/`.

---

## Alert Data Model (`models.py`)

### AlertRule (frozen dataclass)

Defines a threshold-based alert condition:

| Field               | Type    | Purpose                                           |
|---------------------|---------|---------------------------------------------------|
| `id`                | `str`   | Unique rule identifier (e.g., `"high_cpu"`)       |
| `metric`            | `str`   | Metric name to watch                              |
| `condition`         | `str`   | `"gt"` (greater than) or `"lt"` (less than)       |
| `threshold`         | `float` | Trigger value                                     |
| `duration_s`        | `float` | Debounce: condition must hold this long to fire    |
| `hysteresis_offset` | `float` | Clear offset (prevents flapping near threshold)   |
| `cooldown_s`        | `float` | Minimum interval between repeated alert dispatches |

### IncidentState (Enum)

```
NORMAL → PENDING → FIRING
                      ↓
                   NORMAL (cleared via hysteresis)
```

### Incident (mutable dataclass)

Tracks the runtime state of a single rule:

| Field               | Type             | Purpose                          |
|---------------------|------------------|----------------------------------|
| `rule`              | `AlertRule`      | The rule this incident tracks    |
| `state`             | `IncidentState`  | Current state machine position   |
| `first_triggered_at`| `float \| None`  | When condition first went true   |
| `last_fired_at`     | `float \| None`  | When last dispatch occurred      |
| `value`             | `float`          | Most recent metric value         |

---

## Default Rules

Three rules ship out of the box in `DEFAULT_ALERT_RULES`:

| Rule ID           | Metric                    | Condition | Threshold | Duration | Hysteresis | Cooldown |
|-------------------|---------------------------|-----------|-----------|----------|------------|----------|
| `high_cpu`        | `cpu.utilization.total`   | `gt`      | 90%       | 5s       | 10%        | 60s      |
| `high_memory`     | `memory.utilization`      | `gt`      | 90%       | 5s       | 5%         | 60s      |
| `stale_collector` | `cache.staleness`         | `gt`      | 2s        | 2s       | 0          | 30s      |

`cache.staleness` is a virtual metric injected by the evaluator (not from any
provider) — it's the `age_s` value from `cache.health()`.

---

## AlertEvaluator (`evaluator.py`)

The evaluator runs once per collector tick. It implements a three-state machine
per rule:

### State Transitions

```
NORMAL:
  condition met + duration_s == 0  →  FIRING (instant fire)
  condition met + duration_s > 0   →  PENDING (start debounce timer)

PENDING:
  condition still met + elapsed >= duration_s  →  FIRING
  condition no longer met                      →  NORMAL (reset timer)

FIRING:
  value within hysteresis band  →  stays FIRING
  value outside hysteresis band →  NORMAL (cleared)
```

### Hysteresis Logic

To prevent flapping (rapidly toggling between FIRING and NORMAL when a value
hovers near the threshold), the clear condition uses an offset:

- For `gt` rules: clears when `value < threshold - hysteresis_offset`
- For `lt` rules: clears when `value > threshold + hysteresis_offset`

Example: CPU alert fires at 90%. With `hysteresis_offset=10`, it won't clear
until CPU drops below 80%.

### Virtual Metrics

The evaluator injects `cache.staleness` as a virtual metric with the value of
`cache_age` (seconds since last cache push). This lets the `stale_collector`
rule detect a dead or hung collector thread without any provider involvement.

---

## AlertDispatcher (`dispatcher.py`)

The dispatcher processes state transitions and applies a tiered response:

### Tier 1: In-Memory Active Incidents

When a rule transitions to FIRING, the incident is added to
`dispatcher.active_incidents` (a `dict[str, Incident]`). The dashboard reads this
dict to render the Active Alerts panel. When cleared, the incident is removed.

### Tier 2: OS Desktop Notifications

On FIRING transitions (subject to cooldown rate-gating), a platform-native
notification is triggered:

- **macOS:** `osascript -e 'display notification ...'`
- **Windows:** PowerShell `System.Windows.Forms.NotifyIcon.ShowBalloonTip`

Both are fire-and-forget subprocess calls with 1s timeouts. Failure is logged
at DEBUG level and silently ignored.

### Tier 3: Alert Log File

All FIRING and CLEARED transitions are appended to `pc_diagnostic_alerts.log`:

```
[2026-07-22 21:00:00] [ALERT] [FIRING] ID=high_cpu Metric=cpu.utilization.total Value=92.30 Threshold=90.00
[2026-07-22 21:05:15] [ALERT] [CLEARED] ID=high_cpu Metric=cpu.utilization.total Value=78.50 Threshold=90.00
```

### Cooldown Rate-Gating

The dispatcher tracks `last_fired_at` per incident. If a FIRING transition occurs
within `cooldown_s` of the last dispatch, the OS notification and log entry are
suppressed. This prevents notification spam when a metric oscillates around the
hysteresis boundary.

---

## Integration with Collector

The collector calls the evaluator and dispatcher at the end of each tick:

```python
# In Collector._run_loop():
transitions = self.evaluator.evaluate(snapshot, health.age_s, start_tick)
self.dispatcher.dispatch(transitions, start_tick)
```

This keeps alerting inline with the collection loop — no separate thread, no async
complexity. The evaluator and dispatcher are fast (pure computation, no I/O except
the optional OS notification subprocess).
