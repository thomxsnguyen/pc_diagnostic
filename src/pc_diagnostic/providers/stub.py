import random
import time

from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.providers.base import Provider


class StubProvider(Provider):
    def __init__(self) -> None:
        self._start_time = time.time()

    @property
    def name(self) -> str:
        return "stub"

    def available(self) -> bool:
        return True

    def read(self) -> list[MetricReading]:
        uptime_seconds = time.time() - self._start_time
        cpu_val = random.uniform(5.0, 95.0)
        mem_val = random.uniform(40.0, 80.0)

        return [
            MetricReading(
                metric="cpu.utilization.total",
                value=cpu_val,
                unit=MetricUnit.PERCENT,
                source=self.name,
            ),
            MetricReading(
                metric="memory.utilization",
                value=mem_val,
                unit=MetricUnit.PERCENT,
                source=self.name,
            ),
            MetricReading(
                metric="system.uptime",
                value=uptime_seconds,
                unit=MetricUnit.SECONDS,
                source=self.name,
            ),
        ]
