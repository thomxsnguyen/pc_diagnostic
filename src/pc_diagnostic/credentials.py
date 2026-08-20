from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import keyring

SERVICE_NAME = "pc-diagnostic"
STORAGE_UNAVAILABLE_MESSAGE = "Secure storage unavailable"
CONNECTION_TEST_TIMEOUT_SECONDS = 5.0


class AIProvider(StrEnum):
    """AI providers supported by the existing diagnostic integration."""

    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


class CredentialTestFailure(StrEnum):
    """Sanitized connection-test failure categories."""

    UNAUTHORIZED = "unauthorized"
    TIMEOUT = "timeout"
    NETWORK = "network"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    NOT_CONFIGURED = "not_configured"
    SECURE_STORAGE = "secure_storage"


@dataclass(frozen=True)
class CredentialTestResult:
    """Non-sensitive result returned by a provider connection test."""

    success: bool
    message: str
    category: CredentialTestFailure | None = None


@dataclass(frozen=True)
class ProviderCredentialConfig:
    """Stable credential identifiers for one supported AI provider."""

    account: str
    environment_variable: str


PROVIDER_CREDENTIALS: dict[AIProvider, ProviderCredentialConfig] = {
    AIProvider.OPENAI: ProviderCredentialConfig(
        account="openai_api_key",
        environment_variable="OPENAI_API_KEY",
    ),
    AIProvider.GEMINI: ProviderCredentialConfig(
        account="gemini_api_key",
        environment_variable="GEMINI_API_KEY",
    ),
    AIProvider.ANTHROPIC: ProviderCredentialConfig(
        account="anthropic_api_key",
        environment_variable="ANTHROPIC_API_KEY",
    ),
}


@dataclass(frozen=True)
class ProviderValidationConfig:
    """Prompt-free endpoint configuration for provider authentication tests."""

    url: str
    token_header: str
    static_headers: tuple[tuple[str, str], ...] = ()


PROVIDER_VALIDATION: dict[AIProvider, ProviderValidationConfig] = {
    AIProvider.OPENAI: ProviderValidationConfig(
        url="https://api.openai.com/v1/models",
        token_header="Authorization",
    ),
    AIProvider.GEMINI: ProviderValidationConfig(
        url=(
            "https://generativelanguage.googleapis.com/v1beta/models"
            "?pageSize=1"
        ),
        token_header="x-goog-api-key",
    ),
    AIProvider.ANTHROPIC: ProviderValidationConfig(
        url="https://api.anthropic.com/v1/models?limit=1",
        token_header="x-api-key",
        static_headers=(("anthropic-version", "2023-06-01"),),
    ),
}


class CredentialBackend(Protocol):
    """Minimal keyring interface used by the credential service."""

    def set_password(self, service: str, account: str, token: str) -> None: ...

    def get_password(self, service: str, account: str) -> str | None: ...

    def delete_password(self, service: str, account: str) -> None: ...


class ValidationTransport(Protocol):
    """Minimal injectable HTTP transport used by connection tests."""

    def __call__(self, request: Request, timeout: float) -> int: ...


def _send_validation_request(request: Request, timeout: float) -> int:
    with urlopen(request, timeout=timeout) as response:
        return int(response.getcode())


class CredentialStorageUnavailableError(RuntimeError):
    """Raised when the operating system credential vault cannot be used."""

    def __init__(self) -> None:
        super().__init__(STORAGE_UNAVAILABLE_MESSAGE)


class InvalidCredentialTokenError(ValueError):
    """Raised before backend access when a token is blank."""


