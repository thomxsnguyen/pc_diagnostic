import time
from threading import Thread

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


def test_cache_push_latest() -> None:
    cache = RollingCache(maxlen=3)
    assert cache.latest() is None
    assert cache.health().size == 0
    assert cache.health().age_s == float("inf")

    r = MetricReading("cpu.util", 10.0, MetricUnit.PERCENT, "test")
    snap1 = Snapshot(time.time(), [r])
    cache.push(snap1)

    assert cache.latest() == snap1
    assert cache.health().size == 1
    assert cache.health().age_s >= 0.0


def test_cache_rolling_eviction() -> None:
    cache = RollingCache(maxlen=2)
    r = MetricReading("cpu.util", 10.0, MetricUnit.PERCENT, "test")

    snap1 = Snapshot(100.0, [r])
    snap2 = Snapshot(200.0, [r])
    snap3 = Snapshot(300.0, [r])

    cache.push(snap1)
    cache.push(snap2)
    assert cache.health().size == 2

    cache.push(snap3)
    assert cache.health().size == 2
    assert cache.latest() == snap3

    # snap1 should be evicted
    # Let's inspect the internal structure or series to verify snap1 is gone
    series = cache.series("cpu.util", 3)
    assert len(series) == 2
    assert series == [10.0, 10.0]


def test_cache_series() -> None:
    cache = RollingCache(maxlen=5)
    r1 = MetricReading("cpu.util", 10.0, MetricUnit.PERCENT, "test")
    r2 = MetricReading("cpu.util", 20.0, MetricUnit.PERCENT, "test")
    r3 = MetricReading("cpu.util", 30.0, MetricUnit.PERCENT, "test")

    cache.push(Snapshot(1.0, [r1]))
    cache.push(Snapshot(2.0, [r2]))
    cache.push(Snapshot(3.0, [r3]))

    # Request fewer values than exist
    assert cache.series("cpu.util", 2) == [20.0, 30.0]

    # Request more values than exist
    assert cache.series("cpu.util", 5) == [10.0, 20.0, 30.0]

    # Request non-existent metric
    assert cache.series("non_existent", 5) == []


def test_cache_concurrency() -> None:
    # Verify lock behavior under concurrent writes and reads
    cache = RollingCache(maxlen=50)

    def writer() -> None:
        for i in range(100):
            r = MetricReading("cpu.util", float(i), MetricUnit.PERCENT, "test")
            cache.push(Snapshot(time.time(), [r]))
            time.sleep(0.001)

    def reader() -> None:
        for _ in range(100):
            cache.latest()
            cache.series("cpu.util", 10)
            cache.health()
            time.sleep(0.001)

    threads = [
        Thread(target=writer),
        Thread(target=writer),
        Thread(target=reader),
        Thread(target=reader),
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # The test finishes successfully if no exceptions/deadlocks occur
    assert cache.health().size > 0
