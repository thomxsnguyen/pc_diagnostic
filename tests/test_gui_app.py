import unittest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.gui.app import MainWindow
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.theme import ThemeManager, ThemeMode
from pc_diagnostic.models import CacheHealth


class TestGuiApp(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = RollingCache(maxlen=100)
        self.bridge = TelemetryBridge(self.cache)
        self.theme_manager = ThemeManager(ThemeMode.OLED_STEALTH)

    def test_main_window_lifecycle_headless(self) -> None:
        if not PYSIDE6_AVAILABLE:
            with self.assertRaises(RuntimeError):
                MainWindow(self.bridge, self.theme_manager)
            return

        from PySide6.QtWidgets import QApplication

        _app = QApplication.instance() or QApplication([])
        window = MainWindow(self.bridge, self.theme_manager)

        self.assertEqual(
            window.windowTitle(), "PC Diagnostic — Telemetry & AI Diagnostic Monitor"
        )
        self.assertEqual((window.width(), window.height()), (1280, 900))
        self.assertEqual(window.minimumSize(), window.maximumSize())
        self.assertEqual(window.stack.count(), 6)

        # Test switching views
        window._switch_view(2)
        self.assertEqual(window.stack.currentIndex(), 2)

        # Test cache health updates
        window._on_cache_health(
            CacheHealth(size=42, max_size=300, last_updated=100.0, age_s=0.5)
        )
        self.assertEqual(window.cache_badge.text(), "Cache: 42/300")


if __name__ == "__main__":
    unittest.main()
