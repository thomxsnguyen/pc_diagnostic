import time
from collections import deque
from threading import Lock

from pc_diagnostic.models import CacheHealth, Snapshot


class RollingCache:
    def __init__(self, maxlen: int = 300) -> None:
        self._maxlen = maxlen
        self._lock = Lock()
        self._deque: deque[Snapshot] = deque(maxlen=maxlen)
        self._last_updated: float = 0.0

    def push(self, snapshot: Snapshot) -> None:
        """Push a new snapshot onto the cache, evicting the oldest if full."""
        with self._lock:
            self._deque.append(snapshot)
            self._last_updated = time.time()

    def latest(self) -> Snapshot | None:
        """Return the most recent snapshot, or None if the cache is empty."""
        with self._lock:
            if not self._deque:
                return None
            return self._deque[-1]

    def series(self, metric: str, n: int) -> list[float]:
        """Return the last n values for the specified metric name."""
        with self._lock:
            values: list[float] = []
            # Iterate backwards to get the most recent readings first, then reverse
            count = 0
            for snapshot in reversed(self._deque):
                if count >= n:
                    break
                # Find matching reading in this snapshot
                for reading in snapshot.readings:
                    if reading.metric == metric:
                        values.append(reading.value)
                        count += 1
                        break
            values.reverse()
            return values

    def health(self) -> CacheHealth:
        """Return diagnostic health metrics about the cache state."""
        with self._lock:
            size = len(self._deque)
            last_updated = self._last_updated
            age_s = (time.time() - last_updated) if last_updated > 0 else float("inf")

            return CacheHealth(
                size=size,
                max_size=self._maxlen,
                last_updated=last_updated,
                age_s=age_s,
            )
