"""UI HMI resource tests independent of Qt and camera."""
from __future__ import annotations

from pathlib import Path
import tomllib

from scantopath.ui.theme import load_hmi_qss


def test_hmi_resource_packaged_and_subdued():
    qss = load_hmi_qss()
    assert "QMainWindow#ScanToPathMainWindow" in qss
    assert "QDockWidget::title" in qss
    assert "QFrame#workspacePanel" in qss
    assert "QScrollBar:vertical" in qss
    assert "#workspaceState" in qss
    assert "gradient" not in qss.lower().replace("không gradients", "")
    assert qss.count("{") == qss.count("}")
    assert "#" in qss


def test_qss_in_setuptools_package_data():
    root = Path(__file__).resolve().parents[3]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert "*.qss" in data["tool"]["setuptools"]["package-data"]["scantopath.ui.theme"]
