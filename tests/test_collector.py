import time

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.collector import Collector
from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.providers.base import Provider


class MockProvider(Provider):
    def __init__(self, name: str, available: bool = True, fail: bool = False):
        self._name = name
        self._available = available
        self._fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def available(self) -> bool:
        return self._available

    def read(self) -> list[MetricReading]:
        self.calls += 1
        if self._fail:
            raise RuntimeError("Intentional read failure!")
        return [
            MetricReading(
                metric="mock.metric",
                value=100.0,
                unit=MetricUnit.COUNT,
                source=self.name,
            )
        ]


def test_collector_normal_operation() -> None:
    cache = RollingCache(maxlen=10)
    p1 = MockProvider("p1", available=True)
    p2 = MockProvider("p2", available=False)  # Should be skipped

    collector = Collector([p1, p2], cache, interval=0.01)
    collector.start()

    # Allow some ticks to run
    time.sleep(0.05)
    collector.stop()

    assert p1.calls > 0
    assert p2.calls == 0

    latest = cache.latest()
    assert latest is not None
    assert len(latest.readings) == 1
    assert latest.readings[0].source == "p1"


def test_collector_provider_failure_resilience() -> None:
    cache = RollingCache(maxlen=10)
    p1 = MockProvider("p1", fail=True)  # Will raise Exception on read()
    p2 = MockProvider("p2", fail=False)  # Should succeed

    collector = Collector([p1, p2], cache, interval=0.01)
    collector.start()

    time.sleep(0.05)
    collector.stop()

    # The collector loop should NOT crash when p1 fails.
    # It must execute read() on p1, fail, log warning, and successfully read p2.
    assert p1.calls > 0
    assert p2.calls > 0

    latest = cache.latest()
    assert latest is not None
    # Snapshot should contain p2's reading, but not p1's
    assert len(latest.readings) == 1
    assert latest.readings[0].source == "p2"
