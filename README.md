# PC Diagnostic

A cross-platform PC telemetry monitor and AI-driven troubleshooting tool that tracks CPU, memory, storage, network, thermals, and fan speeds in real time. It features a thread-safe rolling cache, threshold-based alerts with debounce and hysteresis, and an on-demand CrewAI diagnostic engine that analyzes live telemetry snapshots to deliver actionable remediation recommendations.

---

## Key Features

- **Real-Time Telemetry Dashboard:** Multi-panel Rich terminal UI displaying overall and per-core CPU load, memory utilization, disk I/O, network bandwidth, and ranked process tables.
- **Hardware-Level Sensor Integration:** Native macOS Apple Silicon / Intel SMC thermals & fan speeds (via C helper), and Windows hardware sensors (via LibreHardwareMonitor WMI).
- **Threshold Alerting Engine:** Multi-state (`NORMAL` → `PENDING` → `FIRING`) alert evaluator with configurable debounce duration, hysteresis margins, OS notifications, and incident logging.
- **On-Demand AI Diagnostics:** Trigger full-system diagnostics at the press of a key (`d`), utilizing a multi-agent CrewAI analyzer (with automatic local rule-based fallback when offline or without API keys).
- **Robust Pipeline Architecture:** Strict layered flow (`Providers → Collector → Normalizer → RollingCache → Consumers`) ensuring high fault tolerance and pluggability.

---

## Quickstart

### 1. Prerequisites
- **Python:** `>= 3.11`
- **macOS:** Xcode Command Line Tools (`xcode-select --install`) for native SMC thermal helper compilation.
- **Windows:** [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) (optional, for advanced thermal and fan sensors).

### 2. Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/thomxsnguyen/pc_diagnostic.git
cd pc_diagnostic

# Using standard venv
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

Or using [`uv`](https://github.com/astral-sh/uv):
```bash
uv sync
```

### 3. Configure AI Diagnostics (Optional)

PC Diagnostic automatically uses a local rule-based engine if no API keys are present. To enable LLM-powered multi-agent diagnostics, create a `.env` file in the project root:

```bash
# Set at least one of the following:
OPENAI_API_KEY="your-openai-api-key"
# or
GEMINI_API_KEY="your-gemini-api-key"
# or
ANTHROPIC_API_KEY="your-anthropic-api-key"
```

---

## Usage

### Interactive Terminal Dashboard (Default)

Launch the full-screen terminal dashboard:

```bash
python -m pc_diagnostic.main
# or with custom refresh rate (e.g. 0.5s):
python -m pc_diagnostic.main --refresh-rate 0.5
```

#### Keyboard Controls
| Key | Action |
| :--- | :--- |
| `q` | Quit the dashboard |
| `d` | Run on-demand AI system diagnosis overlay |
| Any key | Close diagnosis report overlay |

### Log / Headless Mode

For automated environments, CI pipelines, or non-TTY terminals:

```bash
python -m pc_diagnostic.main --log
```

---

## CLI Options

```text
usage: main.py [-h] [--log] [--refresh-rate REFRESH_RATE]

A cross-platform PC monitoring and AI-diagnostic tool

options:
  -h, --help            show this help message and exit
  --log, --no-dashboard
                        Run in log-only stdout fallback mode (no TUI dashboard)
  --refresh-rate REFRESH_RATE
                        TUI dashboard refresh rate in seconds (default: 1.0)
```

---

## Development & Testing

Run the test suite using pytest:

```bash
pytest
```

Run linting and type checks:

```bash
ruff check .
mypy src/
```

### Standalone Packaging

Build standalone binary and installers:

```bash
# Build standalone binary via PyInstaller
python build_binaries.py

# Package macOS App Bundle and Drag-and-Drop DMG
python package_mac.py
```

---

## Documentation Index

Comprehensive technical documentation is maintained in the [`docs/`](docs/) directory:

- [System Architecture](docs/architecture.md) — Layered design, contracts, data flow, and threading model.
- [Data Model Specification](docs/data_model.md) — `MetricReading`, `Snapshot`, `CacheHealth`, and metric tagging conventions.
- [Collector & Rolling Cache](docs/collector_and_cache.md) — Collector lifecycle, thread safety, and ring-buffer mechanics.
- [Hardware Providers](docs/providers.md) — Cross-platform psutil, Windows LHM, and macOS SMC provider guides.
- [Terminal Dashboard](docs/dashboard.md) — Rich TUI layout panels, sparklines, and key bindings.
- [Alerting Subsystem](docs/alerting.md) — Alert rules, incident state machine, debounce, hysteresis, and dispatching.
- [AI Diagnostics Engine](docs/diagnostics.md) — CrewAI integration, local fallback analyzer, and evidence schema.
- [Build & Packaging](docs/build_and_packaging.md) — PyInstaller pipelines, C helper auto-compilation, and macOS signing.
- [Desktop UI Architecture](docs/ui_architecture.md) — Architectural design for transitioning to a Desktop GUI application.
- [UI Implementation Plan](docs/implementation/ui_implementation_plan.md) — Phased engineering plan for the GUI software.

---

## License

This project is licensed under the MIT License.