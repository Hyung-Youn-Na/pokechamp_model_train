"""Independent EX079 final gate checks against concrete result files."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp.fixed_matchup.stopping import schedule, stopping_decision
from integration.pokechamp.fixed_matchup.stopping_finalize import stopping_evidence
from integration.pokechamp.fixed_matchup.storage import atomic, digest, sha


@pytest.fixture
def evidence(tmp_path):
    jobs = schedule()
    manifest = dict(identity='fixture')
    atomic(tmp_path/'inheritance.json', dict(approval='D-126', inherited_round=1,
        inherited_updates=44, inherited_games=list(range(32)),
        parent_identity='22d0be412e4d4f1532009cc6391e7f905ba62eda25c0f1b3cf30be34ed99eb38'))
    atomic(tmp_path/'verification.json', dict(identity='fixture', passed=True))
    (tmp_path/'models').mkdir()
    for name in ['P0', *[f'round-{r:03d}' for r in range(1, 13)]]:
        (tmp_path/'models'/f'{name}.pt').write_bytes(name.encode())
    for round_id in range(1,13):
        atomic(tmp_path/'checkpoint-validation'/f'round-{round_id:03d}.json',
               dict(passed=True, finite=True, identity='fixture', round=round_id,
                    model_sha256=sha(tmp_path/'models'/f'round-{round_id:03d}.pt'),
                    prediction_max_absolute_error=0.0))
    (tmp_path/'checkpoints').mkdir()
    for round_id in range(13):
        file=f'checkpoints/round-{round_id:03d}.pt'
        (tmp_path/file).write_bytes(str(round_id).encode())
        pointer=dict(file=file,round=round_id,sha256=sha(tmp_path/file))
        atomic(tmp_path/'checkpoints'/f'round-{round_id:03d}.json',pointer)
    atomic(tmp_path/'latest.json',pointer)
    rows = []
    for group in jobs['train'][:12]:
        for job in group:
            name = 'P0' if job['round_id']==1 else f'round-{job["round_id"]-1:03d}'
            rows.append(dict(job=job, status='completed', winner='p1',
                             model_hashes={'current':sha(tmp_path/'models'/f'{name}.pt')}))
    history = []
    for round_id in (1,4,8,12):
        name = f'models/round-{round_id:03d}.pt'
        dev_jobs = jobs['dev'][str(round_id)]
        for i,job in enumerate(dev_jobs):
            winner = job['model_side'] if i<32 else ('p2' if job['model_side']=='p1' else 'p1')
            row = dict(job=job,status='completed',winner=winner,
                model_hashes={'current':sha(tmp_path/name),'P0':sha(tmp_path/'models/P0.pt')})
            rows.append(row)
            atomic(tmp_path/'games'/job['slot_id']/'result.json',row)
        hashes = [dict(slot_id=j['slot_id'],result_sha256=sha(tmp_path/'games'/j['slot_id']/'result.json'))
                  for j in sorted(dev_jobs,key=lambda j:j['slot_id'])]
        record = dict(round=round_id,score=.5,file=name,sha256=sha(tmp_path/name),identity='fixture',
                      schedule_sha256=digest(dev_jobs),results_sha256=digest(hashes))
        history.append(record)
        atomic(tmp_path/'dev'/f'round-{round_id:03d}.json',record)
    atomic(tmp_path/'training-stop.json',dict(identity='fixture',history_sha256=digest(history),state=stopping_decision(history)))
    atomic(tmp_path/'selection.json',history[0])
    lock = dict(selected_file=history[0]['file'],P1=history[0]['sha256'],
                selection_sha256=sha(tmp_path/'selection.json'),training_stop_sha256=sha(tmp_path/'training-stop.json'))
    return tmp_path,manifest,jobs,rows,lock,history


def check(evidence):
    return stopping_evidence(*evidence[:5])


def test_normal_stop_uses_inheritance_and_stopping_not_pilot(evidence):
    gates,details = check(evidence)
    assert all(gates.values()) and 'pilot-gate.json' not in gates
    assert details['stop']['reason']=='plateau'
    assert details['selection']['round']==1
    assert details['new_games']==608


def test_no_selection_cannot_pass_final_gate(evidence):
    (evidence[0]/'selection.json').unlink()
    gates,_=check(evidence)
    assert not gates['training_stop']


def test_dev_receipt_cannot_override_actual_wins(evidence):
    directory,manifest,_,_,lock,history=evidence
    history[0]['score']=.51
    atomic(directory/'dev/round-001.json',history[0])
    atomic(directory/'training-stop.json',dict(identity=manifest['identity'],history_sha256=digest(history),state=stopping_decision(history)))
    lock['training_stop_sha256']=sha(directory/'training-stop.json')
    with pytest.raises(ValueError,match='score/model/schedule'):
        check(evidence)


def test_missing_training_game_is_not_normal_stop(evidence):
    evidence[3].pop(0)
    with pytest.raises(ValueError,match='training collection'):
        check(evidence)


def test_extra_training_after_stop_rejected(evidence):
    evidence[3].append(dict(job=evidence[2]['train'][12][0],status='incomplete'))
    with pytest.raises(ValueError,match='training collection'):
        check(evidence)


def test_earliest_best_tie_required(evidence):
    atomic(evidence[0]/'selection.json',evidence[5][1])
    with pytest.raises(ValueError,match='best completed'):
        check(evidence)


def test_test_lock_cannot_change_stop(evidence):
    evidence[4]['training_stop_sha256']='tampered'
    with pytest.raises(ValueError,match='evaluation lock'):
        check(evidence)


def test_wrong_verification_identity_fails_gate(evidence):
    atomic(evidence[0]/'verification.json',dict(identity='other',passed=True))
    gates,_=check(evidence)
    assert not gates['verification.json']


def test_missing_checkpoint_reload_evidence_rejected(evidence):
    (evidence[0]/'checkpoint-validation/round-004.json').unlink()
    with pytest.raises(ValueError,match='lacks checkpoint validation'):
        check(evidence)


def test_corrupt_checkpoint_cannot_pass_standalone_finalization(evidence):
    (evidence[0]/'checkpoints/round-004.pt').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='checkpoint file/pointer corrupted'):
        check(evidence)


@pytest.fixture
def alarms():
    path=Path(__file__).resolve().parents[3]/'project_context/exec-plans/evidence/ep131/stage_alarms.py'
    spec=importlib.util.spec_from_file_location('ep131_alarms',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_alarms_deliver_once_without_model_or_real_queue(tmp_path,alarms):
    run=tmp_path/'run'; root=tmp_path/'alarms'; root.mkdir()
    atomic(run/'manifest.json',dict(identity='id'))
    config=dict(directory=str(run),identity='id',codex='codex',thread='fake')
    calls=[]
    def sender(*args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)
    assert not alarms.deliver(root,config,sender=sender,running=True)
    for r in (1,4):
        atomic(run/'dev'/f'round-{r:03d}.json',dict(round=r,score=.5))
        assert not alarms.deliver(root,config,sender=sender,running=True)
        assert not alarms.deliver(root,config,sender=sender,running=True)
    atomic(run/'training-stop.json',dict(reason='plateau'))
    assert not alarms.deliver(root,config,sender=sender,running=True)
    atomic(run/'completed.json',dict(procedure_complete=True))
    assert alarms.deliver(root,config,sender=sender,running=False)
    assert alarms.deliver(root,config,sender=sender,running=False)
    assert len(calls)==4


def test_uncertain_alarm_is_not_resent(tmp_path,alarms):
    run=tmp_path/'run'; root=tmp_path/'alarms'; root.mkdir()
    atomic(run/'manifest.json',dict(identity='id'))
    config=dict(directory=str(run),identity='id',codex='codex',thread='fake')
    calls=[]
    def sender(*args,**kwargs):
        calls.append(args)
        raise TimeoutError()
    assert alarms.deliver(root,config,sender=sender,running=False)
    assert alarms.deliver(root,config,sender=sender,running=False)
    assert len(calls)==1
