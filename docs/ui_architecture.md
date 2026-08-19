# PC Diagnostic — UI Transformation & GUI Architecture

This document describes the architectural evolution of **PC Diagnostic** from a terminal-based TUI (Terminal User Interface) to a fully functional, cross-platform Desktop GUI Software application.

The design is modeled after industry-standard PC diagnostic suites and hardware monitors (such as *NZXT CAM*, *HWiNFO64*, *macOS Activity Monitor / Stats*, and *MSI Afterburner*), while retaining the clean, modular backend telemetry pipeline already established in the codebase.

---

## 1. Executive Summary & Transformation Vision

### 1.1 From CLI/TUI to Native Desktop Application
PC Diagnostic currently operates in the terminal using Rich's Live TUI and ANSI character sparklines. While lightweight and portable, a modern desktop telemetry monitor provides:
- **60 FPS Hardware-Accelerated Telemetry Rendering:** Smooth vector gauges, real-time cubic bezier time-series graphs, and interactive sensor heatmaps.
- **Interactive Process & Resource Management:** Sortable, filterable multi-column tables with search, process inspection, and thread/PID tree hierarchies.
- **AI Diagnostics Studio:** Rich markdown rendering with collapsible evidence trees, interactive remedy suggestions, and diagnostic history comparison.
- **System Tray & Menu Bar Resident Companion:** Continuous background monitoring, menu bar metric previews, and configurable threshold toast notifications without keeping a terminal open.
- **Modern Dark/Light Theme Engine:** OLED Stealth and Clean Light aesthetic design.

### 1.2 Preservation of the Core Architectural Invariant
The fundamental design principle of PC Diagnostic remains strictly preserved:
```
Providers → Collector → Normalizer → RollingCache → Consumers (GUI, Alerts, AI Diagnostics)
```
The backend telemetry engine (`Provider` ABC, `PsutilProvider`, `LhmProvider`, `SmcProvider`, `Normalizer`, `RollingCache`, and `AlertEvaluator`) is completely independent of the UI layer. The GUI is simply a new **Presentation Layer Consumer** that subscribes to cache snapshots and telemetry events.

---

## 2. High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                TELEMETRY ENGINE (Background Threads)                   │
│                                                                                        │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐                       │
│  │ PsutilProvider  │   │   LhmProvider   │   │   SmcProvider   │  ← Hardware Providers │
│  │   (Cross-OS)    │   │    (Windows)    │   │     (macOS)     │                       │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘                       │
│           │                     │                     │                                │
│           └───────────┬─────────┴───────────┬─────────┘                                │
│                       ▼                     ▼                                          │
│           ┌───────────────────────────────────────────┐                                │
│           │                 Collector                 │  ← 1.0s Polling Loop           │
│           └─────────────────────┬─────────────────────┘                                │
│                                 ▼                                                      │
│           ┌───────────────────────────────────────────┐                                │
│           │                Normalizer                 │  ← Validation & Drop Gate      │
│           └─────────────────────┬─────────────────────┘                                │
│                                 ▼                                                      │
│           ┌───────────────────────────────────────────┐                                │
│           │               RollingCache                │  ← Ring buffer (deque)         │
│           └──────────┬─────────────────────┬──────────┘    with Lock                   │
│                      │                     │                                           │
│                      ▼                     ▼                                           │
│           ┌────────────────────┐ ┌────────────────────┐                                │
│           │   AlertEvaluator   │ │ AlertDispatcher    │  ← State Machine Alerts        │
│           └────────────────────┘ └────────────────────┘                                │
└──────────────────────┼─────────────────────────────────────────────────────────────────┘
                       │
                       │ Thread-Safe Event Bridge (Signals / Callbacks / IPC)
                       ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              DESKTOP GUI PRESENTATION LAYER                            │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              GUI State Manager & Bridge                          │  │
