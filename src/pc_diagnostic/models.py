from dataclasses import dataclass, field
from enum import Enum


class MetricUnit(Enum):
    PERCENT = "PERCENT"
    BYTES = "BYTES"
    BYTES_PER_SEC = "BYTES_PER_SEC"
    HERTZ = "HERTZ"
    CELSIUS = "CELSIUS"
    RPM = "RPM"
    COUNT = "COUNT"
    SECONDS = "SECONDS"
    INFO = "INFO"  # For metadata / static specs
    VOLTS = "VOLTS"


@dataclass(frozen=True)
class MetricReading:
    metric: str
    value: float
    unit: MetricUnit
    source: str
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Snapshot:
    timestamp: float
    readings: list[MetricReading]


@dataclass(frozen=True)
class CacheHealth:
    size: int
    max_size: int
    last_updated: float
    age_s: float
