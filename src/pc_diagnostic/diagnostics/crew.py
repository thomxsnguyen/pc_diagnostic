import logging
import os

logger = logging.getLogger(__name__)

# Try to import CrewAI components for AI diagnostics
try:
    from crewai import Agent, Crew, Process, Task  # type: ignore[import-untyped]

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


class LocalDiagnosticAnalyzer:
    """Fallback local diagnostic analyzer when AI/CrewAI are unavailable."""

    def analyze(self, evidence: dict) -> str:
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


def run_diagnosis(evidence_packet: dict) -> str:
    """Main entry point to execute system diagnostics.

    Attempts to use CrewAI if API key is present, otherwise falls back.
    """
    has_api_key = bool(
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )

    if CREWAI_AVAILABLE and has_api_key:
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
        except Exception as e:
            logger.warning(
                "CrewAI execution failed, falling back to local "
                f"analysis: {e}"
            )

    # Fallback to local rule engine
    analyzer = LocalDiagnosticAnalyzer()
    return analyzer.analyze(evidence_packet)
