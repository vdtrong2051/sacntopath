"""07.9 visual design contract without Qt: avoids false pass on screenshots."""
from pathlib import Path
import re


def _qss() -> str:
    from scantopath.ui.theme import load_hmi_qss
    return load_hmi_qss()


def _lightness(color: str) -> float:
    vals = [int(color[i:i+2], 16)/255 for i in (1,3,5)]
    linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in vals]
    return sum(a*b for a,b in zip(linear, (.2126,.7152,.0722)))


def _contrast(fg: str,bg: str) -> float:
    a,b=sorted((_lightness(fg),_lightness(bg)),reverse=True)
    return (a+.05)/(b+.05)


def test_contrast_exceeds_normal_text_reference():
    # Relative luminance of the shipped default foreground/background tokens.
    assert _contrast('#17263C','#FFFFFF') > 12
    assert _contrast('#405A78','#FFFFFF') > 6
    assert _contrast('#FFFFFF','#1463D7') > 5


def test_qss_has_tangible_rounded_selector_rules():
    qss=_qss()
    assert 'QTabBar::tab:selected' in qss
    assert 'QFrame#workspacePanel' in qss
    assert 'QDockWidget::title' in qss
    assert 'QTreeWidget, QListWidget, QTableWidget' in qss
    assert 'QToolBar#workspaceToolbar' in qss
    assert 'QPushButton#workspacePrimaryAction' in qss
    assert qss.count('border-radius:') >= 10
    assert 'font-size: 10pt' in qss
    assert '#F4F8FD' in qss
    assert '#1463D7' in qss
    assert '#171D25' not in qss
    assert not re.search(r'font-size:\s*-',qss)


def test_readable_workspace_copy_reflects_existing_07_features():
    # Static source assertions: the headless CI host need not install Qt.
    root = Path(__file__).resolve().parents[1]
    source = (root / 'src/scantopath/ui/workspaces/pages.py').read_text(encoding='utf-8')
    assert 'Đã có thể mở kho SQLite' in source
    assert 'Xem ProcessingRun' in source
    assert 'phiên 08' in source
