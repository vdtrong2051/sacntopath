"""Điểm vào desktop ScanToPath (GĐ1-06.3); không mở SDK/SQLite khi import."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from scantopath.ui.shell import ScanToPathMainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("ScanToPath")
    app.setOrganizationName("ScanToPath")
    window = ScanToPathMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
