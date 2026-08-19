# UI Implementation Plan — PC Diagnostic Desktop Application

This document outlines the engineering implementation plan for transforming **PC Diagnostic** from a terminal-based interface into a cross-platform desktop hardware monitor and AI diagnostic application, based on the specifications in [docs/ui_architecture.md](../ui_architecture.md).

---

## 1. Overview & Objectives

### 1.1 Goal
Develop and integrate a native desktop GUI software for PC Diagnostic with visual parity to industry-standard PC monitors (NZXT CAM, HWiNFO64, macOS Activity Monitor / Stats) while preserving 100% of the existing telemetry pipeline, provider abstraction, and AI diagnostic capabilities.

### 1.2 Non-Breaking Requirements
- **Preserve CLI/TUI Functionality:** The terminal interface (`TerminalDashboard`) remains accessible via `--cli` or `--tui` flags.
- **Contract Integrity:** The `Provider → Collector → Normalizer → RollingCache` data pipeline remains unchanged. The GUI consumes data strictly via `cache.latest()`, `cache.series()`, and `cache.health()`.
- **Zero UI Freezing:** Metric polling, AI LLM reasoning, and disk/network I/O must never block the 60 FPS UI rendering thread.

---

## 2. Technology Stack & Dependencies

### 2.1 Selected GUI Stack: **PySide6 (Qt 6 for Python) + PyQtGraph**
- **Core GUI Framework:** `PySide6>=6.6.0` (Official Qt 6 Python bindings, LGPL-compliant).
- **High-Performance Charting:** `pyqtgraph>=0.13.3` (Hardware-accelerated 60 FPS real-time vector charting).
- **Markdown & Code Rendering:** `markdown2>=2.4.0` / Qt WebEngine or Rich Text `QTextDocument` for AI diagnostic reports.
- **Icons & Styling:** Custom SVG vector icon suite + Dark/OLED/Light QSS stylesheets.

### 2.2 `pyproject.toml` Dependency Updates
```toml
[project]
dependencies = [
    "psutil>=5.9.0",
    "rich>=13.0.0",
    "crewai>=0.1.0",
    "PySide6>=6.6.0",
    "pyqtgraph>=0.13.3",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-qt>=4.3.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
    "pyinstaller>=6.0.0",
]
```

---

## 3. Architecture & Package Organization

New code will be structured under `src/pc_diagnostic/gui/`, while relocating the legacy terminal dashboard under `src/pc_diagnostic/tui/`:

```
src/pc_diagnostic/
├── main.py                           # Multi-mode entry point (GUI / TUI / Log)
├── models.py                         # Telemetry data models (unchanged)
├── normalizer.py                     # Metric validation (unchanged)
├── cache.py                          # Thread-safe rolling cache (unchanged)
├── collector.py                      # Telemetry collector thread (unchanged)
├── providers/                        # Hardware sensor providers (unchanged)
├── alerts/                           # Alert evaluator & dispatcher (unchanged)
├── diagnostics/                      # CrewAI & LocalAnalyzer (unchanged)
├── tui/                              # [RELOCATED] Terminal Interface
│   ├── __init__.py
│   └── dashboard.py                  # Rich terminal dashboard
└── gui/                              # [NEW] Desktop GUI Package
    ├── __init__.py
    ├── app.py                        # QApplication setup, lifecycle & window management
    ├── bridge.py                     # Thread-safe TelemetryBridge (QObject Signals)
    ├── theme.py                      # Theme tokens, dark/light palettes, QSS stylesheets
    ├── assets/                       # SVG icons and visual assets
    ├── components/                   # Reusable UI widgets
    │   ├── __init__.py
    │   ├── gauge_widget.py           # Radial circular telemetry meters
    │   ├── timeseries_chart.py       # PyQtGraph 60s/300s real-time line charts
    │   ├── sparkline_widget.py       # Micro-sparkline trend indicators
    │   ├── per_core_grid.py          # Per-core CPU load and frequency bars
    │   ├── thermal_matrix.py         # Hardware temperature & fan table
    │   ├── process_table.py          # Sortable process table with search/kill
    │   └── alert_banner.py           # Active alerts bar and notification badge
    ├── views/                        # Tabbed application views
    │   ├── __init__.py
    │   ├── overview_view.py          # Main dashboard overview
    │   ├── sensors_view.py           # In-depth sensor & hardware tree
    │   ├── processes_view.py         # Full-page process inspector
    │   ├── alerts_view.py            # Alert rules, incidents & threshold editor
    │   └── diagnostics_view.py       # AI Diagnostic Studio & markdown viewer
    └── tray.py                       # System Tray & macOS Menu Bar companion
```

