"""Build `laya-compact-imitation/v1` from the sealed EX-071 prepared splits (read-only).

Each output row is a laya training row `{state, questions:{action}, expected:{action}}` plus
`sample_id` and `meta` (decision/label kind, Tera) that laya ignores and the model never sees.
"""
from __future__ import annotations
import json
import re
import shutil
import time

from integration.pokechamp.imitation.dataset import signature
from integration.pokechamp.imitation.schema import ImitationInput

from . import compact
from . import config as c
from .lengths import measure
from .storage import atomic, jsonl, read, seal, sha, source_identity, write_jsonl

SPLITS = ('train', 'validation', 'test')
META = ('decision_kind', 'label_kind', 'tera_used')


def _species(showdown_team):
    out = []
    for block in showdown_team.strip().split('\n\n'):
        head = block.strip().split('\n')[0].split('@')[0].strip()
        head = re.sub(r'\s*\((M|F)\)\s*$', '', head)
        match = re.search(r'\(([^()]+)\)\s*$', head)
        out.append(match.group(1) if match else head)
    return out


def contamination():
    """EX-089 team signatures against every EX-071 replay and split; must be disjoint."""
    manifest = read(c.EX089_COLLECTION / 'manifest.json')
    seal_lines = (c.EX089_COLLECTION / 'checksums.sha256').read_text().splitlines()
    sealed = dict(reversed(line.split('  ', 1)) for line in seal_lines)
    if sealed.get('manifest.json') != sha(c.EX089_COLLECTION / 'manifest.json'):
        raise ValueError('EX-089 manifest does not match its seal')
    teams = {k: signature(_species(v['showdown_team'] if isinstance(v, dict) else v))
             for k, v in manifest['teams'].items()}
    replays = list(jsonl(c.EX071_PREPARATION / 'replays.jsonl'))
    hits = {r['replay_id'] for r in replays if set(teams.values()) & set(r['signatures'])}
    excluded = {r['replay_id'] for r in jsonl(c.EX071_PREPARATION / 'replay-exclusions.jsonl')}
    return dict(ex089_manifest_sha256=sha(c.EX089_COLLECTION / 'manifest.json'), team_signatures=teams,
                replays_with_ex089_team=len(hits), of_which_excluded_by_ex071=len(hits & excluded),
                hit_ids=sorted(hits))


def _source_check():
    manifest = read(c.EX071_PREPARED / 'manifest.json')
    for split in SPLITS:
        name = split + '.jsonl'
        if sha(c.EX071_PREPARED / name) != manifest['files'][name]:
            raise ValueError('EX-071 prepared file changed: ' + name)
    return dict(manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'), files=manifest['files'],
                selected_split=manifest['counts']['selected_split'])


