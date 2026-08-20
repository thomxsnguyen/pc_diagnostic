from __future__ import annotations

from typing import Any

import pytest

from pc_diagnostic.cache import RollingCache
from pc_diagnostic.credentials import (
    AIProvider,
    CredentialStorageUnavailableError,
)
from pc_diagnostic.gui.app import MainWindow
from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE, TelemetryBridge
from pc_diagnostic.gui.views import SettingsView

pytestmark = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


class FakeCredentialService:
    def __init__(self) -> None:
        self.values: dict[AIProvider, str] = {}

    def save_token(self, provider: AIProvider, token: str) -> None:
        self.values[provider] = token

    def get_token(self, provider: AIProvider) -> str | None:
        return self.values.get(provider)

    def has_token(self, provider: AIProvider) -> bool:
        return provider in self.values

    def delete_token(self, provider: AIProvider) -> None:
        self.values.pop(provider, None)


class UnavailableCredentialService(FakeCredentialService):
    def save_token(self, provider: AIProvider, token: str) -> None:
        raise CredentialStorageUnavailableError

    def has_token(self, provider: AIProvider) -> bool:
        raise CredentialStorageUnavailableError


def _view(qtbot: Any, service: Any) -> SettingsView:
    bridge = TelemetryBridge(RollingCache())
    view = SettingsView(bridge, credential_service=service)
    qtbot.addWidget(view)
    return view


def test_ai_provider_controls_are_secure_and_scoped(qtbot: Any) -> None:
    from PySide6.QtWidgets import QLineEdit

    view = _view(qtbot, FakeCredentialService())

    assert view.provider_combo.count() == 3
    assert AIProvider(view.provider_combo.itemData(0)) is AIProvider.OPENAI
    assert AIProvider(view.provider_combo.itemData(1)) is AIProvider.GEMINI
    assert AIProvider(view.provider_combo.itemData(2)) is AIProvider.ANTHROPIC
    assert view.token_input.echoMode() is QLineEdit.EchoMode.Password
    assert view.test_connection_button.isEnabled() is False


def test_save_replace_and_remove_token(qtbot: Any) -> None:
    service = FakeCredentialService()
    view = _view(qtbot, service)
    view._refresh_provider_state()

    view.token_input.setText("secret-token-a8F2")
    view.save_token_button.click()

    assert service.values[AIProvider.OPENAI] == "secret-token-a8F2"
    assert view.token_input.text() == ""
    assert view.credential_status.text() == "Configured ····a8F2"
    assert "secret-token-a8F2" not in view.credential_status.text()
    assert view.save_token_button.text() == "Replace token"
    assert view.remove_token_button.isEnabled()

    view.token_input.setText("replacement-token")
    view.save_token_button.click()
    assert service.values[AIProvider.OPENAI] == "replacement-token"
    assert view.token_input.text() == ""

    view.remove_token_button.click()
    assert AIProvider.OPENAI not in service.values
    assert view.credential_status.text() == "Not configured"
    assert not view.remove_token_button.isEnabled()


def test_provider_change_clears_input_and_updates_selection(qtbot: Any) -> None:
    service = FakeCredentialService()
    view = _view(qtbot, service)
    selected: list[AIProvider] = []
    view.set_provider_callback(selected.append)
    view.token_input.setText("never-store-in-widget-state")

    view.provider_combo.setCurrentIndex(1)

    assert view.selected_provider is AIProvider.GEMINI
    assert view.token_input.text() == ""
    assert selected[-1] is AIProvider.GEMINI


def test_secure_storage_failure_disables_credential_actions(qtbot: Any) -> None:
    view = _view(qtbot, UnavailableCredentialService())

    view._refresh_provider_state()
    view.token_input.setText("secret-token")

    assert view.credential_status.text() == "Secure storage unavailable"
    assert not view.save_token_button.isEnabled()
    assert not view.test_connection_button.isEnabled()
    assert not view.remove_token_button.isEnabled()


def test_failed_save_clears_token_input(qtbot: Any) -> None:
    view = _view(qtbot, UnavailableCredentialService())
    view.token_input.setText("secret-token")

    view.save_token_button.click()

    assert view.token_input.text() == ""
    assert view.credential_status.text() == "Secure storage unavailable"


def test_token_input_clears_when_view_is_hidden(qtbot: Any) -> None:
    view = _view(qtbot, FakeCredentialService())
    view.show()
    view.token_input.setText("temporary-token")

    view.hide()

    assert view.token_input.text() == ""


def test_main_window_routes_provider_selection_to_ai_studio(qtbot: Any) -> None:
    bridge = TelemetryBridge(RollingCache())
    window = MainWindow(bridge, credential_service=FakeCredentialService())
    qtbot.addWidget(window)

    window.settings_view.provider_combo.setCurrentIndex(2)

    assert window.diagnostics_view.provider is AIProvider.ANTHROPIC
