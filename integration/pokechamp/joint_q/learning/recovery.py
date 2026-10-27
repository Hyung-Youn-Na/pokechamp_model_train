"""Evidence-gated recovery of an untrained preflight implementation defect."""

from integration.project_context.registry import record_relative
from pathlib import Path
from ..storage import ROOT, atomic, digest, read, sha
from .artifacts import assert_frozen, environment, latest, now, source_hashes, validate_checkpoint


def validate_zero_gradient_repair(data,out,receipt_path,receipt):
    """Re-freeze a validation guard only, before the first optimizer update."""
    original=out/'versions/zero-gradient-v1'
    old=read(original/'prepared/manifest.json')
    if (receipt['training_updates']!=0 or receipt['test_evaluations']!=0
            or receipt['stop_sha256']!=sha(out/'STOP.json')
            or receipt['original_manifest_sha256']!=sha(original/'prepared/manifest.json')
            or receipt['reproduction_sha256']!=sha(out/'diagnostics/zero-gradient-v1.json')):
        raise ValueError('zero-gradient repair identity mismatch')
    stop=read(out/'STOP.json')
    if (stop['stage']!='train' or stop['error_type']!='KeyboardInterrupt'
            or stop['error']!='technical interruption requested' or not stop['resumable']
            or sha(original/'STOP.json')!=receipt['stop_sha256']):
        raise ValueError('repair does not authorize another stop reason')
    cp=latest(out/'training')
    saved=validate_checkpoint(cp)
    if (cp.name!='initial' or saved['cursor']!={'epoch':1,'index':0,'updates':0}
            or saved['frozen_manifest_sha256']!=digest(old)
            or (out/'training/updates.jsonl').exists() or (out/'evaluation-lock.json').exists()
            or (out/'training/selection.json').exists()):
        raise ValueError('guard-only repair requires the untouched initial checkpoint')
    from .config import CONFIG
    if old['config']!=CONFIG or old['packages']!=environment():
        raise ValueError('repair changed settings/environment')
    current=source_hashes()
    allowed={'integration/pokechamp/joint_q/learning/runtime.py',
             'integration/pokechamp/joint_q/learning/recovery.py',
             'integration/pokechamp/joint_q/learning/verify.py',
             'integration/pokechamp/tests/test_joint_q_learning.py'}
    if set(current)!=set(old['sources']):
        raise ValueError('repair source coverage changed')
    for name,expected in old['sources'].items():
        if sha(original/'source'/name)!=expected or (name not in allowed and current[name]!=expected):
            raise ValueError('repair changed a numerical/input source: '+name)
    runtime='integration/pokechamp/joint_q/learning/runtime.py'
    removed="    if not squares>0:\n        raise FloatingPointError('all trainable gradients are zero')\n"
    before=(original/'source'/runtime).read_text()
    if before.count(removed)!=1 or before.replace(removed,'')!=(ROOT/runtime).read_text():
        raise ValueError('runtime repair exceeds the finite-zero rejection guard')
    proof=read(out/'diagnostics/zero-gradient-v1.json')
    if proof['runtime_sha256']!=old['sources'][runtime] or len(proof['examples'])!=2:
        raise ValueError('original zero-gradient reproduction changed')
    for example in proof['examples']:
        if (example['target'] not in (0,1) or example['prediction']!=example['target']
                or example['mse']!=0 or not example['finite_gradients']
                or example['gate_error']!='all trainable gradients are zero'):
            raise ValueError('reproduction does not establish a false finite-gradient rejection')
    tests=read(out/'verification/tests.json')
    if (not tests['passed'] or receipt['tests_sha256']!=sha(out/'verification/tests.json')
            or tests['test_source_sha256']!=current['integration/pokechamp/tests/test_joint_q_learning.py']):
        raise ValueError('independent zero-gradient regression evidence missing')
    for field,base in [('data_files',Path(data)),('prepared_files',out/'prepared')]:
        for name,expected in old[field].items():
            if sha(base/name)!=expected:
                raise ValueError('repair changed frozen inputs: '+name)
    for name,expected in old['base_files'].items():
        if sha(name)!=expected:
            raise ValueError('repair changed Base weights')
    active=read(out/'prepared/manifest.json')
    if active!=old:
        raise ValueError('active manifest changed before guard re-freeze')
    updated=dict(old,created_at=now(),sources=current,
        source_repair=dict(kind='finite_zero_gradient',original_manifest_sha256=sha(original/'prepared/manifest.json'),
                           receipt_sha256=sha(receipt_path),initial_checkpoint_files_sha256=sha(cp/'files.json')))
    atomic(out/'prepared/manifest.json',updated)
    # Preserve every source revision; the top-level copy follows the current freeze.
    import shutil
    for name,expected in current.items():
        target=out/'source'/name
        shutil.copy2(ROOT/name,target)
        if sha(target)!=expected:
            raise ValueError('updated source preservation failed')
    assert_frozen(out,data)
    return dict(receipt_sha256=sha(receipt_path),old_sources_digest=digest(old['sources']),
        new_sources_digest=digest(current),clock_entry_sha256=sha(out/'entry.json'),
        initial_checkpoint_preserved=True,training_updates=0)


