# PC Diagnostic — Project Plan

> Reconstructed from `phase0_technical_design.txt` and codebase analysis.
> The original PDF (`pc_diagnostic_project_plan.md.pdf`) could not be
> programmatically extracted — this document captures its content based on
> the design documents and implemented code.

---

## Project Vision

A cross-platform terminal-based telemetry dashboard and AI-driven troubleshooting
tool that monitors CPU, memory, storage, fans, and thermals in real time. It features
a rolling cache, active threshold alerts, and an on-demand CrewAI diagnostic crew
that summarizes live performance snapshots to deliver actionable software and hardware
recommendations.

---

## Phased Development Plan

### Phase 0 — Foundations ✅

**Goal:** Establish the contracts that every future phase plugs into.

**Deliverables:**
- [x] `MetricReading` / `Snapshot` / `CacheHealth` data models
- [x] `Provider` ABC with `name`, `available()`, `read()`
- [x] `StubProvider` emitting fake readings
- [x] `Normalizer` validation gate (drop-not-raise)
- [x] `RollingCache` with `deque(maxlen=300)` + `threading.Lock`
- [x] `Collector` background thread with per-provider try/except
- [x] `main.py` wiring it all together
- [x] End-to-end data flow: StubProvider → Collector → Normalizer → Cache

**Exit criterion:** "An empty pipeline skeleton with one stub provider runs end to
end" — data flows correctly from provider → collector → normalizer → cache, and
`cache.latest()` returns the most recent snapshot.

---

### Phase 1–2 — Dashboard & Real Telemetry ✅

**Goal:** Replace stub data with real system metrics and build the TUI.

**Deliverables:**
- [x] `PsutilProvider` — CPU, memory, disk, network, processes, static specs
- [x] `TerminalDashboard` — Rich-based TUI with multi-panel layout
- [x] Sparkline history visualization
- [x] Per-core CPU bars, memory bar, I/O throughput display
- [x] Top processes tables (by CPU and by memory)
- [x] Log-mode fallback for non-TTY environments
- [x] CLI argument parsing (`--log`, `--refresh-rate`)

---

### Phase 3 — Windows Native Sensors ✅

**Goal:** Access hardware sensors not available through psutil on Windows.

**Deliverables:**
- [x] `LhmProvider` — LibreHardwareMonitor WMI integration
- [x] Temperature sensors (CPU, GPU, other)
- [x] Fan speed sensors
- [x] Voltage sensors (CPU, other)
- [x] PowerShell subprocess with timeout
- [x] Graceful degradation when LHM is not running

---

### Phase 4 — macOS Native Sensors ✅

**Goal:** Access Apple's SMC and HID thermal sensors on macOS.

**Deliverables:**
- [x] `SmcProvider` — native C helper for SMC/HID access
- [x] `smc_helper.c` — IOHIDEventSystem (Apple Silicon) + AppleSMC (Intel/fans)
- [x] Auto-compilation at startup (`clang` with IOKit/CoreFoundation frameworks)
- [x] Sensor name mapping (PMU tdie/tdev → canonical metric names)
- [x] Temperature and fan speed readings

---

### Phase 5 — Alerting System ✅

**Goal:** Threshold-based alerting with debounce, hysteresis, and tiered dispatch.

**Deliverables:**
- [x] `AlertRule` / `Incident` / `IncidentState` data models
- [x] `AlertEvaluator` — three-state machine (NORMAL → PENDING → FIRING)
- [x] Debounce (`duration_s`), hysteresis (`hysteresis_offset`), cooldown
- [x] `AlertDispatcher` — in-memory tracking, OS notifications, alert log
- [x] Default rules: high CPU, high memory, stale collector
- [x] Virtual `cache.staleness` metric
- [x] Active Alerts panel in dashboard

---

### Phase 6 — AI Diagnostics ✅

**Goal:** On-demand system analysis with AI-powered or rule-based reporting.

**Deliverables:**
- [x] `CrewAI` integration with configurable LLM backend
- [x] `LocalDiagnosticAnalyzer` rule-based fallback
- [x] Evidence packet construction from cache snapshot
- [x] Background thread execution with loading state
- [x] Markdown report rendering in dashboard overlay
- [x] 10-second cooldown between diagnosis triggers

---

### Phase 7 — Packaging & Distribution ✅

**Goal:** Ship as a standalone executable.

**Deliverables:**
- [x] PyInstaller spec and build script
- [x] Native helper compilation in build pipeline
- [x] macOS code signing (ad-hoc + Developer ID)
- [x] Build verification
- [x] GitHub Releases version check in dashboard

---

## Original Design Rationale

### Why dataclasses over Pydantic?

Pydantic is the right tool for untrusted external input (APIs, config files). Here,
data originates from our own providers — the normalizer is the trust boundary and is
simple enough to write by hand. If serialization needs grow (e.g., evidence packets),
migration to Pydantic is straightforward since the schema shape won't change.

### Why one provider per source?

A single `PsutilProvider` makes one conceptual call to the system and returns
everything. Splitting by category (PsutilCpuProvider, PsutilMemoryProvider, etc.)
would mean multiple providers all calling psutil independently — redundant syscalls.

### Why threads over multiprocessing?

The collector is I/O-bound (system calls to read sensors), not CPU-bound. Python's
GIL is not a bottleneck for I/O-bound work. Multiprocessing would require
serializing snapshots across process boundaries — unnecessary complexity.

### Why flat readings instead of nested?

The cache doesn't need to understand metric semantics — it just stores snapshots.
Grouping/filtering by category is a read-time concern. Flat is simpler to serialize,
validate, and iterate.

---

## Project Structure

```
pc_diagnostic/
├── pyproject.toml
├── .python-version
├── .gitignore
├── README.md
├── build_binaries.py          # PyInstaller build pipeline
├── package_mac.py             # macOS DMG packaging
├── pc_diagnostic.spec         # PyInstaller spec file
├── doc/                       # Design documentation (this folder)
├── src/
│   └── pc_diagnostic/
│       ├── __init__.py
│       ├── models.py          # MetricReading, Snapshot, MetricUnit, CacheHealth
│       ├── normalizer.py      # Stateless validation gate
│       ├── cache.py           # RollingCache (deque + Lock)
│       ├── collector.py       # Background collection thread
│       ├── dashboard.py       # Rich TUI terminal dashboard
│       ├── main.py            # Entry point, CLI parsing, wiring
│       ├── providers/
│       │   ├── base.py        # Provider ABC
│       │   ├── registry.py    # register_providers()
│       │   ├── stub.py        # StubProvider (fake data)
│       │   ├── psutil_provider.py  # Cross-platform telemetry
│       │   ├── lhm_provider.py     # Windows LHM/WMI sensors
│       │   ├── smc_provider.py     # macOS SMC/HID sensors
│       │   ├── smc_helper.c        # Native C helper source
│       │   └── smc_helper          # Compiled binary (generated)
│       ├── alerts/
│       │   ├── models.py      # AlertRule, Incident, IncidentState
│       │   ├── evaluator.py   # AlertEvaluator (state machine)
│       │   └── dispatcher.py  # AlertDispatcher (notifications, log)
│       └── diagnostics/
│           └── crew.py        # CrewAI + LocalDiagnosticAnalyzer
└── tests/
    ├── test_models.py
    ├── test_normalizer.py
    ├── test_cache.py
    ├── test_collector.py
    ├── test_stub_provider.py
    ├── test_psutil_provider.py
    ├── test_lhm_provider.py
    ├── test_smc_provider.py
    ├── test_dashboard.py
    ├── test_alerts.py
    └── test_diagnostics.py
```
