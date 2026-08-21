from pathlib import Path

from pc_diagnostic.main import _application_log_path, _resolve_execution_modes


def test_frozen_app_launches_gui_without_a_terminal() -> None:
    modes = _resolve_execution_modes(
        requested_gui=False,
        requested_tui=False,
        requested_log=False,
        is_tty=False,
        is_frozen=True,
        gui_available=True,
    )

    assert modes == (False, False, True)


def test_development_pipe_keeps_headless_log_mode() -> None:
    modes = _resolve_execution_modes(
        requested_gui=False,
        requested_tui=False,
        requested_log=False,
        is_tty=False,
        is_frozen=False,
        gui_available=True,
    )

    assert modes == (True, False, False)


def test_explicit_log_mode_overrides_frozen_gui_default() -> None:
    modes = _resolve_execution_modes(
        requested_gui=False,
        requested_tui=False,
        requested_log=True,
        is_tty=False,
        is_frozen=True,
        gui_available=True,
    )

    assert modes == (True, False, False)


def test_frozen_macos_app_uses_user_library_log_directory() -> None:
    path = _application_log_path(
        is_frozen=True,
        system="Darwin",
        home=Path("/Users/tester"),
        local_app_data=None,
    )

    assert path == Path(
        "/Users/tester/Library/Logs/PC Diagnostic/pc_diagnostic.log"
    )


def test_frozen_windows_app_uses_local_app_data_log_directory() -> None:
    path = _application_log_path(
        is_frozen=True,
        system="Windows",
        home=Path("C:/Users/tester"),
        local_app_data="C:/Users/tester/AppData/Local",
    )

    assert path == Path(
        "C:/Users/tester/AppData/Local/PC Diagnostic/Logs/pc_diagnostic.log"
    )