---

## 4. Detailed Implementation Phases

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        IMPLEMENTATION TIMELINE                             │
│                                                                            │
│  [Phase 1] Bridge & Core Window Shell                                      │
│      ├── TelemetryBridge (QObject Signals & Tick Timer)                    │
│      ├── MainWindow & Sidebar Navigation                                   │
│      └── Dark/OLED/Light Theme Engine                                      │
│                                                                            │
│  [Phase 2] System Overview & Real-Time Visualization                       │
│      ├── Radial Gauge Widgets (CPU / RAM / GPU)                            │
│      ├── Real-Time PyQtGraph Time-Series Charts                            │
│      └── Storage & Network I/O Cards                                       │
│                                                                            │
│  [Phase 3] Hardware Sensors & Thermal Matrix                               │
│      ├── Per-Core CPU Frequency & Utilization Grid                         │
│      ├── macOS SMC & Windows LHM Sensor Tree View                          │
│      └── Fan Speed Tachometers & Voltage Rails                             │
│                                                                            │
│  [Phase 4] Process Inspector & Alerting Center                             │
│      ├── Interactive Sortable Process Table (CPU/RAM/I/O)                  │
│      ├── Process Filter, Search & Kill Controls                            │
│      └── Live Alert Incident Banner & Threshold Configuration              │
│                                                                            │
│  [Phase 5] AI Diagnostics Studio                                           │
│      ├── Asynchronous Worker Thread for CrewAI                             │
│      ├── Evidence Snapshot Tree Visualizer                                 │
│      └── Markdown Report Viewer with PDF/HTML Export                       │
│                                                                            │
│  [Phase 6] System Tray & Desktop Packaging                                │
│      ├── macOS Menu Bar / Windows System Tray Companion                    │
│      ├── Mini-HUD / Compact Overlay Mode                                   │
│      └── PyInstaller & DMG/EXE Packaging Scripts                           │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Bridge & Core Application Shell

**Objective:** Build the thread-safe communication layer between `RollingCache` and Qt's event loop, set up the main window, sidebar navigation, and design system.

#### Tasks:
1. **Implement `TelemetryBridge` (`src/pc_diagnostic/gui/bridge.py`):**
   - Subclass `QObject` with Qt Signals:
     - `snapshot_updated = Signal(object)` (emits latest `Snapshot`)
     - `alert_triggered = Signal(object)` (emits new `Incident`)
     - `diagnosis_completed = Signal(str)` (emits AI markdown report)
     - `cache_health_changed = Signal(object)` (emits `CacheHealth`)
   - Run a 30–60 FPS UI refresh timer pulling from `cache.latest()` and `cache.series()`.
2. **Implement Theme & Styling Engine (`src/pc_diagnostic/gui/theme.py`):**
   - Palette definitions:
     - **OLED Stealth:** Black and charcoal-gray surfaces with restrained blue accents.
     - **Clean Light:** `#F6F8FA` background, `#FFFFFF` cards, `#0969DA` accent.
   - Global QSS stylesheet with glassmorphism, border radii, smooth hover transitions, and custom scrollbars.
3. **Build Main Application Window (`src/pc_diagnostic/gui/app.py`):**
   - Responsive sidebar navigation:
     - 📊 *Overview* (`OverviewView`)
     - 🌡️ *Sensors* (`SensorsView`)
     - 📋 *Processes* (`ProcessesView`)
     - 🚨 *Alerts* (`AlertsView`)
     - 🤖 *AI Studio* (`DiagnosticsView`)
     - ⚙️ *Settings* (`SettingsView`)
   - Top status bar displaying live polling rate, collector status (Active/Stale), active alert count, and GitHub update notice.
4. **Update `src/pc_diagnostic/main.py`:**
   - Add CLI argument `--ui` / `--gui` (default when running interactively on desktop).
   - Fall back to `--tui` / `--log` if `--no-gui` or headless environment detected.

---

### Phase 2: System Overview & Real-Time Visualization

