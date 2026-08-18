# Collector & Rolling Cache

The Collector and RollingCache form the core data pipeline. The collector runs in
a background thread, polling providers and pushing validated snapshots into the
cache. The cache provides thread-safe read access for consumers.

---

## Collector (`collector.py`)

### Responsibilities

1. Run the tick loop in a background thread (~1 second interval)
2. Iterate registered providers and call `read()` on each
3. Pass readings through the Normalizer validation gate
4. Assemble a `Snapshot` and push it to the cache
5. Run alert evaluation and dispatch after each push
6. Handle provider failures gracefully (try/except per provider)

### Tick Cycle

```python
while not stop_event.is_set():
    start_tick = time.time()
    snapshot_readings = []

    for provider in providers:
        if not provider.available():
            continue
        try:
            readings = provider.read()
        except Exception:
            log warning, continue          # one bad provider must never kill the loop

        valid_readings, dropped = Normalizer.validate(readings)
        snapshot_readings.extend(valid_readings)

    snapshot = Snapshot(timestamp=start_tick, readings=snapshot_readings)
    cache.push(snapshot)

    # Alert evaluation
    transitions = evaluator.evaluate(snapshot, cache.health().age_s, start_tick)
    dispatcher.dispatch(transitions, start_tick)

    # Sleep for remainder of interval
    elapsed = time.time() - start_tick
    stop_event.wait(timeout=max(0, interval - elapsed))
```

### Design Decisions

- **`threading.Thread(daemon=True)`** — dies automatically when the main process
  exits. No shutdown choreography needed beyond `stop_event.set()`.

- **`stop_event.wait(timeout=sleep_time)`** instead of `time.sleep()` — allows
  clean shutdown. When `stop()` sets the event, the wait returns immediately
  instead of blocking for the full interval.

- **Provider-level try/except** — this is the collector's primary reliability
  contract. A provider that throws (e.g., a sensor disappears mid-read) must
  never crash the collector. The snapshot for that tick simply has fewer readings.

- **Normalizer runs per-provider** — validation happens immediately after each
  provider's read, not after all providers. This means a malformed reading from
  one provider doesn't affect another's readings.

### Lifecycle

```python
collector = Collector(providers, cache, interval=1.0)
collector.start()   # spawns background thread
# ... app runs ...
collector.stop()    # sets stop_event, joins thread with 5s timeout
```

`start()` is idempotent — calling it while already running logs a warning and
returns. `stop()` is safe to call even if not started.

---

## Normalizer (`normalizer.py`)

A **stateless** validation gate at the boundary between providers and the cache.

### Validation Checks

| Check                  | Rule                                           | On Failure      |
|------------------------|------------------------------------------------|-----------------|
| Metric name pattern    | Must match `^[a-z0-9_]+(\.[a-z0-9_]+)+$`      | Drop + warn     |
| Value is finite        | Must be `int` or `float`, not NaN, not inf     | Drop + warn     |
| Source is non-empty    | Must be a non-empty string                     | Drop + warn     |

### Return Value

```python
def validate(readings: list[MetricReading]) -> tuple[list[MetricReading], int]:
    # Returns (valid_readings, dropped_count)
```

**Never raises.** Non-conforming readings are logged and silently discarded. This
matches the collector's philosophy: one bad reading must not poison the entire
snapshot.

### Value Normalization

Valid readings are re-constructed with `value=float(r.value)` and
`tags=dict(r.tags)` to ensure consistent types regardless of what the provider
passed in.

---

## RollingCache (`cache.py`)

### Implementation

```python
class RollingCache:
    def __init__(self, maxlen: int = 300):
        self._deque: deque[Snapshot] = deque(maxlen=maxlen)
        self._lock = Lock()
        self._last_updated: float = 0.0
```

`collections.deque(maxlen=N)` provides the "rolling" behavior: when full, the
oldest snapshot is silently evicted. No manual eviction, no memory growth.

### API

| Method                        | Returns               | Purpose                              |
|-------------------------------|-----------------------|--------------------------------------|
| `push(snapshot)`              | `None`                | Append snapshot (write side)         |
| `latest()`                    | `Snapshot \| None`    | Most recent tick's data              |
| `series(metric, n)`           | `list[float]`         | Last n values for a named metric     |
| `health()`                    | `CacheHealth`         | Observability: size, staleness       |

### Thread Safety

All methods acquire `self._lock` before accessing `self._deque`. One writer
(the collector thread), many readers (dashboard, health checks). A simple `Lock`
is sufficient — no need for `RWLock` or lock-free structures. The critical section
is tiny (appending to a deque), so contention is negligible.

### `series()` Implementation

Iterates the deque in reverse (most recent first), finds the first matching
reading per snapshot for the given metric name, collects up to `n` values, then
reverses to return chronological order. Used by sparklines in the dashboard.

### Default Configuration

- **maxlen=300** snapshots at 1s intervals = **5 minutes** of history
- Memory cost is negligible (~few MB for numeric data)
- The CrewAI evidence packet may want 5–15 minutes, so this may need tuning
