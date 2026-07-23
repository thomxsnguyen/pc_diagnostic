# Architecture Overview

PC Diagnostic is a cross-platform terminal-based telemetry dashboard and AI-driven
troubleshooting tool. This document describes the high-level architecture, data flow,
and how the major components connect.

---

## Layered Design

The system follows a strict layered pipeline where data flows in one direction:

```
Providers → Collector → Normalizer → Cache → Consumers (Dashboard, Alerts, Diagnostics)
```

Each layer has a single responsibility and communicates through well-defined contracts
(primarily the `MetricReading` and `Snapshot` data models). This means any layer can be
modified or replaced without touching the others, as long as the contracts are honored.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Background Thread (1s tick)                      │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ PsutilProv.  │  │  LhmProv.    │  │  SmcProv.    │   ← Providers    │
│  │ (all OS)     │  │ (Windows)    │  │ (macOS)      │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                 │                           │
│         └────────┬────────┴────────┬────────┘                          │
│                  ▼                 ▼                                    │
│          ┌──────────────────────────────┐                              │
│          │         Collector            │  ← try/except per provider   │
│          │   (iterates providers,       │                              │
│          │    assembles snapshot)        │                              │
│          └──────────────┬───────────────┘                              │
│                         ▼                                              │
│          ┌──────────────────────────────┐                              │
│          │        Normalizer            │  ← stateless validation gate │
│          │  (validates each reading,    │                              │
│          │   drops non-conforming)      │                              │
│          └──────────────┬───────────────┘                              │
│                         ▼                                              │
│          ┌──────────────────────────────┐                              │
│          │       RollingCache           │  ← deque(maxlen=300) + Lock  │
│          │   push(Snapshot)             │                              │
│          └──────────────┬───────────────┘                              │
│                         │                                              │
│                         ├──── AlertEvaluator (state machine)           │
│                         │         └── AlertDispatcher (OS notifs, log) │
│                         │                                              │
└─────────────────────────┼──────────────────────────────────────────────┘
                          │
                          ▼  (main thread reads from cache)
              ┌───────────────────────┐
              │  TerminalDashboard    │  ← Rich Live TUI
              │  (reads cache.latest, │
              │   cache.series,       │
              │   cache.health)       │
              │                       │
              │  [D] key → triggers   │
              │  DiagnosticsCrew /    │
              │  LocalAnalyzer        │
              └───────────────────────┘
```

---

## Threading Model

| Thread            | Role                                      | Lifecycle           |
|-------------------|-------------------------------------------|---------------------|
| **Main thread**   | Runs the TUI dashboard or log-mode loop   | Lives for app life  |
| **CollectorThread** | Polls providers every ~1s, pushes snapshots | `daemon=True`, dies with main |
| **Diagnosis thread** | One-shot background AI/rule analysis    | Spawned on-demand   |
| **Update checker** | Queries GitHub releases API once at startup | Spawned at init    |

The collector is the only **writer** to the cache. The dashboard and diagnostics are
**readers**. Thread safety is provided by a `threading.Lock` inside `RollingCache`.

### Why threads, not asyncio?

`psutil` calls are synchronous and can block (especially disk I/O on slow drives).
A thread lets us call psutil directly without wrapping everything in
`loop.run_in_executor()`. The collector is inherently a "poll in a loop" pattern —
threading is the natural fit.

---

## Entry Point

`main.py` wires everything together:

1. Parse CLI args (`--log` for stdout fallback, `--refresh-rate` for TUI speed)
2. `register_providers()` — returns available providers for this OS
3. Create `RollingCache(maxlen=300)` — 5 minutes of history at 1s ticks
4. Create `Collector(providers, cache, interval=1.0)` and `start()` it
5. Run either the `TerminalDashboard` (interactive TUI) or a log-mode polling loop

---

## Key Design Principles

1. **One bad provider must never kill the collector.** Every `provider.read()` call
   is wrapped in try/except. A provider that throws results in a snapshot with fewer
   readings, never a crash.

2. **The normalizer drops, never raises.** Non-conforming readings are logged and
   silently discarded. The snapshot always gets pushed to the cache.

3. **Flat schema, dimensional tags.** All readings share one `MetricReading` shape.
   Grouping by category is a read-time concern (the dashboard decides layout).

4. **Explicit registration, no magic.** Providers are listed in `registry.py` with
   `available()` guards. No plugin autodiscovery.

5. **Graceful degradation.** If no real provider is available (e.g., running in CI),
   the `StubProvider` emits fake data so the pipeline still works end-to-end.
