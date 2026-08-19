from __future__ import annotations

from pathlib import Path

import pytest

from pc_diagnostic.credentials import (
    PROVIDER_CREDENTIALS,
    SERVICE_NAME,
    STORAGE_UNAVAILABLE_MESSAGE,
    AIProvider,
    CredentialService,
    CredentialStorageUnavailableError,
    InvalidCredentialTokenError,
)


class MemoryBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.calls: list[tuple[str, str, str]] = []

    def set_password(self, service: str, account: str, token: str) -> None:
        self.calls.append(("set", service, account))
        self.values[(service, account)] = token

    def get_password(self, service: str, account: str) -> str | None:
        self.calls.append(("get", service, account))
        return self.values.get((service, account))

    def delete_password(self, service: str, account: str) -> None:
        self.calls.append(("delete", service, account))
        self.values.pop((service, account), None)


class BrokenBackend:
    def _fail(self) -> None:
        raise RuntimeError("backend failed while handling super-secret-token")

    def set_password(self, service: str, account: str, token: str) -> None:
        self._fail()

    def get_password(self, service: str, account: str) -> str | None:
        self._fail()

    def delete_password(self, service: str, account: str) -> None:
        self._fail()


@pytest.mark.parametrize(
    ("provider", "account", "environment_variable"),
    [
        (AIProvider.OPENAI, "openai_api_key", "OPENAI_API_KEY"),
        (AIProvider.GEMINI, "gemini_api_key", "GEMINI_API_KEY"),
        (AIProvider.ANTHROPIC, "anthropic_api_key", "ANTHROPIC_API_KEY"),
    ],
)
def test_provider_credential_mappings(
    provider: AIProvider,
    account: str,
    environment_variable: str,
) -> None:
    config = PROVIDER_CREDENTIALS[provider]
    assert config.account == account
    assert config.environment_variable == environment_variable


def test_save_get_replace_and_delete_token() -> None:
    backend = MemoryBackend()
    service = CredentialService(backend)

    assert service.get_token(AIProvider.OPENAI) is None
    assert not service.has_token(AIProvider.OPENAI)

    service.save_token(AIProvider.OPENAI, "first-token")
    assert service.get_token(AIProvider.OPENAI) == "first-token"
    assert service.has_token(AIProvider.OPENAI)

    service.save_token(AIProvider.OPENAI, "replacement-token")
    assert service.get_token(AIProvider.OPENAI) == "replacement-token"

    service.delete_token(AIProvider.OPENAI)
    assert service.get_token(AIProvider.OPENAI) is None


def test_delete_missing_token_is_a_no_op() -> None:
    backend = MemoryBackend()
    service = CredentialService(backend)

    service.delete_token(AIProvider.GEMINI)

    assert not any(call[0] == "delete" for call in backend.calls)


@pytest.mark.parametrize("token", ["", " ", "\t\n"])
def test_blank_token_is_rejected_before_backend_access(token: str) -> None:
    backend = MemoryBackend()
    service = CredentialService(backend)

    with pytest.raises(InvalidCredentialTokenError, match="Token cannot be blank"):
        service.save_token(AIProvider.ANTHROPIC, token)

    assert backend.calls == []


@pytest.mark.parametrize("operation", ["save", "get", "has", "delete"])
def test_backend_failures_are_sanitized(operation: str) -> None:
    service = CredentialService(BrokenBackend())

    with pytest.raises(CredentialStorageUnavailableError) as exc_info:
        if operation == "save":
            service.save_token(AIProvider.OPENAI, "super-secret-token")
        elif operation == "get":
            service.get_token(AIProvider.OPENAI)
        elif operation == "has":
            service.has_token(AIProvider.OPENAI)
        else:
            service.delete_token(AIProvider.OPENAI)

    assert str(exc_info.value) == STORAGE_UNAVAILABLE_MESSAGE
    assert "super-secret-token" not in str(exc_info.value)


def test_backend_failure_does_not_create_plaintext_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    service = CredentialService(BrokenBackend())

    with pytest.raises(CredentialStorageUnavailableError):
        service.save_token(AIProvider.OPENAI, "super-secret-token")

    assert list(tmp_path.iterdir()) == []


def test_service_uses_stable_keyring_service_name() -> None:
    backend = MemoryBackend()
    service = CredentialService(backend)

    service.save_token(AIProvider.GEMINI, "token")

    assert backend.calls == [("set", SERVICE_NAME, "gemini_api_key")]
