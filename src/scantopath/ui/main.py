"""Điểm vào desktop ScanToPath (GĐ1-06.3); không mở SDK/SQLite khi import."""
from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from scantopath.ui.shell import ScanToPathMainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if argv is None else argv)
    # Keep a valid point-size baseline even if a Windows theme returns a
    # pixel-sized QFont with pointSize() == -1 (Qt warns on setPointSize(-1)).
    if app.font().pointSize() <= 0:
        font = QFont(app.font())
        font.setPointSize(10)
        app.setFont(font)
    app.setApplicationName("ScanToPath")
    app.setOrganizationName("ScanToPath")
    window = ScanToPathMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
