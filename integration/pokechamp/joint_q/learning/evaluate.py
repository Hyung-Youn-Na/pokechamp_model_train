import gc
import json
from pathlib import Path
import numpy as np
import torch
from ..data import load
from ..serializer import reorder
from ..storage import atomic, digest, jsonl, read, rows, sha
from .artifacts import assert_frozen, file_manifest, now, validate_checkpoint
from .config import CONFIG
from .metrics import observation, paired_bootstrap, report
from .model import JointValuePolicy, load_base, seed_all, tokenizer
from .prepare import aligned_records, encoded_rows
from .render import render, EncodedInput
from .runtime import Progress
from .train import metadata, prediction_rows


def reload_and_lock(data,out):
    frozen=assert_frozen(out,data)
    directory=Path(out)/'reload'
    if (Path(out)/'evaluation-lock.json').exists():
        raise FileExistsError('configuration already locked for test')
    progress=Progress(directory,'reload')
    selection=read(Path(out)/'training/selection.json')
    cp=Path(selection['checkpoint'])
    saved=validate_checkpoint(cp)
    seed_all()
    policy=JointValuePolicy(load_base(directory/'loading.json'),tokenizer(Path(out)/'prepared/tokenizer'),cp)
    if policy.trainable_fingerprints()!=saved['trainable_fingerprints']:
        raise ValueError('reloaded adapter/head fingerprint mismatch')
    validation=aligned_records(data,encoded_rows(out,'validation'),'validation')
    prediction=prediction_rows(policy,validation,metadata(out),progress,phase='reload_validation')
    original=rows(Path(out)/f'training/validation-epoch{selection["selected_epoch"]}.jsonl')
    if [r['observation_id'] for r in prediction]!=[r['observation_id'] for r in original]:
        raise ValueError('reload observation order differs')
    maximum=0.
    for a,b in zip(prediction,original,strict=True):
        if a['action_ids']!=b['action_ids'] or a['target_q']!=b['target_q']:
            raise ValueError('reload candidate/target differs')
        maximum=max(maximum,max(abs(x-y) for x,y in zip(a['predicted_q'],b['predicted_q'],strict=True)))
    jsonl(directory/'validation.jsonl',prediction)
    if maximum>1e-4:
        raise ValueError(f'reload q difference {maximum} exceeds 1e-4')
    reversed_pairs=[]
    for r,e in validation:
        changed=r.reordered(tuple(reversed(r.input.action_ids)))
        reversed_pairs.append((changed,render(changed.input,policy.tokenizer)))
    reversed_prediction=prediction_rows(policy,reversed_pairs,metadata(out),progress,phase='order_diagnostic')
    jsonl(directory/'validation-reversed.jsonl',reversed_prediction)
    differences,changed_selections=[],0
    for a,b in zip(prediction,reversed_prediction,strict=True):
        by_id=dict(zip(b['action_ids'],b['predicted_q'],strict=True))
        differences.extend(abs(q-by_id[aid]) for aid,q in zip(a['action_ids'],a['predicted_q'],strict=True))
        changed_selections+=observation(a)['chosen_id']!=observation(b)['chosen_id']
    result=dict(passed=True,at=now(),selected_epoch=selection['selected_epoch'],
        reloaded_validation_observations=len(prediction),maximum_q_difference=maximum,
        trainable_fingerprints_equal=True,base_unchanged=policy.base_fingerprints()==saved['base_fingerprints'],
        candidate_order_diagnostic=dict(observations=len(prediction),maximum_q_difference=max(differences),
            mean_q_difference=float(np.mean(differences)),p95_q_difference=float(np.quantile(differences,.95)),
            changed_selections=int(changed_selections),original_metrics=report(prediction),
            reversed_metrics=report(reversed_prediction)))
    if not result['base_unchanged']:
        raise ValueError('reloaded base fingerprint differs')
    atomic(directory/'report.json',result,immutable=True)
    lock=dict(at=now(),config=CONFIG,frozen_manifest_sha256=digest(frozen),
        selection_sha256=sha(Path(out)/'training/selection.json'),reload_report_sha256=sha(directory/'report.json'),
        model_checkpoints={'initial':str((Path(out)/'training/initial').resolve()),'selected':str(cp.resolve())},
        checkpoint_files_sha256={name:sha(path/'files.json') for name,path in
            [('initial',Path(out)/'training/initial'),('selected',cp)]},test_model_evaluations=1)
    atomic(Path(out)/'evaluation-lock.json',lock,immutable=True)
    progress.update(phase='complete',maximum_q_difference=maximum)
    return result


def checked_lock(data,out):
    frozen=assert_frozen(out,data)
    lock=read(Path(out)/'evaluation-lock.json')
    if lock['config']!=CONFIG or lock['frozen_manifest_sha256']!=digest(frozen):
        raise ValueError('evaluation lock differs from frozen setup')
    if (lock['selection_sha256']!=sha(Path(out)/'training/selection.json') or
            lock['reload_report_sha256']!=sha(Path(out)/'reload/report.json')):
        raise ValueError('selection/reload report changed after test lock')
    for name,path in lock['model_checkpoints'].items():
        validate_checkpoint(path)
        if sha(Path(path)/'files.json')!=lock['checkpoint_files_sha256'][name]:
            raise ValueError('locked checkpoint changed: '+name)
    return lock


