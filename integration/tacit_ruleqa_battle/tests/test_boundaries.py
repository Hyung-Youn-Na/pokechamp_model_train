import copy
import json
from pathlib import Path
import pytest
from integration.strategist_eval.tests.test_core import snapshot
from integration.tacit_ruleqa_battle import core,execute
from integration.tacit_ruleqa_battle.report import summarize,audit_events


def test_id_mapping_and_no_tera():
    kind,legal=core.candidates(snapshot())
    assert kind=='turn_action'
    assert [(x['option_id'],x['command']) for x in legal]==[('A','/choose move 1'),('B','/choose switch 2')]
    assert core.parse('B. Eevee\nReason.',legal)['choice']=='switch_2'


@pytest.mark.parametrize('raw',['A','A. Move','A) Move','Answer: A','**A**: Move'])
def test_valid_single_id(raw):
    assert core.parse(raw,core.candidates(snapshot())[1])['choice']=='move_1'


@pytest.mark.parametrize('raw',['','A or B','A. or B.','I choose A','X. Other'])
def test_invalid_output_recorded(raw):
    assert core.parse(raw,core.candidates(snapshot())[1])['error']


def test_reproducible_fallback_and_single():
    legal=core.candidates(snapshot())[1]
    a=core.select('invalid',legal,'s','d')
    assert a==core.select('invalid',legal,'s','d') and a['fallback']
    assert a['choice'] in {x['id'] for x in legal}
    b=core.select('',legal[:1],'s','d')
    assert b['automatic'] and not b['fallback']


def test_stale_and_changed_candidate_rejected():
    s=snapshot();legal=core.candidates(s)[1]
    with pytest.raises(ValueError):core.ensure_current(3,4,s['request'],legal,legal,False)
    with pytest.raises(ValueError):core.ensure_current(3,3,s['request'],legal,legal[:1],False)


def test_readiness_stops_on_upstream_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(execute,'TRAIN',tmp_path)
    (tmp_path/'pipeline.json').write_text(json.dumps(dict(stage='waiting-for-training')))
    assert execute.readiness() is False
    (tmp_path/'pipeline.json').write_text(json.dumps(dict(stage='stopped')))
    with pytest.raises(RuntimeError):execute.readiness()


def test_readiness_needs_all_reloads_and_tests(tmp_path,monkeypatch):
    monkeypatch.setattr(execute,'TRAIN',tmp_path)
    (tmp_path/'pipeline.json').write_text(json.dumps(dict(stage='awaiting-blind-review-and-final-report')))
    with pytest.raises(FileNotFoundError):execute.readiness()
    for i in range(3):(tmp_path/f'reload-rank-{i}.json').write_text('{"passed":true}')
    (tmp_path/'selection.json').write_text('{"epoch":2}')
    for name in ['test-base','test-selected']:
        d=tmp_path/'predictions'/name;d.mkdir(parents=True)
        (d/'metrics.json').write_text(json.dumps(dict(forms={k:dict(n=192) for k in ['short_qa','state_qa','state_mc']})))
    assert execute.readiness()


def test_failure_is_not_loss():
    r=summarize({},dict(outcomes=[dict(completed=True,paired_slot_id='p',outcome='player_won'),dict(completed=False,outcome='failed')]),[])
    assert r['wins']==1 and r['losses']==0 and r['failed']==1 and r['complete_pairs']==0


def test_full_state_public_boundary():
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    dex=json.loads((DEFAULT_BUILD/'dex.json').read_text())
    samples=json.loads(Path('/workspace/project_context/exec-plans/evidence/ep176/cpu-gate-inputs.json').read_text())
    try:
        for sample in samples.values():
            inp=core.build_input(sample['official'],sample['prefix'],sample['actor'],dex,sample['own_team'])
            assert inp==sample['payload']
            user=json.loads(inp['messages'][1]['content'])
            assert set(user)=={'context','conditions','question','qa_options'}
            assert set(user['context'])=={'state','battle_actions'}
            assert 'Do not choose a battle action' not in inp['messages'][0]['content']
            assert len(user['qa_options'])==len(inp['candidates'])
        sample=samples['turn_action'];bad=copy.deepcopy(sample['prefix']);other='p2' if sample['actor']=='p1' else 'p1'
        bad[-1]['protocol']+='\n|request|'+json.dumps(dict(side=dict(id=other)))
        with pytest.raises(ValueError):core.build_input(sample['official'],bad,sample['actor'],dex,sample['own_team'])
    finally:core.close_builder()
