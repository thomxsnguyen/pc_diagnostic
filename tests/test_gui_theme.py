import unittest

from pc_diagnostic.gui.theme import (
    CLEAN_LIGHT,
    OLED_STEALTH,
    ThemeManager,
    ThemeMode,
)


class TestThemeManager(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = ThemeManager(ThemeMode.OLED_STEALTH)

    def test_default_theme(self) -> None:
        self.assertEqual(self.manager.mode, ThemeMode.OLED_STEALTH)
        self.assertEqual(self.manager.tokens, OLED_STEALTH)

    def test_switch_to_oled(self) -> None:
        qss = self.manager.set_theme(ThemeMode.OLED_STEALTH)
        self.assertEqual(self.manager.mode, ThemeMode.OLED_STEALTH)
        self.assertEqual(self.manager.tokens, OLED_STEALTH)
        self.assertIn(OLED_STEALTH.bg_window, qss)
        self.assertIn("OLED Stealth", qss)

    def test_switch_to_clean_light(self) -> None:
        qss = self.manager.set_theme(ThemeMode.CLEAN_LIGHT)
        self.assertEqual(self.manager.mode, ThemeMode.CLEAN_LIGHT)
        self.assertEqual(self.manager.tokens, CLEAN_LIGHT)
        self.assertIn("#FFFFFF", qss)
        self.assertIn("Clean Light", qss)

    def test_stylesheet_contains_essential_selectors(self) -> None:
        qss = self.manager.get_stylesheet()
        essential_selectors = [
            "QMainWindow",
            "#top_header",
            "#app_title",
            "#sidebar",
            "QPushButton.nav_button",
            "QFrame.card",
            "QLabel.metric_value",
            "QProgressBar",
            "QScrollBar:vertical",
        ]
        for sel in essential_selectors:
            self.assertIn(
                sel, qss, f"Selector '{sel}' missing from generated stylesheet"
            )


if __name__ == "__main__":
    unittest.main()
