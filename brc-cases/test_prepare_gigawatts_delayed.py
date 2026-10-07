import numpy as np
import pytest
from prepare_gigawatts_delayed import tracer_summary


@pytest.fixture
def tags():
    fields={f'tr17_{n}':np.zeros((1,2,4,4)) for n in range(1,25)}
    fields['tr17_1'][0,0]=.7
    fields['tr17_2'][0,0]=.7*285
    return fields


def test_only_front_source_pairs_need_to_be_present(tags):
    result=tracer_summary(tags,[(270,310)]*11)
    assert result['held_pair_zero']
    assert result['pairs'][0]['active_cells']==16
    assert all(p['active_cells']==0 for p in result['pairs'][1:])


@pytest.mark.parametrize('field,value,message',[
    ('tr17_2',1.,'theta ratio'),('tr17_23',.1,'held pair'),('tr17_1',float('nan'),'nonfinite')])
def test_bad_inheritance_is_rejected(tags,field,value,message):
    tags[field][0,0,0,0]=value
    with pytest.raises(AssertionError,match=message):tracer_summary(tags,[(270,310)]*11)


def test_missing_tags_are_not_success(tags):
    for a in tags.values():a[:]=0
    with pytest.raises(AssertionError,match='no inherited'):tracer_summary(tags,[(270,310)]*11)


def test_masked_tracer_is_rejected(tags):
    tags['tr17_1']=np.ma.array(tags['tr17_1'],mask=False)
    tags['tr17_1'].mask[0,0,0,0]=True
    with pytest.raises(AssertionError,match='masked'):tracer_summary(tags,[(270,310)]*11)
