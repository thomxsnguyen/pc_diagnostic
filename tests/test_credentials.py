from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from pc_diagnostic.credentials import (
    PROVIDER_CREDENTIALS,
    PROVIDER_VALIDATION,
    SERVICE_NAME,
    STORAGE_UNAVAILABLE_MESSAGE,
    AIProvider,
    CredentialService,
    CredentialStorageUnavailableError,
    CredentialTestFailure,
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


@pytest.mark.parametrize(
    ("provider", "header", "header_value"),
    [
        (AIProvider.OPENAI, "Authorization", "Bearer provider-secret"),
        (AIProvider.GEMINI, "X-goog-api-key", "provider-secret"),
        (AIProvider.ANTHROPIC, "X-api-key", "provider-secret"),
    ],
)
def test_connection_test_uses_prompt_free_provider_request(
    provider: AIProvider,
    header: str,
    header_value: str,
) -> None:
    backend = MemoryBackend()
    requests: list[tuple[Request, float]] = []

    def transport(request: Request, timeout: float) -> int:
        requests.append((request, timeout))
        return 200

    service = CredentialService(backend, transport)
    service.save_token(provider, "provider-secret")
    backend.calls.clear()

    result = service.test_token(provider)

    assert result.success
    assert result.message == "Connection verified"
    assert result.category is None
    assert backend.calls == [
        ("get", SERVICE_NAME, PROVIDER_CREDENTIALS[provider].account)
    ]
    request, timeout = requests[0]
    assert request.full_url == PROVIDER_VALIDATION[provider].url
    assert request.method == "GET"
    assert request.data is None
    assert request.get_header(header) == header_value
    assert "provider-secret" not in request.full_url
    assert timeout == 5.0
    if provider is AIProvider.ANTHROPIC:
        assert request.get_header("Anthropic-version") == "2023-06-01"


def test_connection_test_without_token_does_not_make_request() -> None:
    backend = MemoryBackend()
    called = False

    def transport(_request: Request, _timeout: float) -> int:
        nonlocal called
        called = True
        return 200

    result = CredentialService(backend, transport).test_token(AIProvider.OPENAI)

    assert not result.success
    assert result.category is CredentialTestFailure.NOT_CONFIGURED
    assert not called


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (401, CredentialTestFailure.UNAUTHORIZED),
        (403, CredentialTestFailure.UNAUTHORIZED),
        (408, CredentialTestFailure.TIMEOUT),
        (429, CredentialTestFailure.PROVIDER_UNAVAILABLE),
        (503, CredentialTestFailure.PROVIDER_UNAVAILABLE),
    ],
)
def test_connection_test_sanitizes_http_failures(
    status: int,
    category: CredentialTestFailure,
) -> None:
    backend = MemoryBackend()
    backend.values[(SERVICE_NAME, "openai_api_key")] = "provider-secret"

    def transport(request: Request, _timeout: float) -> int:
        raise HTTPError(
            request.full_url,
            status,
            "provider-secret in response",
            {},
            None,
        )

    result = CredentialService(backend, transport).test_token(AIProvider.OPENAI)

    assert not result.success
    assert result.category is category
    assert "provider-secret" not in result.message
    assert "provider-secret" not in repr(result)
    assert (SERVICE_NAME, "openai_api_key") in backend.values
    assert not any(call[0] == "delete" for call in backend.calls)


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (TimeoutError("provider-secret"), CredentialTestFailure.TIMEOUT),
        (
            URLError("provider-secret in network response"),
            CredentialTestFailure.NETWORK,
        ),
    ],
)
def test_connection_test_sanitizes_transport_failures(
    error: Exception,
    category: CredentialTestFailure,
) -> None:
    backend = MemoryBackend()
    backend.values[(SERVICE_NAME, "openai_api_key")] = "provider-secret"

    def transport(_request: Request, _timeout: float) -> int:
        raise error

    result = CredentialService(backend, transport).test_token(AIProvider.OPENAI)

    assert not result.success
    assert result.category is category
    assert "provider-secret" not in result.message


def test_connection_test_sanitizes_storage_failure() -> None:
    result = CredentialService(BrokenBackend()).test_token(AIProvider.OPENAI)

    assert not result.success
    assert result.message == STORAGE_UNAVAILABLE_MESSAGE
    assert result.category is CredentialTestFailure.SECURE_STORAGE
