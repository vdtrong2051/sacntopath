"""Minimal PySide6 project shell. No heavy 3D viewer in phase 01."""
import sys
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QWidget, QVBoxLayout


def main() -> None:
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("ScanToPath | Software foundation (offline)")
    tabs = QTabWidget()
    pages = {
        "Project": "Project / Specimen / Session records",
        "Acquisition": "Gemini 2 SDK v2 integration follows hardware verification",
        "Geometry": "Point-cloud pipeline / native C++20 core",
        "Quality": "Measurement error, coverage, provenance",
        "Features": "Planes, cylinders, holes, axes, relationships",
        "Replica": "Engineering digital replica",
        "Export": "Technical outputs (not CNC/robot commands)",
    }
    for title, detail in pages.items():
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(detail))
        tabs.addTab(widget, title)
    win.setCentralWidget(tabs)
    win.resize(980, 640)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
