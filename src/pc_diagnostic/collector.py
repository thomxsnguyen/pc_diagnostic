import logging
import threading
import time

from pc_diagnostic.alerts.dispatcher import AlertDispatcher
from pc_diagnostic.alerts.evaluator import AlertEvaluator
from pc_diagnostic.alerts.models import DEFAULT_ALERT_RULES
from pc_diagnostic.cache import RollingCache
from pc_diagnostic.models import Snapshot
from pc_diagnostic.normalizer import Normalizer
from pc_diagnostic.providers.base import Provider

logger = logging.getLogger(__name__)


class Collector:
    def __init__(
        self,
        providers: list[Provider],
        cache: RollingCache,
        interval: float = 1.0,
    ) -> None:
        self._providers = providers
        self._cache = cache
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Initialize Alert Evaluator and Dispatcher
        self.evaluator = AlertEvaluator(DEFAULT_ALERT_RULES)
        self.dispatcher = AlertDispatcher()

    def start(self) -> None:
        """Start the background collection thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Collector thread is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="CollectorThread", daemon=True
        )
        self._thread.start()
        logger.info("Collector thread started.")

    def stop(self) -> None:
        """Stop the background collection thread and wait for it to exit."""
        if self._thread is None:
            return

        logger.info("Stopping collector thread...")
        self._stop_event.set()
        self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("Collector thread stopped.")

    def _run_loop(self) -> None:
        """Main execution loop for the background collection thread."""
        while not self._stop_event.is_set():
            start_tick = time.time()
            snapshot_readings = []

            for provider in self._providers:
                if not provider.available():
                    continue

                try:
                    readings = provider.read()
                except Exception as e:
                    logger.exception(
                        f"Error reading from provider '{provider.name}': {e}"
                    )
                    continue

                # Pass through the stateless Normalizer validation boundary
                valid_readings, dropped_count = Normalizer.validate(readings)
                if dropped_count > 0:
                    logger.warning(
                        f"Normalizer dropped {dropped_count} readings "
                        f"from provider '{provider.name}'"
                    )

                snapshot_readings.extend(valid_readings)

            # Package and push the snapshot to the cache
            snapshot = Snapshot(timestamp=start_tick, readings=snapshot_readings)
            self._cache.push(snapshot)

            # Evaluate alert rules against current snapshot and cache age
            health = self._cache.health()
            transitions = self.evaluator.evaluate(snapshot, health.age_s, start_tick)
            self.dispatcher.dispatch(transitions, start_tick)

            # Calculate sleep time to maintain interval,
            # adjusting for execution duration
            elapsed = time.time() - start_tick
            sleep_time = max(0.0, self._interval - elapsed)

            # Wait on stop_event (returns True if set, False if timeout)
            if self._stop_event.wait(timeout=sleep_time):
                break
