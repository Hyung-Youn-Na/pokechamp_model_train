"""EX117 registration and one-shot CLI routing; no API calls."""
import json
import sys

from . import execute, survival
from .transform import PROMPT


def test_registered_manifest_matches_baseline_and_revised_prompt(monkeypatch):
    monkeypatch.setattr(execute, 'EXPERIMENT', 'EX-117')
    value=execute.manifest()
    original=json.loads((survival.REFERENCE/'manifest.json').read_text())
    assert value['experiment_id']=='EX-117' and len(value['schedule'])==32
    for key in ('schedule','teams','model','limits','transport_policy','response_policy'):
        assert value[key]==original[key]
    assert value['prompt']==PROMPT.read_text()!=original['prompt']
    assert value['viewer']['renderer']=='candidate-action-researcher-v2'


def test_collect_cli_passes_configured_runner(monkeypatch):
    seen=[]
    def collect(runner):
        seen.append((runner.EXPERIMENT,runner.RUN,runner.EXPORT))
        return {'started':False,'synthetic':True}
    monkeypatch.setattr(survival,'collect',collect)
    monkeypatch.setattr(sys,'argv',['candidate-action-battle','collect','--experiment','EX-117'])
    for name in ('EXPERIMENT','RUN','EXPORT','MOCK_NAME'):
        monkeypatch.setattr(execute,name,getattr(execute,name))
    execute.main()
    assert seen==[('EX-117',survival.RUN,survival.EXPORT)]