class CredentialService:
    """Store AI provider tokens exclusively in the operating system vault."""

    def __init__(
        self,
        backend: CredentialBackend | None = None,
        validation_transport: ValidationTransport | None = None,
    ) -> None:
        self._backend = backend or keyring
        self._validation_transport = (
            validation_transport or _send_validation_request
        )

    def save_token(self, provider: AIProvider, token: str) -> None:
        """Save or replace a provider token in secure storage."""
        if not token or not token.strip():
            raise InvalidCredentialTokenError("Token cannot be blank")

        account = PROVIDER_CREDENTIALS[provider].account
        try:
            self._backend.set_password(SERVICE_NAME, account, token)
        except Exception:
            raise CredentialStorageUnavailableError from None

    def get_token(self, provider: AIProvider) -> str | None:
        """Retrieve a provider token, returning None when it is not configured."""
        account = PROVIDER_CREDENTIALS[provider].account
        try:
            token = self._backend.get_password(SERVICE_NAME, account)
        except Exception:
            raise CredentialStorageUnavailableError from None
        return token or None

    def has_token(self, provider: AIProvider) -> bool:
        """Return whether a provider token exists in secure storage."""
        return self.get_token(provider) is not None

    def delete_token(self, provider: AIProvider) -> None:
        """Remove a provider token; an already-missing token is a no-op."""
        if self.get_token(provider) is None:
            return

        account = PROVIDER_CREDENTIALS[provider].account
        try:
            self._backend.delete_password(SERVICE_NAME, account)
        except Exception:
            raise CredentialStorageUnavailableError from None

    def test_token(self, provider: AIProvider) -> CredentialTestResult:
        """Verify a stored token with a minimal prompt-free provider request."""
        try:
            token = self.get_token(provider)
        except CredentialStorageUnavailableError:
            return CredentialTestResult(
                success=False,
                message=STORAGE_UNAVAILABLE_MESSAGE,
                category=CredentialTestFailure.SECURE_STORAGE,
            )

        if token is None:
            return CredentialTestResult(
                success=False,
                message="No stored token",
                category=CredentialTestFailure.NOT_CONFIGURED,
            )

        request = self._build_validation_request(provider, token)
        try:
            status = self._validation_transport(
                request, CONNECTION_TEST_TIMEOUT_SECONDS
            )
        except HTTPError as exc:
            return self._result_for_status(exc.code)
        except TimeoutError:
            return CredentialTestResult(
                success=False,
                message="Connection timed out. Try again.",
                category=CredentialTestFailure.TIMEOUT,
            )
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                return CredentialTestResult(
                    success=False,
                    message="Connection timed out. Try again.",
                    category=CredentialTestFailure.TIMEOUT,
                )
            return CredentialTestResult(
                success=False,
                message="Unable to reach the provider.",
                category=CredentialTestFailure.NETWORK,
            )
        except OSError:
            return CredentialTestResult(
                success=False,
                message="Unable to reach the provider.",
                category=CredentialTestFailure.NETWORK,
            )
        except Exception:
            return CredentialTestResult(
                success=False,
                message="Unable to reach the provider.",
                category=CredentialTestFailure.NETWORK,
            )
        return self._result_for_status(status)

    @staticmethod
    def _build_validation_request(provider: AIProvider, token: str) -> Request:
        config = PROVIDER_VALIDATION[provider]
        headers = dict(config.static_headers)
        headers[config.token_header] = (
            f"Bearer {token}" if provider is AIProvider.OPENAI else token
        )
        return Request(config.url, headers=headers, method="GET")

    @staticmethod
    def _result_for_status(status: int) -> CredentialTestResult:
        if 200 <= status < 300:
            return CredentialTestResult(
                success=True,
                message="Connection verified",
            )
        if status in {401, 403}:
            return CredentialTestResult(
                success=False,
                message="Authentication failed. Check the stored token.",
                category=CredentialTestFailure.UNAUTHORIZED,
            )
        if status in {408, 504}:
            return CredentialTestResult(
                success=False,
                message="Connection timed out. Try again.",
                category=CredentialTestFailure.TIMEOUT,
            )
        return CredentialTestResult(
            success=False,
            message="Provider is currently unavailable.",
            category=CredentialTestFailure.PROVIDER_UNAVAILABLE,
        )
