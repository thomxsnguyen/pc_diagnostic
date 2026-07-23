# Provider System

Providers are the data sources of PC Diagnostic. Each provider implements the
`Provider` ABC and produces `MetricReading` objects in the normalized schema.
This document covers the provider interface, registration strategy, and each
concrete provider.

---

## Provider ABC

Defined in `src/pc_diagnostic/providers/base.py`:

```python
class Provider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def read(self) -> list[MetricReading]: ...
```

### Design Decisions

- **ABC, not Protocol.** Providers are an explicit plugin contract — you are choosing
  to implement a provider. ABC makes that opt-in visible and gives a clear error if
  you forget to implement a method. Protocol is better for duck-typing scenarios;
  that's not the case here.

- **Providers return normalized readings directly.** The alternative — providers
  return raw shapes and a centralised normalizer transforms them — creates coupling:
  the normalizer must know the internals of every provider. Instead, each provider
  produces conforming `MetricReading` objects. The normalizer's job is validation,
  not transformation.

- **One provider per source, not per category.** A single `PsutilProvider` returns
  CPU + memory + disk + network readings. Splitting by category would mean multiple
  providers all calling psutil independently — redundant syscalls, no benefit.

---

## Provider Registry

Defined in `src/pc_diagnostic/providers/registry.py`:

```python
def register_providers() -> list[Provider]:
    real_providers = [PsutilProvider(), LhmProvider(), SmcProvider()]
    available_reals = [p for p in real_providers if p.available()]
    if available_reals:
        return available_reals
    return [StubProvider()]
```

Registration is **explicit and OS-aware**. No plugin autodiscovery, no dynamic
loading, no import magic. The `available()` guard on each provider handles
platform-specific availability.

**Fallback behavior:** If no real provider is available (e.g., running tests in CI),
the `StubProvider` kicks in so the pipeline always has data flowing.

---

## Concrete Providers

### StubProvider (`stub.py`)

- **Platform:** All (always available)
- **Purpose:** Fake data for testing and development
- **Metrics produced:** `cpu.utilization.total`, `memory.utilization`, `system.uptime`
- **Behavior:** Returns random CPU (5–95%) and memory (40–80%) values each tick

Used as a fallback when no real providers are available and for unit testing the
pipeline end-to-end.

---

### PsutilProvider (`psutil_provider.py`)

- **Platform:** All (always available where `psutil` is installed)
- **Purpose:** Primary cross-platform telemetry source
- **Dependency:** `psutil>=5.9.0`

#### Metrics Produced

| Category       | Metrics                                                          |
|----------------|------------------------------------------------------------------|
| CPU            | `cpu.utilization.total`, `cpu.utilization.per_core`, `cpu.frequency.current` |
| Memory         | `memory.total`, `memory.used`, `memory.available`, `memory.utilization` |
| Disk           | `disk.usage.used`, `disk.io.read_bytes`, `disk.io.write_bytes`  |
| Network        | `network.io.bytes_sent`, `network.io.bytes_recv`                |
| Processes      | `process.cpu_percent`, `process.memory.used` (top 5 CPU + top 5 memory) |
| Static specs   | `system.info.cpu_model`, `system.info.os_version`, `system.info.total_memory` |

#### Rate Calculation

Disk I/O and network I/O are reported as **rates** (bytes/sec), not cumulative
counters. The provider maintains internal state (`_last_disk_io`, `_last_net_io`,
`_last_time`) and computes deltas between ticks. The first tick after startup
returns no I/O readings (no previous baseline to diff against).

#### macOS Memory Handling

On macOS, the provider uses a custom `_get_mac_virtual_memory()` method that
computes `used = total - available` to match Activity Monitor's definition more
closely. It also captures `wired` and `compressed` memory attributes when available.

#### Process Tracking

The provider maintains a `_processes` dict mapping PIDs to `psutil.Process` objects
across ticks. This is required because `cpu_percent(interval=None)` needs a prior
measurement to compare against — a fresh Process object would always return 0%.
Dead processes are cleaned up each tick.

#### Static Specs

CPU model, OS version, and total memory are read once at `__init__` time and emitted
as `unit=INFO` readings every tick. The actual values live in `tags["value"]`.
Platform-specific methods (`_get_cpu_model`, `_get_os_version`) use:
- macOS: `sysctl` commands
- Windows: `winreg` registry queries
- Linux: `/proc/cpuinfo`

---

### LhmProvider (`lhm_provider.py`)

- **Platform:** Windows only (`sys.platform == "win32"`)
- **Purpose:** Hardware sensors via LibreHardwareMonitor's WMI namespace
- **Dependency:** LibreHardwareMonitor must be running on the system

#### How It Works

Executes a PowerShell command to query the `root\LibreHardwareMonitor` WMI namespace:

```powershell
Get-CimInstance -Namespace root\LibreHardwareMonitor -ClassName Sensor |
  Select-Object Name, SensorType, Value, Identifier |
  ConvertTo-Json -Compress
```

The subprocess has a 1.5s timeout to avoid blocking the collector thread.

#### Metrics Produced

| SensorType    | Metric                                       |
|---------------|----------------------------------------------|
| Temperature   | `system.temperature.cpu` or `.gpu` or `.other` |
| Fan           | `system.fan.speed`                           |
| Voltage       | `system.voltage.cpu` or `.other`             |

CPU vs GPU classification is done by keyword matching on the sensor Name and
Identifier fields (case-insensitive search for "cpu" or "gpu").

#### Failure Mode

If LHM is not running, the WMI namespace doesn't exist and the query fails silently
(logged at DEBUG level). The provider returns an empty list — no crash, no error.

---

### SmcProvider (`smc_provider.py`)

- **Platform:** macOS only (`sys.platform == "darwin"`)
- **Purpose:** Native hardware sensors via Apple's System Management Controller
- **Dependency:** Compiles a native C helper binary at startup

#### Native C Helper (`smc_helper.c`)

The SMC is not accessible through standard Python libraries. The provider ships a
C source file that:

1. **IOHIDEventSystem** — Queries Apple's HID event system for temperature sensors
   (primary source on Apple Silicon). Reads `kIOHIDEventTypeTemperature` events
   from all HID services.

2. **AppleSMC** — Falls back to the traditional SMC interface for:
   - CPU temperature (`TC0D` key, `sp78` format) — only if HID returned nothing
   - Fan speeds (`F0Ac`, `F1Ac` keys, `fpe2` format)

Output is a JSON array printed to stdout, parsed by the Python provider.

#### Sensor Mapping

The provider maintains a `SENSOR_MAP` dict that maps raw HID sensor names to
canonical metric names. This handles the many PMU thermal zone names found on
Apple Silicon (e.g., `PMU tdie1` through `PMU tdie10` → `system.temperature.cpu`).

#### Compilation

The C helper is compiled at `SmcProvider.__init__` time if the binary doesn't exist:

```bash
clang -O3 -framework IOKit -framework CoreFoundation smc_helper.c -o smc_helper
```

If compilation fails (e.g., no Xcode command line tools), the provider reports
`available() = False` and is silently skipped.

---

## Adding a New Provider

1. Create `src/pc_diagnostic/providers/my_provider.py`
2. Subclass `Provider` and implement `name`, `available()`, `read()`
3. Return `list[MetricReading]` with proper metric names, units, and tags
4. Add the provider to `register_providers()` in `registry.py`
5. Add tests in `tests/test_my_provider.py`

The normalizer will automatically validate your readings. Unknown metric names
are accepted (validation only checks the dot-separated pattern, not a fixed
registry of names).
