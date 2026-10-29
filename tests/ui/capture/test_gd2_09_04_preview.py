
"""GD2-09.04: offline Qt preview widget tests."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.decoding import DecodedRgbdFrame
from scantopath.modules.capture.presentation.preview_widget import (
    CapturePreviewWidget,
    depth_display_u8,
    owned_rgb_image,
    owned_depth_image,
)
from tests.support.raw_fixture import raw


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    widget = CapturePreviewWidget()
    widget.resize(900, 490)
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    qapp.processEvents()


def context():
    return CaptureContext(
        "C:/fixture-store", "p1", "s1", "t1", "c1"
    )


def frame():
    base = raw(session="t1", specimen="s1", capture_id="c1")

    rgb = np.zeros((4, 5, 3), dtype=np.uint8)
    rgb[:, :, :] = (255, 0, 0)
    rgb[0, 0, :] = (0, 0, 255)

    depth = np.array(
        [[0, 100, 200], [300, 400, 65535]],
        dtype=np.uint16,
    )

    return DecodedRgbdFrame(
        color_rgb=rgb,
        depth_u16=depth,
        metadata=base.metadata,
    )


def has_image(label) -> bool:
    """Compatible with Qt bindings returning None or QPixmap(null)."""
    pixmap = label.pixmap()
    return pixmap is not None and not pixmap.isNull()

def test_initial_state_has_no_fake_image(panel):
    assert panel.context is None
    assert not panel.replay_button.isEnabled()
    assert not has_image(panel.rgb_image)
    assert not has_image(panel.depth_image)
    assert "Chưa tải dữ liệu" in panel.state_label.text()


def test_explicit_context_enables_replay(panel):
    panel.set_context(context())

    assert panel.replay_button.isEnabled()
    assert "c1" in panel.context_label.text()
    assert "t1" in panel.context_label.text()


def test_busy_state_disables_action(panel):
    panel.set_context(context())
    panel.set_busy(True)

    assert not panel.replay_button.isEnabled()

    panel.set_busy(False)
    assert panel.replay_button.isEnabled()


def test_depth_display_preserves_invalid_zero():
    data = np.array(
        [[0, 100, 200], [300, 400, 65535]],
        dtype=np.uint16,
    )
    before = data.copy()

    gray = depth_display_u8(data)

    assert gray.dtype == np.uint8
    assert gray.shape == data.shape
    assert gray[0, 0] == 0
    assert not gray.flags.writeable

    np.testing.assert_array_equal(data, before)


def test_constant_nonzero_depth_is_displayable():
    depth = np.full((8, 10), 1250, dtype=np.uint16)
    gray = depth_display_u8(depth)

    assert np.all(gray == 180)


def test_depth_display_rejects_wrong_dtype():
    with pytest.raises(ValueError):
        depth_display_u8(np.ones((2, 3), dtype=np.float32))


def test_qimage_owns_rgb_pixel_memory():
    array = np.zeros((4, 5, 3), dtype=np.uint8)
    array[:, :, :] = (250, 5, 2)

    image = owned_rgb_image(array)
    array[:, :, :] = 0

    pixel = image.pixelColor(2, 2)

    assert pixel.red() == 250
    assert pixel.green() == 5
    assert pixel.blue() == 2


def test_qimage_owns_depth_pixel_memory():
    array = np.full((4, 5), 150, dtype=np.uint8)

    image = owned_depth_image(array)
    array[:, :] = 0

    assert image.pixelColor(2, 2).red() == 150


def test_widget_displays_both_native_grids(panel, qapp):
    decoded = frame()
    gray = depth_display_u8(decoded.depth_u16)

    panel.set_context(context())
    panel.show_frame(decoded, gray)
    qapp.processEvents()

    assert has_image(panel.rgb_image)
    assert has_image(panel.depth_image)

    assert "5 × 4" in panel.metadata_label.text()
    assert "3 × 2" in panel.metadata_label.text()
    assert "0.001" in panel.metadata_label.text()

    assert "Fixture tổng hợp" in panel.state_label.text()
    assert decoded.metadata.camera_pose is None


def test_context_invalidation_clears_preview(panel):
    decoded = frame()

    panel.set_context(context())
    panel.show_frame(
        decoded,
        depth_display_u8(decoded.depth_u16),
    )

    panel.set_context(None)

    assert not has_image(panel.rgb_image)
    assert not has_image(panel.depth_image)
    assert not panel.replay_button.isEnabled()


def test_error_clears_old_images(panel):
    decoded = frame()
    panel.set_context(context())

    panel.show_frame(
        decoded,
        depth_display_u8(decoded.depth_u16),
    )
    panel.show_error("RAW không hợp lệ")

    assert not has_image(panel.rgb_image)
    assert not has_image(panel.depth_image)
    assert "RAW không hợp lệ" in panel.state_label.text()


def test_resize_does_not_remove_images(panel, qapp):
    decoded = frame()
    panel.set_context(context())

    panel.show_frame(
        decoded,
        depth_display_u8(decoded.depth_u16),
    )

    panel.resize(700, 400)
    qapp.processEvents()

    assert has_image(panel.rgb_image)
    assert has_image(panel.depth_image)
