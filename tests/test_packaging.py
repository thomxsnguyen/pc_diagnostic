from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules  # type: ignore[import-untyped]

from package_mac import app_plist
from package_win import render_inno_script

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_mac_plist_launches_gui_binary_and_declares_icon() -> None:
    plist = app_plist()

    assert plist["CFBundleExecutable"] == "pc_diagnostic"
    assert plist["CFBundleIconFile"] == "AppIcon"
    assert plist["CFBundlePackageType"] == "APPL"


def test_inno_script_installs_executable_and_shortcuts(tmp_path: Path) -> None:
    script = render_inno_script(
        tmp_path / "pc_diagnostic.exe", tmp_path / "installer"
    )

    assert "[Setup]" in script
    assert "[Files]" in script
    assert "[Icons]" in script
    assert "PC-Diagnostic-Setup" in script
    assert "pc_diagnostic.exe" in script


def test_pyinstaller_collects_native_keyring_backends() -> None:
    keyring_modules = set(collect_submodules("keyring.backends"))

    assert "keyring.backends.macOS" in keyring_modules
    assert "keyring.backends.macOS.api" in keyring_modules
    assert "keyring.backends.Windows" in keyring_modules

    spec = (PROJECT_ROOT / "pc_diagnostic.spec").read_text(encoding="utf-8")
    assert "collect_submodules('keyring.backends')" in spec
    assert "copy_metadata('keyring')" in spec
    assert "*keyring_hiddenimports" in spec
    assert "keyring_datas" in spec


def test_development_environment_file_remains_ignored() -> None:
    ignored_entries = (PROJECT_ROOT / ".gitignore").read_text(
        encoding="utf-8"
    ).splitlines()

    assert ".env" in ignored_entries
