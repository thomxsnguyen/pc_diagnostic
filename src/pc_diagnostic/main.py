import logging
import time

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.collector import Collector
from pc_diagnostic.providers.registry import register_providers

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Initializing PC Diagnostic Foundations (Phase 0)...")

    # 1. Register available providers (only StubProvider in Phase 0)
    providers = register_providers()
    logger.info(f"Registered providers: {[p.name for p in providers]}")

    # 2. Initialize rolling cache (default max size: 300)
    cache = RollingCache(maxlen=300)

    # 3. Initialize collector with 1s interval
    collector = Collector(providers=providers, cache=cache, interval=1.0)

    # 4. Start the background collection thread
    collector.start()

    logger.info("Running tick cycle monitor. Press Ctrl+C to exit.")
    try:
        # Run and print the latest snapshot and cache health every 2 seconds
        for _ in range(15):  # Run for ~30 seconds in non-interactive/exit-proof mode
            time.sleep(2.0)
            latest_snap = cache.latest()
            health = cache.health()

            logger.info(
                f"Cache Health: size={health.size}/{health.max_size}, "
                f"age={health.age_s:.2f}s"
            )
            if latest_snap:
                logger.info(f"Latest Snapshot at {latest_snap.timestamp:.2f}:")
                for reading in latest_snap.readings:
                    tags_str = f" {reading.tags}" if reading.tags else ""
                    logger.info(
                        f"  - {reading.metric}: {reading.value:.2f} "
                        f"{reading.unit.value} (source={reading.source}){tags_str}"
                    )
            else:
                logger.info("No snapshots collected yet.")
    except KeyboardInterrupt:
        logger.info("Interrupt received.")
    finally:
        # 5. Clean stop
        collector.stop()
        logger.info("PC Diagnostic stopped.")


if __name__ == "__main__":
    main()