def build(output=c.DATASET):
    from transformers import AutoTokenizer
    if (output / 'manifest.json').exists():
        raise FileExistsError('dataset already built: %s' % output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    source = _source_check()
    gate = contamination()
    tok = AutoTokenizer.from_pretrained(str(c.MODEL_DIR / 'tokenizer'))
    counts, lengths, exclusions, coverage = {}, {}, [], {}
    for split in SPLITS:
        rows, totals, heads = [], [], []
        kinds = {}
        for record in jsonl(c.EX071_PREPARED / (split + '.jsonl')):
            if record['replay_id'] in gate['hit_ids']:
                raise ValueError('EX-089 team replay inside EX-071 split: ' + record['replay_id'])
            value = ImitationInput.from_body(record['input'])
            state, question = compact.render(value)
            if record['label'] not in question['criteria']:
                raise ValueError('label outside rendered candidates: ' + record['sample_id'])
            if list(question['criteria']) != list(value.action_ids):
                raise ValueError('candidate order changed: ' + record['sample_id'])
            m = measure(tok, state, question)
            if not m['fits']:
                exclusions.append(dict(split=split, sample_id=record['sample_id'], reason='token_budget', **m))
                continue
            totals.append(m['total'])
            heads.append(m['head'])
            kinds[record['decision_kind']] = kinds.get(record['decision_kind'], 0) + 1
            rows.append(dict(sample_id=record['sample_id'], input_sha256=value.sha256, state=state,
                             questions={'action': question}, expected={'action': record['label']},
                             meta={k: record[k] for k in META}))
        write_jsonl(output / (split + '.jsonl'), rows, immutable=True)
        counts[split] = len(rows)
        ordered = sorted(totals)
        pick = lambda p: ordered[int(p * (len(ordered) - 1))]
        lengths[split] = dict(total_p50=pick(.5), total_p95=pick(.95), total_max=ordered[-1],
                              head_max=max(heads), mean=round(sum(totals) / len(totals), 1))
        coverage[split] = dict(decision_kind=kinds)
    validation = dict(source_files_match=True, ex089_disjoint=gate['replays_with_ex089_team'] ==
                      gate['of_which_excluded_by_ex071'], token_budget_exclusions=len(exclusions),
                      counts_match_source={s: counts[s] == source['selected_split'][s] for s in SPLITS})
    write_jsonl(output / 'exclusions.jsonl', exclusions, immutable=True)
    atomic(output / 'validation.json', validation, immutable=True)
    atomic(output / 'coverage.json', dict(lengths=lengths, coverage=coverage), immutable=True)
    atomic(output / 'contamination.json', {k: v for k, v in gate.items() if k != 'hit_ids'}, immutable=True)
    generator = output / 'generator-source'
    for name in ('compact.py', 'dex.py', 'dex_gen9.json', 'data.py', 'lengths.py', 'config.py'):
        generator.mkdir(exist_ok=True)
        shutil.copy2(c.ROOT / 'integration/laya_imitation' / name, generator / name)
    manifest = dict(dataset='laya-compact-imitation', version='v1', experiment='EX-118', created_at=started,
                    seconds=round(time.time() - started, 1), render=compact.version(),
                    token_limit=c.TOKEN_LIMIT, head_limit=c.HEAD_LIMIT, tokenizer=str(c.MODEL_DIR / 'tokenizer'),
                    model_revision=c.MODEL_REVISION, source=source, counts=counts, source_code=source_identity(),
                    files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS})
    atomic(output / 'manifest.json', manifest, immutable=True)
    readme(output, manifest, validation)
    seal(output)
    c.EXPORT.mkdir(parents=True, exist_ok=True)
    for name in ('README.md', 'manifest.json', 'validation.json', 'coverage.json', 'contamination.json',
                 'checksums.sha256'):
        shutil.copy2(output / name, c.EXPORT / name)
    return manifest, validation


def readme(output, manifest, validation):
    lines = [
        '# laya-compact-imitation v1',
        '',
        'EX-071 리플레이 모방 자료(사람 선택)를 laya 0.4.13 학습 행으로 바꾼 자료다. '
        '[EX-118](/workspace/project_context/research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md)이 쓴다.',
        '',
        '- 원본(읽기 전용): `%s` (manifest SHA-256 `%s`)' % (c.EX071_PREPARED, manifest['source']['manifest_sha256']),
        '- 렌더러: `%s`, dex SHA-256 `%s`. 생성 시점 소스는 `generator-source/`에 있다.' % (
            manifest['render']['render'], manifest['render']['dex_sha256']),
        '- 행 수: ' + ', '.join('%s %d' % kv for kv in manifest['counts'].items()),
        '- 길이 한도: 전체 %d, 질문·선택지 %d (laya 토크나이저). 넘는 행은 자르지 않고 `exclusions.jsonl`에 남긴다. '
        '제외 행 수: %d.' % (c.TOKEN_LIMIT, c.HEAD_LIMIT, validation['token_budget_exclusions']),
        '- EX-089 표준 대진 팀과 겹침: `contamination.json` (EX-071이 이미 제외한 경기만 해당).',
        '',
        '## 행 형식',
        '',
        '`{sample_id, input_sha256, state, questions:{action:{type:choice, instructions, criteria}}, '
        'expected:{action}, meta}`. laya `read_jsonl`과 `items_from_rows`가 그대로 읽는다. '
        '`meta`(decision_kind, label_kind, tera_used)는 평가 집계 전용이며 모델 입력이 아니다.',
        '',
        '## 재현',
        '',
        '```bash',
        'cd /workspace && scripts/laya-imitation data   # 이미 있으면 덮어쓰지 않고 실패한다',
        '```',
        '',
        '## 해석 한계',
        '',
        '라벨은 사람 선택이며 승률이나 최적 행동이 아니다. 자신의 세트 보완과 상대 미공개 정보의 한계는 EX-071과 같다. '
        '타입 배율은 순수 타입표 기준이라 특성, 도구, 특수 기술 예외(Freeze-Dry 등)를 반영하지 않는다.',
        '',
    ]
    (output / 'README.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    manifest, validation = build()
    print(json.dumps(dict(counts=manifest['counts'], validation=validation), ensure_ascii=False))
