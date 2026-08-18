from __future__ import annotations

import argparse
import logging
import sys
import time

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.collector import Collector
from pc_diagnostic.dashboard import TerminalDashboard
from pc_diagnostic.gui import PYSIDE6_AVAILABLE, ThemeMode, run_gui
from pc_diagnostic.providers.registry import register_providers

logger = logging.getLogger("pc_diagnostic")


def setup_logging(log_mode: bool) -> None:
    """Setup logging configuration based on execution mode."""
    # Clear any existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    if log_mode:
        # Standard stdout logging for debug/log fallback mode
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
        )
    else:
        # File-only logging for GUI/TUI dashboard mode to avoid display pollution
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            filename="pc_diagnostic.log",
            filemode="a",
        )


def main() -> None:
    # 1. Command-line interface parsing
    parser = argparse.ArgumentParser(
        description="A cross-platform PC telemetry monitor and AI-diagnostic tool"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--gui",
        action="store_true",
        help="Run desktop GUI application (default if display is available)",
    )
    mode_group.add_argument(
        "--tui",
        "--cli",
        action="store_true",
        help="Run interactive terminal dashboard (Rich TUI)",
    )
    mode_group.add_argument(
        "--log",
        "--no-dashboard",
        action="store_true",
        help="Run in headless stdout log fallback mode",
    )

    parser.add_argument(
        "--theme",
        type=str,
        choices=["cyberpunk_dark", "oled_stealth", "clean_light"],
        default="cyberpunk_dark",
        help="GUI color theme (default: cyberpunk_dark)",
    )
    parser.add_argument(
        "--refresh-rate",
        type=float,
        default=1.0,
        help="Dashboard refresh rate in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    # Determine execution mode
    is_tty = sys.stdout.isatty()
    run_in_log_mode = args.log or (not is_tty and not args.gui)
    run_in_tui_mode = args.tui
    run_in_gui_mode = args.gui or (not run_in_log_mode and not run_in_tui_mode and PYSIDE6_AVAILABLE)

    setup_logging(run_in_log_mode)
    logger.info("Initializing PC Diagnostic...")

    # 2. Register available providers
    providers = register_providers()
    logger.info(f"Registered providers: {[p.name for p in providers]}")

    # 3. Initialize rolling cache (default max size: 300)
    cache = RollingCache(maxlen=300)

    # 4. Initialize collector with 1.0s interval
    collector = Collector(providers=providers, cache=cache, interval=1.0)

    # 5. Start the background collection thread
    collector.start()

    try:
        if run_in_log_mode:
            logger.info("Running tick cycle monitor. Press Ctrl+C to exit.")
            while True:
                time.sleep(2.0)
                latest_snap = cache.latest()
                health = cache.health()

                logger.info(
                    f"Cache Health: size={health.size}/{health.max_size}, "
                    f"age={health.age_s:.2f}s"
                )
                if latest_snap:
                    logger.info(f"Latest Snapshot at {latest_snap.timestamp:.2f}:")
                    for reading in latest_snap.readings[:10]:
                        tags_str = f" {reading.tags}" if reading.tags else ""
                        logger.info(
                            f"  - {reading.metric}: {reading.value:.2f} "
                            f"{reading.unit.value} (source={reading.source}){tags_str}"
                        )
                    if len(latest_snap.readings) > 10:
                        logger.info(
                            f"  ... and {len(latest_snap.readings) - 10} more readings"
                        )
                else:
                    logger.info("No snapshots collected yet.")

        elif run_in_gui_mode and PYSIDE6_AVAILABLE:
            # Desktop GUI Mode
            theme_mode = ThemeMode(args.theme)
            run_gui(
                cache=cache,
                dispatcher=collector.dispatcher,
                refresh_rate=args.refresh_rate,
                theme_mode=theme_mode,
            )
        else:
            # Terminal Dashboard mode (TUI)
            dashboard = TerminalDashboard(cache, collector.dispatcher)
            dashboard.run(refresh_rate=args.refresh_rate)

    except KeyboardInterrupt:
        logger.info("Interrupt received.")
    finally:
        # 6. Clean stop
        collector.stop()
        logger.info("PC Diagnostic stopped.")


if __name__ == "__main__":
    main()
