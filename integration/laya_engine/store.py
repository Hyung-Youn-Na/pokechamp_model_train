"""EP-224 / EX-151: engine-judge labels for every EX-071 row (`laya-engine-judge/v1`) and the human-replay check.

Each row is judged from the same input the v5 features store was computed on (`data_v6._value(..., 'v6s')[0]`, the
EX-071 prepared input with `laya-item-state/v1` merged), checked against the store's input hash. Rows keep EX-071
order. `human(store)` counts rows with a judged failure and how often the human chose a judged option.
"""
from __future__ import annotations
import collections
import gzip
import json
from multiprocessing import Pool
from pathlib import Path
import shutil
import sys
import time

from . import judge as J

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
STORE = SHARED / 'datasets/generated/laya-engine-judge/v1'
SPLITS = ('train', 'validation', 'test')

_judge = None


def _init():
    global _judge
    _judge = J.Judge()


def _job(item):
    from integration.laya_imitation import data_v6
    record, extra, cached = item
    if extra['sample_id'] != record['sample_id'] or cached['sample_id'] != record['sample_id']:
        raise ValueError('stores out of order at ' + record['sample_id'])
    value, _ = data_v6._value(record, extra, None, 'v6s')
    if value.sha256 != cached['input_sha256']:
        raise ValueError('input hash differs from the v5 features store at ' + record['sample_id'])
    t0 = time.perf_counter()
    labels, detail = J.option_outcomes(value, _judge)
    return dict(sample_id=record['sample_id'], input_sha256=value.sha256, label=record['label'],
                decision_kind=record['decision_kind'], labels=labels, reproduced=detail.get('reproduced'),
                engine={k: v['label'] for k, v in detail['options'].items()},
                errors={k: v.get('error') for k, v in detail['options'].items() if v['label'] == 'unknown'},
                seconds=round(time.perf_counter() - t0, 4))


def _items(split):
    from integration.laya_imitation import config as c, item_state
    from integration.laya_imitation.storage import jsonl
    with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
        for line, extra, cached in zip(f, item_state.load(split), jsonl(c.V5_FEATURES / (split + '.jsonl')),
                                       strict=True):
            yield json.loads(line), extra, cached


def build(output=STORE, workers=96, splits=SPLITS):
    from integration.laya_imitation import config as c
    from integration.laya_imitation.storage import atomic, seal, sha, verify_seal
    output = Path(output)
    if (output / 'manifest.json').exists():
        raise FileExistsError('judge store already built: %s' % output)
    for store in (c.ITEM_STATE, c.V5_FEATURES):
        if verify_seal(store):
            raise RuntimeError('seal failed: %s' % store)
    output.mkdir(parents=True, exist_ok=True)
    started, counts = time.time(), {}
    with Pool(workers, initializer=_init) as pool:
        for split in splits:
            n = 0
            with open(output / (split + '.jsonl'), 'w') as f:
                for row in pool.imap(_job, _items(split), chunksize=64):
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
                    n += 1
                    if n % 20000 == 0:
                        print('%s %d %.0fs' % (split, n, time.time() - started), flush=True)
            counts[split] = n
    generator = output / 'generator-source'
    generator.mkdir(exist_ok=True)
    for name in J.FILES + ('store.py',):
        shutil.copy2(J.HERE / name, generator / name)
    manifest = dict(dataset='laya-engine-judge', version=output.name, experiment='EX-151', judge=J.identity(),
                    engine='/workspace/pokemon-showdown/dist/sim (e64915c0e)', counts=counts,
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'),
                    item_state_manifest_sha256=sha(c.ITEM_STATE / 'manifest.json'),
                    features_manifest_sha256=sha(c.V5_FEATURES / 'manifest.json'),
                    seconds=round(time.time() - started, 1), created_at=started,
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in splits})
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(README % dict(counts=json.dumps(counts)))
    seal(output)
    print(json.dumps(dict(counts=counts, seconds=manifest['seconds'])))
    return manifest


def load(split, store=STORE):
    with open(Path(store) / (split + '.jsonl')) as f:
        for line in f:
            yield json.loads(line)


