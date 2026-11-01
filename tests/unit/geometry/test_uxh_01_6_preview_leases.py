"""UXH-01.6: deterministic scratch-directory ownership tests (no GUI/VTK)."""
from __future__ import annotations

from pathlib import Path

from scantopath.application.preview_scratch_leases import PreviewScratchLeases


class Scratch:
    def __init__(self, path: Path, fail_once: bool = False):
        self.path = path
        self.calls = 0
        self.fail_once = fail_once
        path.mkdir()
        (path / 'preview.ply').write_bytes(b'fixture')

    def cleanup(self):
        self.calls += 1
        if self.fail_once:
            self.fail_once = False
            raise PermissionError('simulated renderer file lock')
        (self.path / 'preview.ply').unlink()
        self.path.rmdir()


def test_keeps_current_and_retry_sources_until_retirement(tmp_path):
    leases = PreviewScratchLeases()
    a, b, c = (tmp_path / n for n in ('a', 'b', 'c'))
    items = [Scratch(p) for p in (a, b, c)]
    for p, obj in zip((a, b, c), items):
        leases.retain(p / 'preview.ply', obj)
    assert len(leases) == 3
    # Even when no path looks live, the old renderer may be draining its IPC.
    assert leases.release_except((), renderer_retired=False) == 0
    assert all(p.exists() for p in (a, b, c))
    assert leases.release_except((b / 'preview.ply', c / 'preview.ply', None),
                                 renderer_retired=True) == 1
    assert not a.exists() and b.exists() and c.exists()
    assert leases.contains(b / 'preview.ply')
    assert leases.release_all() == 0
    assert not b.exists() and not c.exists()
    assert [o.calls for o in items] == [1, 1, 1]


def test_retries_windows_permission_error_without_losing_ownership(tmp_path):
    directory = tmp_path / 'locked'
    scratch = Scratch(directory, fail_once=True)
    pool = PreviewScratchLeases()
    src = directory / 'preview.ply'
    pool.retain(src, scratch)
    assert pool.release_except((), renderer_retired=True) == 0
    assert pool.contains(src) and src.is_file()
    assert pool.release_except((), renderer_retired=True) == 1
    assert not pool.contains(src) and not directory.exists()
    assert scratch.calls == 2


def test_rejects_duplicate_and_missing_cleanup(tmp_path):
    pool = PreviewScratchLeases()
    src = tmp_path / 'p.ply'
    owner = Scratch(tmp_path / 'owned')
    pool.retain(src, owner)
    import pytest
    with pytest.raises(ValueError, match='DUPLICATE'):
        pool.retain(src, owner)
    with pytest.raises(TypeError, match='REQUIRES_CLEANUP'):
        pool.retain(tmp_path / 'other.ply', object())
    assert pool.release_all() == 0
    assert owner.calls == 1


def test_no_qt_vtk_or_camera_imports():
    from pathlib import Path
    import ast
    path = Path(__file__).resolve().parents[3] / 'src/scantopath/application/preview_scratch_leases.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    imports = [a.name for node in ast.walk(tree) if isinstance(node, ast.Import)
               for a in node.names]
    imports += [node.module or '' for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)]
    assert not any(n.startswith(('PySide6', 'vtk', 'scantopath.modules.capture')) for n in imports)
