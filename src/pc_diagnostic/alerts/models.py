from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IncidentState(Enum):
    NORMAL = "NORMAL"
    PENDING = "PENDING"
    FIRING = "FIRING"


@dataclass(frozen=True)
class AlertRule:
    id: str
    metric: str
    condition: str  # "gt" (greater than) or "lt" (less than)
    threshold: float
    duration_s: float  # debounce duration in seconds
    hysteresis_offset: (
        float  # clear value offset (e.g. CPU clears at threshold - offset)
    )
    cooldown_s: float  # cooldown between alerts


@dataclass
class Incident:
    rule: AlertRule
    state: IncidentState = IncidentState.NORMAL
    first_triggered_at: Optional[float] = None
    last_fired_at: Optional[float] = None
    value: float = 0.0


# Default alerts config
DEFAULT_ALERT_RULES = [
    AlertRule(
        id="high_cpu",
        metric="cpu.utilization.total",
        condition="gt",
        threshold=90.0,
        duration_s=5.0,
        hysteresis_offset=10.0,
        cooldown_s=60.0,
    ),
    AlertRule(
        id="high_memory",
        metric="memory.utilization",
        condition="gt",
        threshold=90.0,
        duration_s=5.0,
        hysteresis_offset=5.0,
        cooldown_s=60.0,
    ),
    AlertRule(
        id="stale_collector",
        metric="cache.staleness",
        condition="gt",
        threshold=2.0,
        duration_s=2.0,
        hysteresis_offset=0.0,
        cooldown_s=30.0,
    ),
]
