import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from pc_diagnostic.credentials import (
    PROVIDER_CREDENTIALS,
    AIProvider,
    CredentialService,
    CredentialStorageUnavailableError,
)

logger = logging.getLogger(__name__)


class CredentialTokenResolver(Protocol):
    """Credential lookup boundary used by the diagnostic entry point."""

    def get_token(self, provider: AIProvider) -> str | None: ...

# Try to import CrewAI components for AI diagnostics
try:
    from crewai import Agent, Crew, Process, Task

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


class LocalDiagnosticAnalyzer:
    """Fallback local diagnostic analyzer when AI/CrewAI are unavailable."""

    def analyze(self, evidence: dict[str, Any]) -> str:
        cpu_util = evidence.get("cpu_util", 0.0)
        ram_util = evidence.get("ram_util", 0.0)
        cpu_temp = evidence.get("cpu_temp", -1.0)
        gpu_temp = evidence.get("gpu_temp", -1.0)
        active_incidents = evidence.get("active_incidents", [])
        top_cpu_procs = evidence.get("top_cpu_procs", [])
        top_mem_procs = evidence.get("top_mem_procs", [])

        issues = []
        recommendations = []

        # 1. Evaluate CPU utilization
        if cpu_util > 85.0:
            issues.append(f"**High CPU Load**: Total CPU is at {cpu_util:.1f}%.")
            if top_cpu_procs:
                top_p = top_cpu_procs[0]
                recommendations.append(
                    f"Runaway process suspected: '{top_p['name']}' "
                    f"(PID {top_p['pid']}) is using {top_p['cpu']:.1f}% CPU. "
                    "Consider terminating it."
                )
            else:
                recommendations.append(
                    "High CPU load detected. Check for busy background services."
                )

        # 2. Evaluate RAM utilization
        if ram_util > 85.0:
            issues.append(
                f"**High RAM Utilization**: Total RAM is {ram_util:.1f}% used."
            )
            if top_mem_procs:
                top_m = top_mem_procs[0]
                recommendations.append(
                    f"Memory pressure detected: '{top_m['name']}' "
                    f"(PID {top_m['pid']}) is using {top_m['mem_str']} RAM. "
                    "Close heavy applications."
                )
            else:
                recommendations.append(
                    "Memory pressure is high. Close unused processes to free up RAM."
                )

        # 3. Evaluate Thermals
        max_t = max(cpu_temp, gpu_temp)
        if max_t > 80.0:
            issues.append(
                "**High Operating Temperature**: "
                f"Thermal sensors report up to {max_t:.1f}°C."
            )
            recommendations.append(
                "System is running hot. Check airflow vents, clean dust "
                "from fans, or reduce high-intensity computations."
            )

        # 4. Evaluate Active Alerts
        if active_incidents:
            for inc in active_incidents:
                issues.append(
                    f"**Active Alert ({inc['rule_id']})**: "
                    "Firing since CPU/RAM threshold was breached."
                )
                recommendations.append(
                    "Investigate incident alert rule: "
                    f"'{inc['rule_id']}' limit violation."
                )

        # Summary Status
        status = "HEALTHY"
        if len(issues) >= 2:
            status = "CRITICAL"
        elif len(issues) == 1:
            status = "WARNING"

        # Generate report
        report_lines = [
            "# PC Diagnostic Analysis Report",
            "",
            f"**Overall System Status**: {status}",
            "",
            "## System Telemetry Summary",
            f"- **CPU Model**: {evidence.get('cpu_model', 'Unknown')}",
            f"- **CPU Utilization**: {cpu_util:.1f}%",
            f"- **Memory Utilization**: {ram_util:.1f}% "
            f"({evidence.get('ram_used_str', 'N/A')} used)",
        ]

        if cpu_temp != -1.0:
            report_lines.append(f"- **CPU Temp**: {cpu_temp:.1f} °C")
        if gpu_temp != -1.0:
            report_lines.append(f"- **GPU Temp**: {gpu_temp:.1f} °C")
        if evidence.get("fan_speed", -1.0) != -1.0:
            report_lines.append(f"- **Fan Speed**: {evidence.get('fan_speed'):.0f} RPM")

        report_lines.extend(
            [
                "",
                "## Diagnostics & Anomalies",
            ]
        )

        if issues:
            for issue in issues:
                report_lines.append(f"- {issue}")
        else:
            report_lines.append(
                "- No anomalies or thresholds violated. "
                "System parameters are within healthy bounds."
            )

        report_lines.extend(
            [
                "",
                "## Actionable Recommendations",
            ]
        )

        if recommendations:
            for rec in recommendations:
                report_lines.append(f"- {rec}")
        else:
            report_lines.append(
                "- No action required. Continue normal system operations."
            )

        return "\n".join(report_lines)


