from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import keyring

SERVICE_NAME = "pc-diagnostic"
STORAGE_UNAVAILABLE_MESSAGE = "Secure storage unavailable"


class AIProvider(StrEnum):
    """AI providers supported by the existing diagnostic integration."""

    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


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


class CredentialBackend(Protocol):
    """Minimal keyring interface used by the credential service."""

    def set_password(self, service: str, account: str, token: str) -> None: ...

    def get_password(self, service: str, account: str) -> str | None: ...

    def delete_password(self, service: str, account: str) -> None: ...


class CredentialStorageUnavailableError(RuntimeError):
    """Raised when the operating system credential vault cannot be used."""

    def __init__(self) -> None:
        super().__init__(STORAGE_UNAVAILABLE_MESSAGE)


class InvalidCredentialTokenError(ValueError):
    """Raised before backend access when a token is blank."""


class CredentialService:
    """Store AI provider tokens exclusively in the operating system vault."""

    def __init__(self, backend: CredentialBackend | None = None) -> None:
        self._backend = backend or keyring

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