│  │            (TelemetryDispatcher, Reactive Store, Series Buffer, Theme Mgr)       │  │
│  └──────┬──────────────────────┬──────────────────────┬──────────────────────┬──────┘  │
│         │                      │                      │                      │         │
│         ▼                      ▼                      ▼                      ▼         │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐       ┌──────────────┐ │
│  │  Dashboard   │       │   Hardware   │       │   Process    │       │ AI Diagnosis │ │
│  │   Overview   │       │   Sensors    │       │   Manager    │       │    Studio    │ │
│  │  • Gauges    │       │  • Per-Core  │       │  • Top CPU   │       │  • Evidence  │ │
│  │  • Thermals  │       │  • Voltages  │       │  • Top Mem   │       │  • AI Advice │ │
│  │  • Sparkline │       │  • Fan curve │       │  • Kill/Tree │       │  • History   │ │
│  └──────────────┘       └──────────────┘       └──────────────┘       └──────────────┘ │
│         │                      │                      │                      │         │
│         └──────────────────────┴───────────┬──────────┴──────────────────────┘         │
│                                            │                                           │
│                       ┌────────────────────┴───────────────────┐                       │
│                       │   System Tray & Menu Bar Companion    │                       │
│                       │   • Live Dock/Tray Mini-Status         │                       │
│                       │   • Background Incident Toast Popups   │                       │
│                       └────────────────────────────────────────┘                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. GUI Technology Stack Evaluation & Architectural Choice

To determine the optimal GUI foundation for PC Diagnostic, three primary technology stacks were evaluated against key requirements: **Native OS integration, real-time chart rendering performance (60 FPS), cross-platform deployment ease, binary size, and visual polish.**

| Criterion | Stack A: Native Qt (PySide6 / PyQt6) | Stack B: PyWebView / Tauri + Web Engine (React/Vite/Tailwind) | Stack C: Flutter / Flet |
| :--- | :--- | :--- | :--- |
| **Aesthetic & Styling** | High (QSS stylesheets, custom QPainter) | **Exceptional** (Tailwind, Lucide icons, glassmorphism, CSS animations) | High (Material / Cupertino) |
| **Real-time Charting** | Ultra-Fast (PyQtGraph / QPainter) | **Exceptional** (ECharts, Chart.js, Canvas WebGL) | Moderate (fl_chart) |
| **Memory Footprint** | Low (~40–80 MB RAM) | Moderate (~80–130 MB RAM via native OS webview) | Moderate (~90–150 MB RAM) |
| **OS System Tray & Menu Bar** | Native (`QSystemTrayIcon`) | Native (via PyWebView/Tauri Tray API) | Native |
| **Packaging & DMG/EXE Size** | Clean standalone binary (~45MB) | Lightweight (~35–55MB using native OS Webview) | Large bundle (~70MB+) |
| **Developer Velocity** | Python-only | Fast UI iteration with modern component libraries | Moderate |

### Recommended Architecture: Dual-Compatible Architecture
1. **Primary Recommended Tier — Modern Desktop GUI via PySide6 (Qt for Python) or PyWebView / Embedded Web UI:**
   - **PySide6 (Qt6):** Ideal for pure-Python deployments, zero browser runtime dependencies, direct high-performance chart widgets (`PyQtGraph` or QCustomPlot), and seamless native macOS/Windows window decorations.
   - **PyWebView + React/Tailwind/ECharts:** Ideal for ultra-rich glassmorphic dashboards matching NZXT CAM/iCUE aesthetic, featuring responsive grid layouts, animated SVG dials, and rich markdown rendering for AI diagnostics.
2. **Abstracted GUI Controller:** The architecture defines a `TelemetryBridge` interface so the core engine can drive either a Qt-based UI or a Web-based UI without code changes to collectors, alerts, or models.

---

## 4. UI Layout & Functional Specification

