# Configuration & Environment Reference

This document serves as the single source of truth for all runtime configuration, environment variables, command-line options, logging behaviors, alert thresholds, and telemetry tuning parameters in **PC Diagnostic**.

---

## 1. Environment Variables

PC Diagnostic uses `python-dotenv` to load environment variables from a `.env` file in the project root directory.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `OPENAI_API_KEY` | String | *None* | OpenAI API key for LLM-powered multi-agent diagnostics via CrewAI. |
| `GEMINI_API_KEY` | String | *None* | Google Gemini API key for CrewAI diagnostics backend. |
| `ANTHROPIC_API_KEY` | String | *None* | Anthropic Claude API key for CrewAI diagnostics backend. |

### Environment Variable Behavior:
- **LLM Detection:** When any of the supported API keys are present and the `crewai` library is installed, the diagnostic engine automatically initializes `CrewAI` with a `Senior Systems Performance Analyst` agent.
- **Graceful Fallback:** If no API key is defined or if the network/API call fails, the system automatically falls back to `LocalDiagnosticAnalyzer` (the built-in heuristic rule analyzer) without throwing errors.

---

## 2. Command-Line Options (CLI)

The application entry point (`src/pc_diagnostic/main.py`) accepts the following arguments:

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `-h`, `--help` | Flag | — | Displays the help message and available options. |
| `--log`, `--no-dashboard` | Flag | `False` | Disables the Rich terminal dashboard and outputs telemetry snapshot logs directly to `stdout`. |
| `--refresh-rate` | Float | `1.0` | Refresh interval in seconds for the terminal TUI dashboard render loop. |

### Execution Mode Selection:
- **Interactive TUI Mode (Default):** Runs when standard output is an interactive TTY (`sys.stdout.isatty() == True`) and `--log` is not set.
- **Log Mode (Headless Fallback):** Automatically activates when redirected to a pipe/file, executed in non-TTY environments (CI/CD, background services), or when `--log` is explicitly passed.

---

## 3. Logging Subsystem

PC Diagnostic routes logs based on the active execution mode to ensure terminal UI rendering is never corrupted by background log statements.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             LOGGING TOPOLOGY                             │
│                                                                          │
│  [Interactive Dashboard Mode] ──► Writes to: "pc_diagnostic.log"         │
│  [Log / Headless Mode]        ──► Writes to: "stdout"                    │
│                                                                          │
│  [Alert Dispatcher Engine]    ──► Writes to: "pc_diagnostic_alerts.log"  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Log File Specifications

| Log File | Purpose | Managed By | Log Format |
| :--- | :--- | :--- | :--- |
| `pc_diagnostic.log` | General application logs (collector lifecycle, provider errors, normalizer dropped readings, update checks). | `src/pc_diagnostic/main.py` | `%(asctime)s [%(levelname)s] %(name)s: %(message)s` |
| `pc_diagnostic_alerts.log` | Audit trail of all threshold alert incidents (transitions into `PENDING`, `FIRING`, and `NORMAL`). | `src/pc_diagnostic/alerts/dispatcher.py` | `%(asctime)s [ALERT] %(message)s` |

---

## 4. Alerting Thresholds & Rule Engine

Alert rules are defined as immutable `AlertRule` dataclasses evaluated on every collector tick (1.0s) against live metrics.

### 4.1 Default Alert Rules

| Rule ID | Monitored Metric | Condition | Trigger Threshold | Debounce Duration (`duration_s`) | Hysteresis Offset (`hysteresis_offset`) | Cooldown (`cooldown_s`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `high_cpu` | `cpu.utilization.total` | `>` (`gt`) | **`90.0%`** | `5.0s` | `10.0%` (clears at `< 80.0%`) | `60.0s` |
| `high_memory` | `memory.utilization` | `>` (`gt`) | **`90.0%`** | `5.0s` | `5.0%` (clears at `< 85.0%`) | `60.0s` |
| `stale_collector`| `cache.staleness` | `>` (`gt`) | **`2.0s`** | `2.0s` | `0.0s` (clears at `< 2.0s`) | `30.0s` |

### 4.2 State Machine & Hysteresis Mechanics

Each alert rule is tracked through an `Incident` state machine:

```
          Value >= Threshold (held for duration_s)
  NORMAL ───────────────────────────────────────────► PENDING
    ▲                                                    │
    │ Value < (Threshold - Hysteresis)                   │ Value stays >= Threshold
    │                                                    ▼
  NORMAL ◄──────────────────────────────────────────── FIRING
          Value < (Threshold - Hysteresis)
```

- **Debounce (`duration_s`):** The metric must remain continuously breached for `duration_s` seconds before transitioning from `PENDING` to `FIRING`. Brief momentary spikes do not trigger notifications.
- **Hysteresis (`hysteresis_offset`):** Prevents alert flapping near the threshold boundary. For example, `high_cpu` triggers at `90%`, but only resolves once CPU drops below `80%` (`90% - 10%`).
- **Cooldown (`cooldown_s`):** Minimum quiet period after an alert fires before the same rule can trigger another OS desktop notification.

---

## 5. Telemetry & Internal Engine Parameters

| Subsystem | Parameter | Default Value | Location | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`RollingCache`** | `maxlen` | `300` | `src/pc_diagnostic/cache.py` | Maximum snapshot capacity. Retains 5 minutes of continuous history at 1.0s ticks. |
| **`Collector`** | `interval` | `1.0s` | `src/pc_diagnostic/collector.py` | Polling frequency for hardware telemetry providers. |
| **`Collector`** | Stop Timeout | `5.0s` | `src/pc_diagnostic/collector.py` | Max time allowed for background thread clean shutdown. |
| **Sparklines** | History Window | `20 points` | `src/pc_diagnostic/dashboard.py` | Number of historical readings rendered in dashboard Unicode sparklines. |
| **Diagnostics** | Cooldown | `10.0s` | `src/pc_diagnostic/dashboard.py` | Minimum cooldown between consecutive on-demand AI diagnosis runs. |
| **Update Checker**| HTTP Timeout | `3.0s` | `src/pc_diagnostic/dashboard.py` | Timeout for querying the GitHub Releases API at startup. |

---

## 6. How to Extend & Scale Configurations

### 6.1 Adding a Custom Alert Rule
To add a new alert rule, append an `AlertRule` instance to `DEFAULT_ALERT_RULES` in `src/pc_diagnostic/alerts/models.py`:

```python
AlertRule(
    id="high_cpu_temp",
    metric="thermal.cpu.temp",
    condition="gt",
    threshold=85.0,              # Trigger if CPU temp > 85°C
    duration_s=10.0,             # Must stay hot for 10 seconds
    hysteresis_offset=5.0,       # Clears when temp drops < 80°C
    cooldown_s=120.0,            # 2-minute notification cooldown
)
```

### 6.2 Tuning Cache Size for Long-Term Monitoring
To increase history retention (e.g. 15 minutes of history):
```python
# 15 minutes * 60 seconds = 900 snapshots
cache = RollingCache(maxlen=900)
```
