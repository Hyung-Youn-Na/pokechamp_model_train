import copy
import hashlib
import json
import pytest
from integration.jev_omni import formatting as f
from integration.jev_omni.config import MODEL_ID, REVISION
from integration.jev_planner.config import model_spec, load_config, validate_prepared
from integration.jev_planner.runtime import validate_resources, create_model
from integration.jev27b.server import LocalService


def payload():
    return dict(state={'turn': 7, 'strategy': {'objective': 'preserve ☃', 'age': 2}}, questions={
        'action': dict(type='choice', instructions='Check goals\nThen act.', criteria={
            'move_9': dict(display_name='Lokix — U-turn', nested={'slot': 9}),
            'switch_2': dict(display_name='Switch to Pecharunt', slot=2)})})


def response(p):
    options = f.choice_request(p)['options']
    return dict(prediction=options[1], prediction_index=1, confidence=.75,
                probabilities=dict(zip(options, [.251, .75])))


def test_lossless_numeric_prompt_and_raw_scores():
    p=payload();before=copy.deepcopy(p);r=f.choice_request(p);formatted=f.format_request(p)
    assert json.loads(r['state'])==p['state']
    assert r['question']==p['questions']['action']['instructions']
    assert [json.loads(v) for v in r['options']]==[{k:v} for k,v in p['questions']['action']['criteria'].items()]
    assert '1. '+r['options'][0] in formatted.prompt and '2. '+r['options'][1] in formatted.prompt
    result=f.mapped_response(p,response(p),123)
    assert result['answers']['action']['choice']=='switch_2'
    assert list(result['answers']['action']['probabilities'].values())==[.251,.75]
    assert result['usage']==dict(input_tokens=123,output_tokens=0) and p==before
    from integration.pokechamp.jev_battle import judgment_diagnostics, validate_answer
    criteria=p['questions']['action']['criteria']
    assert validate_answer(result,criteria)=='switch_2'
    assert 'probability_sum' in judgment_diagnostics(result['answers']['action'],criteria)


@pytest.mark.parametrize('index',[-1,2,True,None])
def test_invalid_choice_fails(index):
    p=payload();r=response(p);r['prediction_index']=index
    with pytest.raises(ValueError):f.mapped_response(p,r,12)


def test_auxiliary_probabilities_do_not_override_choice():
    p=payload();r=response(p);r['probabilities']={};r['confidence']=None
    assert f.mapped_response(p,r,12)['answers']['action']['choice']=='switch_2'


def test_config_profile_and_adapter():
    cfg=load_config('project_context/exec-plans/evidence/ep162/config.json')
    validate_prepared(cfg,'live')
    assert validate_resources(cfg)['revision']==REVISION
    assert model_spec('jev-omni')['python'].endswith('jev-omni-runtime/.venv/bin/python')
    assert create_model(cfg).__class__.__module__=='integration.jev_omni.model'


def test_duplicate_request_performs_one_forward(tmp_path):
    class Fake:
        calls=0
        def metadata(self):return dict(model=MODEL_ID,revision=REVISION,loaded=True,serving_identity='a'*64)
        def validate_input(self,p):f.format_request(p)
        def evaluate(self,p):
            self.calls+=1
            return f.mapped_response(p,response(p),123)
    model=Fake();service=LocalService(model,tmp_path,model_id=MODEL_ID,revision=REVISION,validate_before_inference=True)
    raw=json.dumps(dict(model=MODEL_ID,**payload())).encode();kwargs=dict(request_id='omni-1',body_sha256=hashlib.sha256(raw).hexdigest(),expected_identity='a'*64)
    try:
        first=service.evaluate(raw,**kwargs);second=service.evaluate(raw,**kwargs)
        assert first[0]==second[0]==200 and first[1]==second[1] and second[2]
        assert model.calls==1
        assert service.registry.get('omni-1')['inference_calls']==1
    finally:service.close()


def test_all_duplicate_preflight_choices_must_match(tmp_path):
    import asyncio
    from integration.jev_omni.preflight import run_preflight
    requests=[dict(case=str(i),payload=payload()) for i in range(8)]
    class Executor:
        count=0
        async def __call__(self,payload,*,decision):
            self.count+=1
            r=response(payload)
            if self.count==4:
                r['prediction_index']=0;r['prediction']=f.choice_request(payload)['options'][0]
            return f.mapped_response(payload,r,123)
    cfg=dict(evaluation=dict(executor_repeat_policy='probability_diagnostic',executor_preflight=dict(data=dict(requests=requests))))
    with pytest.raises(ValueError,match='repeated inference'):
        asyncio.run(run_preflight(cfg,Executor(),tmp_path,before_executor=lambda **kw:None))
    assert json.loads((tmp_path/'preflight.json').read_text())['completed_preflight_responses']==8