The user interface is organized into a cohesive, multi-tabbed desktop layout:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  [PC DIAGNOSTIC v0.2.0]   [● Live 1000ms]   [Alerts: 0]   [CPU 38°C]   [⚙ Settings] [—][□][✕] │
├────────────┬───────────────────────────────────────────────────────────────────────────┤
│ 📊 Overview│  SYSTEM OVERVIEW                                                          │
│            │  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐        │
│ 🌡️ Sensors │  │ CPU UTILIZATION   │ │ MEMORY CAPACITY   │ │ GPU TELEMETRY     │        │
│            │  │      [ 34% ]      │ │      [ 58% ]      │ │      [ 12% ]      │        │
│ 💻 Hardware│  │ 10-Core Apple M1  │ │ 18.6 GB / 32.0 GB │ │ 42°C  •  1100 MHz │        │
│            │  │ ~~~~~~ 2.4 GHz ~~~│ │ ~~~ Active ~~~~~~~│ │ ~~~ Fan: 0 RPM ~~~│        │
│ 📋 Processes│ └───────────────────┘ └───────────────────┘ └───────────────────┘        │
│            │                                                                           │
│ 🚨 Alerts  │  REAL-TIME TELEMETRY STREAM (60s Window)                                  │
│            │  ┌──────────────────────────────────────────────────────────────────────┐ │
│ 🤖 AI Studio│ │ [CPU Total %]  [Memory %]  [Disk I/O MB/s]  [Net Rx/Tx KB/s]         │ │
│            │ │ 100% ┼                                                               │ │
│ ⚙️ Settings│ │      │      /\_                                                      │ │
│            │ │  50% ┼─/\──/   \──────/\─────────/\────────                          │ │
│            │ │   0% ┴───────────────────────────────────────                         │ │
│            │ └──────────────────────────────────────────────────────────────────────┘ │
│            │                                                                           │
│            │  STORAGE & NETWORK I/O             TOP ACTIVE PROCESSES (Live)            │
│            │  ┌───────────────────────────────┐ ┌────────────────────────────────────┐ │
│            │  │ Disk 0 (APFS): 452 GB / 1 TB  │ │ Process       PID    CPU%   RAM    │ │
│            │  │ Read: 12.4 MB/s  Write: 4.1MB/│ │ Google Chrome 4812   14.2%  1.8 GB │ │
│            │  │ en0: ↓ 2.4 MB/s   ↑ 140 KB/s  │ │ PyCharm       9011    8.1%  2.4 GB │ │
│            │  └───────────────────────────────┘ └────────────────────────────────────┘ │
└────────────┴───────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Views & Capabilities Breakdown

#### Tab 1: System Overview (Main Dashboard)
- **Radial Telemetry Gauges:** Instant visual status for CPU load, Memory pressure, GPU load, and System Thermals with dynamic color bands (Green `<55%`, Amber `55–80%`, Red `>80%`).
- **Live Vector History Graph:** Smooth continuous line charts displaying past 60–300 seconds of CPU, RAM, and Disk throughput with interactive tooltips on hover.
- **Hardware Badge:** Hostname, OS version, architecture, uptime, and collector status indicator.

#### Tab 2: Hardware & Thermal Sensors (HWiNFO64-Style Deep Dive)
- **Per-Core CPU Grid:** Individual utilization bars and frequency counters for every logical core.
- **Thermal Heatmap Matrix:** Sensor table displaying CPU Package, GPU Core, Memory Dimms, SSD Thermals, and ambient sensors (sourced from `SmcProvider` on macOS and `LhmProvider` on Windows).
- **Fan & Voltage Monitors:** RPM gauges and core voltage readings with min/max/average tracking over time.

#### Tab 3: Process Inspector & Task Manager
- **Live Process Table:** Real-time sortable table featuring PID, Process Name, CPU%, Memory (RSS), Disk Read/Write, and Thread Count.
- **Search & Filter Bar:** Instant regex/keyword search to isolate runaway processes.
- **Action Controls:** Right-click context menu with `Inspect Process`, `Terminate (SIGTERM/SIGKILL)`, and `Filter Historical Telemetry`.

#### Tab 4: Alerting & Incident Center
- **Incident Dashboard:** Real-time cards for `FIRING` and `PENDING` incidents with severity badges (Warning, Critical).
- **Interactive Threshold Editor:** Sliders to adjust CPU/Memory trigger limits, debounce duration (`duration_s`), and hysteresis margins directly in the GUI.
- **Notification History Log:** Searchable log of past alert triggers with timestamp, peak metric values, and resolution times.

