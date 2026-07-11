import logging
from typing import Any, dict, list, tuple

from pc_diagnostic.alerts.models import AlertRule, Incident, IncidentState
from pc_diagnostic.models import Snapshot

logger = logging.getLogger(__name__)


class AlertEvaluator:
    def __init__(self, rules: list[AlertRule]) -> None:
        self.rules = rules
        self.incidents = {rule.id: Incident(rule=rule) for rule in rules}

    def evaluate(
        self, snapshot: Snapshot, cache_age: float, timestamp: float
    ) -> list[tuple[Incident, IncidentState, IncidentState]]:
        """Evaluate a snapshot and return list of transitions (incident, old_state, new_state)."""
        transitions: list[tuple[Incident, IncidentState, IncidentState]] = []

        # Map metric readings for fast lookup
        metrics: dict[str, float] = {}
        for r in snapshot.readings:
            # Enforce overall/last value per metric key
            metrics[r.metric] = r.value

        # Inject virtual staleness metric
        metrics["cache.staleness"] = cache_age

        for rule in self.rules:
            incident = self.incidents[rule.id]
            old_state = incident.state

            # If the metric is not available and not cache.staleness, skip evaluation
            if rule.metric not in metrics:
                continue

            value = metrics[rule.metric]
            incident.value = value

            # 1. Check if condition is currently met (trigger condition)
            is_triggered = False
            if rule.condition == "gt":
                is_triggered = value > rule.threshold
            elif rule.condition == "lt":
                is_triggered = value < rule.threshold

            # 2. State Machine Transitions
            if incident.state == IncidentState.NORMAL:
                if is_triggered:
                    incident.state = IncidentState.PENDING
                    incident.first_triggered_at = timestamp
                    # No transition event emitted for PENDING state entries

            elif incident.state == IncidentState.PENDING:
                if is_triggered:
                    # Check if debounce duration has elapsed
                    triggered_duration = timestamp - (
                        incident.first_triggered_at or timestamp
                    )
                    if triggered_duration >= rule.duration_s:
                        incident.state = IncidentState.FIRING
                        transitions.append(
                            (incident, IncidentState.PENDING, IncidentState.FIRING)
                        )
                else:
                    # Clear debounce state if it dropped below threshold
                    incident.state = IncidentState.NORMAL
                    incident.first_triggered_at = None

            elif incident.state == IncidentState.FIRING:
                # Apply hysteresis check to determine if alert should clear
                still_active = False
                if rule.condition == "gt":
                    still_active = value >= (rule.threshold - rule.hysteresis_offset)
                elif rule.condition == "lt":
                    still_active = value <= (rule.threshold + rule.hysteresis_offset)

                if not still_active:
                    incident.state = IncidentState.NORMAL
                    incident.first_triggered_at = None
                    transitions.append(
                        (incident, IncidentState.FIRING, IncidentState.NORMAL)
                    )

            if old_state != incident.state:
                logger.debug(
                    f"Alert {rule.id} transitioned: {old_state.value} -> {incident.state.value} (val={value})"
                )

        return transitions
