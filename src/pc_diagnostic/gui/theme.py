from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ThemeMode(Enum):
    CYBERPUNK_DARK = "cyberpunk_dark"
    OLED_STEALTH = "oled_stealth"
    CLEAN_LIGHT = "clean_light"


@dataclass(frozen=True)
class ThemeTokens:
    name: str
    bg_window: str
    bg_sidebar: str
    bg_header: str
    bg_card: str
    bg_card_hover: str
    bg_input: str
    border_subtle: str
    border_card: str
    border_accent: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent_primary: str
    accent_secondary: str
    accent_glow: str
    status_normal: str
    status_warning: str
    status_critical: str
    status_info: str
    font_family: str = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
    font_family_mono: str = (
        "'SF Mono', Monaco, 'Cascadia Code', 'Courier New', monospace"
    )


CYBERPUNK_DARK = ThemeTokens(
    name="Cyberpunk Dark",
    bg_window="#0B0E14",
    bg_sidebar="#111620",
    bg_header="#151C29",
    bg_card="#151C29",
    bg_card_hover="#1B2435",
    bg_input="#0D121B",
    border_subtle="#202A3C",
    border_card="#253248",
    border_accent="#00E5FF",
    text_primary="#F0F6FC",
    text_secondary="#90A4AE",
    text_muted="#546E7A",
    accent_primary="#00E5FF",
    accent_secondary="#7C4DFF",
    accent_glow="rgba(0, 229, 255, 0.15)",
    status_normal="#00E676",
    status_warning="#FFD600",
    status_critical="#FF1744",
    status_info="#00B0FF",
)

OLED_STEALTH = ThemeTokens(
    name="OLED Stealth",
    bg_window="#000000",
    bg_sidebar="#050505",
    bg_header="#0A0A0A",
    bg_card="#0D0D0D",
    bg_card_hover="#171717",
    bg_input="#050505",
    border_subtle="#1F1F1F",
    border_card="#262626",
    border_accent="#00FF66",
    text_primary="#FFFFFF",
    text_secondary="#A3A3A3",
    text_muted="#525252",
    accent_primary="#00FF66",
    accent_secondary="#00CCFF",
    accent_glow="rgba(0, 255, 102, 0.12)",
    status_normal="#00FF66",
    status_warning="#FFB703",
    status_critical="#FF0055",
    status_info="#00E5FF",
)

CLEAN_LIGHT = ThemeTokens(
    name="Clean Light",
    bg_window="#F4F6F8",
    bg_sidebar="#FFFFFF",
    bg_header="#FFFFFF",
    bg_card="#FFFFFF",
    bg_card_hover="#F8FAFC",
    bg_input="#F1F5F9",
    border_subtle="#E2E8F0",
    border_card="#CBD5E1",
    border_accent="#0284C7",
    text_primary="#0F172A",
    text_secondary="#475569",
    text_muted="#94A3B8",
    accent_primary="#0284C7",
    accent_secondary="#6366F1",
    accent_glow="rgba(2, 132, 199, 0.10)",
    status_normal="#16A34A",
    status_warning="#D97706",
    status_critical="#DC2626",
    status_info="#0284C7",
)

THEMES: dict[ThemeMode, ThemeTokens] = {
    ThemeMode.CYBERPUNK_DARK: CYBERPUNK_DARK,
    ThemeMode.OLED_STEALTH: OLED_STEALTH,
    ThemeMode.CLEAN_LIGHT: CLEAN_LIGHT,
}


