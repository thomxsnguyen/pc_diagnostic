"""Manual Phase 5.2 GUI benchmark; intentionally excluded from pytest discovery."""

from __future__ import annotations

import argparse
import json
import time
from typing import cast

import psutil  # type: ignore[import-untyped]
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.app import MainWindow
from pc_diagnostic.gui.bridge import TelemetryBridge
from pc_diagnostic.models import MetricReading, MetricUnit, Snapshot


class PaintCounter(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.frames = 0

    def eventFilter(  # noqa: N802
        self, watched: QObject, event: QEvent
    ) -> bool:
        if event.type() == QEvent.Type.Paint:
            self.frames += 1
        return super().eventFilter(watched, event)


def _snapshot(frame: int) -> Snapshot:
    cpu = float((frame * 3) % 100)
    memory = float(45 + ((frame // 10) % 20))
    return Snapshot(
        timestamp=time.time(),
        readings=[
            MetricReading(
                "cpu.utilization.total", cpu, MetricUnit.PERCENT, "benchmark"
            ),
            MetricReading(
                "memory.utilization", memory, MetricUnit.PERCENT, "benchmark"
            ),
            MetricReading(
                "system.temperature.cpu",
                55.0,
                MetricUnit.CELSIUS,
                "benchmark",
            ),
            MetricReading(
                "process.cpu_percent",
                12.0,
                MetricUnit.PERCENT,
                "benchmark",
                {"pid": "1", "name": "benchmark", "type": "cpu_top"},
            ),
        ],
    )


def run_benchmark(duration_s: float) -> dict[str, float | bool]:
    app = cast(QApplication | None, QApplication.instance()) or QApplication([])
    cache = RollingCache(maxlen=300)
    bridge = TelemetryBridge(cache)
    window = MainWindow(bridge)
    window.show()

    counter = PaintCounter()
    window.overview_view.chart.installEventFilter(counter)
    process = psutil.Process()
    maximum_rss = process.memory_info().rss
    frame = 0
    start_time = time.perf_counter()
    start_cpu = sum(process.cpu_times()[:2])

    timer = QTimer()
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.setInterval(16)

    def update_frame() -> None:
        nonlocal frame, maximum_rss
        frame += 1
        snapshot = _snapshot(frame)
        cache.push(snapshot)
        bridge._on_tick()
        maximum_rss = max(maximum_rss, process.memory_info().rss)
        if time.perf_counter() - start_time >= duration_s:
            timer.stop()
            app.quit()

    timer.timeout.connect(update_frame)
    timer.start()
    app.exec()

    elapsed = time.perf_counter() - start_time
    cpu_time = sum(process.cpu_times()[:2]) - start_cpu
    results: dict[str, float | bool] = {
        "duration_s": round(elapsed, 3),
        "requested_updates": frame,
        "painted_frames": counter.frames,
        "fps": round(counter.frames / elapsed, 2),
        "cpu_percent": round((cpu_time / elapsed) * 100.0, 2),
        "rss_mb": round(maximum_rss / (1024.0 * 1024.0), 2),
    }
    results["fps_pass"] = float(results["fps"]) >= 59.0
    results["cpu_pass"] = float(results["cpu_percent"]) < 3.5
    results["memory_pass"] = float(results["rss_mb"]) < 85.0
    window.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.duration), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
