"""공개 리플레이의 현재 로컬 규칙 위반 증거를 분류한다. 완전한 세트 검증이 아니다."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = ('candidate', 'incompatible', 'needs_review', 'other_format')
LIMITATIONS = [
    '미공개 기술·아이템·특성·능력치·합법 세트 조합은 검증하지 못함',
    'inputLog/seed/request 부재로 완전한 재실행·합법 후보 복원을 보장하지 않음',
    'candidate는 공개 증거의 위반 미발견이며 완전한 합법성 인증이 아님',
]


def norm(value):
    return re.sub('[^a-z0-9]', '', str(value).lower())


def digest(value):
    return hashlib.sha256(value).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def local_rules():
    result = subprocess.run(['node', str(Path(__file__).with_name('rules.cjs'))],
                            check=True, capture_output=True, text=True)
    rules = json.loads(result.stdout)
    if rules['complex_bans'] or rules['complex_team_bans']:
        raise ValueError('현재 분류기가 지원하지 않는 복합 금지 규칙')
    return rules


class Classifier:
    def __init__(self, rules, reviewed):
        self.rules = rules
        self.catalog = rules['catalog']
        self.reviewed = set(reviewed)

    def lookup(self, kind, name):
        key = norm(name)
        for _ in range(3):
            if key in self.catalog[kind]:
                return self.catalog[kind][key]
            alias = self.rules['aliases'].get(key)
            if not alias:
                break
            key = norm(alias)
        return None

    def species_options(self, label):
        name = label.split(',')[0].strip()
        if name.endswith('-*'):
            base = self.lookup('species', name[:-2])
            if not base:
                return []
            # 전투 전용 폼도 포함한다: Zamazenta-Crowned는 아이템에 의해 시작 시 변한다.
            return sorted({base['id']} | {
                s['id'] for n in base['other_formes'] + base['cosmetic_formes']
                if (s := self.lookup('species', n))})
        obj = self.lookup('species', name)
        return [obj['id']] if obj else []

    def classify(self, data):
        issues, ignored = [], []
        result = dict(replay_id=data.get('id'), format=data.get('formatid'),
                      category=None, reasons=issues, derived_banned_effects=ignored,
                      reviewed108='unknown', reviewed108_outside=[], teams={},
                      historical_rules=[], information_gaps=list(LIMITATIONS))
        if data.get('formatid') != 'gen9ou':
            result['category'] = 'other_format'
            return result
        log = data.get('log')
        if not isinstance(log, str):
            result['category'] = 'needs_review'
            issues.append(dict(severity='review', code='missing_log', message='로그 없음'))
            return result
        lines = log.splitlines()
        previews = {'p1': [], 'p2': []}
        seen = Counter()
        turn = 0

        def evidence(code, message, index, raw, owner=None, obj=None, severity='review'):
            return dict(severity=severity, code=code, message=message, line_number=index,
                        turn=turn, side=owner[:2] if owner else None, owner=owner,
                        object=obj, raw=raw)

        def add(code, message, index, raw, owner=None, obj=None, severity='review'):
            issues.append(evidence(code, message, index, raw, owner, obj, severity))

        # 폼 해소는 원래 switch만 사용한다. detailschange/formechange/transform은 팀 증거가 아니다.
        original_switches = defaultdict(set)
        switch_evidence = defaultdict(list)
        for index, raw in enumerate(lines, 1):
            a = raw.split('|')
            if len(a) < 2 or a[0]:
                continue
            tag = a[1]
            seen[tag] += 1
            if tag == 'poke':
                if len(a) < 4 or a[2] not in previews:
                    add('malformed_preview', '팀 프리뷰 파싱 불가', index, raw)
                    continue
                options = self.species_options(a[3])
                previews[a[2]].append(dict(label=a[3], species_ids=options,
                                           preview_line=index, raw=raw))
                if not options:
                    add('unknown_species', '알 수 없는 프리뷰 종/폼', index, raw, a[2], a[3])
            elif tag in ('switch', 'drag', 'replace') and len(a) >= 4:
                obj = self.lookup('species', a[3].split(',')[0])
                if obj:
                    original_switches[a[2][:2]].add(obj['id'])
                    switch_evidence[(a[2][:2], obj['id'])].append(
                        dict(line_number=index, raw=raw, species_id=obj['id']))
            elif tag == 'rule' and len(a) >= 3:
                result['historical_rules'].append(a[2])
            elif tag == 'gen' and a[2:] != ['9']:
                add('wrong_generation', '메타데이터와 로그의 세대 불일치', index, raw)
            elif tag == 'gametype' and a[2:] != ['singles']:
                add('wrong_game_type', 'singles가 아닌 로그', index, raw)
            elif tag == 'tier' and (len(a) < 3 or norm(a[2]) != 'gen9ou'):
                add('wrong_tier', '메타데이터와 로그의 format 불일치', index, raw)

        outside, unresolved108 = [], False
        for side, team in previews.items():
            if not (self.rules['limits']['min_team_size'] <= len(team) <=
                    self.rules['limits']['max_team_size']):
                add('incomplete_preview', '팀 프리뷰 크기 누락/범위 오류', None, None, side)
                unresolved108 = True
            if len(team) != 6:
                unresolved108 = True  # D-091은 정확히6슬롯을 대상으로 함.
            for member in team:
                options = member['species_ids']
                resolved = sorted(set(options) & original_switches[side])
                if len(options) > 1 and len(resolved) == 1:
                    options = member['species_ids'] = resolved
                    member['resolution_evidence'] = switch_evidence[(side, resolved[0])]
                objects = [self.catalog['species'][s] for s in options]
                blocked = [s for s in objects if s['problems']]
                if objects and len(blocked) == len(objects):
                    for obj in blocked:
                        add('banned_species', '; '.join(obj['problems']),
                            member['preview_line'], member['raw'], side, obj['name'], 'violation')
                elif blocked:
                    add('masked_form', '가려진 폼에 허용/금지 후보가 함께 남음',
                        member['preview_line'], member['raw'], side, member['label'])
                if not options:
                    unresolved108 = True
                elif all(s not in self.reviewed for s in options):
                    outside.append(dict(side=side, label=member['label'], species_ids=options))
                elif any(s not in self.reviewed for s in options):
                    unresolved108 = True
            known_bases = [self.catalog['species'][m['species_ids'][0]]['base_species']
                           for m in team if len(m['species_ids']) == 1]
            for base, count in Counter(known_bases).items():
                if count > 1 and any(k == 'speciesclause' for k, _ in self.rules['rule_table']):
                    add('species_clause', '같은 기본 종이 팀에 중복됨', None, None, side, base, 'violation')
        result['teams'] = previews
        result['reviewed108_outside'] = outside
        result['reviewed108'] = 'fail' if outside else ('unknown' if unresolved108 else 'pass')
        for required in ['teampreview', 'start', 'turn', 'gen', 'gametype', 'tier']:
            if not seen[required]:
                add('missing_structure', '필수 로그 이벤트 없음: ' + required, None, None)
        if seen['win'] + seen['tie'] != 1:
            add('missing_result', '종료 결과 누락/중복', None, None)

        transformed, altered_moves, acquired_items, changed_abilities = set(), set(), set(), set()
        identities = {}

        def key(owner):
            # 동일 닉네임의 슬롯 a/b 표기는 동일 개체로 취급한다. 이 작업은 singles다.
            if not owner or not re.match(r'^p[12][a-z]?: ', owner):
                return None
            return owner[:2] + ': ' + owner.split(': ', 1)[1]

        def check(kind, name, owner, index, raw, derived=None, ambiguous=None):
            obj = self.lookup(kind, name)
            if not obj:
                add('unknown_' + kind, '알 수 없는 관측 객체', index, raw, owner, name)
                return
            if not obj['problems']:
                return
            msg = '; '.join(obj['problems'])
            if derived:
                ignored.append(evidence('derived_' + kind, derived + ': ' + msg,
                                        index, raw, owner, obj['name'], 'derived'))
            elif ambiguous:
                add('ambiguous_' + kind, ambiguous + ': ' + msg, index, raw, owner, obj['name'])
            elif key(owner) not in identities:
                add('unknown_owner', '금지 객체의 원래 개체 식별 불가: ' + msg,
                    index, raw, owner, obj['name'])
            else:
                add('banned_' + kind, msg, index, raw, owner, obj['name'], 'violation')

        for index, raw in enumerate(lines, 1):
            a = raw.split('|')
            if len(a) < 2 or a[0]:
                continue
            tag = a[1]
            if tag in ('-transform', '-ability', '-endability', '-item', '-enditem',
                       'detailschange', '-formechange') and len(a) < 4:
                add('malformed_effect', '효과 이벤트 파싱 불가', index, raw)
                continue
            if tag == 'turn':
                try:
                    turn = int(a[2])
                except (IndexError, ValueError):
                    add('malformed_turn', '턴 파싱 불가', index, raw)
                continue
            if tag in ('switch', 'drag', 'replace'):
                if len(a) < 4 or not key(a[2]):
                    add('malformed_switch', '교체 파싱 불가', index, raw)
                    continue
                ident = key(a[2])
                obj = self.lookup('species', a[3].split(',')[0])
                if not obj:
                    add('unknown_species', '등장 종/폼 파싱 불가', index, raw, a[2], a[3])
                else:
                    identities[ident] = obj['id']
                    # 등장 폼은 이미 변신한 전투 중 효과와 달리 원래 교체 상태의 증거다.
                    if obj['problems']:
                        add('banned_species', '; '.join(obj['problems']), index, raw,
                            a[2], obj['name'], 'violation')
                    originals = [obj['id']]
                    if obj['battle_only']:
                        names = obj['battle_only'] if isinstance(obj['battle_only'], list) else [obj['battle_only']]
                        originals += [s['id'] for n in names if (s := self.lookup('species', n))]
                    possible = {s for m in previews[a[2][:2]] for s in m['species_ids']}
                    if not set(originals) & possible:
                        add('preview_identity_mismatch', '등장 개체를 프리뷰 원래 종에 연결할 수 없음',
                            index, raw, a[2], obj['name'])
                if tag != 'replace':
                    transformed.discard(ident)
                    altered_moves.discard(ident)
                    changed_abilities.discard(ident)
                continue
            if tag == '-transform' and len(a) >= 4:
                transformed.add(key(a[2]))
            if tag in ('detailschange', '-formechange') and len(a) >= 4:
                obj = self.lookup('species', a[3].split(',')[0])
                if not obj:
                    add('unknown_species', '전투 폼 식별 불가', index, raw, a[2], a[3])
                elif obj['problems'] and key(a[2]) not in transformed:
                    if obj['required_items']:
                        add('banned_required_form', '; '.join(obj['problems']), index, raw,
                            a[2], obj['name'], 'violation')
                    else:
                        add('ambiguous_battle_form', '금지 폼의 원래 세트 출처 미확정',
                            index, raw, a[2], obj['name'])
            if tag in ('move', 'cant'):
                if len(a) < 4:
                    add('malformed_move', '기술 이벤트 파싱 불가', index, raw)
                    continue
                owner = a[2]
                ident = key(owner)
                name = a[3] if tag == 'move' else (a[4] if len(a) > 4 else None)
                if name:
                    flags = a[5:] if tag == 'move' else a[5:]
                    source = next((f[7:] for f in flags if f.startswith('[from] ')), None)
                    derived = ambiguous = None
                    if ident in transformed:
                        derived = 'Transform으로 복사된 기술'
                    elif ident in altered_moves:
                        ambiguous = 'Mimic/Sketch 이후 기술 출처 미확정'
                    elif source and source != 'move: Sleep Talk':
                        if source in {'ability: Magic Bounce', 'ability: Dancer',
                                      'move: Metronome', 'move: Assist', 'move: Copycat',
                                      'move: Mirror Move', 'move: Me First', 'move: Nature Power'}:
                            derived = '호출/반사된 효과 (' + source + ')'
                        else:
                            ambiguous = '기술 호출 출처 미확정 (' + source + ')'
                    check('moves', name, owner, index, raw, derived, ambiguous)
                    if tag == 'move' and norm(name) in ('mimic', 'sketch'):
                        altered_moves.add(ident)
            if len(a) < 3:
                continue
            owner = a[2]
            ident = key(owner)
            flags = a[4:] if tag in ('-ability', '-endability', '-item', '-enditem') else a[3:]
            source = next((f[7:] for f in flags if f.startswith('[from] ')), None)
            if tag == '-ability' and source:
                changed_abilities.add(ident)
            if tag == '-item' and source and source != 'ability: Frisk':
                acquired_items.add(ident)
            if tag in ('-ability', '-endability') and len(a) >= 4:
                derived = 'Transform/복사·교환된 특성' if ident in transformed or ident in changed_abilities else None
                check('abilities', a[3], owner, index, raw, derived=derived)
                # Trace는 원래 소유자의 특성도 명시한다.
                if source == 'ability: Trace':
                    donor = next((f[5:] for f in flags if f.startswith('[of] ')), None)
                    if donor:
                        dk = key(donor)
                        check('abilities', a[3], donor, index, raw,
                              derived='원 소유자도 변신/특성 변경' if dk in transformed or dk in changed_abilities else None)
            if tag in ('-item', '-enditem') and len(a) >= 4:
                check('items', a[3], owner, index, raw,
                      ambiguous='획득/교환 이후 아이템의 원래 출처 미확정' if ident in acquired_items else None)
            # 효과를 발동한 소유자는 [of]가 있으면 그 개체, 없으면 이벤트 대상이다.
            if source and source.startswith(('ability: ', 'item: ')):
                effect_owner = next((f[5:] for f in flags if f.startswith('[of] ')), owner)
                ek = key(effect_owner)
                if source.startswith('ability: '):
                    check('abilities', source[9:], effect_owner, index, raw,
                          derived='Transform/복사·교환된 특성' if ek in transformed or ek in changed_abilities else None)
                else:
                    check('items', source[6:], effect_owner, index, raw,
                          ambiguous='획득/교환 이후 아이템의 원래 출처 미확정' if ek in acquired_items else None)
        result['category'] = ('incompatible' if any(i['severity'] == 'violation' for i in issues)
                              else 'needs_review' if issues else 'candidate')
        return result


def normalized_sources(directory):
    # 기존 환경에 설치된 pyarrow를 사용하며 새 의존성을 설치하지 않는다.
    import pyarrow.parquet as pq
    sources = defaultdict(list)
    hashes = {}
    for path in sorted(directory.glob('*.parquet')):
        hashes[str(path.relative_to(ROOT))] = digest(path.read_bytes())
        columns = ['replay_id', 'canonical_url', 'parent_url', 'source_parent_urls',
                   'snapshot_id', 'raw_sha256', 'input_log']
        for row in pq.read_table(path, columns=columns).to_pylist():
            row['normalized_path'] = str(path.relative_to(ROOT))
            row['has_input_log'] = bool(row.pop('input_log'))
            sources[row['replay_id']].append(row)
    return sources, hashes


def run(raw_dir, normalized_dir, output, reviewed_path):
    if output.exists():
        raise FileExistsError('기존 출력은 덮어쓰지 않습니다: ' + str(output))
    rules = local_rules()
    reviewed_bytes = reviewed_path.read_bytes()
    reviewed = json.loads(reviewed_bytes)['reviewed_species_ids']
    assert len(reviewed) == len(set(reviewed)) == 108
    classifier = Classifier(rules, reviewed)
    sources, normalized_hashes = normalized_sources(normalized_dir)
    rows, raw_hashes, failures, seen_ids = [], {}, [], {}
    files = sorted(p for p in raw_dir.iterdir() if p.is_file())
    for path in files:
        raw = path.read_bytes()
        rel = str(path.relative_to(ROOT))
        raw_hashes[rel] = digest(raw)
        try:
            decoded = gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw
            data = json.loads(decoded)
            if not isinstance(data, dict) or not isinstance(data.get('id'), str):
                raise ValueError('replay ID 누락/객체가 아닌 JSON')
            payload_hash = digest(decoded)
            if data['id'] in seen_ids:
                previous = seen_ids[data['id']]
                if previous['payload_sha256'] != payload_hash:
                    raise ValueError('동일 replay ID의 내용 충돌: ' + data['id'])
                previous['duplicate_paths'].append(rel)
                continue
            row = classifier.classify(data)
            row.update(raw_path=rel, raw_file_sha256=digest(raw), payload_sha256=payload_hash,
                       duplicate_paths=[], sources=sources.get(data['id'], []))
            # 이 자료의 raw_sha256는 저장된 gzip 파일 바이트의 해시다.
            if any(s['raw_sha256'] != digest(raw) for s in row['sources']):
                raise ValueError('정규화 출처와 저장된 원본 파일 해시 불일치: ' + data['id'])
            rows.append(row)
            seen_ids[data['id']] = row
        except (ValueError, UnicodeError, OSError, EOFError) as exc:
            failures.append(dict(path=rel, error=str(exc)))
    if failures:
        raise ValueError(f'원본 처리 실패 {len(failures)}개; 분류 결과를 생성하지 않음. 처음5개: '
                         + json.dumps(failures[:5], ensure_ascii=False))
    counts = Counter(r['category'] for r in rows)
    assert sum(counts.values()) == len(rows)
    assert len(rows) + sum(len(r['duplicate_paths']) for r in rows) == len(files)
    # 읽기 전용 입력 및 분류에 사용한 규칙 파일이 실행 중 바뀌지 않았음을 확인한다.
    for rel, expected in {**raw_hashes, **normalized_hashes, **rules['file_sha256']}.items():
        assert digest((ROOT / rel).read_bytes()) == expected, '입력 변경: ' + rel
    assert digest(reviewed_path.read_bytes()) == digest(reviewed_bytes)
    output.mkdir(parents=True)
    dump(output / 'rules-snapshot.json', rules)
    with (output / 'classification.jsonl').open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    fields = ['replay_id', 'format', 'category', 'reviewed108', 'raw_path', 'raw_file_sha256',
              'payload_sha256', 'reasons', 'reviewed108_outside', 'information_gaps', 'sources']
    with (output / 'classification.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], (list, dict))
                             else row[k] for k in fields})
    for category in CATEGORIES:
        (output / (category + '.txt')).write_text(''.join(r['replay_id'] + '\n' for r in rows
                                                       if r['category'] == category))
    selected = [r['replay_id'] for r in rows if r['category'] == 'candidate' and r['reviewed108'] == 'pass']
    (output / 'candidate-reviewed108.txt').write_text(''.join(s + '\n' for s in selected))
    target = [r for r in rows if r['format'] == 'gen9ou']
    reasons = Counter((i['code'], i.get('object')) for r in target for i in r['reasons'])
    reason_games = Counter(k for r in target for k in {(i['code'], i.get('object')) for i in r['reasons']})
    summary = dict(raw_files=len(files), unique_replays=len(rows), gen9ou=len(target),
                   duplicates=len(files)-len(rows), processing_failures=0,
                   categories={c: counts[c] for c in CATEGORIES},
                   reviewed108=dict(Counter(r['reviewed108'] for r in target)),
                   candidate_reviewed108=len(selected),
                   reason_counts=[dict(code=k[0], object=k[1], events=n, games=reason_games[k])
                                  for k, n in reasons.most_common()],
                   normalized_linked=sum(bool(r['sources']) for r in rows),
                   derived_banned_events=sum(len(r['derived_banned_effects']) for r in rows))
    dump(output / 'summary.json', summary)
    report(output, rows, summary)
    manifest = dict(schema_version='replay-rule-eligibility/v1',
                    created_at_utc=datetime.now(timezone.utc).isoformat(),
                    command='pokechamp/.venv/bin/python scripts/replay_eligibility/classify.py',
                    source_sha256={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
                                   [Path(__file__), Path(__file__).with_name('rules.cjs'),
                                    Path(__file__).with_name('test_classify.py')]},
                    reviewed_species_source=str(reviewed_path.relative_to(ROOT)),
                    reviewed_species_sha256=digest(reviewed_bytes),
                    raw_file_sha256=raw_hashes, normalized_file_sha256=normalized_hashes,
                    input_preservation_verified=True,
                    output_sha256={p.name: digest(p.read_bytes()) for p in sorted(output.iterdir())})
    dump(output / 'manifest.json', manifest)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def report(output, rows, summary):
    text = ['# 현재 로컬 Gen9 OU 리플레이 분류', '',
            '현재 로컬 Showdown 규칙의 공개 위반 증거를 검사한 결과다. 완전한 세트 합법성 인증이 아니다.', '',
            '## 분류 결과', '', '| 분류 | 경기 수 |', '|---|---:|']
    text += [f'| `{c}` | {summary["categories"][c]:,} |' for c in CATEGORIES]
    text += ['', f'원본 {summary["raw_files"]:,}파일, Gen9 OU {summary["gen9ou"]:,}경기. '
             f'중복 {summary["duplicates"]}개, 처리 실패 {summary["processing_failures"]}개.', '',
             f'후보 중 양측108종 제한 충족: **{summary["candidate_reviewed108"]:,}경기**. '
             '선별 목록은 [candidate-reviewed108.txt](candidate-reviewed108.txt)다.', '',
             '108종 독립 판정(전체 Gen9 OU): ' + json.dumps(summary['reviewed108'], ensure_ascii=False), '',
             '## 주요 판정 이유', '', '| 코드 | 객체 | 해당 경기 수 | 증거 이벤트 수 |', '|---|---|---:|---:|']
    text += [f'| {r["code"]} | {r["object"] or "—"} | {r["games"]:,} | {r["events"]:,} |'
             for r in summary['reason_counts'][:25]]
    text += ['', '한 경기의 여러 위반을 보존하므로 이유별 경기 수를 더하면 전체 경기 수와 다르다.', '',
             '## 대표 사례', '']
    for category in CATEGORIES[:3]:
        examples = [r for r in rows if r['category'] == category][:3]
        for r in examples:
            reason = r['reasons'][0] if r['reasons'] else None
            detail = (f'{reason["code"]}: {reason["message"]} '
                      f'(행 {reason.get("line_number")}, 턴 {reason.get("turn")})') if reason else '관측된 규칙 위반 없음'
            text.append(f'- `{category}` / `{r["replay_id"]}` / 108종 `{r["reviewed108"]}` — {detail}')
    text += ['', '## 판정 범위와 재현', '',
             '- `candidate`: 필요한 구조가 있고 관측된 위반/판정에 영향을 주는 미해결 문제가 없음.',
             '- `incompatible`: 현재 규칙 위반의 명확한 증거 있음. 다른 검토 이유도 함께 보존.',
             '- `needs_review`: 가려진 폼, 효과 출처, 알 수 없는 객체, 구조 부족 등 미해결 문제.',
             '- `other_format`: Gen9 OU가 아닌 자료.',
             '- 원래 팀은 프리뷰/원래 switch에서 확인하며 Transform·전투 폼은 새 팀 구성으로 보지 않음.',
             '- 호출/반사된 기술·복사된 특성은 출처를 구분하고, 교환 아이템의 원래 출처는 보수적으로 검토.',
             '- 108종은 규칙 판정과 독립적이며 정확한 종/폼 ID와 양측6슬롯을 검사.',
             '- 미공개 세트와 습득 가능 기술 조합/EV/IV/이벤트 제약까지 검증한 결과는 아님.',
             '- 과거 규칙 문구와 업로드 날짜·rating·승패는 제외 기준으로 사용하지 않음.',
             '- 기존 normalized 자료와 연결된 원본은 저장된 gzip 파일 해시까지 대조. 압축 전 payload 해시는 별도로 저장.',
             '- [rules-snapshot.json](rules-snapshot.json)에 실제 런타임 규칙·객체별 금지 판정·소스 해시 보존.',
             '- [classification.jsonl](classification.jsonl)에 원문·행(1부터)·턴·진영·전체 이유 보존.',
             '- [classification.csv](classification.csv), 분류별 txt 및 [summary.json](summary.json) 제공.',
             '- [manifest.json](manifest.json)에 입력/분류기 해시와 원본 보존 검사 보존.', '',
             '기존 출력을 덮어쓰지 않으며 재현 시 새 디렉터리를 지정한다.', '', '```bash',
             'pokechamp/.venv/bin/python scripts/replay_eligibility/classify.py --output /workspace/exports/replay-eligibility/gen9ou-local-rerun',
             '```', '']
    (output / 'report.md').write_text('\n'.join(text))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=ROOT / 'data/showdown-replays/raw')
    parser.add_argument('--normalized', type=Path, default=ROOT / 'data/showdown-replays/normalized/replays')
    parser.add_argument('--reviewed', type=Path, default=ROOT / 'export/teams/gen9ou_reviewed108_teams.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'exports/replay-eligibility/gen9ou-local-v1')
    args = parser.parse_args()
    run(args.raw.resolve(), args.normalized.resolve(), args.output.resolve(), args.reviewed.resolve())


if __name__ == '__main__':
    main()
