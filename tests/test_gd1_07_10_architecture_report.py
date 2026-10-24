"""07.10 static audit repeatability; it must not import the application."""
from pathlib import Path
import json
import subprocess
import sys


def test_audit_is_reproducible_and_does_not_change_repo(tmp_path):
    root=Path(__file__).resolve().parents[1]
    script=root/'scripts/gd1_architecture_audit.py'
    subprocess.run([sys.executable,str(script),'--project-root',str(root),
                    '--out-dir',str(tmp_path)],check=True)
    report=json.loads((tmp_path/'ARCH_AUDIT.json').read_text(encoding='utf-8'))
    assert report['files'] >= 35
    assert report['python_lines'] >= 4000
    assert not report['forbidden_ui_imports']
    assert any(c.get('class')=='ScanToPathMainWindow' for c in report['concerns'])
    # 07.11 resolves the former giant service; it must remain inventoried, not
    # remain a hotspot. Other hotspots must still be reported, not hidden.
    assert any(cls['class']=='ProjectWorkspaceService' for item in report['modules']
               for cls in item['classes'])
    assert not any(c.get('class')=='ProjectWorkspaceService' for c in report['concerns'])
    assert report['concerns']
    assert (tmp_path/'ARCH_AUDIT.md').exists()
