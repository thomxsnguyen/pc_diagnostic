# Build & Packaging

PC Diagnostic can be packaged as a standalone executable using PyInstaller.
This document covers the build pipeline, native compilation, and code signing.

---

## Build Pipeline (`build_binaries.py`)

The build script orchestrates a multi-step pipeline:

```
1. Compile native macOS SMC helper  (macOS only)
2. Code-sign the SMC helper binary  (macOS only)
3. Run PyInstaller build
4. Code-sign the final application  (macOS only)
5. Verify build output
```

### Usage

```bash
python build_binaries.py
```

---

## Step 1: Native SMC Helper Compilation

On macOS, the SMC helper C source (`src/pc_diagnostic/providers/smc_helper.c`)
is compiled into a native binary:

```bash
clang -O3 -framework IOKit -framework CoreFoundation smc_helper.c -o smc_helper
```

This binary is bundled into the PyInstaller package as a data file so the
`SmcProvider` can invoke it at runtime.

**Skipped on non-macOS platforms.**

---

## Step 2: Code Signing (macOS)

The `sign_binary()` function handles macOS code signing with two modes:

### Ad-hoc Signing (default)

When no `CODESIGN_IDENTITY` environment variable is set, uses identity `"-"`:

```bash
codesign --force --sign - <binary>
```

This is for local development. Does not enforce hardened runtime to allow loading
Python shared libraries from different Team IDs.

### Developer ID Signing

When `CODESIGN_IDENTITY` is set (e.g., for distribution):

```bash
codesign --force --options runtime --entitlements entitlements.plist --sign <identity> <binary>
```

The entitlements plist is generated dynamically if missing, with:
- `com.apple.security.cs.disable-library-validation` = `true`

This is necessary because PyInstaller bundles contain Python shared libraries
that won't pass strict library validation.

---

## Step 3: PyInstaller Build

Uses the `pc_diagnostic.spec` file for configuration:

```bash
pyinstaller --clean pc_diagnostic.spec
```

The spec file defines:
- Entry point: `src/pc_diagnostic/main.py`
- Bundled data files (including the SMC helper binary)
- Hidden imports for dynamic dependencies
- Output: single-file executable in `dist/`

---

## Step 4: Final Application Signing

After PyInstaller produces the executable, it's code-signed using the same
`sign_binary()` function. On macOS, this signs:

```
dist/pc_diagnostic
```

---

## Step 5: Build Verification

Checks that the expected output file exists:

- macOS/Linux: `dist/pc_diagnostic`
- Windows: `dist/pc_diagnostic.exe`

Exits with code 1 if the binary is missing.

---

## macOS Packaging (`package_mac.py`)

A separate script for creating macOS distribution packages (DMG, etc.).
See `package_mac.py` for details.

---

## Project Configuration (`pyproject.toml`)

```toml
[project]
name = "pc-diagnostic"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "psutil>=5.9.0",     # Cross-platform system monitoring
    "rich>=13.0.0",      # Terminal UI rendering
    "crewai>=0.1.0",     # AI diagnostics (optional at runtime)
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",     # Testing
    "ruff>=0.3.0",       # Linting + formatting
    "mypy>=1.8.0",       # Type checking (strict mode)
    "pyinstaller>=6.0.0", # Standalone bundling
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Tooling

| Tool          | Config Location     | Purpose                         |
|---------------|---------------------|---------------------------------|
| Ruff          | `pyproject.toml`    | Linting (E, F, I, N, UP, B, A, C4, RUF) + formatting |
| mypy          | `pyproject.toml`    | Strict type checking            |
| pytest        | Default discovery   | Unit tests in `tests/`          |
| PyInstaller   | `pc_diagnostic.spec`| Standalone executable bundling  |

### src/ Layout

The `src/pc_diagnostic/` layout (as opposed to flat `pc_diagnostic/` at root)
prevents a common Python packaging bug: without `src/`, running tests from the
repo root can accidentally import the local directory instead of the installed
package. The `src/` layout forces you to install the package (even in editable
mode) before importing it.
