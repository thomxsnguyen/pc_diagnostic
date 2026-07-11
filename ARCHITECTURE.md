# Architecture Documentation - PC Diagnostic

This document outlines the architecture, component contracts, and locked-down data schema for the PC Diagnostic monitoring application.

## 1. Component Layering

The system is structured as four distinct decoupled layers:

1. **System & OS Interfaces (Providers)**: Calls system library interfaces (like `psutil`) or native APIs. Emits collections of raw `MetricReading` structures.
2. **Collection Loop & Validation**: Runs continuously on a daemon background thread. Polls providers, filters out invalid readings at the `Normalizer` boundary, and bundles them into timestamped `Snapshot` structures.
3. **Data Cache Boundary (`RollingCache`)**: A thread-safe ring buffer (`collections.deque`) guarded by locks. Decouples fast background metric acquisition from potentially blocking user interface loops.
4. **Presentation TUI (`TerminalDashboard`)**: Runs on the main execution thread. Queries the cache and renders live system data and sparkline histories.

---

## 2. Metric Naming Convention

All metric keys follow a dot-separated format matching: `^[a-z0-9_]+(?:\.[a-z0-9_]+)+$`.

### Locked-down Metric Names

| Metric Name | Unit | Tags | Description |
|---|---|---|---|
| **CPU Metrics** | | | |
| `cpu.utilization.total` | `PERCENT` | | Overall CPU utilization percentage. |
| `cpu.utilization.per_core` | `PERCENT` | `{"core": "N"}` | Per-core CPU utilization percentage. |
| `cpu.frequency.current` | `HERTZ` | | Current CPU core clock frequency in Hz. |
| **Memory Metrics** | | | |
| `memory.used` | `BYTES` | | Total memory currently in use. |
| `memory.available` | `BYTES` | | Total memory currently available for allocation. |
| `memory.utilization` | `PERCENT` | | Percentage memory utilization. |
| **Disk Metrics** | | | |
| `disk.usage.used` | `BYTES` | `{"device": "X", "mountpoint": "Y"}` | Total storage bytes consumed on partition. |
| `disk.io.read_bytes` | `BYTES_PER_SEC` | `{"device": "X"}` | Bytes read from storage drive per second. |
| `disk.io.write_bytes` | `BYTES_PER_SEC` | `{"device": "X"}` | Bytes written to storage drive per second. |
| **Network Metrics** | | | |
| `network.io.bytes_sent` | `BYTES_PER_SEC` | `{"interface": "X"}` | Bytes transmitted on network interface per second. |
| `network.io.bytes_recv` | `BYTES_PER_SEC` | `{"interface": "X"}` | Bytes received on network interface per second. |
| **Process Metrics** | | | |
| `process.cpu_percent` | `PERCENT` | `{"pid": "N", "name": "X", "type": "cpu_top"}` | Per-process CPU utilization percentage. |
| `process.memory.used` | `BYTES` | `{"pid": "N", "name": "X", "type": "mem_top"}` | Per-process Memory RSS bytes. |
| **Static Metadata Specs** | | | |
| `system.info.cpu_model` | `INFO` | `{"value": "Model Str"}` | Host CPU hardware processor identifier. |
| `system.info.os_version` | `INFO` | `{"value": "OS Str"}` | Host platform release operating system. |
| `system.info.total_memory` | `INFO` | `{"value": "RAM Bytes"}`| Host installed total physical memory memory. |

---

## 3. Resilience and Graceful Degradation

- **Provider Failure**: Exceptions raised during a provider `.read()` loop are caught and logged inside the `Collector`. The collector continues execution for other active providers.
- **Absent Metrics**: The presentation TUI fallback logic retrieves metrics with default safe values (e.g. `0.0`, `""`) and checks mapping presence before rendering. Missing metrics default to dark-grey `[N/A]` markers instead of triggering rendering thread crashes.
- **Cache Staleness**: If the collector background thread stalls or crashes, `CacheHealth.age_s` will rise. The presentation layer displays a prominent warning when cache updates lag by more than 2.0 seconds.
