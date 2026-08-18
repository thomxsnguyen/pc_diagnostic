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
        "pmu tcal": "system.temperature.cpu",
        "pmu2 tcal": "system.temperature.cpu",
        "soc die temperature": "system.temperature.cpu",
        **{f"pmu tdie{i}": "system.temperature.cpu" for i in range(1, 17)},
        **{f"pmu2 tdie{i}": "system.temperature.cpu" for i in range(1, 17)},
        "pmu tdie": "system.temperature.cpu",
        # GPU / Dev thermal zones
        "gpu die temperature": "system.temperature.gpu",
        **{f"pmu tdev{i}": "system.temperature.gpu" for i in range(1, 17)},
        **{f"pmu2 tdev{i}": "system.temperature.gpu" for i in range(1, 17)},
        "pmu tdev": "system.temperature.gpu",
        # Storage & Battery thermals
        "nand ch0 temp": "system.temperature.storage",
        "nand ch1 temp": "system.temperature.storage",
        "gas gauge battery": "system.temperature.battery",
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