#### Tab 5: AI Diagnostics Studio
- **One-Click Diagnostic Execution:** `Run Full System Diagnosis` button triggering the CrewAI multi-agent diagnostic crew (or `LocalDiagnosticAnalyzer` fallback).
- **Live Evidence Inspector:** Expandable tree showing the exact telemetry snapshot captured (CPU spikes, memory hogs, thermal anomalies).
- **Interactive AI Report Viewer:** Markdown-rendered diagnostic report with syntax-highlighted code recommendations, hardware health scores, and actionable mitigation steps.
- **Export & Share:** Export diagnostic reports to Markdown, HTML, or PDF formats.

#### Tab 6: System Tray & Mini Overlay Mode
- **System Tray / Menu Bar Icon:** Dynamic tray icon displaying CPU or Temp percentage in the macOS Menu Bar / Windows Taskbar.
- **Mini-Widget / Compact HUD:** Detachable floating mini-monitor that can stay "Always on Top" during gaming, rendering, or software compilation.

---

## 5. Concurrency & Threading Architecture

Maintaining a fluid 60 FPS user interface while collecting system metrics and running LLM agents requires a strict multi-threaded architecture:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                               THREAD TOPOLOGY                            │
│                                                                          │
│  [1. Collector Thread] (Daemon)                                          │
│      Polls hardware providers every 1000ms → Normalizes → Pushes to Cache │
│                                                                          │
│  [2. Alert Evaluator Thread] (Daemon)                                    │
│      Evaluates rule state machines on each snapshot → Triggers Dispatcher│
│                                                                          │
│  [3. UI Event Loop (Main Thread)]                                        │
│      Runs 30–60 FPS Qt / Webview render loop                            │
│      Pulls from TelemetryBridge buffer without holding collector lock    │
│                                                                          │
│  [4. AI Diagnostic Worker Thread] (On-Demand)                            │
│      Executes CrewAI / LLM API calls in background                       │
│      Emits progress signals (0% → 100%) and final Markdown report        │
│                                                                          │
│  [5. Background Update Checker] (One-Shot)                               │
│      Queries GitHub Releases API asynchronously                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Thread Safety & Lock Strategy
- **`RollingCache` Invariant:** The `threading.Lock` protects snapshot insertion and retrieval. The GUI thread never blocks the collector thread; it reads copies of the latest `Snapshot` or requests sliced time-series via `cache.series()`.
- **Decoupled Telemetry Bridge:** A `TelemetryBridge` queue acts as a pub/sub ring buffer. The collector publishes snapshots; the GUI consumes them via thread-safe signals/events (`QMetaObject.invokeMethod` in Qt or WebSocket messages in PyWebView).
- **Non-blocking AI Execution:** AI diagnostics runs on a dedicated worker thread, preventing UI freezes during long LLM inference times.

---

## 6. Implementation Code Structure

The project structure evolves to cleanly separate the new GUI layer while preserving the backend:

```
pc_diagnostic/
├── pyproject.toml
├── build_binaries.py                  # PyInstaller multi-platform build script
├── package_mac.py                     # macOS App Bundle & DMG packager
├── package_win.py                     # Windows Inno Setup / MSI installer
├── docs/                              # Technical documentation
│   ├── architecture.md                # System-level design
│   ├── ui_architecture.md             # Desktop GUI architecture (this document)
│   ├── dashboard.md                   # Legacy Terminal TUI reference
│   ├── collector_and_cache.md
│   ├── alerting.md
│   └── diagnostics.md
├── src/
│   └── pc_diagnostic/
│       ├── __init__.py
│       ├── main.py                    # Entry point: launches GUI (default) or --cli/--log
│       ├── models.py                  # MetricReading, Snapshot, CacheHealth
│       ├── normalizer.py              # Validation gate
│       ├── cache.py                   # RollingCache ring buffer
│       ├── collector.py               # Background collection thread
│       ├── providers/                 # Psutil, LHM, SMC hardware providers
│       ├── alerts/                    # Evaluator, Dispatcher, Rule models
│       ├── diagnostics/               # CrewAI and LocalAnalyzer
│       ├── gui/                       # [NEW] Desktop GUI Presentation Layer
│       │   ├── __init__.py
│       │   ├── app.py                 # GUI Application Lifecycle & Window Manager
│       │   ├── bridge.py              # Thread-safe Telemetry Bridge (Cache → UI)
│       │   ├── theme.py               # Dark/Light/OLED color palettes & fonts
│       │   ├── components/            # Reusable UI widgets
│       │   │   ├── gauge.py           # Radial & arc telemetry meters
│       │   │   ├── sparkline_chart.py # 60fps real-time vector time-series charts
│       │   │   ├── sensor_tree.py     # Thermal & voltage tree explorer
│       │   │   ├── process_table.py   # Interactive sortable process inspector
│       │   │   └── alert_banner.py    # Toast notification & active incident bar
│       │   ├── views/                 # Tabbed views
│       │   │   ├── overview_view.py   # Main Dashboard
│       │   │   ├── sensors_view.py    # Hardware thermals & fan curves
│       │   │   ├── processes_view.py  # Process Manager & task controls
│       │   │   ├── alerts_view.py     # Alert rules & incident history
│       │   │   └── diagnostics_view.py# AI Diagnostics Studio & markdown viewer
│       │   └── tray.py                # System Tray & Menu Bar Companion
│       └── tui/                       # [RELOCATED] Terminal Rich TUI Dashboard
│           └── dashboard.py
```

