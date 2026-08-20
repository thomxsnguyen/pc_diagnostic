from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ThemeMode(Enum):
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


OLED_STEALTH = ThemeTokens(
    name="OLED Stealth",
    bg_window="#0B0C0E",
    bg_sidebar="#101114",
    bg_header="#121417",
    bg_card="#15171B",
    bg_card_hover="#1C1F24",
    bg_input="#0F1013",
    border_subtle="#24272D",
    border_card="#30343B",
    border_accent="#3B82F6",
    text_primary="#ECEEF1",
    text_secondary="#A6ABB3",
    text_muted="#6F7680",
    accent_primary="#3B82F6",
    accent_secondary="#93C5FD",
    accent_glow="rgba(59, 130, 246, 0.08)",
    status_normal="#34C759",
    status_warning="#F5A524",
    status_critical="#F05252",
    status_info="#60A5FA",
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
    ThemeMode.OLED_STEALTH: OLED_STEALTH,
    ThemeMode.CLEAN_LIGHT: CLEAN_LIGHT,
}


class ThemeManager:
    """Manages application theme state, color tokens, and QSS generation."""

    def __init__(self, default_mode: ThemeMode = ThemeMode.OLED_STEALTH) -> None:
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
        self._tokens = THEMES.get(mode, OLED_STEALTH)
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
        }}

        #header_controls {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            border-radius: 6px;
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
            background-color: {t.bg_card_hover};
            color: {t.accent_primary};
            border-left: 2px solid {t.accent_primary};
            font-weight: 700;
        }}

        /* --- Card Containers --- */
        QFrame.card {{
            background-color: {t.bg_card};
            border: 1px solid {t.border_card};
            border-radius: 6px;
            padding: 16px;
        }}

        QFrame.card:hover {{
            border: 1px solid {t.border_card};
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
            background-color: transparent;
            color: {t.status_normal};
            border: none;
            padding: 3px 9px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        QLabel.status_stale {{
            background-color: transparent;
            color: {t.status_critical};
            border: none;
            padding: 3px 9px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        QLabel.alert_badge {{
            background-color: transparent;
            color: {t.text_muted};
            border: none;
            padding: 3px 9px;
            font-size: 11px;
            font-weight: 600;
        }}

        QLabel.alert_badge[active="true"] {{
            color: {t.status_critical};
            font-weight: 700;
        }}

        #cache_badge {{
            background-color: transparent;
            color: {t.text_secondary};
            border: none;
            padding: 3px 9px;
            font-size: 11px;
            font-weight: 600;
        }}

        QComboBox#theme_combo {{
            background-color: {t.bg_input};
            color: {t.text_primary};
            border: 1px solid {t.border_subtle};
            border-radius: 4px;
            padding: 4px 28px 4px 10px;
            min-width: 92px;
            font-size: 11px;
            font-weight: 600;
        }}

        QComboBox#theme_combo:hover {{
            background-color: {t.bg_card_hover};
            border-color: {t.border_card};
        }}

        QComboBox#theme_combo:focus,
        QComboBox#theme_combo:on {{
            border-color: {t.border_accent};
        }}

        /* --- Action Buttons --- */
        QPushButton.primary_btn {{
            background-color: {t.accent_primary};
            color: {t.bg_window};
            border: none;
            border-radius: 4px;
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
            border-radius: 4px;
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
            border-radius: 4px;
            gridline-color: {t.border_subtle};
            selection-background-color: {t.bg_card_hover};
            selection-color: {t.text_primary};
            font-size: 12px;
        }}

        /* --- AI Studio --- */
        #studio_page_title, #overview_page_title, #process_page_title,
        #sensors_page_title, #alerts_page_title, #settings_page_title {{
            background-color: transparent;
            color: {t.text_primary};
            font-size: 18px;
            font-weight: 700;
        }}

        #studio_page_subtitle, #studio_section_subtitle,
        #overview_page_subtitle, #overview_section_subtitle,
        #process_page_subtitle, #process_section_subtitle,
        #sensors_page_subtitle, #sensors_section_subtitle,
        #alerts_page_subtitle, #alerts_section_subtitle,
        #settings_page_subtitle, #settings_section_subtitle,
        #recommendation_categories {{
            background-color: transparent;
            color: {t.text_secondary};
            font-size: 11px;
        }}

        #studio_section_title, #overview_section_title, #process_section_title,
        #sensors_section_title, #alerts_section_title, #settings_section_title {{
            background-color: transparent;
            color: {t.text_primary};
            font-size: 13px;
            font-weight: 700;
        }}

        #studio_summary_title {{
            background-color: transparent;
            color: {t.text_primary};
            font-size: 11px;
            font-weight: 700;
        }}

        #recommendation_panel {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            border-radius: 4px;
        }}

        QTreeWidget#evidence_tree, QTextBrowser#report_view {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            border-radius: 4px;
            padding: 4px;
        }}

        QProgressBar#studio_progress {{
            background-color: {t.border_subtle};
            border: none;
            border-radius: 2px;
            min-height: 4px;
            max-height: 4px;
        }}

        QProgressBar#studio_progress::chunk {{
            background-color: {t.accent_primary};
            border-radius: 2px;
        }}

        /* --- Overview --- */
        QWidget#overview_root QLabel {{
            background-color: transparent;
        }}

        QScrollArea#overview_scroll {{
            background-color: transparent;
            border: none;
        }}

        QWidget#overview_root QFrame.card {{
            background-color: {t.bg_card};
            border: 1px solid {t.border_card};
            border-radius: 6px;
            padding: 0;
        }}

        #overview_meta_label {{
            color: {t.text_muted};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.6px;
        }}

        #overview_meta_primary {{
            color: {t.text_primary};
            font-size: 12px;
            font-weight: 600;
        }}

        #overview_meta_secondary {{
            color: {t.text_secondary};
            font-size: 11px;
        }}

        #overview_header_divider {{
            color: {t.border_subtle};
            background-color: {t.border_subtle};
            max-width: 1px;
        }}

        #overview_group_title {{
            color: {t.text_primary};
            font-size: 12px;
            font-weight: 700;
        }}

        #overview_detail_label {{
            color: {t.text_secondary};
            font-size: 11px;
        }}

        #overview_rate_primary, #overview_rate_secondary {{
            font-size: 12px;
            font-weight: 600;
        }}

        #overview_rate_primary {{
            color: {t.accent_primary};
        }}

        #overview_rate_secondary {{
            color: {t.accent_secondary};
        }}

        #overview_section_divider {{
            color: {t.border_subtle};
            background-color: {t.border_subtle};
            max-height: 1px;
        }}

        QProgressBar#overview_storage_bar {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            min-height: 12px;
            max-height: 12px;
        }}

        QTableWidget#overview_processes_table {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            font-size: 11px;
        }}

        /* --- Processes --- */
        #process_page_title, #process_page_subtitle,
        #process_section_title, #process_section_subtitle,
        #process_stat_label, #process_stat_value, #process_count {{
            background-color: transparent;
        }}

        #process_stat_label {{
            color: {t.text_muted};
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.6px;
        }}

        #process_stat_value {{
            color: {t.text_primary};
            font-size: 12px;
            font-weight: 600;
        }}

        #process_count {{
            color: {t.text_secondary};
            border: 1px solid {t.border_card};
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        }}

        QLineEdit#process_search {{
            background-color: {t.bg_input};
            color: {t.text_primary};
            border: 1px solid {t.border_subtle};
            border-radius: 4px;
            padding: 7px 10px;
            selection-background-color: {t.accent_primary};
        }}

        QLineEdit#process_search:focus {{
            border-color: {t.border_accent};
        }}

        QPushButton#process_pause[paused="true"] {{
            color: {t.status_warning};
            border-color: {t.status_warning};
        }}

        /* --- Sensors --- */
        QScrollArea#sensors_scroll {{
            background-color: transparent;
            border: none;
        }}

        QWidget#sensors_root QLabel {{
            background-color: transparent;
        }}

        #sensors_page_title, #sensors_page_subtitle,
        #sensors_section_title, #sensors_section_subtitle {{
            background-color: transparent;
        }}

        #sensors_count {{
            color: {t.text_secondary};
            border: 1px solid {t.border_card};
            border-radius: 4px;
            padding: 3px 9px;
            font-size: 11px;
            font-weight: 600;
        }}

        #sensors_group_title {{
            color: {t.text_primary};
            font-size: 12px;
            font-weight: 700;
        }}

        #sensors_empty_state {{
            color: {t.text_muted};
            font-size: 11px;
        }}

        #sensor_core_name {{
            color: {t.text_secondary};
            font-size: 11px;
            font-weight: 600;
        }}

        #sensor_core_value {{
            color: {t.text_primary};
            font-size: 11px;
            font-weight: 700;
        }}

        #sensors_divider {{
            color: {t.border_subtle};
            background-color: {t.border_subtle};
            max-height: 1px;
        }}

        QTableWidget#sensors_thermal_table {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            font-size: 11px;
        }}

        /* --- Alerts --- */
        QScrollArea#alerts_scroll {{
            background-color: transparent;
            border: none;
        }}

        QWidget#alerts_root QLabel {{
            background-color: transparent;
        }}

        #alerts_page_title, #alerts_page_subtitle,
        #alerts_section_title, #alerts_section_subtitle {{
            background-color: transparent;
        }}

        QTableWidget#alerts_incidents_table {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            font-size: 11px;
        }}

        QFrame#alert_control_panel {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            border-radius: 5px;
        }}

        #alert_control_title {{
            color: {t.text_primary};
            font-size: 12px;
            font-weight: 600;
        }}

        #alert_control_description {{
            color: {t.text_muted};
            font-size: 10px;
        }}

        #alert_control_value {{
            color: {t.accent_secondary};
            font-size: 12px;
            font-weight: 700;
        }}

        QSlider#alert_slider {{
            min-height: 28px;
        }}

        QSlider#alert_slider::groove:horizontal {{
            background-color: {t.border_subtle};
            height: 4px;
            border-radius: 2px;
        }}

        QSlider#alert_slider::sub-page:horizontal {{
            background-color: {t.accent_primary};
            border-radius: 2px;
        }}

        QSlider#alert_slider::add-page:horizontal {{
            background-color: {t.border_subtle};
            border-radius: 2px;
        }}

        QSlider#alert_slider::handle:horizontal {{
            background-color: {t.accent_secondary};
            border: 2px solid {t.bg_card};
            width: 14px;
            height: 14px;
            margin: -6px 0;
            border-radius: 8px;
        }}

        QSlider#alert_slider::handle:horizontal:hover {{
            background-color: {t.text_primary};
            border-color: {t.accent_primary};
        }}

        /* --- Settings --- */
        #settings_page_title, #settings_page_subtitle,
        #settings_section_title, #settings_section_subtitle,
        #settings_field_label, #settings_security_note,
        #ai_credential_status {{
            background-color: transparent;
        }}

        QFrame#ai_credential_panel {{
            background-color: {t.bg_input};
            border: 1px solid {t.border_subtle};
            border-radius: 5px;
        }}

        #settings_field_label {{
            color: {t.text_primary};
            font-size: 12px;
            font-weight: 600;
        }}

        #settings_security_note {{
            color: {t.text_muted};
            font-size: 10px;
        }}

        #ai_credential_status {{
            color: {t.text_secondary};
            border: 1px solid {t.border_card};
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        }}

        #ai_credential_status[state="configured"] {{
            color: {t.accent_secondary};
            border-color: {t.border_accent};
        }}

        #ai_credential_status[state="error"] {{
            color: {t.status_critical};
            border-color: {t.status_critical};
        }}

        QComboBox#ai_provider_combo, QLineEdit#ai_token_input {{
            background-color: {t.bg_input};
            color: {t.text_primary};
            border: 1px solid {t.border_card};
            border-radius: 4px;
            padding: 7px 10px;
            selection-background-color: {t.accent_primary};
        }}

        QComboBox#ai_provider_combo {{
            min-width: 150px;
            padding-right: 32px;
        }}

        QComboBox#ai_provider_combo:hover {{
            background-color: {t.bg_card_hover};
            border-color: {t.text_muted};
        }}

        QComboBox#ai_provider_combo:focus,
        QComboBox#ai_provider_combo:on,
        QLineEdit#ai_token_input:focus {{
            border-color: {t.border_accent};
        }}

        QComboBox#theme_combo::drop-down,
        QComboBox#ai_provider_combo::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 26px;
            border: none;
        }}

        QComboBox#theme_combo::down-arrow,
        QComboBox#ai_provider_combo::down-arrow {{
            width: 8px;
            height: 8px;
        }}

        QComboBox#theme_combo QAbstractItemView,
        QComboBox#ai_provider_combo QAbstractItemView {{
            background-color: {t.bg_card};
            color: {t.text_primary};
            border: 1px solid {t.border_card};
            border-radius: 4px;
            outline: none;
            padding: 4px;
            selection-background-color: {t.bg_card_hover};
            selection-color: {t.accent_secondary};
        }}

        QComboBox#theme_combo QAbstractItemView::item,
        QComboBox#ai_provider_combo QAbstractItemView::item {{
            padding: 0 10px;
            border: none;
            font-size: 12px;
            font-weight: 500;
        }}

        QComboBox#theme_combo QAbstractItemView::item:hover,
        QComboBox#ai_provider_combo QAbstractItemView::item:hover {{
            background-color: {t.bg_card_hover};
            color: {t.text_primary};
        }}

        QPushButton#remove_ai_token {{
            color: {t.text_secondary};
        }}

        QPushButton#remove_ai_token:hover {{
            color: {t.status_critical};
            border-color: {t.status_critical};
        }}

        QPushButton#ai_save_token:disabled,
        QPushButton#ai_test_connection:disabled,
        QPushButton#remove_ai_token:disabled {{
            background-color: {t.bg_card};
            color: {t.text_muted};
            border: 1px solid {t.border_subtle};
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
