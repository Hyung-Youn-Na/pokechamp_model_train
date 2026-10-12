"""최종화는 원자료·동결·전체 test의 독립 검증 없이 완료를 주장하지 않는다."""
from pathlib import Path
import pytest
from integration.pokechamp.abyssal_rl import finalize as f, reporting
from integration.pokechamp.abyssal_rl.storage import atomic, read, sha, write_jsonl, Clock
from integration.pokechamp.tests.test_abyssal_reporting import outcomes


def test_independent_bootstrap_recounts_wins_not_draw_scores():
    left, right = outcomes('initial',result='draw'), outcomes('selected')
    for index,row in enumerate(right):
        if index % 3 == 0:
            row['result']='draw'
    actual=f.independent_statistics(left,right)
    reference=reporting.paired_bootstrap(left,right)
    for key in ('win_rate','mean_difference','win_rate_ci95','ci95'):
        assert actual[key]==reference[key]
    right[0].update(status='failed',result=None)
    assert not f.independent_statistics(left,right)['complete']


def test_independent_source_audit_rejects_actor_and_wire_mismatch(tmp_path, monkeypatch):
    slot=dict(slot_id='test',stage='test',model='selected',round=0,model_side='p1',model_seed=1,opponent_seed=2)
    result=dict(slot,status='completed',result='win',turns=2)
    folder=tmp_path/'games/test'
    atomic(folder/'request.json',dict(slot=slot))
    for side,seed,outcome in [('p1',1,'win'),('p2',2,'loss')]:
        atomic(folder/(side+'.result.json'),dict(actor=side,seed=seed,python_hash_seed=str(seed),status='completed',result=outcome,turns=2))
    monkeypatch.setattr(f,'audit_match',lambda *args: (dict(passed=True),[]))
    assert f.independent_audit(tmp_path,[slot],[result],[])['passed']
    bad=read(folder/'p2.result.json');bad['result']='win';atomic(folder/'p2.result.json',bad)
    with pytest.raises(ValueError,match='terminal results'):
        f.independent_audit(tmp_path,[slot],[result],[])
    bad['result']='loss';atomic(folder/'p2.result.json',bad)
    monkeypatch.setattr(f,'audit_match',lambda *args: (dict(passed=False),[]))
    with pytest.raises(ValueError,match='wire reconstruction'):
        f.independent_audit(tmp_path,[slot],[result],[])


def minimal_run(root):
    slot=dict(slot_id='reserved-dev',stage='dev',round=128,model='round-128',pair_id='p',model_side='p1',opponent='abyssal',simulator_seed=[1],assignment=0)
    atomic(root/'manifest.json',dict(experiment_id='EX-073',source={}))
    atomic(root/'prepared/schedule.json',[slot])
    atomic(root/'prepared/manifest.json',dict(files={'schedule.json':sha(root/'prepared/schedule.json')}))
    atomic(root/'state.json',dict(checks={},dev_attempted=[]))
    Clock(root,start=True)


def test_missing_artifacts_closes_incomplete_and_does_not_evaluate_test(tmp_path):
    root=tmp_path/'run';minimal_run(root)
    result=f.finalize(root,export_root=tmp_path/'viewer')
    assert result['closed'] and not result['experiment_complete']
    assert result['viewer_path'] is None
    report=read(result['result_path'])
    assert report['reserved_dev_slots']==1 and report['actual_dev_evaluations']==0
    assert report['planned']==0
    assert report['finalization_error']['type']=='ValueError'
    assert f.finalize(root,export_root=tmp_path/'viewer')==result
    assert not (tmp_path/'viewer').exists()


def test_closure_hash_change_and_prior_final_are_refused(tmp_path):
    root=tmp_path/'run';minimal_run(root)
    result=f.finalize(root,export_root=tmp_path/'viewer')
    atomic(Path(result['result_path']),dict(tampered=True))
    with pytest.raises(ValueError,match='changed after completion'):
        f.finalize(root)
    other=tmp_path/'other';minimal_run(other)
    (other/'final').mkdir()
    (other/'final/preserve').write_text('original')
    with pytest.raises(FileExistsError): f.finalize(other)
    assert (other/'final/preserve').read_text()=='original'


def test_operational_accounting_reports_selected_and_collected_decisions(tmp_path):
    Clock(tmp_path,start=True,now=100)
    atomic(tmp_path/'supervisor-exit.json',dict(at=3700))
    atomic(tmp_path/'rounds/round-1-training.json',dict(state=dict(selected_ids=['one','two'])))
    rows=[dict(slot_id='a',stage='train',round=1,status='completed')]
    metrics=f.operation_metrics(tmp_path,dict(last_completed_round=1,trainer=dict(global_updates=4)),rows,[dict(slot_id='a')])
    assert metrics['training_decisions']==2
    assert metrics['collected_train_decisions']==1
    assert metrics['reserved_gpu_hours']==4
    assert metrics['global_updates']==4


