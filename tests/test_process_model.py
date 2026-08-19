from __future__ import annotations

from typing import Any

import pytest

from pc_diagnostic.gui.bridge import PYSIDE6_AVAILABLE
from pc_diagnostic.gui.components import process_table
from pc_diagnostic.gui.components.process_table import ProcessTableWidget

pytestmark = pytest.mark.skipif(not PYSIDE6_AVAILABLE, reason="PySide6 not installed")


def test_process_table_sorts_numerically_and_filters(qtbot: Any) -> None:
    from PySide6.QtCore import Qt

    widget = ProcessTableWidget()
    qtbot.addWidget(widget)
    widget.update_processes(
        [
            (101, "small", 5.0, 80.0, "running"),
            (102, "large", 100.0, 900.0, "sleeping"),
            (103, "medium", 25.0, 300.0, "running"),
        ]
    )

    widget.table.sortItems(2, Qt.SortOrder.DescendingOrder)
    assert widget.table.item(0, 2).text() == "100.0%"
    widget.search_input.setText("medium")
    assert widget.lbl_process_count.text() == "1 Processes"


def test_process_termination_routes_term_and_kill(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    class FakeProcess:
        def terminate(self) -> None:
            calls.append("terminate")

        def kill(self) -> None:
            calls.append("kill")

    class FakePsutil:
        NoSuchProcess = ProcessLookupError
        AccessDenied = PermissionError

        @staticmethod
        def Process(pid: int) -> FakeProcess:  # noqa: N802
            assert pid == 42
            return FakeProcess()

    monkeypatch.setattr(process_table, "psutil", FakePsutil)
    widget = ProcessTableWidget()
    qtbot.addWidget(widget)

    assert widget._terminate_pid(42, "worker") is True
    assert widget._terminate_pid(42, "worker", force=True) is True
    assert calls == ["terminate", "kill"]