def evaluate(data,out):
    lock=checked_lock(data,out)
    directory=Path(out)/'evaluation'
    directory.mkdir(parents=True,exist_ok=True)
    progress=Progress(directory,'evaluate')
    tok=tokenizer(Path(out)/'prepared/tokenizer')
    records=list(load(data,split='test'))
    encoded=[(r,render(r.input,tok)) for r in records]
    if len(encoded)!=709 or sum(len(r.q) for r,e in encoded)!=6369:
        raise ValueError('test denominator differs')
    # No test token cache is used for training or model choice.
    token_path=directory/'test-tokens.jsonl'
    if not token_path.exists():
        jsonl(token_path,[e.to_row(r.observation_id) for r,e in encoded])
    else:
        cached=rows(token_path)
        if cached!=[json.loads(json.dumps(e.to_row(r.observation_id))) for r,e in encoded]:
            raise ValueError('test token encoding changed')
    meta=metadata(out)
    for name,path in lock['model_checkpoints'].items():
        output=directory/f'test-{name}.jsonl'
        reservation=directory/f'reservation-{name}.json'
        completed=directory/f'completed-{name}.json'
        if completed.exists():
            done=read(completed)
            if sha(output)!=done['predictions_sha256'] or done['observations']!=709:
                raise ValueError('completed test evidence changed')
            continue
        if reservation.exists():
            raise RuntimeError('test evaluation already attempted; forward retry forbidden: '+name)
        atomic(reservation,dict(at=now(),model=name,checkpoint=path,
            evaluation_lock_sha256=sha(Path(out)/'evaluation-lock.json'),model_evaluation_number=1),immutable=True)
        seed_all()
        policy=JointValuePolicy(load_base(directory/f'loading-{name}.json'),tok,Path(path))
        saved=validate_checkpoint(path)
        if policy.trainable_fingerprints()!=saved['trainable_fingerprints']:
            raise ValueError('test checkpoint trainable fingerprint differs')
        before=policy.trainable_fingerprints()
        policy.eval()
        result=[]
        for i,(r,e) in enumerate(encoded):
            with torch.no_grad(),progress.timed():
                prediction=policy.values(e).cpu().tolist()
            row=dict(observation_id=r.observation_id,action_ids=list(e.action_ids),
                target_q=list(r.q),predicted_q=prediction,tokens=len(e.input_ids),
                prompt_sha256=e.prompt_sha256,readout_positions=list(e.readout_positions),**meta[r.observation_id])
            result.append(row)
            # Partial test evidence survives a stop; it never authorizes a second pass.
            with (directory/f'partial-test-{name}.jsonl').open('a') as handle:
                handle.write(json.dumps(row)+'\n')
            if (i+1)%10==0 or i+1==len(encoded):
                progress.update(phase='test',model=name,observations=i+1,total_observations=len(encoded))
        if before!=policy.trainable_fingerprints() or policy.base_fingerprints()!=saved['base_fingerprints']:
            raise ValueError('evaluation changed model parameters')
        jsonl(output,result)
        atomic(completed,dict(at=now(),model=name,observations=len(result),candidates=sum(len(r.q) for r,e in encoded),
            predictions_sha256=sha(output),base_unchanged=True,trainable_unchanged=True),immutable=True)
        del policy
        gc.collect()
        torch.cuda.empty_cache()
    progress.update(phase='complete')
    return dict(completed_models=list(lock['model_checkpoints']),observations_per_model=709)


def analyze(data,out):
    lock=checked_lock(data,out)
    directory=Path(out)/'evaluation'
    predictions={name:rows(directory/f'test-{name}.jsonl') for name in lock['model_checkpoints']}
    for name in predictions:
        done=read(directory/f'completed-{name}.json')
        if done['predictions_sha256']!=sha(directory/f'test-{name}.jsonl'):
            raise ValueError('test prediction receipt mismatch')
    train_records=list(load(data,split='train'))
    train_constant=float(np.mean([np.mean(r.q) for r in train_records]))
    template=predictions['initial']
    for name,value in [('constant_0.5',.5),('train_mean_constant',train_constant)]:
        predictions[name]=[{**row,'predicted_q':[value]*len(row['action_ids'])} for row in template]
        jsonl(directory/f'test-{name}.jsonl',predictions[name])
    result=dict(at=now(),train_observation_weighted_q_constant=train_constant,
        metrics={name:report(values) for name,values in predictions.items()},
        paired_test_team_bootstrap={name:paired_bootstrap(predictions['selected'],values)
                                  for name,values in predictions.items() if name!='selected'},
        interpretation='fixed own team, hidden actual state, Abyssal continuation conditional q; battle efficacy unmeasured')
    atomic(directory/'metrics.json',result,immutable=True)
    return result
