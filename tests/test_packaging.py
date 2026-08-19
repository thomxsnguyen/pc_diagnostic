from pathlib import Path

from package_mac import app_plist
from package_win import render_inno_script


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
