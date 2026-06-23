import logging
import math
import re

from pc_diagnostic.models import MetricReading, MetricUnit

logger = logging.getLogger(__name__)

# Pattern for dot-separated naming convention: e.g. cpu.utilization.total
METRIC_NAME_PATTERN = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$")


class Normalizer:
    @staticmethod
    def validate(readings: list[MetricReading]) -> tuple[list[MetricReading], int]:
        """Validate metric readings.

        Filters out non-conforming readings and returns a tuple of:
        (valid_readings, dropped_count)
        """
        valid_readings: list[MetricReading] = []
        dropped_count = 0

        for r in readings:
            # 1. Validate metric name pattern
            if not r.metric or not METRIC_NAME_PATTERN.match(r.metric):
                logger.warning(
                    f"Dropped reading: Invalid metric name pattern '{r.metric}'"
                )
                dropped_count += 1
                continue

            # 2. Validate value is a finite float
            if not isinstance(r.value, (int, float)) or not math.isfinite(r.value):
                logger.warning(
                    f"Dropped reading '{r.metric}': Non-finite value '{r.value}'"
                )
                dropped_count += 1
                continue



            # 4. Validate source is non-empty
            if not r.source or not isinstance(r.source, str):
                logger.warning(
                    f"Dropped reading '{r.metric}': "
                    f"Empty or invalid source '{r.source}'"
                )
                dropped_count += 1
                continue

            # Cast value to float to ensure consistency in schema
            normalized_reading = MetricReading(
                metric=r.metric,
                value=float(r.value),
                unit=r.unit,
                source=r.source,
                tags=dict(r.tags) if r.tags else {},
            )
            valid_readings.append(normalized_reading)

        return valid_readings, dropped_count
