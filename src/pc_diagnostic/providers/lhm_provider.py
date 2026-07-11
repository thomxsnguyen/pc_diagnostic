import json
import logging
import subprocess
import sys
from typing import Any

from pc_diagnostic.models import MetricReading, MetricUnit
from pc_diagnostic.providers.base import Provider

logger = logging.getLogger(__name__)


class LhmProvider(Provider):
    @property
    def name(self) -> str:
        return "lhm"

    def available(self) -> bool:
        """Available only on Windows platforms."""
        return sys.platform == "win32"

    def _query_wmi(self) -> list[dict[str, Any]]:
        """Query LibreHardwareMonitor WMI sensors namespace using PowerShell."""
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance -Namespace root\\LibreHardwareMonitor -ClassName Sensor | "
            "Select-Object Name, SensorType, Value, Identifier | "
            "ConvertTo-Json -Compress",
        ]
        try:
            # Short timeout to avoid blocking collector thread
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1.5,
                check=True,
            )
            stdout = res.stdout.strip()
            if not stdout:
                return []

            data = json.loads(stdout)
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
            return []
        except subprocess.TimeoutExpired:
            logger.warning("LibreHardwareMonitor WMI query timed out.")
            return []
        except Exception as e:
            # Silently log if namespace is absent or LHM is not running
            logger.debug(f"LibreHardwareMonitor WMI query failed: {e}")
            return []

    def read(self) -> list[MetricReading]:
        readings: list[MetricReading] = []
        sensors = self._query_wmi()

        for sensor in sensors:
            try:
                name = str(sensor.get("Name", "unknown"))
                sensor_type = str(sensor.get("SensorType", ""))
                value = float(sensor.get("Value", 0.0))
                identifier = str(sensor.get("Identifier", ""))

                tags = {"sensor": name, "identifier": identifier}

                if sensor_type == "Temperature":
                    # Determine whether it's CPU or GPU based on Name / Identifier
                    name_lower = name.lower()
                    id_lower = identifier.lower()
                    if "cpu" in name_lower or "cpu" in id_lower:
                        metric = "system.temperature.cpu"
                    elif "gpu" in name_lower or "gpu" in id_lower:
                        metric = "system.temperature.gpu"
                    else:
                        metric = "system.temperature.other"

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

                elif sensor_type == "Voltage":
                    name_lower = name.lower()
                    id_lower = identifier.lower()
                    if "cpu" in name_lower or "cpu" in id_lower:
                        metric = "system.voltage.cpu"
                    else:
                        metric = "system.voltage.other"

                    readings.append(
                        MetricReading(
                            metric=metric,
                            value=value,
                            unit=MetricUnit.VOLTS,
                            source=self.name,
                            tags=tags,
                        )
                    )
            except Exception as e:
                logger.warning(f"Error parsing LHM sensor reading: {e}")
                continue

        return readings