def human(store=STORE, splits=SPLITS):
    """Per split: turn rows, rows with a judged failure, human chose a judged option (by label)."""
    out = {}
    for split in splits:
        s = collections.Counter()
        chosen = collections.Counter()
        moves = collections.Counter()
        for r in load(split, store):
            if r['decision_kind'] != 'turn_action':
                continue
            s['turn_rows'] += 1
            s['not_reproduced'] += r['reproduced'] is False
            confirmed = {k: v for k, v in r['labels'].items() if v in J.FAILING}
            likely = {k: v for k, v in r['labels'].items() if v == J.LIKELY}
            s['rows_marked'] += bool(confirmed)
            s['options_marked'] += len(confirmed)
            s['rows_likely'] += bool(likely)
            if r['label'] in confirmed:
                s['human_chose_marked'] += 1
                chosen[confirmed[r['label']]] += 1
                moves[r['label'].split(':')[1]] += 1
            s['human_chose_likely'] += r['label'] in likely
        s = dict(s)
        s['human_chose_marked_rate'] = s.get('human_chose_marked', 0) / max(1, s.get('rows_marked', 0))
        s['human_chose_likely_rate'] = s.get('human_chose_likely', 0) / max(1, s.get('rows_likely', 0))
        out[split] = dict(s, chosen_by_label=dict(chosen), chosen_moves=moves.most_common(25))
    return out


def human_outcomes(store=STORE, splits=SPLITS):
    """Rows where the human chose a judged failure: what that move really did in the replay (after `cutoff_line`,
    the battle reports' failure test plus absorbed / bounced / missed / protected / foe switched or Terastallized
    first)."""
    from integration.laya_imitation import config as c
    from integration.pokechamp.imitation.impute import lines_of
    from .validate import _actual
    replays = {}
    for line in open(c.EX071 / 'preparation/replays.jsonl'):
        r = json.loads(line)
        replays[r['replay_id']] = r['raw_path']
    rows, out = [], collections.Counter()
    for split in splits:
        records = {}
        with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
            for line in f:
                r = json.loads(line)
                records[r['sample_id']] = (r['replay_id'], r['perspective'], r['cutoff_line'])
        for r in load(split, store):
            label = r['labels'].get(r['label'])
            if label not in J.FAILING:
                continue
            replay_id, side, cutoff = records[r['sample_id']]
            raw = Path(replays[replay_id]).read_bytes()
            lines = lines_of(json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw))
            foe = 'p2' if side == 'p1' else 'p1'
            found, before = None, []
            for i in range(cutoff, len(lines)):
                p = lines[i].split('|')
                if len(p) > 1 and p[1] == 'turn':
                    break
                if len(p) > 3 and p[1] == 'move' and p[2].startswith(side) and '[from]' not in lines[i]:
                    found = i
                    break
                before.append(lines[i])
            row = dict(split=split, sample_id=r['sample_id'], choice=r['label'], judged=label)
            if found is None:
                row['executed'] = False
            else:
                row.update(executed=True, **_actual(lines, found, side),
                           foe_switched=any(x.startswith(('|switch|' + foe, '|drag|' + foe)) for x in before),
                           foe_tera=any(x.startswith('|-terastallize|' + foe) for x in before))
            rows.append(row)
            if not row['executed']:
                out['not_executed'] += 1
            elif row['foe_switched']:
                out['foe_switched'] += 1
            elif row['failed'] or row['bounced'] or row['absorbed'] or row['miss'] or row['protected']:
                out['did_not_work'] += 1
            else:
                out['worked'] += 1
    return dict(out), rows


README = """# laya-engine-judge v1 — EX-071 행의 엔진 판정기 실패 표시

EP-224(EX-151)의 엔진 판정기(`/workspace/integration/laya_engine`, 고정 Showdown 엔진 e64915c0e)로 EX-071 모든 행의
기술 선택지를 판정한 결과다. 입력은 v5 사실값 저장소와 같은 입력(EX-071 prepared + `laya-item-state/v1`)이며 입력 해시를
행마다 확인했다. 행 순서는 EX-071과 같다.

- 행: %(counts)s
- `labels`: 확정 실패(`fails`/`immune`/`absorbed`/`reflected`)와 확률 실패(`likely fails`)만
- `engine`: 선택지별 엔진 답(`works`, `side`(부가 효과만 실패), `unknown` 포함), `reproduced`: 국면 재현 여부
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(Path(sys.argv[2]) if len(sys.argv) > 2 else STORE)
    elif sys.argv[1] == 'outcomes':
        counts, rows = human_outcomes(Path(sys.argv[2]) if len(sys.argv) > 2 else STORE)
        print(json.dumps(counts))
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    elif sys.argv[1] == 'human':
        print(json.dumps(human(Path(sys.argv[2]) if len(sys.argv) > 2 else STORE), ensure_ascii=False, indent=1))
