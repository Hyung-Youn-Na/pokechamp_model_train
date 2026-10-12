import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from integration.pokechamp import jev_study as s, jev_battle as j


def test_repeat_schedule_treatment_and_retry_identity():
    rows, teams, origin=s.study_schedule('EX-054')
    old=json.loads((s.ROOT/'.pokechamp-data/jev/ex053-live/manifest.json').read_text())
    assert (rows,teams)==(old['schedule'],old['teams'])
    assert origin['experiment']=='EX-053'
    identity=s.v3_identity(rows,teams,origin,old['model'],j.source_identity(),'EX-054')
    assert identity['experiment_id']=='EX-054' and identity['limits']['retries']==3
    assert identity['transport_policy']==j.jev_retry.V1 and identity['retry_delays_seconds']==[1,2,4]
    assert identity['prompt_sha256']==s.sha(j.PROMPT)
    assert len(rows)==32 and sum(r['repetition']==1 for r in rows)==8
    assert s.experiment_settings('EX-054')[0].name=='ex054-live'


@pytest.mark.parametrize('alteration',['old_id','zero_retries','delay'])
def test_old_or_wrong_retry_receipt_blocks_new_live(tmp_path,monkeypatch,alteration):
    rows,teams,origin=s.study_schedule('EX-054')
    config=dict(model='test',endpoint='https://invalid.example/systemone')
    source=j.source_identity();identity=s.v3_identity(rows,teams,origin,config,source,'EX-054')
    if alteration=='old_id':identity['experiment_id']='EX-053'
    if alteration=='zero_retries':identity['limits']['retries']=0
    if alteration=='delay':identity['retry_delays_seconds']=[1,2,3]
    receipt=tmp_path/'receipt.json';receipt.write_text(json.dumps(dict(passed=True,source=source,model=config,schedule_sha256=j.digest(rows),identity=identity)))
    directory=tmp_path/'fresh'
    monkeypatch.setattr(s,'experiment_settings',lambda _: (directory,receipt,'EP-077','jev-choice-v3'))
    monkeypatch.setattr(s,'configuration',lambda _: (config,{}))
    with pytest.raises(ValueError,match='identity verification'):asyncio.run(s.run(directory,experiment='EX-054'))
    assert not directory.exists()


def test_recovered_request_not_counted_as_missing_logical_response():
    records=[dict(type='transport',decision='one',request_number=i) for i in range(1,5)]
    records += [dict(type='attempt_failure',decision='one',attempt=i,category='http',status_code=503) for i in range(1,4)]
    records += [dict(type='http_response',status_code=503 if i<4 else 200,elapsed_seconds=.1) for i in range(1,5)]
    records += [dict(type='response',decision='one',body=dict(model='test',usage=dict(input_tokens=10,output_tokens=2)),elapsed_seconds=7.4)]
    fake=SimpleNamespace(records=records,calls=4,fake=True,started=None,retry_policy=j.jev_retry.CURRENT)
    result=s.summarize(fake,[],[])
    assert result['logical_requests']==1 and result['retry_attempts']==3 and result['recovered_requests']==1
    assert result['http_errors']==3 and result['http_no_response']==0
    assert result['unsuccessful_logical_requests']==0 and result['exhausted_requests']==0
    assert result['latency_includes_retries'] and result['tokens']['input_tokens']==10
