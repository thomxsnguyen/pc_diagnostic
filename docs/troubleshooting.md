# Hardware Sensors & Platform Troubleshooting Guide

This guide addresses platform-specific hardware sensor quirks, permission requirements, fallback behaviors, and common operational issues in **PC Diagnostic** on macOS and Windows.

---

## 1. Quick Diagnostic Checklist

If metrics or sensors are displaying `N/A`, unexpected values, or the collector indicates a stale state:

1. **Check the application log:**
   ```bash
   tail -n 50 pc_diagnostic.log
   ```
2. **Check the alert log for firing incidents:**
   ```bash
   tail -n 50 pc_diagnostic_alerts.log
   ```
3. **Run in debug log mode to view real-time provider output:**
   ```bash
   python -m pc_diagnostic.main --log
   ```

---

## 2. macOS Hardware Sensors & Troubleshooting

macOS manages sensor telemetry through two distinct architectures: **Apple Silicon (M-Series)** and **Intel Macs**. Hardware readings are collected via the native C helper (`src/pc_diagnostic/providers/smc_helper.c`).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           macOS SENSOR PIPELINE                         │
│                                                                         │
│  [Apple Silicon (M1/M2/M3/M4)] ──► IOHIDEventSystemClient (PMU Channels)│
│  [Intel Macs]                  ──► AppleSMC Driver (SMC Keys & Fans)    │
│                                           │                             │
│                                           ▼                             │
│                              smc_helper (Compiled Binary)               │
│                                           │                             │
│                                           ▼                             │
│                               SmcProvider (Python Wrapper)              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Issue: Thermals Display "N/A" on macOS

#### Cause A: Missing C Compiler / Xcode Command Line Tools
The `SmcProvider` attempts to auto-compile `smc_helper.c` on startup using `clang`. If Xcode Command Line Tools are not installed, compilation fails and sensor readings degrade gracefully to `N/A`.

**Resolution:**
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Verify clang is available
clang --version
```

#### Cause B: Helper Binary Permission or Compilation Error
If compilation was interrupted or permissions were altered:

**Resolution:**
```bash
# Navigate to providers directory and manually compile
cd src/pc_diagnostic/providers
clang -O2 -Wall -Wextra -framework IOKit -framework CoreFoundation -o smc_helper smc_helper.c
chmod +x smc_helper

