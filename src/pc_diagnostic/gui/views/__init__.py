from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pc_diagnostic.credentials import (
    PROVIDER_CREDENTIALS,
    AIProvider,
    CredentialService,
    CredentialStorageUnavailableError,
    InvalidCredentialTokenError,
)
from pc_diagnostic.gui.views.alerts_view import AlertsView
from pc_diagnostic.gui.views.diagnostics_view import DiagnosticsView
from pc_diagnostic.gui.views.overview_view import OverviewView
from pc_diagnostic.gui.views.processes_view import ProcessesView
from pc_diagnostic.gui.views.sensors_view import SensorsView

if TYPE_CHECKING:
    from pc_diagnostic.gui.bridge import TelemetryBridge

try:
    from PySide6.QtWidgets import (
        QComboBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore[misc,assignment]


class BaseView(QWidget):
    """Base class for all tabbed views in the PC Diagnostic GUI."""

    def __init__(self, bridge: TelemetryBridge, parent: Any = None) -> None:
        if PYSIDE6_AVAILABLE:
            super().__init__(parent)
        self.bridge = bridge
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize view layout and widgets."""
        pass


class SettingsView(BaseView):
    """Secure AI provider credential management view."""

    def __init__(
        self,
        bridge: TelemetryBridge,
        parent: Any = None,
        credential_service: CredentialService | None = None,
    ) -> None:
        self._credential_service = credential_service or CredentialService()
        self._configured = False
        self._vault_available = True
        self._session_suffixes: dict[AIProvider, str] = {}
        self._provider_callback: Callable[[AIProvider], None] | None = None
        super().__init__(bridge, parent)

    def _init_ui(self) -> None:
        if not PYSIDE6_AVAILABLE:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        header = QFrame(self)
        header.setProperty("class", "card")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(4)

        title = QLabel("Settings")
        title.setObjectName("settings_page_title")
        subtitle = QLabel("Application preferences and secure integrations")
        subtitle.setObjectName("settings_page_subtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        card = QFrame(self)
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 18)
        card_layout.setSpacing(14)

        card_header = QHBoxLayout()
        card_header.setSpacing(12)
        heading_column = QVBoxLayout()
        heading_column.setSpacing(4)
        card_title = QLabel("AI Provider")
        card_title.setObjectName("settings_section_title")
        card_subtitle = QLabel(
            "Store one provider token securely in your operating system vault"
        )
        card_subtitle.setObjectName("settings_section_subtitle")
        heading_column.addWidget(card_title)
        heading_column.addWidget(card_subtitle)
        card_header.addLayout(heading_column, stretch=1)

        self.credential_status = QLabel("Not configured")
        self.credential_status.setObjectName("ai_credential_status")
        self.credential_status.setProperty("state", "neutral")
        card_header.addWidget(self.credential_status)
        card_layout.addLayout(card_header)

        credential_panel = QFrame(card)
        credential_panel.setObjectName("ai_credential_panel")
        panel_layout = QVBoxLayout(credential_panel)
        panel_layout.setContentsMargins(14, 12, 14, 14)
        panel_layout.setSpacing(10)

        provider_row = QHBoxLayout()
        provider_row.setSpacing(12)
        provider_label = QLabel("Provider")
        provider_label.setObjectName("settings_field_label")
        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("ai_provider_combo")
        self.provider_combo.addItem("OpenAI", AIProvider.OPENAI)
        self.provider_combo.addItem("Gemini", AIProvider.GEMINI)
        self.provider_combo.addItem("Anthropic", AIProvider.ANTHROPIC)
        for index in range(self.provider_combo.count()):
            provider = AIProvider(self.provider_combo.itemData(index))
            environment_variable = PROVIDER_CREDENTIALS[
                provider
            ].environment_variable
            if os.environ.get(environment_variable):
                self.provider_combo.setCurrentIndex(index)
                break
        provider_row.addWidget(provider_label)
        provider_row.addStretch()
        provider_row.addWidget(self.provider_combo)
        panel_layout.addLayout(provider_row)

        token_label = QLabel("API token")
        token_label.setObjectName("settings_field_label")
        panel_layout.addWidget(token_label)

        self.token_input = QLineEdit()
        self.token_input.setObjectName("ai_token_input")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Enter a provider token")
        self.token_input.setClearButtonEnabled(True)
        panel_layout.addWidget(self.token_input)

        security_note = QLabel(
            "The token is stored in Keychain or Credential Locker and is never "
            "written to application settings."
        )
        security_note.setObjectName("settings_security_note")
        security_note.setWordWrap(True)
        panel_layout.addWidget(security_note)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.save_token_button = QPushButton("Save token")
        self.save_token_button.setObjectName("ai_save_token")
        self.save_token_button.setProperty("class", "primary_btn")
        self.test_connection_button = QPushButton("Test connection")
        self.test_connection_button.setObjectName("ai_test_connection")
        self.test_connection_button.setProperty("class", "secondary_btn")
        self.test_connection_button.setEnabled(False)
        self.remove_token_button = QPushButton("Remove token")
        self.remove_token_button.setObjectName("remove_ai_token")
        self.remove_token_button.setProperty("class", "secondary_btn")
        actions.addWidget(self.save_token_button)
        actions.addWidget(self.test_connection_button)
        actions.addStretch()
        actions.addWidget(self.remove_token_button)
        panel_layout.addLayout(actions)

        card_layout.addWidget(credential_panel)
        layout.addWidget(card)
        layout.addStretch()

        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.token_input.textChanged.connect(self._update_controls)
        self.save_token_button.clicked.connect(self._save_token)
        self.remove_token_button.clicked.connect(self._remove_token)
        self._update_controls()

    @property
    def selected_provider(self) -> AIProvider:
        try:
            return AIProvider(self.provider_combo.currentData())
        except (TypeError, ValueError):
            return AIProvider.OPENAI

    def set_provider_callback(
        self, callback: Callable[[AIProvider], None]
    ) -> None:
        """Notify the application when the selected provider changes."""
        self._provider_callback = callback
        callback(self.selected_provider)

    def _on_provider_changed(self, _index: int) -> None:
        self.token_input.clear()
        self._refresh_provider_state()
        if self._provider_callback is not None:
            self._provider_callback(self.selected_provider)

    def _refresh_provider_state(self) -> None:
        self.token_input.clear()
        try:
            self._configured = self._credential_service.has_token(
                self.selected_provider
            )
        except CredentialStorageUnavailableError:
            self._configured = False
            self._vault_available = False
            self._set_status("Secure storage unavailable", "error")
        else:
            self._vault_available = True
            if self._configured:
                suffix = self._session_suffixes.get(self.selected_provider)
                status = f"Configured ····{suffix}" if suffix else "Configured"
                self._set_status(status, "configured")
            else:
                self._set_status("Not configured", "neutral")
        self._update_controls()

    def _save_token(self) -> None:
        token = self.token_input.text()
        try:
            self._credential_service.save_token(self.selected_provider, token)
        except InvalidCredentialTokenError:
            self._set_status("Enter a valid token", "error")
        except CredentialStorageUnavailableError:
            self._configured = False
            self._vault_available = False
            self._set_status("Secure storage unavailable", "error")
        else:
            self._configured = True
            self._vault_available = True
            suffix = token[-4:] if len(token) >= 4 else token
            self._session_suffixes[self.selected_provider] = suffix
            self._set_status(f"Configured ····{suffix}", "configured")
            if self._provider_callback is not None:
                self._provider_callback(self.selected_provider)
        finally:
            self.token_input.clear()
            self._update_controls()

    def _remove_token(self) -> None:
        try:
            self._credential_service.delete_token(self.selected_provider)
        except CredentialStorageUnavailableError:
            self._vault_available = False
            self._set_status("Secure storage unavailable", "error")
        else:
            self._configured = False
            self._session_suffixes.pop(self.selected_provider, None)
            self._set_status("Not configured", "neutral")
        finally:
            self.token_input.clear()
            self._update_controls()

    def _set_status(self, text: str, state: str) -> None:
        self.credential_status.setText(text)
        self.credential_status.setProperty("state", state)
        self.credential_status.style().unpolish(self.credential_status)
        self.credential_status.style().polish(self.credential_status)

    def _update_controls(self) -> None:
        has_input = bool(self.token_input.text().strip())
        self.save_token_button.setText(
            "Replace token" if self._configured else "Save token"
        )
        self.save_token_button.setEnabled(self._vault_available and has_input)
        self.remove_token_button.setEnabled(
            self._vault_available and self._configured
        )
        # Network validation is implemented in the separate connection-test phase.
        self.test_connection_button.setEnabled(False)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self._refresh_provider_state()
        super().showEvent(event)

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        self.token_input.clear()
        super().hideEvent(event)


__all__ = [
    "AlertsView",
    "BaseView",
    "DiagnosticsView",
    "OverviewView",
    "ProcessesView",
    "SensorsView",
    "SettingsView",
]
