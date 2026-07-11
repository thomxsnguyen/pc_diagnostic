import logging
import subprocess
import sys
import time
from threading import Lock

from pc_diagnostic.alerts.models import Incident, IncidentState

logger = logging.getLogger(__name__)


class AlertDispatcher:
    def __init__(self, log_path: str = "pc_diagnostic_alerts.log") -> None:
        self.log_path = log_path
        self.active_incidents: dict[str, Incident] = {}
        self._lock = Lock()

    def dispatch(
        self,
        transitions: list[tuple[Incident, IncidentState, IncidentState]],
        timestamp: float,
    ) -> None:
        """Process incident state transitions and apply tiered alerting responses."""
        with self._lock:
            for incident, old_state, new_state in transitions:
                rule = incident.rule

                if new_state == IncidentState.FIRING:
                    # Tier 1: Update in-memory active incidents
                    self.active_incidents[rule.id] = incident

                    # Cooldown rate gating check
                    is_cooldown_active = (
                        incident.last_fired_at is not None
                        and (timestamp - incident.last_fired_at) < rule.cooldown_s
                    )

                    if not is_cooldown_active:
                        incident.last_fired_at = timestamp
                        # Tier 2: Local desktop OS notification
                        self._trigger_os_notification(incident)
                        # Tier 3: Escalation log hook entry
                        self._log_incident(incident, "FIRING", timestamp)

                elif new_state == IncidentState.NORMAL:
                    if old_state == IncidentState.FIRING:
                        # Tier 1: Remove from active list
                        self.active_incidents.pop(rule.id, None)
                        # Tier 3: Escalation log hook entry
                        self._log_incident(incident, "CLEARED", timestamp)

    def _trigger_os_notification(self, incident: Incident) -> None:
        """Trigger platform-native desktop notification popup."""
        rule = incident.rule
        title = "PC Diagnostic Alert"
        msg = (
            f"Alert {rule.id} threshold violated! "
            f"Value: {incident.value:.1f} (limit: {rule.threshold:.1f})"
        )

        try:
            if sys.platform == "darwin":
                # AppleScript display notification call
                cmd = [
                    "osascript",
                    "-e",
                    f'display notification "{msg}" with title "{title}"',
                ]
                subprocess.run(cmd, capture_output=True, check=True, timeout=1.0)
            elif sys.platform == "win32":
                # PowerShell notification balloons call
                ps_script = (
                    "[void][System.Reflection.Assembly]::"
                    "LoadWithPartialName('System.Windows.Forms'); "
                    f"$n = New-Object System.Windows.Forms.NotifyIcon; "
                    f"$n.Icon = [System.Drawing.SystemIcons]::Information; "
                    f"$n.BalloonTipTitle = '{title}'; "
                    f"$n.BalloonTipText = '{msg}'; "
                    f"$n.Visible = $True; "
                    f"$n.ShowBalloonTip(5000)"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True,
                    check=True,
                    timeout=1.0,
                )
        except Exception as e:
            logger.debug(f"Failed to send OS desktop notification: {e}")

    def _log_incident(self, incident: Incident, status: str, timestamp: float) -> None:
        """Tier 3 response: Log incident transition to alerts log file."""
        rule = incident.rule
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        log_entry = (
            f"[{time_str}] [ALERT] [{status}] ID={rule.id} Metric={rule.metric} "
            f"Value={incident.value:.2f} Threshold={rule.threshold:.2f}\n"
        )
        try:
            with open(self.log_path, "a") as f:
                f.write(log_entry)
        except Exception as e:
            logger.warning(f"Failed to write to alerts log file {self.log_path}: {e}")
