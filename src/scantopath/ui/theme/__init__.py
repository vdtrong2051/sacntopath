"""QSS resources: HMI neutral appearance, no behavior or service dependencies."""
from __future__ import annotations
from importlib.resources import files


def load_hmi_qss() -> str:
    """Read packaged stylesheet as Unicode (works in editable and wheel installs)."""
    return files("scantopath.ui.theme").joinpath("hmi_panel.qss").read_text(encoding="utf-8")