def validate_preflight_recovery(data,out,receipt_path):
    out,receipt_path=Path(out),Path(receipt_path)
    receipt=read(receipt_path)
    if receipt['kind']=='finite_zero_gradient':
        return validate_zero_gradient_repair(data,out,receipt_path,receipt)
    original=out/'versions/preflight-v1'
    if (receipt['kind']!='masked_padding_normalization' or receipt['training_updates']!=0
            or receipt['test_evaluations']!=0 or receipt['stop_sha256']!=sha(out/'STOP.json')
            or receipt['original_manifest_sha256']!=sha(original/'prepared/manifest.json')):
        raise ValueError('preflight recovery identity mismatch')
    old,new=read(original/'prepared/manifest.json'),assert_frozen(out,data)
    old_config,new_config=dict(old['config']),dict(new['config'])
    fallback=receipt.get('gpu_authorization')=='D-106'
    if fallback:
        decision=ROOT/record_relative('D-106', prefix=True)
        if new_config['physical_gpu']!=1 or receipt.get('gpu_authorization_sha256')!=sha(decision):
            raise ValueError('idle GPU fallback lacks the specific user authorization')
    changed_gpu=old_config['physical_gpu']!=new_config['physical_gpu']
    if changed_gpu:
        decision=ROOT/record_relative('D-105', prefix=True)
        if (old_config['physical_gpu']!=1 or new_config['physical_gpu']!=2
                or receipt.get('gpu_authorization')!='D-105'
                or receipt.get('gpu_authorization_sha256')!=sha(decision)):
            raise ValueError('GPU change lacks the specific user authorization')
        old_config['physical_gpu']=2
    if old_config!=new_config:
        raise ValueError('recovery changed frozen treatment')
    for key in ('data_files','base_files','tokenizer_files','denominators','prepared_files'):
        if old[key]!=new[key]:
            raise ValueError('recovery changed frozen input/treatment: '+key)
    if receipt['new_manifest_sha256']!=sha(out/'prepared/manifest.json'):
        raise ValueError('new preparation evidence changed')
    tests=read(out/'verification/tests.json')
    diagnostic=read(out/'diagnostics/padding-v2.json')
    if (not tests['passed'] or receipt['tests_sha256']!=sha(out/'verification/tests.json')
            or receipt['diagnostic_sha256']!=sha(out/'diagnostics/padding-v2.json')
            or not diagnostic['passed'] or diagnostic['original_unpadded_max_difference']!=0
            or diagnostic['padding_max_difference']!=0 or diagnostic['source_hashes']!=new['sources']):
        raise ValueError('independent padding/default-input verification did not pass')
    if read(original/'STOP.json')['error']!='padding changed valid candidate q':
        raise ValueError('original padding stop evidence changed')
    stop=read(out/'STOP.json')
    if stop['error']!='padding changed valid candidate q':
        interrupted=out/'versions/prepare-gpu1-interrupted/STOP.json'
        if (not (changed_gpu or fallback) or stop['stage']!='prepare' or stop['error_type']!='KeyboardInterrupt'
                or stop['error']!='technical interruption requested'
                or not interrupted.exists() or sha(interrupted)!=receipt['stop_sha256']):
            raise ValueError('recovery does not authorize another stop reason')
    for name,expected in old['sources'].items():
        if sha(original/'source'/name)!=expected:
            raise ValueError('original source evidence changed')
    if (out/'training').exists() or (out/'evaluation-lock.json').exists():
        raise ValueError('preflight recovery requires no previous training/test')
    return dict(receipt_sha256=sha(receipt_path),old_sources_digest=digest(old['sources']),
                new_sources_digest=digest(new['sources']),clock_entry_sha256=sha(out/'entry.json'))
