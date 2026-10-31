"""UXH-01.2: four grid modes across IPC and async command validation."""
import json
import pytest
from scantopath.modules.viewer3d.infrastructure.resident_poc.protocol import decode_request
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
from scantopath.modules.viewer3d.infrastructure.resident_poc.client import RenderHostError


@pytest.mark.parametrize('mode', ['xy', 'xz', 'yz', 'base'])
def test_ipc_accepts_four_reference_planes(mode):
    msg = {'id': 1, 'op': 'set_grid', 'enabled': True, 'mode': mode}
    assert decode_request((json.dumps(msg) + '\n').encode('ascii'))['mode'] == mode


@pytest.mark.parametrize('mode', ['world', 'floor', '', None, 1])
def test_ipc_rejects_invalid_grid_modes(mode):
    with pytest.raises(ValueError, match='INVALID_REFERENCE_GRID'):
        msg = {'id': 1, 'op': 'set_grid', 'enabled': True, 'mode': mode}
        decode_request((json.dumps(msg) + '\n').encode('ascii'))


def test_async_grid_accepts_new_modes_before_session_state_check():
    session = CoalescingRenderSession(320, 240)
    # Session is not started. For a VALID mode we expect this state error,
    # not INVALID_REFERENCE_GRID. No Render Host process is spawned.
    for mode in ('xy', 'xz', 'yz', 'base'):
        with pytest.raises(RenderHostError, match='SESSION_NOT_RUNNING'):
            session.set_grid(True, mode)
    with pytest.raises(ValueError, match='INVALID_REFERENCE_GRID'):
        session.set_grid(True, 'world')
