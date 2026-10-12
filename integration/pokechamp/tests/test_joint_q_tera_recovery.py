"""A reporting/input recovery cannot silently change the policy or old evidence."""
from pathlib import Path

import pytest

from integration.pokechamp.joint_q import tera_recovery as recovery
from integration.pokechamp.joint_q.storage import atomic,digest,sha


@pytest.fixture
def preserved(tmp_path,monkeypatch):
    current=tmp_path/'code'
    parent=tmp_path/'original'
    current.mkdir()
    files={}
    for name,content in [('policy.py','frozen policy'),('allowed.py','old presentation')]:
        (current/name).write_text(content)
        destination=parent/'frozen/collection'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(content)
        files[name]=sha(destination)
    atomic(parent/'manifest.json',dict(version='v1'))
    source=digest(files)
    atomic(parent/'frozen-collection.json',dict(source_id=source,files=files,
                                              manifest_sha256=sha(parent/'manifest.json')))
    monkeypatch.setattr(recovery,'ROOT',current)
    monkeypatch.setattr(recovery,'ORIGINAL_SOURCE',source)
    monkeypatch.setattr(recovery,'ALLOWED_CHANGED',frozenset({'allowed.py'}))
    monkeypatch.setattr(recovery,'ADDED',())
    (current/'allowed.py').write_text('corrected presentation')
    return parent,current


def test_only_registered_input_reporting_files_can_change(preserved):
    parent,current=preserved
    evidence=recovery.repair_sources(parent)
    assert set(evidence['changed'])=={'allowed.py'} and evidence['unchanged_original_sources']==1
    (current/'policy.py').write_text('changed policy')
    with pytest.raises(ValueError,match='policy/core'):
        recovery.repair_sources(parent)


def test_even_corrected_file_original_bytes_must_remain_preserved(preserved):
    parent,_=preserved
    (parent/'frozen/collection/allowed.py').write_text('replaced old evidence')
    with pytest.raises(ValueError,match='preserved original source'):
        recovery.repair_sources(parent)


def test_original_manifest_cannot_be_rewritten(preserved):
    parent,_=preserved
    atomic(parent/'manifest.json',dict(version='v2'))
    with pytest.raises(ValueError,match='original manifest'):
        recovery.repair_sources(parent)


def test_recovery_directory_and_single_version_limit_are_enforced(tmp_path):
    parent=tmp_path/'original'
    with pytest.raises(ValueError,match='registered separate'):
        recovery.prepare(parent,tmp_path/'arbitrary-version')
    atomic(parent/'manifest.json',dict(version='ex067-abyssal-tera-rollout-v2',recovery=dict(previous=True)))
    with pytest.raises(ValueError,match='one recovery'):
        recovery.prepare(parent,parent/'versions/public-tera-v2')


def test_regenerated_manifest_preserves_all_seeds_and_first_clock(monkeypatch):
    from integration.pokechamp.joint_q import manifest
    old=dict(version='v1',created_at=123.5,games=[dict(game_id='same',simulator_seed=[1,2,3,4])],
             policy=dict(policy_id='unchanged'),limits=dict(attempts_per_rollout=3))
    fresh=dict(old,version='v2',created_at=999.0)
    def prepare(directory,**kwargs):
        assert kwargs==dict(experiment='EX-067')
        atomic(directory/'manifest.json',fresh)
        return dict(games=1,teams=1,pilot=1,manifest_sha256=sha(directory/'manifest.json'))
    monkeypatch.setattr(manifest,'prepare',prepare)
    corrected=recovery.matching_schedule(old)
    assert corrected==dict(old,version='v2')
    fresh['games']=[dict(game_id='same',simulator_seed=[1,2,3,5])]
    with pytest.raises(ValueError,match='schedule, seeds'):
        recovery.matching_schedule(old)