class ThemeManager:
    """Manages application theme state, color tokens, and QSS generation."""

    def __init__(self, default_mode: ThemeMode = ThemeMode.CYBERPUNK_DARK) -> None:
        self._mode = default_mode
        self._tokens = THEMES[default_mode]

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def tokens(self) -> ThemeTokens:
        return self._tokens

    def set_theme(self, mode: ThemeMode) -> str:
        """Switch active theme and return the generated QSS stylesheet."""
        self._mode = mode
        self._tokens = THEMES.get(mode, CYBERPUNK_DARK)
        return self.get_stylesheet()

    def get_stylesheet(self) -> str:
        """Generate polished Qt QSS stylesheet based on current tokens."""
        t = self._tokens
        return f"""
        /* ===================================================================
           PC Diagnostic Theme: {t.name}
           =================================================================== */

        QMainWindow, QWidget {{
            background-color: {t.bg_window};
            color: {t.text_primary};
            font-family: {t.font_family};
            font-size: 13px;
        }}

        /* --- Header & Top Bar --- */
        #top_header {{
            background-color: {t.bg_header};
            border-bottom: 1px solid {t.border_subtle};
            padding: 8px 16px;
        }}

        #app_title {{
            font-size: 15px;
            font-weight: 700;
            color: {t.text_primary};
            letter-spacing: 0.5px;
        }}

        #app_version_badge {{
            background-color: {t.bg_card};
            color: {t.accent_primary};
            border: 1px solid {t.border_subtle};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: 600;
            font-family: {t.font_family_mono};
        }}

        /* --- Sidebar Navigation --- */
        #sidebar {{
            background-color: {t.bg_sidebar};
            border-right: 1px solid {t.border_subtle};
            min-width: 200px;
            max-width: 220px;
            padding: 12px 8px;
        }}

        QPushButton.nav_button {{
            background-color: transparent;
            color: {t.text_secondary};
            border: none;
            border-radius: 6px;
            padding: 10px 14px;
            text-align: left;
            font-size: 13px;
            font-weight: 600;
        }}

        QPushButton.nav_button:hover {{
            background-color: {t.bg_card_hover};
            color: {t.text_primary};
        }}

        QPushButton.nav_button:checked, QPushButton.nav_button[active="true"] {{
            background-color: {t.accent_glow};
            color: {t.accent_primary};
            border-left: 3px solid {t.accent_primary};
            font-weight: 700;
        }}

        /* --- Glassmorphic Card Containers --- */
        QFrame.card {{
            background-color: {t.bg_card};
            border: 1px solid {t.border_card};
            border-radius: 10px;
            padding: 16px;
        }}

        QFrame.card:hover {{
            border: 1px solid {t.border_accent};
        }}

        QLabel.card_title {{
            font-size: 14px;
            font-weight: 700;
            color: {t.text_primary};
            margin-bottom: 8px;
        }}

        QLabel.card_subtitle {{
            font-size: 12px;
            color: {t.text_secondary};
        }}

        QLabel.metric_value {{
            font-size: 28px;
            font-weight: 800;
            font-family: {t.font_family_mono};
            color: {t.accent_primary};
        }}

        /* --- Status Indicators & Badges --- */
        QLabel.status_active {{
            background-color: rgba(0, 230, 118, 0.15);
            color: {t.status_normal};
            border: 1px solid {t.status_normal};
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        QLabel.status_stale {{
            background-color: rgba(255, 23, 68, 0.15);
            color: {t.status_critical};
            border: 1px solid {t.status_critical};
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        QLabel.alert_badge {{
            background-color: rgba(255, 214, 0, 0.15);
            color: {t.status_warning};
            border: 1px solid {t.status_warning};
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
        }}

        /* --- Action Buttons --- */
        QPushButton.primary_btn {{
            background-color: {t.accent_primary};
            color: {t.bg_window};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 700;
            font-size: 13px;
        }}

        QPushButton.primary_btn:hover {{
            background-color: {t.status_info};
        }}

        QPushButton.secondary_btn {{
            background-color: {t.bg_card};
            color: {t.text_primary};
            border: 1px solid {t.border_card};
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: 600;
        }}

        QPushButton.secondary_btn:hover {{
            background-color: {t.bg_card_hover};
            border-color: {t.border_accent};
        }}

        /* --- Progress Bars --- */
        QProgressBar {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            border-radius: 4px;
            text-align: center;
            font-family: {t.font_family_mono};
            font-size: 11px;
            font-weight: 600;
            color: {t.text_primary};
            min-height: 14px;
        }}

        QProgressBar::chunk {{
            background-color: {t.accent_primary};
            border-radius: 3px;
        }}

        /* --- Table Views & Headers --- */
        QTableView, QTableWidget {{
            background-color: {t.bg_card};
            border: 1px solid {t.border_card};
            border-radius: 8px;
            gridline-color: {t.border_subtle};
            selection-background-color: {t.accent_glow};
            selection-color: {t.accent_primary};
            font-size: 12px;
        }}

        QHeaderView::section {{
            background-color: {t.bg_header};
            color: {t.text_secondary};
            border: none;
            border-bottom: 1px solid {t.border_card};
            padding: 8px;
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
        }}

        /* --- Scrollbars --- */
        QScrollBar:vertical {{
            background-color: {t.bg_window};
            width: 8px;
            margin: 0;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {t.border_card};
            min-height: 24px;
            border-radius: 4px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {t.border_accent};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {t.bg_window};
            height: 8px;
            margin: 0;
            border-radius: 4px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {t.border_card};
            min-width: 24px;
            border-radius: 4px;
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* --- Tab Widget & Stacked Area --- */
        QStackedWidget {{
            background-color: {t.bg_window};
        }}

        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        """
