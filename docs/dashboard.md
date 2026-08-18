# Terminal Dashboard

The dashboard is a real-time terminal UI (TUI) built with the
[Rich](https://github.com/Textualize/rich) library. It reads from the `RollingCache`
and renders a multi-panel layout at a configurable refresh rate.

Defined in `src/pc_diagnostic/dashboard.py`.

---

## Layout Structure

The dashboard uses Rich's `Layout` system to create a grid:

```
┌──────────────────────────────────────────────────────────┐
│                        HEADER                            │
│  OS info  │  PC DIAGNOSTIC LIVE TUI MONITOR  │  Cache    │
├────────────────────────┬─────────────────────────────────┤
│                        │                                 │
│   CPU Utilization      │   Resource Process Monitor      │
│   (overall + per-core) │   (top CPU + top Memory)        │
│                        │                                 │
├────────────────────────┼─────────────────────────────────┤
│                        │                                 │
│   Memory               │   Thermals & Fans               │
│   (bar + sparkline)    │   (CPU/GPU temp, fan, voltage)  │
│                        │                                 │
├────────────────────────┼─────────────────────────────────┤
│                        │                                 │
│   I/O Throughput       │   Active Alerts                 │
│   (storage + network)  │   (firing incidents)            │
│                        │                                 │
│                        ├─────────────────────────────────┤
│                        │   Cache & Specs                 │
│                        │   (collector status, version)   │
└────────────────────────┴─────────────────────────────────┘
```

---

## Panel Details

### Header

- **Left:** OS version string (from `system.info.os_version`)
- **Center:** Title — turns red and blinks when cache is stale (>2s since last tick)
- **Right:** Last tick timestamp and cache fill level (e.g., `150/300`)

### CPU Utilization

- Overall CPU progress bar with color coding (green <50%, yellow 50–80%, red >80%)
- CPU model string and current frequency (converted from Hz to MHz)
- 20-point Unicode sparkline showing recent CPU history
- Per-core utilization bars arranged in two columns

### Memory

- RAM utilization progress bar with used/total display
- Available RAM in human-readable format
- 20-point sparkline for memory trend

### I/O Throughput & Storage

Split into two sub-sections:
- **Storage:** Per-disk used bytes and read/write rates (bytes/sec)
- **Network:** Upload (Tx) and download (Rx) rates per interface

### Resource Process Monitor

Two side-by-side ranked tables:
- **Top CPU Processes:** Sorted by CPU%, showing PID, name, CPU%, and RAM
- **Top Memory Processes:** Sorted by RAM usage, same columns

Process type differentiation uses the `type` tag (`cpu_top` vs `mem_top`).

### Thermals & Fans

Shows CPU temperature, GPU temperature, fan speed, and CPU core voltage when
sensor data is available. Falls back to "N/A" per-metric or a message about
LibreHardwareMonitor not being detected.

### Active Alerts

Displays currently FIRING alert incidents with rule ID, status (blinking red
"FIRING"), current value, and threshold limit. Shows "No Active Alerts (System
Healthy)" in green when nothing is firing.

### Cache & Specs

- Collector status: ACTIVE (green) or STALE/LAGGING (red)
- Cache tick age and cache length
- Total RAM capacity
- App version / update availability

---

## Sparklines

The `generate_sparkline()` method produces Unicode block-character sparklines:

```python
blocks = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
```

Each character represents one historical data point from `cache.series()`. Values
are clamped to a 0–max_val range and mapped to block characters proportionally.
Default: 20 data points at max_val=100 for percentage metrics.

---

## Key Controls

The dashboard uses a custom `KeyReader` class for non-blocking keyboard input:

| Key | Action                                    |
|-----|-------------------------------------------|
| `q` | Quit the dashboard                        |
| `d` | Toggle AI diagnosis overlay               |
| Any | Close diagnosis overlay (when showing)     |

`KeyReader` sets the terminal to cbreak mode using `termios`/`tty` (Unix/macOS)
and polls `sys.stdin` via `select.select()` with a short timeout (100ms).

---

## Diagnosis Overlay

When the user presses `d`, the dashboard:

1. Replaces the multi-panel layout with a single full-screen panel
2. Shows a "loading" state while analysis runs
3. Spawns a background thread running `trigger_background_diagnosis()`
4. Builds an evidence packet from the latest snapshot (CPU, RAM, thermals,
   processes, active incidents)
5. Calls `run_diagnosis()` from the diagnostics module
6. Renders the returned markdown report via Rich's `Markdown` renderer
7. Any key press returns to the normal telemetry view

A 10-second cooldown prevents spamming the diagnosis trigger.

---

## Execution Modes

The app supports two modes selected by CLI args or TTY detection:

| Mode          | When                       | Behavior                         |
|---------------|----------------------------|----------------------------------|
| Dashboard     | Default (interactive TTY)  | Full Rich TUI with Live screen   |
| Log mode      | `--log` flag or non-TTY    | Prints snapshots to stdout/file  |

In log mode, the main thread polls `cache.latest()` every 2 seconds and logs the
first 10 readings plus cache health via the standard `logging` module.

### Logging Configuration

- **Dashboard mode:** Logs to `pc_diagnostic.log` file to avoid polluting the TUI
- **Log mode:** Logs to `stdout` for direct visibility

---

## Update Checker

On startup, the dashboard spawns a daemon thread that queries:

```
https://api.github.com/repos/thomxsnguyen/pc_diagnostic/releases/latest
```

If a newer version tag is found, the "Cache & Specs" panel shows an update
notification. The check has a 3-second timeout and fails silently if offline.
