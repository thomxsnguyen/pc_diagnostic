import pytest

from pc_diagnostic.diagnostics.crew import LocalDiagnosticAnalyzer, run_diagnosis


def test_local_diagnostic_analyzer_healthy() -> None:
    evidence = {
        "cpu_model": "Apple M3 Pro",
        "cpu_util": 10.0,
        "ram_util": 40.0,
        "ram_used_str": "7.2 GB",
        "cpu_temp": 45.0,
        "gpu_temp": 40.0,
        "fan_speed": 1200.0,
        "top_cpu_procs": [],
        "top_mem_procs": [],
        "active_incidents": [],
    }

    analyzer = LocalDiagnosticAnalyzer()
    report = analyzer.analyze(evidence)

    assert "Overall System Status**: HEALTHY" in report
    assert "System Telemetry Summary" in report
    assert "Diagnostics & Anomalies" in report
    assert "No anomalies or thresholds violated" in report
    assert "No action required" in report


def test_local_diagnostic_analyzer_cpu_warning() -> None:
    evidence = {
        "cpu_model": "Apple M3 Pro",
        "cpu_util": 90.0,
        "ram_util": 40.0,
        "ram_used_str": "7.2 GB",
        "cpu_temp": 45.0,
        "gpu_temp": 40.0,
        "fan_speed": 1200.0,
        "top_cpu_procs": [{"pid": "123", "name": "python", "cpu": 88.0, "mem": 1024}],
        "top_mem_procs": [],
        "active_incidents": [],
    }

    analyzer = LocalDiagnosticAnalyzer()
    report = analyzer.analyze(evidence)

    assert "Overall System Status**: WARNING" in report
    assert "High CPU Load" in report
    assert "Runaway process suspected" in report


def test_local_diagnostic_analyzer_critical() -> None:
    evidence = {
        "cpu_model": "Apple M3 Pro",
        "cpu_util": 90.0,
        "ram_util": 95.0,
        "ram_used_str": "17.1 GB",
        "cpu_temp": 85.0,
        "gpu_temp": 82.0,
        "fan_speed": 2500.0,
        "top_cpu_procs": [],
        "top_mem_procs": [{"pid": "456", "name": "chrome", "mem_str": "8.0 GB"}],
        "active_incidents": [{"rule_id": "high_cpu", "state": "firing", "value": 90.0}],
    }

    analyzer = LocalDiagnosticAnalyzer()
    report = analyzer.analyze(evidence)

    assert "Overall System Status**: CRITICAL" in report
    assert "High CPU Load" in report
    assert "High RAM Utilization" in report
    assert "High Operating Temperature" in report
    assert "Active Alert (high_cpu)" in report


def test_run_diagnosis_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure any environment variables for keys are cleared so it falls back
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    evidence = {
        "cpu_model": "Apple M3 Pro",
        "cpu_util": 10.0,
        "ram_util": 40.0,
        "ram_used_str": "7.2 GB",
        "cpu_temp": 45.0,
        "gpu_temp": 40.0,
        "fan_speed": 1200.0,
    }

    report = run_diagnosis(evidence)
    assert "Overall System Status**: HEALTHY" in report
