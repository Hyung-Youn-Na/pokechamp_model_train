"""No disk quota in new planner runs; historical limits and device budgets survive."""
from dataclasses import asdict

import pytest

from integration.jev27b import resource
from integration.jev27b.config import DISK_BYTES, runtime_profile
from integration.jev_planner import config, runtime
from integration.jev_planner.tests.test_runtime import configuration


@pytest.mark.parametrize('name', ['jev9b','jev27b','minicpm5-jev'])
def test_new_resource_profile_has_no_disk_limit_and_preserves_device_budgets(name, tmp_path, monkeypatch):
    spec=config.model_spec(name);profile=runtime_profile(spec['runtime_name'])
    original=runtime_profile(spec['model_runtime_name'])
    assert spec['disk_bytes'] is profile.disk_bytes is None
    before=asdict(original);after=asdict(profile)
    assert {k:v for k,v in before.items() if k not in ('name','disk_bytes')} == {k:v for k,v in after.items() if k not in ('name','disk_bytes')}
    sample=dict(rss_bytes=profile.host_bytes,disk_bytes=DISK_BYTES*100,
                gpus={i:dict(memory_used_mib=profile.gpu_bytes//1024**2) for i in profile.physical_gpus})
    assert resource.limit_errors(sample,profile=spec['runtime_name'])==[]
    sample['rss_bytes']+=1
    sample['gpus'][profile.physical_gpus[0]]['memory_used_mib']+=1
    errors=resource.limit_errors(sample,profile=spec['runtime_name'])
    assert 'host_memory_exceeded' in errors and any(e.startswith('gpu') for e in errors)
    assert 'disk_budget_exceeded' not in errors
    # Both parent/server select this profile; volume measurement still runs.
    monitor=resource.ResourceMonitor(tmp_path,profile=spec['runtime_name'])
    monkeypatch.setattr(resource,'disk_bytes',lambda **kw: DISK_BYTES*100)
    assert monitor._disk_bytes()==DISK_BYTES*100
    assert monitor.settings.disk_bytes is None
    assert runtime.validate_resources(configuration(name))['runtime_name']==spec['runtime_name']


def test_old_profile_keeps_the_original_disk_rule():
    profile=runtime_profile('ex087');assert profile.disk_bytes==DISK_BYTES
    sample=dict(rss_bytes=0,disk_bytes=DISK_BYTES+1,gpus={i:dict(memory_used_mib=0) for i in profile.physical_gpus})
    assert resource.limit_errors(sample,profile='ex087')==['disk_budget_exceeded']


@pytest.mark.parametrize('name', ['jev9b','jev27b','minicpm5-jev'])
def test_loader_uses_original_placement_with_unlimited_metadata(name,monkeypatch):
    from integration.jev_eval import model as evaluation
    called=[]
    class FakeModel:
        def __init__(self,path,**kwargs):
            called.append(kwargs);self.profile=runtime_profile(kwargs['profile'])
    for cls in ('Evaluation27B','Evaluation9B','EvaluationMiniCPM'):monkeypatch.setattr(evaluation,cls,FakeModel)
    instance=runtime.create_model(configuration(name));spec=config.model_spec(name)
    assert called[0]['profile']==spec['model_runtime_name']
    assert instance.profile.name==spec['model_runtime_name']
    assert instance.profile.disk_bytes is None
    assert runtime_profile(spec['model_runtime_name']).disk_bytes == (None if name=='minicpm5-jev' else DISK_BYTES)
