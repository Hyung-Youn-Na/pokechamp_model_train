import copy,json
import pytest
from .study import partition_schedule
from .report import aggregate
from .core import BASELINE


def test_full_schedule_disjoint_pairs_and_original_rows():
    full=json.loads((BASELINE/'manifest.json').read_text())['schedule'];before=copy.deepcopy(full);parts=partition_schedule(full)
    assert full==before
    assert [len(parts[g]) for g in (1,2,3)]==[12,10,10]
    assert {r['slot_id'] for v in parts.values() for r in v}=={r['slot_id'] for r in full}
    for v in parts.values():
        for pair in {r['paired_slot_id'] for r in v}:assert len([r for r in v if r['paired_slot_id']==pair])==2


def test_aggregate_global_slot_identity_and_no_missing_as_loss():
    full=json.loads((BASELINE/'manifest.json').read_text())['schedule'];parts=partition_schedule(full);rs={}
    for gpu,part in parts.items():
        outcomes=[dict(r,slot=i+1,completed=True,audit_passed=True,outcome='player_won' if r['jev_actor']=='p1' else 'player_lost') for i,r in enumerate(part)]
        rs[gpu]=dict(outcomes=outcomes,pair_scores={r['paired_slot_id']:.5 for r in part},passed=True)
    result=aggregate(rs,full);assert result['passed'] and result['overall']['wins']==16 and result['overall']['losses']==16
    assert [o['slot_id'] for o in result['outcomes']]==[o['slot_id'] for o in full]
    partial=aggregate({1:rs[1]},full);assert not partial['passed'] and partial['unattempted']==20 and partial['overall']['losses']==6
    bad=copy.deepcopy(rs);bad[2]['outcomes'].append(rs[1]['outcomes'][0])
    with pytest.raises(AssertionError):aggregate(bad,full)