@pytest.mark.parametrize("browser_passed", [False, True])
def test_publication_requires_browser_gate_even_when_all_test_games_complete(tmp_path, monkeypatch, browser_passed):
    root=tmp_path/'run'
    schedule=[]
    for model in ('initial','selected'):
        for row in outcomes(model,result='win' if model=='selected' else 'loss'):
            row.update(stage='test',round=0,turns=2,actors_cleaned=True,server_cleaned=True)
            schedule.append({k:v for k,v in row.items() if k not in ('status','result','turns','actors_cleaned','server_cleaned')})
            game=root/'games'/row['slot_id']
            atomic(game/'outcome.json',row)
            write_jsonl(game/'decisions.jsonl',[dict(slot_id=row['slot_id'],decision_id='chosen',wdl_before=[.5,.2,.3],wdl_after=[.5,.2,.3])])
    train=dict(slot_id='train',stage='train',round=1,model='initial',pair_id='training',model_side='p1',opponent='abyssal',simulator_seed=[1],assignment=0)
    schedule.append(train)
    atomic(root/'games/train/outcome.json',dict(train,status='completed',result='win',actors_cleaned=True,server_cleaned=True))
    write_jsonl(root/'games/train/decisions.jsonl',[])
    atomic(root/'manifest.json',dict(experiment_id='EX-073',source={}))
    atomic(root/'prepared/schedule.json',schedule)
    atomic(root/'prepared/manifest.json',dict(files={'schedule.json':sha(root/'prepared/schedule.json')}))
    checks={name:True for name in ('cpu_validation','gpu_preflight','first_eight_audit','training','trained_candidate_dev','policy_selection','calibration_decision','resume_validation')}
    atomic(root/'state.json',dict(checks=checks,dev_attempted=[],last_completed_round=1))
    atomic(root/'supervisor-exit.json',dict(returncode=0))
    Clock(root,start=True)
    monkeypatch.setattr(f,'required_artifacts',lambda *args: [])
    monkeypatch.setattr(f,'head_action_invariance',lambda *args: True)
    monkeypatch.setattr(f,'independent_audit',lambda *args: dict(passed=True))
    monkeypatch.setattr(f,'verify_browser_environment',lambda *args: None)
    def fake_export(source, output, **kwargs):
        output.mkdir(parents=True)
        atomic(output/'index.html',b'<html><main>synthetic</main></html>')
        return dict(index=str(output/'index.html'))
    monkeypatch.setattr(f.viewer,'export',fake_export)
    class FailedBrowser:
        returncode=0 if browser_passed else 1
        stdout=''
        stderr='synthetic browser gate failure'
    def browser(*args, **kwargs):
        if browser_passed:
            atomic(root/'final/viewer-check.json',dict(passed=True))
        return FailedBrowser()
    monkeypatch.setattr(f.subprocess,'run',browser)
    closed=f.finalize(root,export_root=tmp_path/'export')
    assert closed['experiment_complete'] is browser_passed
    result=read(closed['result_path'])
    assert result['paired']['complete'] and result['target_achieved']
    assert result['stage_status']['viewer'] is browser_passed
    if not browser_passed:
        assert result['finalization_error']['detail']=='moved offline viewer verification failed'
        assert 'finalization' in result['incomplete_requirements']


def test_latency_reads_raw_server_json_and_prefers_primary_decision_wall_time(tmp_path):
    import json
    Clock(tmp_path,start=True,now=100)
    atomic(tmp_path/'supervisor-exit.json',dict(at=3700))
    events=[dict(type='http_response',decision='one',status_code=200,raw_body=json.dumps({'elapsed_seconds':2.5})),
            dict(type='http_response',decision='two',status_code=200,raw_body='{}',elapsed_seconds=3),
            dict(type='response',decision='two',elapsed_seconds=4),
            dict(type='http_response',decision='failed',status_code=500,raw_body=json.dumps({'elapsed_seconds':99}))]
    write_jsonl(tmp_path/'games/a/events.jsonl',events)
    metrics=f.operation_metrics(tmp_path,{},[dict(slot_id='a',stage='train',round=1,status='completed')],[])
    assert metrics['decision_latency']['count']==2
    assert metrics['decision_latency']['mean_seconds']==3.25
    assert metrics['decision_latency']['sources']==dict(server_response_elapsed_seconds=1,successful_decision_wall_seconds=1)