**Objective:** Implement the primary telemetry dashboard with 60 FPS hardware-accelerated gauges, time-series charts, and resource summaries.

#### Tasks:
1. **Build `RadialGaugeWidget` (`src/pc_diagnostic/gui/components/gauge_widget.py`):**
   - Custom `QWidget` using `QPainter` with antialiasing.
   - Smooth arc rendering with dynamic gradient coloring based on threshold values (0–50% green, 50–80% yellow, 80–100% red).
   - Animated needle/sweep transition using `QPropertyAnimation`.
2. **Build `TimeSeriesChart` (`src/pc_diagnostic/gui/components/timeseries_chart.py`):**
   - Wrap `pyqtgraph.PlotWidget` for ultra-low CPU overhead.
   - Display sliding 60s / 300s window for:
     - CPU Total Load (%)
     - Memory Utilization (%)
     - Storage Read/Write (MB/s)
     - Network Download/Upload (KB/s or MB/s)
   - Interactive crosshair cursor with value tooltip on hover.
3. **Build Storage & Network Cards (`src/pc_diagnostic/gui/components/`):**
   - Storage volume progress bars (Used / Total GB) and real-time read/write throughput rates.
   - Network interface cards with active IP, Tx/Rx counters, and throughput graphs.
4. **Assemble `OverviewView` (`src/pc_diagnostic/gui/views/overview_view.py`):**
   - Grid layout organizing gauges, 60s time-series chart, storage/network metrics, and top 5 processes preview.

---

### Phase 3: Hardware Sensors & Thermal Deep-Dive

**Objective:** Provide detailed hardware inspection on par with HWiNFO64 and macOS Stats.

#### Tasks:
1. **Build `PerCoreGridWidget` (`src/pc_diagnostic/gui/components/per_core_grid.py`):**
   - Auto-wrapping grid of mini progress bars representing each logical CPU core (e.g., Core 0 to Core 15).
   - Display individual core frequency in MHz alongside load percentage.
2. **Build `ThermalMatrixWidget` (`src/pc_diagnostic/gui/components/thermal_matrix.py`):**
   - Dynamic table grouping temperature sensors:
     - CPU Package / Die / Individual Cores
     - GPU Core / Memory / Hotspot
     - Storage SSD thermals
     - Motherboard & ambient sensors
   - Min / Current / Max temperature tracking with color-coded heat badges.
3. **Build Fan Speed & Voltage Monitors:**
   - Tachometer gauges for fan RPM readings and percentage of maximum speed.
   - Voltage rail monitor (VCore, 12V, 5V, 3.3V) when provided by `LhmProvider` or `SmcProvider`.
4. **Assemble `SensorsView` (`src/pc_diagnostic/gui/views/sensors_view.py`):**
   - Split view with per-core CPU layout on the left and full sensor tree on the right.

---

### Phase 4: Process Inspector & Active Alerting Center

**Objective:** Enable interactive process monitoring and real-time threshold alert management.

#### Tasks:
1. **Build `ProcessTableView` (`src/pc_diagnostic/gui/components/process_table.py`):**
   - `QTableView` backed by `QAbstractTableModel` for high performance with 500+ processes.
   - Columns: PID, Process Name, CPU %, Memory (RSS MB), Disk Read (KB/s), Disk Write (KB/s), User, Status.
   - Instant sorting by clicking any column header.
   - Real-time search filter input box (filters by PID or name with debounced typing).
2. **Process Management Actions:**
   - Context menu (right-click):
     - `End Process` (`SIGTERM` / `TerminateProcess`)
     - `Force Kill` (`SIGKILL`)
     - `Filter Historical Charts by PID`
3. **Build `AlertsView` & Incident Banner (`src/pc_diagnostic/gui/views/alerts_view.py`):**
   - Floating banner on top of the GUI when alerts are `FIRING`.
   - Table of active and past incidents with trigger timestamp, peak value, and duration.
   - Interactive rule configuration sliders:
     - High CPU threshold (default 90%)
     - High Memory threshold (default 90%)
     - Debounce duration slider (1s – 30s)
     - Hysteresis margin slider (1% – 10%)

---

### Phase 5: AI Diagnostics Studio

**Objective:** Deliver an integrated AI troubleshooting environment powered by CrewAI and local rule engines.