def _provider_from_environment() -> AIProvider | None:
    """Preserve the existing environment-based provider detection order."""
    for provider in AIProvider:
        environment_variable = PROVIDER_CREDENTIALS[provider].environment_variable
        if os.environ.get(environment_variable):
            return provider
    return None


def _resolve_provider_token(
    provider: AIProvider,
    credential_service: CredentialTokenResolver,
) -> str | None:
    """Resolve a token from secure storage, then the existing environment."""
    try:
        stored_token = credential_service.get_token(provider)
    except CredentialStorageUnavailableError:
        logger.warning(
            "Secure credential storage is unavailable; checking environment"
        )
    else:
        if stored_token:
            return stored_token

    environment_variable = PROVIDER_CREDENTIALS[provider].environment_variable
    return os.environ.get(environment_variable) or None


@contextmanager
def _temporary_provider_environment(
    provider: AIProvider,
    token: str,
) -> Iterator[None]:
    """Expose one provider token for a single CrewAI execution."""
    environment_variable = PROVIDER_CREDENTIALS[provider].environment_variable
    previous_value = os.environ.get(environment_variable)
    os.environ[environment_variable] = token
    try:
        yield
    finally:
        if previous_value is None:
            os.environ.pop(environment_variable, None)
        else:
            os.environ[environment_variable] = previous_value


def run_diagnosis(
    evidence_packet: dict[str, Any],
    provider: AIProvider | None = None,
    credential_service: CredentialTokenResolver | None = None,
) -> str:
    """Main entry point to execute system diagnostics.

    Resolve the selected provider from secure storage or the environment, then
    attempt CrewAI. Fall back to local analysis when no credential is available
    or the AI execution cannot complete.
    """
    selected_provider = provider or _provider_from_environment()
    if not CREWAI_AVAILABLE or selected_provider is None:
        return LocalDiagnosticAnalyzer().analyze(evidence_packet)

    service = credential_service or CredentialService()
    token = _resolve_provider_token(selected_provider, service)
    if token is None:
        return LocalDiagnosticAnalyzer().analyze(evidence_packet)

    with _temporary_provider_environment(selected_provider, token):
        try:
            # Construct a text string representing the telemetry snapshot evidence
            evidence_str = (
                f"CPU Model: {evidence_packet.get('cpu_model', 'Unknown')}\n"
                f"CPU Total Utilization: {evidence_packet.get('cpu_util', 0.0):.1f}%\n"
                f"RAM Total Utilization: {evidence_packet.get('ram_util', 0.0):.1f}%\n"
                f"RAM Used: {evidence_packet.get('ram_used_str', 'N/A')}\n"
                f"CPU Temp: {evidence_packet.get('cpu_temp', -1.0)} C\n"
                f"GPU Temp: {evidence_packet.get('gpu_temp', -1.0)} C\n"
                f"Fan Speed: {evidence_packet.get('fan_speed', -1.0)} RPM\n"
                f"Active alerts: {evidence_packet.get('active_incidents', [])}\n"
                f"Top CPU processes: {evidence_packet.get('top_cpu_procs', [])}\n"
                f"Top Memory processes: {evidence_packet.get('top_mem_procs', [])}\n"
            )

            analyst = Agent(
                role="Senior Systems Performance Analyst",
                goal=(
                    "Analyze system telemetry data to diagnose "
                    "hardware/software performance issues."
                ),
                backstory=(
                    "An expert diagnostic engineer specializing in "
                    "identifying resource leaks, thermal throttling, "
                    "and process misbehaviors."
                ),
                allow_delegation=False,
                verbose=False,
            )

            task = Task(
                description=(
                    "Review this system telemetry evidence packet:\n\n"
                    f"{evidence_str}\n\n"
                    "Identify any performance anomalies, bottlenecks, "
                    "runaway processes, or overheating risks. "
                    "Provide a plain-language diagnosis and specific "
                    "actionable recommendations to resolve the issues."
                ),
                expected_output=(
                    "A clean, structured markdown report summarizing "
                    "status, identified anomalies, and recommendations."
                ),
                agent=analyst,
            )

            crew = Crew(
                agents=[analyst],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )

            result = crew.kickoff()
            # crew.kickoff() can return a CrewOutput object; convert to string
            return str(result)
        except Exception:
            logger.warning("CrewAI execution failed; falling back to local analysis")

    # Fallback to local rule engine
    analyzer = LocalDiagnosticAnalyzer()
    return analyzer.analyze(evidence_packet)
