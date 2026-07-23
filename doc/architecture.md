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

### What "honoring the contract" means in practice

The contract between layers is the **type signature** at each boundary. As long as a
component accepts the right input and produces the right output, everything else is
free to change. Here are concrete examples:

**Swap the cache implementation — nothing else notices.**
The current `RollingCache` uses a `deque` in memory. You could replace it with a
SQLite-backed cache, a Redis store, or a shared-memory ring buffer. As long as the
new class still exposes `push(Snapshot)`, `latest() → Snapshot | None`,
`series(str, int) → list[float]`, and `health() → CacheHealth`, the collector keeps
pushing and the dashboard keeps reading — neither knows the storage changed.

```python
# Before (in-memory deque):
cache = RollingCache(maxlen=300)

# After (hypothetical SQLite-backed cache):
cache = SqliteCache(db_path="metrics.db", max_age_s=900)

# The collector and dashboard code stays IDENTICAL because both caches
# honor the same API contract: push(), latest(), series(), health()
collector = Collector(providers, cache, interval=1.0)  # unchanged
dashboard = TerminalDashboard(cache, dispatcher)        # unchanged
```

**Add a new provider — no changes to collector, normalizer, cache, or dashboard.**
You just subclass `Provider`, implement `read() → list[MetricReading]`, and add it
to `registry.py`. The collector already iterates `providers` generically. The
normalizer already validates any `MetricReading`. The dashboard already renders
any metric name it finds in the snapshot.

```python
# New provider — the rest of the system doesn't know or care
class NvidiaGpuProvider(Provider):
    @property
    def name(self) -> str: return "nvidia_smi"

    def available(self) -> bool:
        return shutil.which("nvidia-smi") is not None

    def read(self) -> list[MetricReading]:
        # As long as this returns list[MetricReading], the contract is honored
        return [
            MetricReading(
                metric="gpu.utilization.total",
                value=get_gpu_util(),
                unit=MetricUnit.PERCENT,
                source=self.name,
            )
        ]
```

**Replace the dashboard with a web UI — providers, collector, cache are untouched.**
The dashboard is just a consumer that calls `cache.latest()` and `cache.series()`.
You could write a Flask app, a Textual TUI, or a raw curses interface. As long as
it reads from the cache's public API, the entire backend pipeline is oblivious.

```python
# The cache doesn't care WHO reads from it
# Option A: Rich TUI (current)
dashboard = TerminalDashboard(cache, dispatcher)

# Option B: hypothetical web dashboard
app = FlaskDashboard(cache, dispatcher)
app.run(port=8080)

# Option C: hypothetical Textual app
app = TextualDashboard(cache, dispatcher)
app.run()
```

The key insight: **each layer only depends on the data types at its boundaries**
(`MetricReading`, `Snapshot`, `CacheHealth`), never on the internal implementation
of other layers. That's what makes them independently replaceable.

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
