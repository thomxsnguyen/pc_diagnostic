# AI Diagnostics System

The diagnostics module provides on-demand system analysis that examines a snapshot
of telemetry data and produces a structured markdown report with findings and
actionable recommendations.

Defined in `src/pc_diagnostic/diagnostics/crew.py`.

---

## Dual-Mode Design

The system has two analysis backends with automatic fallback:

```
run_diagnosis(evidence_packet)
    │
    ├── CrewAI available + API key present?
    │       YES → CrewAI Agent analysis (LLM-powered)
    │       Exception? → fall through to local
    │
    └── NO → LocalDiagnosticAnalyzer (rule-based)
```

### Why dual-mode?

- CrewAI requires an API key (`OPENAI_API_KEY`, `GEMINI_API_KEY`, or
  `ANTHROPIC_API_KEY`) and network access. Not always available.
- The local analyzer provides instant, deterministic results with no external
  dependencies — always works, even offline.
- Users get value from the diagnostics feature regardless of their setup.

---

## Evidence Packet

Both backends receive the same `dict[str, Any]` evidence packet built by the
dashboard from the latest cache snapshot:

| Key                | Type               | Content                          |
|--------------------|--------------------|----------------------------------|
| `cpu_model`        | `str`              | Processor brand string           |
| `cpu_util`         | `float`            | Overall CPU percentage           |
| `ram_util`         | `float`            | Overall RAM percentage           |
| `ram_used_str`     | `str`              | Human-readable used RAM          |
| `cpu_temp`         | `float`            | CPU temperature (-1 if N/A)      |
| `gpu_temp`         | `float`            | GPU temperature (-1 if N/A)      |
| `fan_speed`        | `float`            | Fan RPM (-1 if N/A)              |
| `top_cpu_procs`    | `list[dict]`       | Top 5 processes by CPU           |
| `top_mem_procs`    | `list[dict]`       | Top 5 processes by memory        |
| `active_incidents` | `list[dict]`       | Currently firing alert incidents |

---

## CrewAI Backend

When available, the system creates a single-agent CrewAI crew:

- **Agent:** "Senior Systems Performance Analyst" — specialized in diagnosing
  resource leaks, thermal throttling, and process misbehaviors
- **Task:** Analyze the evidence packet and produce a structured markdown report
  with anomalies, bottlenecks, and specific actionable recommendations
- **Process:** Sequential (single agent, single task)
- **Verbose:** Disabled to avoid polluting the TUI

The evidence packet is formatted as a plain-text string and embedded in the task
description. The agent's output is returned as-is (converted to string).

---

## Local Diagnostic Analyzer

The `LocalDiagnosticAnalyzer` is a deterministic rule engine that evaluates
thresholds and generates a report:

### Rule Checks

| Check              | Threshold | Trigger                                    |
|--------------------|-----------|--------------------------------------------|
| High CPU           | >85%      | Identifies top CPU process, suggests termination |
| High RAM           | >85%      | Identifies top memory process, suggests closing apps |
| High Temperature   | >80°C     | Recommends airflow check, dust cleaning    |
| Active Alerts      | Any firing| Links to specific alert rule violations    |

### Report Structure

```markdown
# PC Diagnostic Analysis Report

**Overall System Status**: HEALTHY / WARNING / CRITICAL

## System Telemetry Summary
- CPU Model, utilization, memory, temps, fan speed

## Diagnostics & Anomalies
- List of identified issues (or "no anomalies")

## Actionable Recommendations
- Specific steps to resolve each issue (or "no action required")
```

### Status Classification

| Condition              | Status     |
|------------------------|------------|
| 0 issues               | HEALTHY    |
| 1 issue                | WARNING    |
| 2+ issues              | CRITICAL   |

---

## Integration with Dashboard

The diagnostics system is triggered by pressing `d` in the dashboard:

1. Dashboard calls `trigger_background_diagnosis()`
2. A 10-second cooldown prevents spamming
3. Evidence packet is built from `cache.latest()`
4. `run_diagnosis()` runs in a background daemon thread
5. The report text is stored in `self.diagnosis_text`
6. Dashboard renders it as a full-screen markdown overlay
7. Any key press dismisses the overlay

If the diagnosis fails for any reason, an error message is displayed in the
overlay rather than crashing.
