"""생성된 산출물의 전수 증거 좌표·파일 해시·분류 목록을 별도로 대조한다."""
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'exports/replay-eligibility/gen9ou-local-v1'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep100'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    rows = [json.loads(line) for line in (OUTPUT/'classification.jsonl').read_text().splitlines()]
    manifest = json.loads((OUTPUT/'manifest.json').read_text())
    rules = json.loads((OUTPUT/'rules-snapshot.json').read_text())
    summary = json.loads((OUTPUT/'summary.json').read_text())
    reviewed = set(json.loads((ROOT/manifest['reviewed_species_source']).read_text())['reviewed_species_ids'])
    for name, expected in manifest['output_sha256'].items():
        assert sha(OUTPUT/name) == expected, name
    for name, expected in {**manifest['raw_file_sha256'], **manifest['normalized_file_sha256'],
                           **manifest['source_sha256'], **rules['file_sha256']}.items():
        assert sha(ROOT/name) == expected, name
    assert sha(ROOT/manifest['reviewed_species_source']) == manifest['reviewed_species_sha256']
    assert len({r['replay_id'] for r in rows}) == len(rows)
    counts = Counter(r['category'] for r in rows)
    assert dict(counts) == {k: v for k, v in summary['categories'].items() if v}
    assert len(rows) == summary['unique_replays']
    assert len(manifest['raw_file_sha256']) == summary['raw_files']
    with (OUTPUT/'classification.csv').open() as stream:
        csv_rows = list(csv.DictReader(stream))
    assert [(r['replay_id'], r['category'], r['reviewed108']) for r in csv_rows] == [
        (r['replay_id'], r['category'], r['reviewed108']) for r in rows]
    for category in summary['categories']:
        assert (OUTPUT/(category+'.txt')).read_text().splitlines() == [
            r['replay_id'] for r in rows if r['category'] == category]
    assert (OUTPUT/'candidate-reviewed108.txt').read_text().splitlines() == [
        r['replay_id'] for r in rows if r['category'] == 'candidate' and r['reviewed108'] == 'pass']
    proof_count, resolution_count, linked = 0, 0, 0
    samples, sampled = [], set()
    for row in rows:
        raw = (ROOT/row['raw_path']).read_bytes()
        payload = gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw
        data = json.loads(payload)
        assert data['id'] == row['replay_id']
        assert hashlib.sha256(payload).hexdigest() == row['payload_sha256']
        lines = data['log'].splitlines()
        turn, turns = 0, []
        for line in lines:
            if line.startswith('|turn|'):
                turn = int(line.split('|')[2])
            turns.append(turn)
        for source in row['sources']:
            assert source['raw_sha256'] == row['raw_file_sha256']
            linked += 1
        for reason in row['reasons'] + row['derived_banned_effects']:
            number = reason.get('line_number')
            if number is not None:
                assert 1 <= number <= len(lines)
                assert reason['raw'] == lines[number-1]
                assert reason['turn'] == turns[number-1]
                proof_count += 1
        for side, members in row['teams'].items():
            for member in members:
                assert lines[member['preview_line']-1] == member['raw']
                assert member['raw'].startswith('|poke|'+side+'|')
                for resolution in member.get('resolution_evidence', []):
                    assert lines[resolution['line_number']-1] == resolution['raw']
                    assert resolution['species_id'] in member['species_ids']
                    resolution_count += 1
        if row['category'] == 'candidate':
            assert not row['reasons']
        if row['category'] == 'incompatible':
            assert any(r['severity'] == 'violation' for r in row['reasons'])
        if row['category'] == 'needs_review':
            assert row['reasons'] and all(r['severity'] == 'review' for r in row['reasons'])
        if row['reviewed108'] == 'pass':
            assert all(len(t) == 6 for t in row['teams'].values())
            assert all(m['species_ids'] and set(m['species_ids']) <= reviewed
                       for t in row['teams'].values() for m in t)
        if row['reviewed108'] == 'fail':
            assert row['reviewed108_outside']
        # 분류/108종 조합 및 주요 판정 객체별 첫 사례를 감사 기록으로 보존한다.
        keys = {(row['category'], row['reviewed108'])}
        keys |= {(r['code'], r.get('object')) for r in row['reasons']}
        if keys - sampled:
            samples.append(dict(replay_id=row['replay_id'], category=row['category'],
                                reviewed108=row['reviewed108'], raw_path=row['raw_path'],
                                reasons=row['reasons'][:3]))
            sampled |= keys
    result = dict(passed=True, unique_replays=len(rows), input_files_checked=summary['raw_files'],
                  categories=summary['categories'], candidate_reviewed108=summary['candidate_reviewed108'],
                  evidence_coordinates_checked=proof_count, form_resolution_coordinates_checked=resolution_count,
                  normalized_hash_links_checked=linked, csv_and_lists_agree=True,
                  input_and_runtime_hashes_unchanged=True, output_hashes_match=True,
                  auditor_sha256=sha(Path(__file__)), samples=samples)
    (EVIDENCE/'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'samples'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    audit()
