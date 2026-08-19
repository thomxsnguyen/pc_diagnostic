import time
import unittest

from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE
from pc_diagnostic.gui.components import (
    RadialGaugeWidget,
    StorageNetworkCard,
    TimeSeriesChart,
    TopProcessesPreview,
)
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class TestGuiComponents(unittest.TestCase):
    def test_radial_gauge_values_and_clamping(self) -> None:
        gauge = RadialGaugeWidget(title="CPU Load", unit="%", min_val=0, max_val=100)
        self.assertEqual(gauge.title, "CPU Load")
        self.assertEqual(gauge.value, 0.0)

        gauge.set_value(45.0, subtitle="2.4 GHz")
        self.assertEqual(gauge.value, 45.0)
        self.assertEqual(gauge._subtitle, "2.4 GHz")

        # Test upper clamp
        gauge.set_value(150.0)
        self.assertEqual(gauge.value, 100.0)

        # Test lower clamp
        gauge.set_value(-20.0)
        self.assertEqual(gauge.value, 0.0)

    def test_timeseries_chart_buffer(self) -> None:
        chart = TimeSeriesChart(maxlen=60)
        chart.add_point("cpu.utilization.total", 50.0)
        chart.add_point("cpu.utilization.total", 75.0)

        self.assertEqual(len(chart._series["cpu.utilization.total"]["values"]), 2)
        self.assertEqual(
            list(chart._series["cpu.utilization.total"]["values"]), [50.0, 75.0]
        )

        # Test visibility toggle
        chart.set_series_visibility("cpu.utilization.total", False)
        self.assertFalse(chart._series["cpu.utilization.total"]["visible"])

    def test_timeseries_chart_snapshot_update(self) -> None:
        chart = TimeSeriesChart(maxlen=60)
        readings = [
            MetricReading(
                metric="cpu.utilization.total",
                value=30.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="memory.utilization",
                value=60.0,
                unit=MetricUnit.PERCENT,
                source="test",
            ),
            MetricReading(
                metric="disk.read_bytes_per_sec",
                value=10 * 1024 * 1024,
                unit=MetricUnit.BYTES_PER_SEC,
                source="test",
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)
        chart.update_from_snapshot(snap)

        self.assertEqual(len(chart._series["cpu.utilization.total"]["values"]), 1)
        self.assertEqual(chart._series["cpu.utilization.total"]["values"][0], 30.0)
        self.assertEqual(chart._series["memory.utilization"]["values"][0], 60.0)
        self.assertEqual(
            chart._series["disk.read_bytes_per_sec"]["values"][0], 10.0
        )  # Converted to MB/s

    def test_storage_network_card_update(self) -> None:
        card = StorageNetworkCard()
        readings = [
            MetricReading(
                metric="disk.usage.used",
                value=12 * 1_000_000_000,
                unit=MetricUnit.BYTES,
                source="test",
                tags={"mountpoint": "/"},
            ),
            MetricReading(
                metric="disk.usage.total",
                value=1000 * 1_000_000_000,
                unit=MetricUnit.BYTES,
                source="test",
                tags={"mountpoint": "/"},
            ),
            MetricReading(
                metric="disk.usage.percent",
                value=1.2,
                unit=MetricUnit.PERCENT,
                source="test",
                tags={"mountpoint": "/"},
            ),
            MetricReading(
                metric="disk.usage.used",
                value=500 * 1_000_000_000,
                unit=MetricUnit.BYTES,
                source="test",
                tags={"mountpoint": "/System/Volumes/Data"},
            ),
            MetricReading(
                metric="disk.usage.total",
                value=1000 * 1_000_000_000,
                unit=MetricUnit.BYTES,
                source="test",
                tags={"mountpoint": "/System/Volumes/Data"},
            ),
            MetricReading(
                metric="disk.usage.percent",
                value=50.0,
                unit=MetricUnit.PERCENT,
                source="test",
                tags={"mountpoint": "/System/Volumes/Data"},
            ),
            MetricReading(
                metric="disk.io.read_bytes",
                value=5 * 1024 * 1024,
                unit=MetricUnit.BYTES_PER_SEC,
                source="test",
            ),
            MetricReading(
                metric="disk.io.write_bytes",
                value=2 * 1024 * 1024,
                unit=MetricUnit.BYTES_PER_SEC,
                source="test",
            ),
            MetricReading(
                metric="network.io.bytes_recv",
                value=1024 * 1024,
                unit=MetricUnit.BYTES_PER_SEC,
                source="test",
            ),
            MetricReading(
                metric="network.io.bytes_sent",
                value=512 * 1024,
                unit=MetricUnit.BYTES_PER_SEC,
                source="test",
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)
        card.update_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertIn("500.0 GB", card.lbl_storage_used.text())
            self.assertIn("1000.0 GB", card.lbl_storage_used.text())
            self.assertEqual(card.storage_bar.value(), 50)
            self.assertIn("5.0 MB/s", card.lbl_disk_read.text())
            self.assertIn("2.0 MB/s", card.lbl_disk_write.text())
            self.assertIn("1.0 MB/s", card.lbl_net_rx.text())
            self.assertIn("512.0 KB/s", card.lbl_net_tx.text())

    def test_top_processes_preview_update(self) -> None:
        procs_card = TopProcessesPreview()
        readings = [
            MetricReading(
                metric="process.cpu",
                value=24.5,
                unit=MetricUnit.PERCENT,
                source="test",
                tags={
                    "type": "cpu_top",
                    "pid": "1234",
                    "name": "python",
                    "mem_str": "250 MB",
                },
            ),
            MetricReading(
                metric="process.cpu",
                value=12.0,
                unit=MetricUnit.PERCENT,
                source="test",
                tags={
                    "type": "cpu_top",
                    "pid": "5678",
                    "name": "chrome",
                    "mem_str": "1.2 GB",
                },
            ),
        ]
        snap = Snapshot(timestamp=time.time(), readings=readings)
        procs_card.update_snapshot(snap)

        if PYSIDE6_AVAILABLE:
            self.assertEqual(procs_card.table.item(0, 0).text(), "1234")
            self.assertEqual(procs_card.table.item(0, 1).text(), "python")
            self.assertEqual(procs_card.table.item(0, 2).text(), "24.5%")
            self.assertEqual(procs_card.table.item(0, 3).text(), "250 MB")

    def test_top_processes_preview_pairs_cpu_and_memory_readings(self) -> None:
        procs_card = TopProcessesPreview()
        readings = [
            MetricReading(
                metric="process.cpu_percent",
                value=78.0,
                unit=MetricUnit.PERCENT,
                source="test",
                tags={"type": "cpu_top", "pid": "60359", "name": "python3.13"},
            ),
            MetricReading(
                metric="process.memory.used",
                value=481427456.0,
                unit=MetricUnit.BYTES,
                source="test",
                tags={"type": "cpu_top", "pid": "60359", "name": "python3.13"},
            ),
        ]

        procs_card.update_snapshot(Snapshot(timestamp=time.time(), readings=readings))

        if PYSIDE6_AVAILABLE:
            self.assertEqual(procs_card.table.item(0, 0).text(), "60359")
            self.assertEqual(procs_card.table.item(0, 2).text(), "78.0%")
            self.assertEqual(procs_card.table.item(0, 3).text(), "459.1 MB")
            self.assertEqual(procs_card.table.item(1, 0).text(), "—")


if __name__ == "__main__":
    unittest.main()
