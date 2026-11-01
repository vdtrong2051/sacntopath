"""UXH-01.5: actual typed native-pick contract, no GUI or VTK needed."""
import copy
import math
import pytest

from scantopath.modules.viewer3d.application.scene_contracts import SceneDescriptor, SceneSelectionRef
from scantopath.modules.viewer3d.application.typed_pick import (
    StalePickResult, validate_native_pick,
)


def _descriptor(kind='mesh'):
    return SceneDescriptor.from_result({
        'name':'part.ply', 'source_sha256':'a'*64, 'source_bytes':150,
        'source_format':'ply','geometry_kind':kind,'point_count':4,
        'face_count':2 if kind=='mesh' else 0,
        'bounds':[-1,1,-1,1,-1,1],'has_rgb':False,
        'units':'unknown','coordinate_frame':'unknown',
    })


def _result(kind='mesh'):
    return {'id':1,'ok':True,'scene_revision':3,'frame_revision':8,
            'source_sha256':'a'*64,'geometry_kind':kind,
            'units':'unknown','coordinate_frame':'unknown','hit':True,
            'kind':'face' if kind=='mesh' else 'point',
            'element_id':1,'xyz':[0.25,0.5,-0.75]}


def test_hit_for_point_and_face_is_typed_and_unverified():
    for kind in ('mesh','points'):
        result = validate_native_pick(_result(kind),_descriptor(kind),3,8)
        assert isinstance(result,SceneSelectionRef)
        assert result.kind == ('face' if kind=='mesh' else 'point')
        assert result.xyz == (0.25,0.5,-0.75)
        assert result.units == result.coordinate_frame == 'unknown'


def test_clean_miss_returns_none_not_stale_selection():
    payload=_result();payload['hit']=False
    for field in ('kind','element_id','xyz'):payload.pop(field)
    assert validate_native_pick(payload,_descriptor(),3,8) is None
    for field in ('kind','xyz','element_id'):
        invalid=dict(payload,**{field:None})
        with pytest.raises(ValueError):validate_native_pick(invalid,_descriptor(),3,8)


@pytest.mark.parametrize('mutation',[ 
    {'scene_revision':2}, {'frame_revision':7},
    {'source_sha256':'b'*64}, {'geometry_kind':'points'},
])
def test_identity_mismatch_is_stale(mutation):
    data={**_result(),**mutation}
    with pytest.raises(StalePickResult):validate_native_pick(data,_descriptor(),3,8)


@pytest.mark.parametrize('mutation',[ 
    {'kind':'point'},{'kind':True},{'element_id':2},
    {'element_id':True},{'element_id':-1},{'xyz':[0.,float('nan'),0.]},
    {'xyz':[float('inf'),0.,0.]},{'xyz':[True,0.,0.]},
    {'xyz':'1,2,3'},{'units':'mm'},
    {'coordinate_frame':'world'},{'id':True},{'ok':False},
    {'scene_revision':True},{'frame_revision':False},
    {'hit':1}, {'unexpected':'something'},
])
def test_reject_malformed_reply(mutation):
    with pytest.raises((ValueError,TypeError)):
        validate_native_pick({**_result(),**mutation},_descriptor(),3,8)


def test_no_implicit_scene_or_frame_guess():
    with pytest.raises(ValueError):validate_native_pick(_result(),_descriptor(),0,8)
    with pytest.raises(ValueError):validate_native_pick(_result(),_descriptor(),3,True)
    assert validate_native_pick({k:v for k,v in _result().items() if k not in ('id','ok')},
                                _descriptor(),3,8).element_id==1
    with pytest.raises(ValueError):validate_native_pick({k:v for k,v in _result().items() if k!='ok'},
                                                         _descriptor(),3,8)


def test_result_is_immutable_and_copies_source_values():
    data=_result()
    result=validate_native_pick(data,_descriptor(),3,8)
    data['xyz'][0]=900
    assert result.xyz[0]==0.25
    with pytest.raises((AttributeError,TypeError)):
        result.element_id = 4
