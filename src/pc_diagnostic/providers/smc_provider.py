import json
import logging
import os
import subprocess
import sys
from typing import ClassVar

from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.providers.base import Provider

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
C_SOURCE_PATH = os.path.join(CURRENT_DIR, "smc_helper.c")
BINARY_PATH = os.path.join(CURRENT_DIR, "smc_helper")


class SmcProvider(Provider):
    # Map raw sensor names to canonical metric keys
    SENSOR_MAP: ClassVar[dict[str, str]] = {
        # CPU Die / Core temps (Intel & Apple Silicon PMU)
        "cpu die temperature": "system.temperature.cpu",
        "pmu tdie": "system.temperature.cpu",
        "pmu tdie1": "system.temperature.cpu",
        "pmu tdie2": "system.temperature.cpu",
        "pmu tdie3": "system.temperature.cpu",
        "pmu tdie4": "system.temperature.cpu",
        "pmu tdie5": "system.temperature.cpu",
        "pmu tdie6": "system.temperature.cpu",
        "pmu tdie7": "system.temperature.cpu",
        "pmu tdie8": "system.temperature.cpu",
        "pmu tdie9": "system.temperature.cpu",
        "pmu tdie10": "system.temperature.cpu",
        # GPU / Dev thermal zones
        "gpu die temperature": "system.temperature.gpu",
        "pmu tdev": "system.temperature.gpu",
        "pmu tdev1": "system.temperature.gpu",
        "pmu tdev2": "system.temperature.gpu",
        "pmu tdev3": "system.temperature.gpu",
        "pmu tdev4": "system.temperature.gpu",
        "pmu tdev5": "system.temperature.gpu",
        "pmu tdev6": "system.temperature.gpu",
        "pmu tdev7": "system.temperature.gpu",
        "pmu tdev8": "system.temperature.gpu",
    }

    def __init__(self) -> None:
        self._compile_helper()

    @property
    def name(self) -> str:
        return "smc"

    def available(self) -> bool:
        """Available on macOS and when helper binary has successfully compiled."""
        if sys.platform != "darwin":
            return False
        return os.path.exists(BINARY_PATH)

    def _compile_helper(self) -> None:
        """Attempt to compile native SMC helper tool if missing on macOS."""
        if sys.platform != "darwin":
            return
        if os.path.exists(BINARY_PATH):
            return

        logger.info(f"Compiling native SMC helper source: {C_SOURCE_PATH}")
        cmd = [
            "clang",
            "-O3",
            "-framework",
            "IOKit",
            "-framework",
            "CoreFoundation",
            C_SOURCE_PATH,
            "-o",
            BINARY_PATH,
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=5.0,
            )
            logger.info("Successfully compiled native macOS SMC helper.")
        except Exception as e:
            logger.warning(
                f"Failed to compile native macOS SMC helper: {e}. "
                "macOS thermal sensors will be unavailable."
            )

    def read(self) -> list[MetricReading]:
        if not self.available():
            return []

        readings: list[MetricReading] = []
        try:
            # Query native compiled C helper
            res = subprocess.run(
                [BINARY_PATH],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=True,
            )
            stdout = res.stdout.strip()
            if not stdout:
                return []

            sensors = json.loads(stdout)
            for sensor in sensors:
                sensor_name = str(sensor.get("sensor", ""))
                sensor_type = str(sensor.get("type", ""))
                value = float(sensor.get("value", 0.0))

                tags = {"sensor": sensor_name}

                if sensor_type == "Temperature":
                    # Match known mapped sensors
                    lower_name = sensor_name.lower()
                    if lower_name in self.SENSOR_MAP:
                        metric = self.SENSOR_MAP[lower_name]
                        readings.append(
                            MetricReading(
                                metric=metric,
                                value=value,
                                unit=MetricUnit.CELSIUS,
                                source=self.name,
                                tags=tags,
                            )
                        )
                elif sensor_type == "Fan":
                    readings.append(
                        MetricReading(
                            metric="system.fan.speed",
                            value=value,
                            unit=MetricUnit.RPM,
                            source=self.name,
                            tags=tags,
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("macOS native SMC helper query timed out.")
        except Exception as e:
            logger.warning(f"Failed to read macOS SMC helper: {e}")

        return readings
