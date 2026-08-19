from __future__ import annotations

import logging
import os
from typing import Any

import pytest

from pc_diagnostic.credentials import (
    AIProvider,
    CredentialStorageUnavailableError,
)
from pc_diagnostic.diagnostics import crew as crew_module


class StubCredentialService:
    def __init__(self, token: str | None) -> None:
        self.token = token
        self.requested: list[AIProvider] = []

    def get_token(self, provider: AIProvider) -> str | None:
        self.requested.append(provider)
        return self.token


class UnavailableCredentialService:
    def get_token(self, provider: AIProvider) -> str | None:
        raise CredentialStorageUnavailableError


class FakeCrew:
    def __init__(
        self,
        environment_variable: str,
        expected_token: str,
        *,
        failure: Exception | None = None,
    ) -> None:
        self.environment_variable = environment_variable
        self.expected_token = expected_token
        self.failure = failure

    def kickoff(self) -> str:
        assert os.environ[self.environment_variable] == self.expected_token
        if self.failure is not None:
            raise self.failure
        return "AI report"


def _install_fake_crewai(
    monkeypatch: pytest.MonkeyPatch,
    fake_crew: FakeCrew,
    captured_tasks: list[dict[str, Any]] | None = None,
) -> None:
    monkeypatch.setattr(crew_module, "CREWAI_AVAILABLE", True)
    monkeypatch.setattr(crew_module, "Agent", lambda **_kwargs: object())

    def build_task(**kwargs: Any) -> object:
        if captured_tasks is not None:
            captured_tasks.append(kwargs)
        return object()

    monkeypatch.setattr(crew_module, "Task", build_task)
    monkeypatch.setattr(crew_module, "Crew", lambda **_kwargs: fake_crew)


def _healthy_evidence() -> dict[str, Any]:
    return {
        "cpu_model": "Test CPU",
        "cpu_util": 10.0,
        "ram_util": 20.0,
        "ram_used_str": "2.0 GB",
        "cpu_temp": 40.0,
        "gpu_temp": 38.0,
        "fan_speed": 1000.0,
    }


def test_stored_token_precedes_environment_and_is_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-token")
    service = StubCredentialService("stored-token")
    fake_crew = FakeCrew("OPENAI_API_KEY", "stored-token")
    _install_fake_crewai(monkeypatch, fake_crew)

    report = crew_module.run_diagnosis(
        _healthy_evidence(),
        provider=AIProvider.OPENAI,
        credential_service=service,
    )

    assert report == "AI report"
    assert service.requested == [AIProvider.OPENAI]
    assert os.environ["OPENAI_API_KEY"] == "environment-token"


def test_environment_is_used_when_secure_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "environment-token")
    service = StubCredentialService(None)
    fake_crew = FakeCrew("GEMINI_API_KEY", "environment-token")
    _install_fake_crewai(monkeypatch, fake_crew)

    report = crew_module.run_diagnosis(
        _healthy_evidence(),
        provider=AIProvider.GEMINI,
        credential_service=service,
    )

    assert report == "AI report"
    assert os.environ["GEMINI_API_KEY"] == "environment-token"


def test_unavailable_storage_uses_environment_without_sensitive_logging(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-token")
    fake_crew = FakeCrew("ANTHROPIC_API_KEY", "environment-token")
    _install_fake_crewai(monkeypatch, fake_crew)

    with caplog.at_level(logging.WARNING):
        report = crew_module.run_diagnosis(
            _healthy_evidence(),
            provider=AIProvider.ANTHROPIC,
            credential_service=UnavailableCredentialService(),
        )

    assert report == "AI report"
    assert "environment-token" not in caplog.text


def test_missing_credentials_use_local_analyzer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(crew_module, "CREWAI_AVAILABLE", True)
    monkeypatch.setattr(
        crew_module,
        "Crew",
        lambda **_kwargs: pytest.fail("CrewAI should not run without a token"),
    )

    report = crew_module.run_diagnosis(
        _healthy_evidence(),
        provider=AIProvider.ANTHROPIC,
        credential_service=StubCredentialService(None),
    )

    assert "Overall System Status**: HEALTHY" in report


def test_temporary_environment_is_removed_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fake_crew = FakeCrew("OPENAI_API_KEY", "stored-token")
    _install_fake_crewai(monkeypatch, fake_crew)

    report = crew_module.run_diagnosis(
        _healthy_evidence(),
        provider=AIProvider.OPENAI,
        credential_service=StubCredentialService("stored-token"),
    )

    assert report == "AI report"
    assert "OPENAI_API_KEY" not in os.environ


def test_environment_is_restored_and_failure_logging_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "previous-token")
    fake_crew = FakeCrew(
        "OPENAI_API_KEY",
        "stored-token",
        failure=RuntimeError("request exposed stored-token"),
    )
    _install_fake_crewai(monkeypatch, fake_crew)

    with caplog.at_level(logging.WARNING):
        report = crew_module.run_diagnosis(
            _healthy_evidence(),
            provider=AIProvider.OPENAI,
            credential_service=StubCredentialService("stored-token"),
        )

    assert "Overall System Status**: HEALTHY" in report
    assert os.environ["OPENAI_API_KEY"] == "previous-token"
    assert "stored-token" not in caplog.text


def test_token_is_not_added_to_evidence_or_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _healthy_evidence()
    captured_tasks: list[dict[str, Any]] = []
    fake_crew = FakeCrew("OPENAI_API_KEY", "stored-token")
    _install_fake_crewai(monkeypatch, fake_crew, captured_tasks)

    report = crew_module.run_diagnosis(
        evidence,
        provider=AIProvider.OPENAI,
        credential_service=StubCredentialService("stored-token"),
    )

    assert report == "AI report"
    assert "stored-token" not in repr(evidence)
    assert "stored-token" not in repr(captured_tasks)


def test_omitted_provider_preserves_environment_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-token")
    service = StubCredentialService(None)
    fake_crew = FakeCrew("ANTHROPIC_API_KEY", "environment-token")
    _install_fake_crewai(monkeypatch, fake_crew)

    report = crew_module.run_diagnosis(
        _healthy_evidence(),
        credential_service=service,
    )

    assert report == "AI report"
    assert service.requested == [AIProvider.ANTHROPIC]
