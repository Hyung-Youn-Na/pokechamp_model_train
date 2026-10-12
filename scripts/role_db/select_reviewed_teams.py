"""고정된 Metamon 입력에서 검토 완료 종만으로 구성된 팀 목록을 생성한다."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from expand_team_pool import ROOT, PACKAGE, EVIDENCE, parse_team


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build(output: Path, team_root: Path):
    manifest_path = EVIDENCE / 'build/input_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    source = PACKAGE / 'data/generated/gen9ou_role_db.json'
    raw = source.read_bytes()
    expected = {row['path']: row['sha256'] for row in manifest['input_files']}
    assert sha(raw) == expected[str(source)], '원본 역할 DB 변경'
    reviewed = sorted(p['id'] for p in json.loads(raw)['pokemon']
                      if p['annotation_status'] == 'reviewed')
    assert len(reviewed) == 108
    allowed = set(reviewed)
    mechanics_path = EVIDENCE / 'mechanics.json'
    mechanics_raw = mechanics_path.read_bytes()
    assert sha(mechanics_raw) == expected[str(mechanics_path)]
    dex = json.loads(mechanics_raw)
    pinned_root = Path('/tmp/metamon_cache/teams/modern_replays/gen9ou')
    rows = [r for r in manifest['team_files'] if r['corpus'] == 'modern_replays']
    assert len(rows) == 25192
    relative_paths = {Path(r['path']).relative_to(pinned_root).as_posix() for r in rows}
    actual_paths = {p.relative_to(team_root).as_posix()
                    for p in team_root.rglob('*.gen9ou_team')}
    assert relative_paths == actual_paths, '입력 파일 집합 변경'
    selected = []
    for row in rows:
        relative = Path(row['path']).relative_to(pinned_root).as_posix()
        content = (team_root / relative).read_bytes()
        assert sha(content) == row['sha256'], relative
        members = parse_team(content.decode(), dex)
        species = [m['id'] for m in members]
        if all(s in allowed for s in species):
            selected.append(dict(path=relative, sha256=sha(content), species=species))
    combinations = {tuple(sorted(r['species'])) for r in selected}
    assert len(selected) == 16034 and len(combinations) == 5197
    result = dict(
        schema_version='reviewed-species-team-list-v1', format='gen9ou',
        corpus='modern_replays', default_team_root=str(pinned_root),
        selection='all_six_species_in_reviewed_ids',
        role_source=dict(path=str(source.relative_to(ROOT)), sha256=sha(raw)),
        input_manifest=dict(path=str(manifest_path.relative_to(ROOT)),
                            sha256=sha(manifest_path.read_bytes())),
        reviewed_species_ids=reviewed,
        counts=dict(input_files=len(rows), selected_files=len(selected),
                    excluded_files=len(rows)-len(selected),
                    unique_species_compositions=len(combinations)),
        teams=selected,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / 'gen9ou_reviewed108_teams.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (output / 'gen9ou_reviewed108_teams.txt').write_text(
        ''.join(r['path'] + '\n' for r in selected))
    print(json.dumps(result['counts']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'export/teams')
    parser.add_argument('--team-root', type=Path,
                        default=Path('/tmp/metamon_cache/teams/modern_replays/gen9ou'))
    args = parser.parse_args()
    build(args.output_dir, args.team_root)
