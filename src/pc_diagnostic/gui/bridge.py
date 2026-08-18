from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pc_diagnostic.alerts.dispatcher import AlertDispatcher
    from pc_diagnostic.alerts.models import Incident
    from pc_diagnostic.cache import RollingCache
    from pc_diagnostic.models import CacheHealth, Snapshot

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import QObject, QTimer, Signal

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

    # Fallback dummy class and decorator for non-GUI environments
    class QObject:  # type: ignore[no-redef]
        def __init__(self, parent: Any = None) -> None:
            self._parent = parent

    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args: Any) -> None:
            self._callbacks: list[Any] = []

        def connect(self, slot: Any) -> None:
            self._callbacks.append(slot)

        def emit(self, *args: Any) -> None:
            for cb in self._callbacks:
                try:
                    cb(*args)
                except Exception as e:
                    logger.exception(f"Error in signal callback: {e}")


class TelemetryBridge(QObject):
    """Thread-safe event and telemetry bridge connecting the backend telemetry pipeline

    to Qt's reactive UI event loop.
    """

    snapshot_updated = Signal(object)
    alert_triggered = Signal(object)
    cache_health_changed = Signal(object)
    collector_status_changed = Signal(bool)
    diagnosis_completed = Signal(str)

    def __init__(
        self,
        cache: RollingCache,
        dispatcher: AlertDispatcher | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._cache = cache
        self._dispatcher = dispatcher
        self._timer: Any = None
        self._is_active: bool = False
        self._last_snapshot_ts: float = 0.0

        if PYSIDE6_AVAILABLE:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_tick)

    @property
    def cache(self) -> RollingCache:
        return self._cache

    @property
    def dispatcher(self) -> AlertDispatcher | None:
        return self._dispatcher

    def start(self, interval_ms: int = 1000) -> None:
        """Start the periodic UI state synchronization timer."""
        self._is_active = True
        if self._timer is not None:
            self._timer.start(interval_ms)
            # Trigger immediate first tick
            self._on_tick()
        logger.debug(f"TelemetryBridge started with interval {interval_ms}ms")

    def stop(self) -> None:
        """Stop the UI update timer."""
        self._is_active = False
        if self._timer is not None:
            self._timer.stop()
        logger.debug("TelemetryBridge stopped")

    def _on_tick(self) -> None:
        """Internal timer callback executing on the Qt main UI thread."""
        try:
            # 1. Fetch latest snapshot
            latest_snap = self._cache.latest()
            if latest_snap is not None:
                self._last_snapshot_ts = latest_snap.timestamp
                self.snapshot_updated.emit(latest_snap)

            # 2. Fetch cache health
            health = self._cache.health()
            self.cache_health_changed.emit(health)

            # 3. Determine and emit collector active/stale status
            is_healthy = health.age_s <= 2.0
            self.collector_status_changed.emit(is_healthy)

        except Exception as e:
            logger.exception(f"Error during TelemetryBridge tick: {e}")

    def get_latest_snapshot(self) -> Snapshot | None:
        """Thread-safe getter for the most recent snapshot."""
        return self._cache.latest()

    def get_series(self, metric: str, n: int = 60) -> list[float]:
        """Thread-safe getter for a historical metric time-series."""
        return self._cache.series(metric, n)

    def get_health(self) -> CacheHealth:
        """Thread-safe getter for cache capacity and age health metrics."""
        return self._cache.health()

    def emit_alert(self, incident: Incident) -> None:
        """Emit an alert triggered event across Qt widgets."""
        self.alert_triggered.emit(incident)

    def emit_diagnosis(self, report_markdown: str) -> None:
        """Emit a completed AI diagnostic markdown report."""
        self.diagnosis_completed.emit(report_markdown)
