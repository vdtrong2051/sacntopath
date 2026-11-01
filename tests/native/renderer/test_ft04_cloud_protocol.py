"""FT-04 ABI v1 golden and hostile inputs; no SDK, camera, or VTK required."""
from __future__ import annotations
import struct
from multiprocessing import shared_memory

import numpy as np
import pytest

from scantopath.modules.viewer3d.infrastructure.resident_poc.cloud_protocol import (
    CloudIdentity, CloudProtocolError, CLOUD_SHM_BYTES, HEADER_BYTES,
    MAGIC, MAX_POINTS, SLOT_BYTES, encode_cloud, decode_cloud, publish_slot,
    read_slot,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.protocol import (
    decode_request, encode_response,
)


def identity(sequence=1, generation=7):
    return CloudIdentity(461, generation, sequence, 99 + sequence, 123456, 'a' * 64)


def xyz():
    return np.array([[0., 0., 1.], [.25, -.5, 2.]], dtype='<f4')


def test_ipc_abi_01_golden_header_exact_offsets_and_roundtrip():
    blob = encode_cloud(identity(), xyz())
    assert len(blob) == 128 + 24
    assert blob[:8] == MAGIC
    assert struct.unpack_from('<HHHH', blob, 8) == (1, 0, 128, 0)
    assert struct.unpack_from('<Q', blob, 16)[0] == 461
    assert struct.unpack_from('<Q', blob, 24)[0] == 7
    assert struct.unpack_from('<Q', blob, 32)[0] == 1
    assert struct.unpack_from('<I', blob, 56)[0] == 2
    assert struct.unpack_from('<I', blob, 60)[0] == 24
    assert struct.unpack_from('<I', blob, 64)[0] == 12
    assert struct.unpack_from('<I', blob, 68)[0] == 1
    assert blob[72:104] == bytes.fromhex('a' * 64)
    assert struct.unpack_from('<I', blob, 108)[0] == 1
    assert blob[112:128] == bytes(16)
    decoded, out = decode_cloud(blob)
    assert decoded == identity()
    np.testing.assert_array_equal(out, xyz())
    assert not out.flags.writeable
    assert not np.shares_memory(out, np.frombuffer(blob, dtype='u1'))


@pytest.mark.parametrize('offset,replacement', [
    (0, b'BADMAGIC'), (8, struct.pack('<H', 2)),
    (10, struct.pack('<H', 1)), (12, struct.pack('<H', 127)),
    (14, struct.pack('<H', 1)), (56, struct.pack('<I', MAX_POINTS + 1)),
    (60, struct.pack('<I', 25)), (64, struct.pack('<I', 16)),
    (68, struct.pack('<I', 9)), (108, struct.pack('<I', 2)),
    (112, b'\x01'), (104, b'\xff\xff\xff\xff'),
])
def test_ipc_abi_02_reject_header_corruption(offset, replacement):
    blob = bytearray(encode_cloud(identity(), xyz()))
    blob[offset:offset + len(replacement)] = replacement
    with pytest.raises(CloudProtocolError):
        decode_cloud(blob)


@pytest.mark.parametrize('arr', [
    np.array([[0, 0, 0]],dtype='<f4'),
    np.array([[0, 0, -1]],dtype='<f4'),
    np.array([[0, 0, np.nan]],dtype='<f4'),
    np.array([[np.inf, 0, 1]],dtype='<f4'),
    np.ones((0,3),dtype='<f4'),
    np.ones((MAX_POINTS + 1,3),dtype='<f4'),
    np.ones((3,3),dtype='<f8'),
    np.ones((3,4),dtype='<f4'),
])
def test_ipc_abi_03_reject_bad_geometry(arr):
    with pytest.raises(CloudProtocolError):
        encode_cloud(identity(), arr)


def test_ipc_abi_04_truncation_and_crc():
    blob = encode_cloud(identity(), xyz())
    with pytest.raises(CloudProtocolError):
        decode_cloud(blob[:100])
    with pytest.raises(CloudProtocolError):
        decode_cloud(blob[:-1])
    bad = bytearray(blob)
    bad[-1] ^= 1
    with pytest.raises(CloudProtocolError) as e:
        decode_cloud(bad)
    assert e.value.code == 'CLOUD_CRC_INVALID'


def test_ipc_life_01_two_independent_slots_and_publish():
    shm = shared_memory.SharedMemory(create=True,size=CLOUD_SHM_BYTES)
    try:
        b0 = encode_cloud(identity(1), xyz())
        b1 = encode_cloud(identity(2), xyz() * 2)
        publish_slot(shm,0,b0)
        publish_slot(shm,1,b1)
        i0,x0=read_slot(shm,0)
        i1,x1=read_slot(shm,1)
        assert (i0.cloud_sequence,i1.cloud_sequence) == (1,2)
        np.testing.assert_array_equal(x0,xyz())
        np.testing.assert_array_equal(x1,xyz() * 2)
        # VTK would retain its owned copy after ACK; rewrite input is invisible.
        publish_slot(shm,0,encode_cloud(identity(3),xyz()*3))
        np.testing.assert_array_equal(x0,xyz())
    finally:
        shm.close()
        shm.unlink()


def test_ipc_life_02_invalid_slot_without_write():
    shm=shared_memory.SharedMemory(create=True,size=CLOUD_SHM_BYTES)
    try:
        with pytest.raises(CloudProtocolError):
            publish_slot(shm,2,encode_cloud(identity(),xyz()))
        with pytest.raises(CloudProtocolError):
            read_slot(shm,-1)
    finally:
        shm.close();shm.unlink()


@pytest.mark.parametrize('op,extra', [
    ('begin_live_cloud', dict(live_session_token=461,camera_generation=7)),
    ('update_live_cloud',dict(live_session_token=461,camera_generation=7,cloud_sequence=1,slot=0)),
    ('end_live_cloud', dict(live_session_token=461,camera_generation=7)),
])
def test_ipc_data_01_json_strict_valid(op,extra):
    packet = {'id':1,'op':op,**extra}
    assert decode_request(encode_response(packet)) == packet


@pytest.mark.parametrize('mutation', [
    {'live_session_token':True},{'live_session_token':0},
    {'camera_generation':0},{'cloud_sequence':0},
    {'slot':2},{'unexpected_field':'blocked'},
])
def test_ipc_data_02_json_rejects_invalid(mutation):
    packet = {'id':1,'op':'update_live_cloud','live_session_token':1,
              'camera_generation':1,'cloud_sequence':1,'slot':0,**mutation}
    with pytest.raises(ValueError):
        decode_request(encode_response(packet))