# Test the binary directly
./smc_helper
```
*Expected output:* A space-delimited list of key-value pairs (e.g. `pmu_tdie_0=42.50 cpu_fan_0=1200`).

### 2.2 Issue: Fan Speeds Show "N/A" on Apple Silicon
- **Normal Behavior:** Many Apple Silicon devices (MacBook Air M1/M2/M3) are **passively cooled** with no internal fans. On these models, `SmcProvider` correctly reports fan speeds as `N/A`.
- On actively cooled Apple Silicon Macs (MacBook Pro, Mac Studio, Mac mini), fan speeds are exposed when under active thermal load.

### 2.3 Issue: Process Telemetry Missing on macOS
On macOS, sandboxing or restrictive Terminal permissions may limit `psutil` from reading memory/CPU stats for system-owned root processes.

**Resolution:**
- If running inside a custom terminal (iTerm2, Alacritty, VS Code), ensure the terminal has permission under:  
  **System Settings → Privacy & Security → Full Disk Access / Accessibility** (if monitoring privileged system daemons).

---

## 3. Windows Hardware Sensors & Troubleshooting

On Windows, `psutil` provides standard CPU, Memory, Disk, and Network telemetry. Extended thermal, fan RPM, and voltage metrics require **LibreHardwareMonitor (LHM)** via WMI (Windows Management Instrumentation).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WINDOWS SENSOR PIPELINE                        │
│                                                                         │
│  [LibreHardwareMonitor.exe] ──► Exposes WMI: root/LibreHardwareMonitor  │
│                                           │                             │
│                                           ▼                             │
│                              PowerShell WMI Query (3s timeout)          │
│                                           │                             │
│                                           ▼                             │
│                               LhmProvider (Python Wrapper)              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Issue: Thermals, Fans, and Voltages Show "N/A" on Windows

#### Cause A: LibreHardwareMonitor is Not Running
`LhmProvider` queries WMI namespace `root/LibreHardwareMonitor` (or fallback `root/OpenHardwareMonitor`). If neither application is running in the background, sensor data is unavailable.

**Resolution:**
1. Download and run [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases).
2. Ensure **Options → WMI → Enable WMI** is checked in LibreHardwareMonitor.
3. Keep LibreHardwareMonitor minimized to the system tray.

#### Cause B: Missing Administrator Privileges (UAC)
Accessing low-level motherboard Super I/O chips, GPU voltage rails, and CPU core temperature registers on Windows requires Administrator privileges.

**Resolution:**
- Launch your terminal (`cmd.exe` or `PowerShell`) with **Run as Administrator**.
- For standalone packaged binaries, ensure the application manifest requests elevation (`requireAdministrator`).

### 3.2 Issue: Slow WMI Queries Causing Collector Staleness
PowerShell WMI queries on slow or heavily loaded Windows machines can occasionally exceed 1.0 second, triggering a `stale_collector` alert.

**Resolution:**
- The `LhmProvider` enforces a strict 3.0s timeout per read cycle.
- If WMI latency persists, increase the collector interval in `src/pc_diagnostic/main.py`:
  ```python
  collector = Collector(providers=providers, cache=cache, interval=2.0)
  ```

---

## 4. Alerting & Incident Troubleshooting

### 4.1 Issue: Alert Fires and Doesn't Clear Immediately
- **Cause:** This is by design due to **Hysteresis**.
- **Explanation:** For the `high_cpu` rule (trigger threshold `90%`, hysteresis offset `10%`), the incident will only transition from `FIRING` back to `NORMAL` once total CPU drops below **`80%`** (`90% - 10%`). This prevents rapid on/off alert flapping.

### 4.2 Issue: "STALE COLLECTOR" Alert Triggered
- **Trigger Condition:** Metric `cache.staleness > 2.0s`.
- **Cause:** One of the registered providers is blocking inside its `read()` method longer than 2 seconds (typically disk I/O on disconnected network drives or slow WMI calls).
- **Investigation:**
  Search `pc_diagnostic.log` for:
  ```text
  Error reading from provider '<provider_name>'
  ```

---

## 5. AI Diagnostics Engine Troubleshooting

### 5.1 Secure Credential Storage by Platform

Tokens saved under **Settings → AI Provider** use the stable service name
`pc-diagnostic` and remain in the operating system's credential vault:

- **macOS:** `keyring` stores the token in the user's macOS Keychain. macOS may
  ask the user to unlock or approve Keychain access.
- **Windows:** `keyring` stores the token through Windows Credential Manager
  (Credential Locker) for the current Windows user.

The application stores separate entries for OpenAI, Gemini, and Anthropic. It
never falls back to a plaintext credential file when the native vault cannot be
used.

#### Issue: "Secure storage unavailable"

This exact, sanitized message means that `keyring` could not access a usable
credential backend. The application does not display or log the backend's raw
error and does not save the token elsewhere.

On macOS, confirm that the login Keychain is unlocked and that Keychain Access
does not show a denied application entry. On Windows, confirm that Credential
Manager is available for the current user. Restart the application after
correcting vault access. For development only, the selected provider's ignored
`.env` variable can still be used as the documented fallback.

### 5.2 Issue: AI Diagnosis Returns "Local Heuristic Report" Instead of CrewAI Analysis

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DIAGNOSTICS RESOLUTION FLOW                      │
│                                                                         │
│  [User presses 'd']                                                     │
│         │                                                               │
│         ▼                                                               │
│  Selected provider token in OS vault?                                  │
│         ├───────────► NO: Check selected provider environment variable │
│         │                                                               │
│         ▼                                                               │
│  Credential available and CrewAI installed?                            │
│         ├───────────► YES: Executes CrewAI diagnostic                   │
│         └───────────► NO:  Executes LocalDiagnosticAnalyzer             │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Cause A: Missing Provider Credential
No token was found in the operating system vault or in the selected provider's
environment variable.

**Resolution:**
Save the token under **Settings → AI Provider**. For development only, create an
ignored `.env` file in the project root:
```bash
OPENAI_API_KEY="sk-..."
```

#### Cause B: API Rate Limit or Network Timeout
If CrewAI encounters an API error (e.g. HTTP 429 Too Many Requests, expired quota, or network drop), it automatically catches the exception, logs a warning in `pc_diagnostic.log`, and immediately falls back to `LocalDiagnosticAnalyzer` so the user is never left without a diagnosis.

### 5.3 Issue: Pressing `d` Does Not Trigger a New Diagnosis
- **Cause:** Diagnostic Cooldown.
- **Explanation:** A **10-second cooldown** is enforced between diagnosis runs to prevent accidental spamming and excessive LLM token consumption. The overlay displays the existing report until the cooldown expires.

---

## 6. Normalizer & Data Model Issues

### 6.1 Issue: "Normalizer dropped X readings from provider" in Log
- **Cause:** A provider emitted a reading that failed contract validation in `src/pc_diagnostic/normalizer.py`.
- **Common reasons:**
  - `value` is `NaN`, `Inf`, or `None`.
  - `metric` name is empty or contains non-string characters.
  - `unit` is not an instance of `MetricUnit`.
- **Behavior:** The Normalizer is a **drop-not-raise** validation gate. Non-conforming readings are safely discarded; valid readings continue to the cache without crashing the pipeline.
