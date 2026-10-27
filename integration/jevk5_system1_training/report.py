"""Offline final analysis and portable non-merged adapter delivery."""
import csv
import json
from pathlib import Path
import shutil
from .config import CONFIG,ROOT
from .data import rows,sha,dump
from .metrics import summarize,bootstrap


def predictions(output,name):return sum((list(rows(output/'predictions'/name/f'rank-{r}.jsonl')) for r in range(3)),[])


def report(output):
    base=predictions(output,'test-base');selected=predictions(output,'test-selected')
    assert len(base)==len(selected)==2304
    results=dict(base=summarize(base),selected=summarize(selected),bootstrap=bootstrap(base,selected))
    results['diagnostics']={name:summarize(predictions(output,'diagnostic-'+name)) for name in ['base','selected']}
    # Pair original/reordered role decisions by meaning, accounting for reversed target indices.
    results['role_order_diagnostics']={}
    for name in ['base','selected']:
        rs=predictions(output,'diagnostic-'+name);pairs={}
        for r in rs:
            if r['domain'].startswith('role-'):pairs.setdefault(r['group'],{})[r['domain']]=r
        assert len(pairs)==3717 and all(len(p)==2 for p in pairs.values())
        results['role_order_diagnostics'][name]=dict(n=3717,meaning_consistent=sum(p['role-original']['choice']==1-p['role-reordered']['choice'] for p in pairs.values()))
    dump(output/'results.json',results)
    with (output/'domains.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['domain','n','base_accuracy','selected_accuracy','difference','base_nll','selected_nll','base_brier','selected_brier','base_ece','selected_ece'])
        for domain,a in results['base']['domains'].items():
            b=results['selected']['domains'][domain];writer.writerow([domain,a['n'],a['accuracy'],b['accuracy'],b['accuracy']-a['accuracy'],a['nll'],b['nll'],a['brier'],b['brier'],a['ece'],b['ece']])
    curve=list(rows(output/'train-rank-0.jsonl'));assert len(curve)==4068 and [r['step'] for r in curve]==list(range(1,4069))
    assert sum(r['examples'] for r in curve)==390447
    assert sum(r['input_tokens'] for r in curve)==148312287
    with (output/'learning-curve.csv').open('w') as f:
        keys=['step','epoch','loss','gradient_norm','learning_rate','examples','input_tokens','padded_tokens','seconds']
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(curve)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(2,1,figsize=(10,7))
    axes[0].plot([r['step'] for r in curve],[r['loss'] for r in curve],linewidth=.4);axes[0].set_ylabel('Weighted CE')
    epochs=json.loads((output/'epochs.json').read_text());baseval=json.loads((output/'predictions/validation-base/metrics.json').read_text())
    axes[1].plot([0]+[x['epoch'] for x in epochs],[baseval['macro_accuracy']]+[x['metrics']['macro_accuracy'] for x in epochs],marker='o');axes[1].set_xlabel('Epoch');axes[1].set_ylabel('Validation macro accuracy')
    figure.tight_layout();figure.savefig(output/'learning-curve.png');plt.close(figure)
    selection=json.loads((output/'selection.json').read_text());ci=results['bootstrap'];training=json.loads((output/'training-validation.json').read_text())
    lines=['# EX-116 JevK5 전체 System One 학습 보고','',f"선택 epoch: {selection['epoch']}. 130,149문항×3epoch, 4,068update, 390,447노출을 완료했다.",
           f"실제 입력 {sum(r['input_tokens'] for r in curve):,}토큰, padding 포함 {sum(r['padded_tokens'] for r in curve):,}토큰.",'',
           '| 평가 영역 | 문항 | 원본 정확도 | 선택 정확도 | 차이 |','|---|---:|---:|---:|---:|']
    for d,a in results['base']['domains'].items():
        b=results['selected']['domains'][d];lines.append(f"| {d} | {a['n']} | {a['accuracy']:.4f} | {b['accuracy']:.4f} | {b['accuracy']-a['accuracy']:+.4f} |")
    lines+=['',f"주지표 7영역 macro 정확도 차이 {ci['difference']*100:+.3f}%p, 대조묶음 단위 paired bootstrap 10,000회 95% 구간 [{ci['ci95'][0]*100:+.3f}, {ci['ci95'][1]*100:+.3f}]%p.",
            '이 평가에서 개선 근거가 있다.' if ci['ci95'][0]>0 else '이 평가에서 개선을 입증하지 못했다.',
            '', 'T=1이며 온도 보정은 하지 않았다. NLL·Brier·ECE와 전체 수치는 results.json 및 domains.csv, 문항별 logits/확률은 predictions에 있다.',
            '', '새 규칙 조합은 고정 Gen9 제어 장면이며 자연 경기·모든 규칙에 대한 일반화를 보장하지 않는다. 리플레이는 학습과 ID/로그/양팀 서명을 분리한 균형표집이며 자연 발생 KO 확률로 해석하지 않는다.',
            '타입 의미그룹 대표 및 역할 원문/순서변화 점수는 학습자료 재현 진단이다. 독립 일반화와 checkpoint 선택에 포함하지 않았다. 역할 미확인은 역할 수행 불가가 아니다.',
            '', '실제 배틀과 서버 교체는 수행하지 않았다. 배틀 승률 개선을 주장하지 않는다. 실험 수행 완료는 completion.json, 성능 개선은 위 구간으로 별도 판단한다.',
            '', '선택 adapter: adapter-selected/; 마지막 epoch: adapter-last/; 완전 checkpoint: checkpoints/; 학습곡선: learning-curve.png 및 CSV.',
            '모델 revision·tokenizer·공식 비Thinking 판독·소스·동결 protocol과 최초 실패/복구 내역을 함께 보존한다.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')


def export(output):
    from .launcher import launch
    selection=json.loads((output/'selection.json').read_text())
    for name,step in [('adapter-selected',selection['epoch']*1356),('adapter-last',4068)]:
        source=output/'checkpoints'/f'step-{step:04d}'/'adapter';dest=output/name
        shutil.copytree(source,dest);shutil.copytree(output/'tokenizer',dest/'tokenizer')
        dump(dest/'base-model.json',dict(model=CONFIG['model'],revision=CONFIG['revision']))
        dump(dest/'readout.json',dict(temperature=1,enable_thinking=False,position='last_real_input_token',labels='ABCDEFGHIJK',candidates='2..11; original order',normalization='valid-candidate softmax',selection='first argmax'))
        dump(dest/'training-config.json',CONFIG)
        shutil.copy2(ROOT/'integration/jevk5_system1_training/loading.py',dest/'loading.py')
        for filename in ['upstream_prompt.py','LICENSE','NOTICE']:shutil.copy2(ROOT/'integration/jevk5_battle'/filename,dest/filename)
    launch('reload',output);report(output)
    checkpoints=sorted((output/'checkpoints').glob('step-*'))
    expected=sorted({0,1356,2712,4068}|set(range(128,4069,128)))
    assert [int(p.name[5:]) for p in checkpoints]==expected
    for path in checkpoints:
        for n,h in json.loads((path/'complete.json').read_text())['files'].items():assert sha(path/n)==h
    assert sum(len(json.loads((output/f'reload-rank-{r}.json').read_text())['rows']) for r in range(3))==24
    receipts=[json.loads(p.read_text()) for p in output.glob('*-receipt-*.json')]
    dump(output/'usage.json',dict(receipts=receipts,gpu_stage_seconds=sum(r['ended']-r['started'] for r in receipts)))
    dump(output/'seal.json',{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file() and p.name not in ['seal.json','completion.json','controller.lock','pipeline.log']})
    dump(output/'completion.json',dict(completed=True,steps=4068,examples=390447,test_rows_per_model=2304,workers_joined=True,
        locks_released=True,reload_rows=24,improvement_supported=json.loads((output/'results.json').read_text())['bootstrap']['ci95'][0]>0))
