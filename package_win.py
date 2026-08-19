# ruff: noqa: E501 - Inno Setup directives must remain single physical lines.
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "PC Diagnostic"
VERSION = "0.1.0"


def render_inno_script(source_executable: Path, output_dir: Path) -> str:
    source = str(source_executable.resolve()).replace("\\", "\\\\")
    output = str(output_dir.resolve()).replace("\\", "\\\\")
    return f'''#define MyAppName "{APP_NAME}"
#define MyAppVersion "{VERSION}"
#define MyAppPublisher "PC Diagnostic"
#define MyAppExeName "pc_diagnostic.exe"

[Setup]
AppId={{{{DF8A2396-6B22-4CE8-BA77-C6C0B6CF015A}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\PC Diagnostic
DefaultGroupName=PC Diagnostic
OutputDir={output}
OutputBaseFilename=PC-Diagnostic-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}

[Files]
Source: "{source}"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{autoprograms}}\\PC Diagnostic"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\PC Diagnostic"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "Launch PC Diagnostic"; Flags: nowait postinstall skipifsilent
'''


def build_installer() -> Path:
    if platform.system() != "Windows":
        raise RuntimeError("Windows packaging must run on Windows")

    project_dir = Path(__file__).resolve().parent
    source_executable = project_dir / "dist" / "pc_diagnostic.exe"
    if not source_executable.is_file():
        raise FileNotFoundError(
            "dist/pc_diagnostic.exe was not found; run build_binaries.py first"
        )

    iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    if iscc is None:
        raise RuntimeError("Inno Setup 6 is required and ISCC.exe must be on PATH")

    script_dir = project_dir / "build" / "installer"
    output_dir = project_dir / "dist" / "installer"
    script_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / "pc_diagnostic.iss"
    script_path.write_text(
        render_inno_script(source_executable, output_dir), encoding="utf-8"
    )
    subprocess.run([iscc, str(script_path)], check=True)

    installer = output_dir / "PC-Diagnostic-Setup.exe"
    if not installer.is_file():
        raise RuntimeError(f"Inno Setup did not produce {installer}")
    print(f"[SUCCESS] Windows installer created: {installer}")
    return installer


if __name__ == "__main__":
    try:
        build_installer()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
