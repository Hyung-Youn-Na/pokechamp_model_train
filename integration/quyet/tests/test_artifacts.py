import copy
import json
from pathlib import Path

import pytest

from integration.quyet import audit, execute, resource, study, viewer
from integration.quyet.config import BASELINE, ROOT, RUNTIME
from integration.quyet.model import fixed_device_map
from integration.quyet.tests.test_policy import payload


def test_device_split_and_resource_caps_cover_all_four_gpus():
    mapping=fixed_device_map()
    assert mapping['model.embed_tokens']==mapping['lm_head']==0
    assert mapping['model.norm']==3
    assert [mapping[f'model.layers.{i}'] for i in range(32)] == [0]*8+[1]*8+[2]*8+[3]*8
    sample=dict(rss_bytes=32*1024**3,disk_bytes=100*1024**3,
                gpus={i:{'memory_used_mib':44*1024} for i in range(4)},
                gpu_allocated_bytes=[40*1024**3]*4)
    assert resource.limit_errors(sample)==[]
    sample['gpu_allocated_bytes'][3]+=1
    assert resource.limit_errors(sample)==['gpu3_allocated_bytes_exceeded']
    sample['gpus'][2]['memory_used_mib']+=1
    assert 'gpu2_memory_exceeded' in resource.limit_errors(sample)
    roots=resource.disk_roots()
    assert RUNTIME.resolve() in roots and BASELINE.resolve() in roots
    assert not any(a!=b and a in b.parents for a in roots for b in roots)


def test_reference_has_unique_complete_schedule_but_no_inherited_new_outcomes():
    manifest,result=study.load_baseline()
    assert len(manifest['schedule'])==len(result['outcomes'])==32
    assert [r['submission_order'] for r in manifest['schedule']]==list(range(1,33))
    assert len({r['paired_slot_id'] for r in manifest['schedule']})==16
    assert manifest['schedule'][0]['slot_id']=='b01-r3-s1'


def test_export_all_raw_stages_and_detect_tampering(tmp_path):
    source=tmp_path/'source';source.mkdir();out=tmp_path/'export'
    p=payload();p['state']['turn']=2
    events=[dict(type='input',decision='user-8-1',payload=p,at=1,event_seq=1),
            dict(type='stage_selection',decision='user-8-1',stage='action_type',automatic=False,choice='move',event_seq=2),
            dict(type='http_request',decision='user-8-1',stage='action_detail',body={'original':'</script> \n hello'},
                 raw_body='{"original":"raw bytes"}',event_seq=3),
            dict(type='stage_failure',decision='user-8-1',stage='action_detail',error={'type':'UnusableChoice','detail':'outside'},event_seq=4)]
    (source/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    outcome=dict(slot=1,slot_id='a',username='user',jev_actor='p1',completed=False,outcome='output_failure')
    result=dict(planned=32,completed=0,failed=1,invalid=0,unattempted=31,completed_pairs=0,
                overall=dict(wins=0,draws=0,losses=0),decisions=1,outcomes=[outcome])
    study.write_json(source/'result.json',result);study.write_json(source/'manifest.json',{'experiment_id':'EX-084'})
    study.seal(source)
    assert viewer.export(source,out,compared={})['decisions']==1
    actual=json.loads((out/'battle-1/decisions.json').read_text())
    detail=actual['decisions'][0]['stages']['action_detail']
    assert detail==events[2:]
    assert actual['decisions'][0]['wire'] is None
    actual['decisions'][0]['stages']['action_detail'][0]['body']['original']='tampered'
    study.write_json(out/'battle-1/decisions.json',actual)
    with pytest.raises(ValueError,match='originals differ'):viewer.verify_data(source,out)


def test_preflight_rejects_previous_execution_without_starting_any_process(tmp_path,monkeypatch):
    (tmp_path/'execution.json').write_text('{}')
    monkeypatch.setattr(execute,'RUN',tmp_path)
    with pytest.raises(FileExistsError):execute.execute()


def test_final_check_rejects_missing_match_audit(tmp_path):
    study.write_json(tmp_path/'manifest.json',{'schedule':[{'slot_id':'x'}]})
    study.write_json(tmp_path/'result.json',{'outcomes':[{'slot_id':'x','slot':1}]})
    (tmp_path/'events.jsonl').write_text('')
    study.seal(tmp_path)
    result=audit.final_check(tmp_path)
    assert not result['passed'] and result['observation_reaudits']==0


def test_terminal_status_is_included_in_final_seal(tmp_path, monkeypatch):
    from contextlib import redirect_stdout
    monkeypatch.setattr(execute, 'RUN', tmp_path)
    monkeypatch.setattr(execute, 'EVIDENCE', tmp_path/'evidence')
    monkeypatch.setattr(execute, 'report', lambda _: (tmp_path/'report.md').write_text('완료\n'))
    completion = dict(passed=True, error=None, result=dict(completed=32))
    with (tmp_path/'controller.log').open('w') as output, redirect_stdout(output):
        execute.finish_completion(completion)
    assert json.loads((tmp_path/'controller.log').read_text())['completed'] == 32
    assert 'controller.log' in study.verify_seal(tmp_path)
