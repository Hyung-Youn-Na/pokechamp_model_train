"""Versioned display-only exports of completed, sealed EX-088/089 evaluations."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import time

from integration.jev27b.study import event_rows, file_hash, seal, verify_seal, write_json
from . import damage_data, viewer
from .config import BROWSER_PYTHON, DISK_BYTES, ROOT, experiment

EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep142'
EDITIONS = tuple(ROOT / 'exports/battle_viewers' / name for name in (
    'ex088-damage-v1', 'ex089-damage-v1', '.ex088-damage-v1-building', '.ex089-damage-v1-building'))


def verify_complete_seal(path):
    path = Path(path)
    files = verify_seal(path)
    actual = {str(p.relative_to(path)) for p in path.rglob('*')
              if p.is_file() and p != path / 'checksums.sha256'}
    if set(files) != actual:
        raise ValueError('sealed file inventory differs: ' + str(path))
    return dict(path=str(path), files=len(files), sha256=file_hash(path / 'checksums.sha256'))


def renderer_identity():
    sources = viewer.source_identity()
    for name in ('integration/jev_eval/reexport.py', 'integration/jev_eval/damage_browser.py',
                 'integration/jev27b/study.py', 'integration/pokechamp/jev_battle.py',
                 'integration/jev_eval/execute.py', 'scripts/jev-eval'):
        sources[name] = file_hash(ROOT / name)
    return sources


def check_disk(config, *, extra_roots=(), reserve=0):
    from .resource import disk_bytes, disk_roots
    extra = (*EDITIONS, EVIDENCE, *extra_roots)
    size = disk_bytes(config, extra_roots=extra)
    if size + reserve > DISK_BYTES:
        raise ValueError('display export plus temporary copy exceeds 100 GiB disk budget')
    return dict(bytes=size, reserved_bytes=reserve, limit_bytes=DISK_BYTES,
                roots=[str(p) for p in disk_roots(config, extra_roots=extra)])


def build_export(source, previous, output, *, collected_run=None, budget_check=None):
    """Preserve sealed originals/turn prose; add only per-decision damage and new UI."""
    source, previous, output = map(Path, (source, previous, output))
    if output.exists():
        raise FileExistsError('display editions cannot overwrite an existing path: ' + str(output))
    source_seal = verify_complete_seal(source)
    previous_seal = verify_complete_seal(previous)
    manifest = json.loads((source / 'manifest.json').read_text())
    result = json.loads((source / 'result.json').read_text())
    if (manifest.get('experiment_id') not in ('EX-088', 'EX-089')
            or manifest.get('schema_version') != 'jev-choice-v6'
            or result.get('passed') is not True or result.get('final_audit_passed') is not True
            or result.get('completed') != result.get('planned')):
        raise ValueError('display re-export requires a completed, audited EX-088/089')
    prior = json.loads((previous / 'provenance.json').read_text())
    if (prior.get('experiment') != manifest['experiment_id']
            or prior.get('source_files', {}).get('checksums.sha256') != source_seal['sha256']):
        raise ValueError('previous viewer is not linked to this sealed collection')
    sources = renderer_identity()
    entries = damage_data.input_events(event_rows(source))
    shutil.copytree(previous, output)
    # The copied seal belongs to the old edition until all new rendering is finished.
    (output / 'checksums.sha256').unlink()
    seen = set()
    for outcome in result['outcomes']:
        target = output / f"battle-{outcome['slot']}"
        data = json.loads((target / 'decisions.json').read_text())
        if data['experiment'] != manifest['experiment_id'] or data['outcome'] != outcome:
            raise ValueError('previous viewer battle identity differs')
        for decision in data['decisions']:
            if decision['id'] in seen:
                raise ValueError('duplicate exported decision identity')
            seen.add(decision['id'])
        damage_data.export_battle(source, target, data, entries)
        write_json(target / 'decisions.json', data)
        (target / 'index.html').write_text(viewer.render_data(data))
        if budget_check:
            budget_check()
    if seen != set(entries):
        raise ValueError('display edition does not cover every recorded input')
    for name, checksum in sources.items():
        target = output / 'renderer-source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        if file_hash(target) != checksum:
            raise ValueError('renderer changed during export: ' + name)
    prior.update(viewer_source=sources, display_version=damage_data.VERSION,
        collected_source=dict(manifest_sha256=file_hash(source / 'manifest.json'),
            files=manifest['source'], collection_seal=source_seal, run_seal=collected_run),
        renderer_source=dict(files=sources, copied_under='renderer-source/',
                             distinct_from_collection_source=True),
        previous_export=previous_seal,
        damage=dict(source='input event → input_audit.path/sha256 → saved damage',
            decisions=len(seen), per_decision_local_scripts=True, recalculations=0,
            model_calls=0, battles=0, scenario_order='original calculations array'),
        exported_at=time.time())
    write_json(output / 'provenance.json', prior)
    index = (output / 'index.html').read_text().replace('입력·선택·턴 로그</a>', '입력·선택·턴 로그·Damage-calc</a>')
    index = index.replace('</h1>', '</h1><p>Damage-calc 판본 · 전체 결정의 당시 저장 계산을 연결했습니다. '
        '상대 가정과 공개 정보를 구분하고, 계산을 다시 실행하지 않습니다.</p>', 1)
    (output / 'index.html').write_text(index)
    if sources != renderer_identity():
        raise ValueError('renderer changed during export')
    seal(output)
    checked = viewer.verify_data(source, output)
    if checked['damage_decisions'] != result['decisions']:
        raise ValueError('damage export decision denominator differs')
    checked.update(previous_export=previous_seal, source=source_seal,
                   renderer_source=sources, display_version=damage_data.VERSION)
    return checked


def reexport(config):
    cfg = experiment(config)
    if cfg.experiment not in ('EX-088', 'EX-089'):
        raise ValueError('only completed EX-088/089 have approved Damage-calc editions')
    output = cfg.export.with_name(cfg.namespace + '-damage-v1')
    staging = output.with_name('.' + output.name + '-building')
    evidence = EVIDENCE / cfg.experiment
    if output.exists() or staging.exists() or evidence.exists():
        raise FileExistsError('display re-export cannot overwrite an edition or its evidence')
    initial = check_disk(cfg)
    collected = verify_complete_seal(cfg.run)
    completion = json.loads((cfg.evidence / 'completion.json').read_text())
    if completion.get('passed') is not True or completion.get('experiment_id') != cfg.experiment:
        raise ValueError('completed source receipt is required')
    evidence.mkdir(parents=True)
    write_json(evidence / 'initial.json', dict(disk=initial, collected_run=collected))
    # Reserve the original copy before writing; each subsequent battle checks its additions.
    size = sum(p.stat().st_size for p in cfg.export.rglob('*') if p.is_file())
    check_disk(cfg, reserve=size)
    exported = build_export(cfg.run / 'collection', cfg.export, staging, collected_run=collected,
                            budget_check=lambda: check_disk(cfg))
    write_json(evidence / 'data-verification.json', exported)
    command = [str(BROWSER_PYTHON), '-m', 'integration.jev_eval.damage_browser',
               '--output', str(staging), '--receipt', str(evidence / 'browser.json')]
    with (evidence / 'browser.log').open('x') as stream:
        subprocess.run(command, cwd=ROOT, check=True, stdout=stream, stderr=subprocess.STDOUT)
    browser = json.loads((evidence / 'browser.json').read_text())
    if not browser.get('passed'):
        raise ValueError('offline browser validation did not pass')
    staging.rename(output)
    verified = verify_complete_seal(output)
    receipt = dict(passed=exported['passed'] and browser['passed'], experiment=cfg.experiment,
        output=str(output), data=exported, browser=browser, export_seal=verified,
        final_disk=check_disk(cfg), extra_battles=0, extra_model_calls=0, damage_recalculations=0)
    write_json(evidence / 'completion.json', receipt)
    seal(evidence)
    return receipt