#### Tasks:
1. **Implement `DiagnosticWorkerThread` (`src/pc_diagnostic/gui/views/diagnostics_view.py`):**
   - Subclass `QThread` to execute `run_diagnosis()` asynchronously.
   - Emit progress signals: `status_updated(str)`, `progress_percent(int)`, `diagnosis_finished(str)`.
   - Prevent UI lockup while LLM calls or rule analyses run.
2. **Build Evidence Snapshot Tree:**
   - Tree view displaying the exact evidence packet captured at the moment of diagnosis:
     - CPU spikes & runaway threads
     - Memory allocation breakdown
     - Thermal throttling indicators
     - Active threshold incidents
3. **Build Markdown Report Viewer:**
   - Formatted markdown display supporting bolding, tables, code blocks, alerts, and bullet points.
   - Visual health score badge (0–100%) and categorised recommendations (Hardware vs. Software fixes).
4. **Export & Sharing Tools:**
   - `Save Report as Markdown (.md)`
   - `Export as HTML Report`
   - `Copy to Clipboard`

---

### Phase 6: System Tray Companion & Desktop Packaging

**Objective:** Background tray monitoring, mini-HUD mode, and standalone OS installers.

#### Tasks:
1. **Implement `TrayManager` (`src/pc_diagnostic/gui/tray.py`):**
   - Native system tray / macOS menu bar icon using `QSystemTrayIcon`.
   - Live dynamic icon drawing showing real-time CPU % or temperature badge.
   - Tray context menu:
     - *Open Dashboard*
     - *Toggle Mini HUD*
     - *Run AI Diagnosis*
     - *Quit*
   - Desktop OS toast notifications for FIRING alerts.
2. **Implement Mini-HUD / Compact Overlay Mode:**
   - Frameless, semi-transparent, draggable mini-window with `Qt.WindowStaysOnTopHint`.
   - Compact display of CPU%, RAM%, GPU%, and Top Process during gaming or full-screen work.
3. **Packaging & Installer Updates:**
   - Update `build_binaries.py` to bundle PySide6 plugins and PyQtGraph assets into the standalone binary.
   - Update `package_mac.py` to package `PC Diagnostic.app` with proper AppIcon, Info.plist, and create `PC-Diagnostic-Installer.dmg`.
   - Create `package_win.py` with Inno Setup script generating Windows installer.

---

## 5. Verification & Testing Plan

### 5.1 Automated Unit & GUI Testing
| Test Suite | File | Verification Target |
| :--- | :--- | :--- |
| **Bridge Tests** | `tests/test_gui_bridge.py` | Verify `TelemetryBridge` emits signals accurately on snapshot ticks without race conditions. |
| **Widget Tests** | `tests/test_gui_widgets.py` | Headless `pytest-qt` tests verifying `RadialGaugeWidget` and `TimeSeriesChart` handle empty/extreme data. |
| **Process Model Tests** | `tests/test_process_model.py` | Verify sorting, filtering, and PID termination signals in `ProcessTableModel`. |
| **Worker Thread Tests** | `tests/test_diagnostics_worker.py` | Verify `DiagnosticWorkerThread` cleanly emits progress and completes without hanging on error. |

### 5.2 Performance Benchmarks & Targets
- **UI Render Rate:** Steady 60 FPS during normal operation.
- **CPU Footprint:** `<3.5%` CPU utilization during active 60 FPS dashboard rendering.
- **Memory Footprint:** `<85 MB` resident memory (RSS).
- **Graceful Degradation:** If sensor providers (SMC/LHM) fail or are unavailable, UI displays "N/A" without throwing unhandled exceptions.

---

## 6. Implementation Summary & Next Steps

1. **Step 1:** Add `PySide6` and `pyqtgraph` to `pyproject.toml`.
2. **Step 2:** Relocate existing terminal dashboard to `src/pc_diagnostic/tui/`.
3. **Step 3:** Implement `src/pc_diagnostic/gui/bridge.py` and `src/pc_diagnostic/gui/theme.py`.
4. **Step 4:** Build the core `MainWindow` in `src/pc_diagnostic/gui/app.py`.
5. **Step 5:** Incrementally develop `OverviewView`, `SensorsView`, `ProcessesView`, `AlertsView`, and `DiagnosticsView`.
6. **Step 6:** Package and verify standalone macOS `.dmg` and Windows `.exe` installers.
