import os
import tempfile
from typing import cast
from unittest.mock import patch

from pc_diagnostic.alerts.dispatcher import AlertDispatcher
from pc_diagnostic.alerts.evaluator import AlertEvaluator
from pc_diagnostic.alerts.models import AlertRule, IncidentState
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


def test_evaluator_debounce_transitions() -> None:
    rule = AlertRule(
        id="test_cpu",
        metric="cpu.utilization.total",
        condition="gt",
        threshold=90.0,
        duration_s=5.0,
        hysteresis_offset=0.0,
        cooldown_s=30.0,
    )
    evaluator = AlertEvaluator([rule])

    # Tick 1 (t=0s): Value exceeds threshold -> moves NORMAL to PENDING
    snap1 = Snapshot(
        timestamp=0.0,
        readings=[
            MetricReading(
                metric="cpu.utilization.total",
                value=95.0,
                unit=MetricUnit.PERCENT,
                source="test",
            )
        ],
    )
    transitions = evaluator.evaluate(snap1, cache_age=0.0, timestamp=0.0)
    assert len(transitions) == 0
    assert evaluator.incidents["test_cpu"].state == IncidentState.PENDING

    # Tick 2 (t=3.0s): Exceeds threshold but debounce time (5s) not reached
    snap2 = Snapshot(
        timestamp=3.0,
        readings=[
            MetricReading(
                metric="cpu.utilization.total",
                value=95.0,
                unit=MetricUnit.PERCENT,
                source="test",
            )
        ],
    )
    transitions = evaluator.evaluate(snap2, cache_age=0.0, timestamp=3.0)
    assert len(transitions) == 0
    assert evaluator.incidents["test_cpu"].state == IncidentState.PENDING

    # Tick 3 (t=6.0s): Exceeds threshold and debounce time reached -> FIRING
    snap3 = Snapshot(
        timestamp=6.0,
        readings=[
            MetricReading(
                metric="cpu.utilization.total",
                value=95.0,
                unit=MetricUnit.PERCENT,
                source="test",
            )
        ],
    )
    transitions = evaluator.evaluate(snap3, cache_age=0.0, timestamp=6.0)
    assert len(transitions) == 1
    assert transitions[0][1] == IncidentState.PENDING
    assert transitions[0][2] == IncidentState.FIRING
    assert (
        cast(IncidentState, evaluator.incidents["test_cpu"].state)
        == IncidentState.FIRING
    )


def test_evaluator_hysteresis_boundary() -> None:
    rule = AlertRule(
        id="test_mem",
        metric="memory.utilization",
        condition="gt",
        threshold=90.0,
        duration_s=0.0,  # Immediate fire
        hysteresis_offset=10.0,  # Clears only below 80.0
        cooldown_s=30.0,
    )
    evaluator = AlertEvaluator([rule])

    # Trigger immediately
    snap1 = Snapshot(
        timestamp=0.0,
        readings=[
            MetricReading(
                metric="memory.utilization",
                value=92.0,
                unit=MetricUnit.PERCENT,
                source="test",
            )
        ],
    )
    transitions = evaluator.evaluate(snap1, cache_age=0.0, timestamp=0.0)
    assert len(transitions) == 1
    assert evaluator.incidents["test_mem"].state == IncidentState.FIRING

    # Drop value to 85.0 (below threshold 90, but above hysteresis floor 80)
    # Stays FIRING because of hysteresis
    snap2 = Snapshot(
        timestamp=1.0,
        readings=[
            MetricReading(
                metric="memory.utilization",
                value=85.0,
                unit=MetricUnit.PERCENT,
                source="test",
            )
        ],
    )
    transitions = evaluator.evaluate(snap2, cache_age=0.0, timestamp=1.0)
    assert len(transitions) == 0
    assert evaluator.incidents["test_mem"].state == IncidentState.FIRING

    # Drop value to 78.0 (below hysteresis floor 80) -> transitions back to NORMAL
    snap3 = Snapshot(
        timestamp=2.0,
        readings=[
            MetricReading(
                metric="memory.utilization",
                value=78.0,
                unit=MetricUnit.PERCENT,
                source="test",
            )
        ],
    )
    transitions = evaluator.evaluate(snap3, cache_age=0.0, timestamp=2.0)
    assert len(transitions) == 1
    assert transitions[0][1] == IncidentState.FIRING
    assert transitions[0][2] == IncidentState.NORMAL
    assert (
        cast(IncidentState, evaluator.incidents["test_mem"].state)
        == IncidentState.NORMAL
    )


def test_dispatcher_tiered_responses() -> None:
    rule = AlertRule(
        id="test_alert",
        metric="cpu.utilization.total",
        condition="gt",
        threshold=90.0,
        duration_s=0.0,
        hysteresis_offset=0.0,
        cooldown_s=30.0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        alerts_log = os.path.join(tmpdir, "alerts.log")
        dispatcher = AlertDispatcher(log_path=alerts_log)

        evaluator = AlertEvaluator([rule])

        # Tick 1: trigger firing transition
        snap1 = Snapshot(
            timestamp=0.0,
            readings=[
                MetricReading(
                    metric="cpu.utilization.total",
                    value=95.0,
                    unit=MetricUnit.PERCENT,
                    source="test",
                )
            ],
        )
        transitions = evaluator.evaluate(snap1, cache_age=0.0, timestamp=0.0)

        with patch("subprocess.run") as mock_run:
            dispatcher.dispatch(transitions, timestamp=0.0)

            # Assert Tier 1: In-memory collection active
            assert "test_alert" in dispatcher.active_incidents
            assert dispatcher.active_incidents["test_alert"].value == 95.0

            # Assert Tier 2: Subprocess notification triggered
            assert mock_run.call_count == 1

            # Assert Tier 3: Incident logged to file
            assert os.path.exists(alerts_log)
            with open(alerts_log) as f:
                content = f.read()
                assert "FIRING" in content
                assert "ID=test_alert" in content

        # Tick 2: consecutive tick within cooldown ->
        # dispatcher does not alert OS/log again during cooldown
        transitions2 = [
            (
                evaluator.incidents["test_alert"],
                IncidentState.PENDING,
                IncidentState.FIRING,
            )
        ]
        with patch("subprocess.run") as mock_run2:
            # Re-dispatched within cooldown (t=10.0s < 30.0s cooldown)
            dispatcher.dispatch(transitions2, timestamp=10.0)
            assert mock_run2.call_count == 0

        # Tick 3: clear transition -> NORMAL
        snap3 = Snapshot(
            timestamp=40.0,
            readings=[
                MetricReading(
                    metric="cpu.utilization.total",
                    value=50.0,
                    unit=MetricUnit.PERCENT,
                    source="test",
                )
            ],
        )
        transitions3 = evaluator.evaluate(snap3, cache_age=0.0, timestamp=40.0)
        dispatcher.dispatch(transitions3, timestamp=40.0)

        # Assert Tier 1: Removed from in-memory dictionary
        assert "test_alert" not in dispatcher.active_incidents

        # Assert Tier 3: CLEARED log entry
        with open(alerts_log) as f:
            content = f.read()
            assert "CLEARED" in content