---

## 7. Packaging, Distribution & Operating System Integration

### 7.1 macOS Distribution (`.app` & `.dmg`)
- **Native App Bundle:** Packaged into `PC Diagnostic.app` containing the compiled binary, native `smc_helper` binary, App Icons (`AppIcon.icns`), and `Info.plist`.
- **System Permissions & Entitlements:** Entitlements for `com.apple.security.device.audio-input` (if needed) and Apple Silicon SMC sensor access via `IOHIDEventSystemClient`.
- **Menu Bar Status Integration:** NSStatusItem/Qt Menu Bar icon showing CPU and temperature stats directly in the top menu bar.
- **Drag-and-Drop DMG:** Automated creation of `PC-Diagnostic-Installer.dmg` using `create-dmg` with custom background artwork and `/Applications` symlink.

### 7.2 Windows Distribution (`.exe` & `.msi`)
- **Single-File / Directory Binary:** Packaged via PyInstaller into `PC_Diagnostic.exe` with application manifest.
- **UAC Sensor Elevation:** Windows manifest configured for `requireAdministrator` or on-demand elevation to permit LibreHardwareMonitor WMI reading of fan and temperature sensors.
- **System Tray & Toast Notifications:** Integration with Windows 10/11 Notification Center for threshold alerts.
- **Installer:** Inno Setup script generating an installer with Start Menu shortcuts and automatic uninstallation.

### 7.3 Linux Distribution (`AppImage` / `.deb`)
- **AppImage:** Single self-contained executable running across Ubuntu, Debian, Fedora, and Arch.
- **Desktop File:** `pc-diagnostic.desktop` registered with system application launchers and tray indicators.

---

## 8. Phased UI Migration Roadmap

| Phase | Milestone | Deliverables |
| :--- | :--- | :--- |
| **Phase 8.1** | **State Bridge & Core GUI Harness** | Implement `TelemetryBridge`, decouple CLI dashboard into `tui/`, create base GUI application window and theme system. |
| **Phase 8.2** | **Overview Dashboard & Gauges** | Build dynamic radial gauges, 60s vector line charts, and system hardware info card. |
| **Phase 8.3** | **Hardware Sensors & Thermal Matrix** | Integrate full SMC (macOS) and LHM (Windows) sensor tree with per-core bars and fan speed gauges. |
| **Phase 8.4** | **Process Manager & Alert Center** | Add interactive sortable process table with search/kill, plus live alert banner and threshold configuration UI. |
| **Phase 8.5** | **AI Diagnostics Studio** | Implement asynchronous diagnosis execution panel with markdown report viewer, evidence explorer, and export options. |
| **Phase 8.6** | **System Tray & Packaging** | Add menu bar/tray companion widget, build macOS `.dmg` and Windows `.exe` installers, and verify signing/notarization. |

---

## 9. Conclusion
By transitioning PC Diagnostic from a terminal-based interface to a modern Desktop GUI application, the software provides an intuitive, high-performance monitoring experience comparable to industry-standard PC monitors while enhancing troubleshooting with integrated, real-time AI hardware diagnostics.
