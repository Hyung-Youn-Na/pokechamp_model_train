"""Independent EX081 denominators, paired analysis and Korean final artifacts."""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import math
from pathlib import Path
import random
import shutil

from ..storage import atomic, digest, read, sha
from .audit import PROFILE, ROOT, audit, _summary

BOOTSTRAP_SEED = 20261008
BOOTSTRAP_REPLICATES = 20000
BASELINE_SHA256 = 'e1d1f15a64746e0ce5888de42846cf3f16eb25638f64183cbdae1ed6a5ea71ef'
LIMITATION = ('대응 비교는 EX065의 역사적 Abyssal 실행과 새 최대 q 정책의 차이다. '
              '5개 상대 팀 군집과 작은 표본, 실행 방식·정책·Tera 차이로 학습의 단독 효과나 '
              '일반 Gen9 OU 성능 개선을 주장하지 않는다. 실패·무효·미실행은 패배로 변환하지 않는다. '
              'q는 양측 Abyssal 후속 정책 조건부 추정값이며 실제 자기 후속 정책 승률과 같다고 전제하지 않는다.')
IDENTITY_FIELDS = ('profile', 'model', 'revision', 'checkpoint_sha256', 'head_sha256',
                   'server_pid', 'server_started_at', 'source_sha256', 'physical_gpu', 'gpu_uuid')
CLOSURE_FLAGS = ('weights_unchanged', 'base_unchanged', 'checkpoint_files_unchanged', 'source_unchanged')


def _inside(root, name):
    path = (Path(root) / name).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('evidence path leaves source directory: ' + str(name))
    return path


def _baseline_capture_path(directory, name):
    """Permit only a version-local capture or its same-experiment original.

    EX065 collection-v5 deliberately links ``games`` to ``../../games``. This
    exception belongs to historical captures only; all other artifact readers
    retain the strict containment rule in _inside.
    """
    relative = Path(name)
    if (relative.is_absolute() or '..' in relative.parts or '.' in relative.parts or
            len(relative.parts) != 3 or relative.parts[0] != 'games' or
            relative.parts[-1] != 'capture.json' or relative.as_posix() != name):
        raise ValueError('invalid historical capture relative path: ' + str(name))
    directory = Path(directory).absolute()
    resolved_directory = directory.resolve()
    target = (directory / relative).resolve()
    if target.is_relative_to(resolved_directory):
        return target
    if directory.parent.name == 'versions':
        experiment = directory.parent.parent.resolve()
        if (resolved_directory.parent == experiment / 'versions' and
                target == experiment / relative):
            return target
    raise ValueError('historical capture leaves original experiment lineage: ' + name)


def _baseline_teams(configuration, manifest, row, original):
    if manifest.get('experiment') != 'EX-065' or manifest.get('actor') != 'p2' or row.get('joint_actor') != 'p2':
        raise ValueError('historical experiment or actor identity differs')
    opponent = [team for team in manifest['opponents'] if team['number'] == row['team_number'] and
                team['split'] == 'test']
    if len(opponent) != 1 or len(row['teams']) != 2:
        raise ValueError('historical team identity missing or ambiguous')
    for key, team in zip(row['teams'], (opponent[0], manifest['own']), strict=True):
        frozen = configuration['teams'][key]
        if frozen['packed'] != team['packed'] or frozen['showdown_team'] != team['text']:
            raise ValueError('historical frozen team content differs')
    if 'group_id' in original and row.get('group_id') != original['group_id']:
        raise ValueError('historical opponent group identity differs')


def verify_seal(directory, *, required=()):
    """Every immutable source file must be accounted for, including omissions."""
    directory = Path(directory).resolve()
    recorded = {}
    for line in (directory / 'checksums.sha256').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        path = _inside(directory, name)
        if name in recorded or not path.is_file() or sha(path) != checksum:
            raise ValueError('source seal mismatch: ' + name)
        recorded[name] = checksum
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*')
              if p.is_file() and p.name != 'checksums.sha256'}
    if actual != recorded.keys() or not set(required) <= recorded.keys():
        raise ValueError('source seal omits required evidence or contains extra files')
    return recorded


def _score(outcome):
    return {'player_won': 1.0, 'tied': .5, 'player_lost': 0.0}.get(outcome)


def _counts(games):
    counts = Counter(g['outcome'] for g in games if g['valid'])
    valid = sum(g['valid'] for g in games)
    attempted = sum(g['attempted'] for g in games)
    completed = sum(g['completed'] for g in games)
    invalid = sum(g['attempted'] and (not g['audit_passed'] or (g['completed'] and not g['valid'])) for g in games)
    failed = sum(g['attempted'] and not g['completed'] for g in games)
    wins, draws, losses = counts['player_won'], counts['tied'], counts['player_lost']
    return dict(planned=len(games), attempted=attempted, completed=completed,
                valid=valid, valid_completed=valid, failed=failed, invalid=invalid,
                unrun=len(games) - attempted, wins=wins, draws=draws, losses=losses,
                score=(wins + .5 * draws) / valid if valid else None,
                failure_and_invalid_can_overlap=True)


def _integrity(configuration, qualified, closures, closed, configuration_sha256):
    errors = []
    health = qualified.get('server', {})
    qualification_ok = (qualified.get('passed') is True and
                        qualified.get('configuration_sha256') == configuration_sha256 and
                        qualified.get('observations_per_process') == 320 and
                        qualified.get('candidates_per_process') == 2991 and
                        qualified.get('tolerance') == 1e-4)
    for field in ('maximum_q_difference', 'maximum_process_difference'):
        value = qualified.get(field)
        qualification_ok = qualification_ok and type(value) in (int, float) and 0 <= value <= 1e-4
    qualification_ok = qualification_ok and all(field in health for field in IDENTITY_FIELDS)
    qualification_ok = qualification_ok and health.get('physical_gpu') == 0 and health.get('profile') == PROFILE
    model = configuration.get('model', {})
    qualification_ok = qualification_ok and all(health.get(k) == model.get(k) for k in
        ('model', 'revision', 'checkpoint_sha256', 'head_sha256'))
    serving_source = configuration.get('serving_source')
    serving_hash = configuration.get('serving_source_sha256')
    qualification_ok = qualification_ok and isinstance(serving_source, dict) and bool(serving_source)
    qualification_ok = qualification_ok and digest(serving_source) == serving_hash == health.get('source_sha256')
    if not qualification_ok:
        errors.append('qualification receipt does not prove the frozen two-process validation gate')
    matching = [c for c in closures if all(field in health and c.get(field) == health[field]
                                         for field in IDENTITY_FIELDS)]
    closure_ok = (len(matching) == 1 and all(matching[0].get(k) is True for k in CLOSURE_FLAGS) and
                  matching[0].get('optimizer_updates') == 0)
    if not closure_ok:
        errors.append('exact qualified B server closure is missing, ambiguous, or fails integrity')
    expected_closure = {k:v for k,v in matching[0].items() if k != 'path'} if len(matching) == 1 else None
    clean_exit = (isinstance(closed, dict) and closed.get('returncode') == 0 and
                  closed.get('pid') == health.get('server_pid') and
                  expected_closure is not None and closed.get('closure') == expected_closure)
    if not clean_exit:
        errors.append('qualified B clean process exit is not bound to its exact closure')
    return dict(passed=bool(qualification_ok and closure_ok and clean_exit),
                qualification_passed=bool(qualification_ok), qualified_server_closure_verified=bool(closure_ok),
                qualified_server_clean_exit=bool(clean_exit), errors=errors)


def _percentile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def paired_comparison(games, baseline, team_numbers):
    """Sample the five declared teams with replacement, retaining paired games."""
    teams = list(dict.fromkeys(str(t) for t in team_numbers))
    common = []
    by_team = defaultdict(list)
    for game in games:
        reference = baseline.get(game['game_id'])
        if not game['valid'] or reference is None or not reference.get('valid'):
            continue
        row = dict(game_id=game['game_id'], team_number=str(game['team_number']),
                   new_score=_score(game['outcome']), baseline_score=reference['score'])
        row['difference'] = row['new_score'] - row['baseline_score']
        common.append(row)
        by_team[row['team_number']].append(row['difference'])
    estimate = sum(r['difference'] for r in common) / len(common) if common else None
    interval = None
    reason = None
    if len(teams) != 5:
        reason = '동결 상대 팀 군집이 5개가 아니므로 사전 지정 bootstrap을 계산하지 않음'
    elif set(by_team) != set(teams):
        reason = '5개 군집 모두에 공통 유효 대진이 있지 않아 5군집 bootstrap을 계산하지 않음'
    else:
        rng = random.Random(BOOTSTRAP_SEED)
        draws = []
        for _ in range(BOOTSTRAP_REPLICATES):
            chosen = [rng.choice(teams) for _ in teams]
            values = [v for team in chosen for v in by_team[team]]
            draws.append(sum(values) / len(values))
        draws.sort()
        interval = [_percentile(draws, .025), _percentile(draws, .975)]
    return dict(common_valid=len(common), missing_pairs=len(games) - len(common),
                new_score=sum(r['new_score'] for r in common) / len(common) if common else None,
                baseline_score=sum(r['baseline_score'] for r in common) / len(common) if common else None,
                difference=estimate, interval_95=interval,
                bootstrap=dict(unit='opponent_team', declared_clusters=len(teams),
                               observed_clusters=len(by_team), seed=BOOTSTRAP_SEED,
                               replicates=BOOTSTRAP_REPLICATES if interval else 0,
                               method='paired percentile; sample teams then retain all common valid seeds'),
                unavailable_reason=reason, pairs=common, limitation=LIMITATION)


def baseline_outcomes(configuration, *, frozen_configuration):
    """Read only original terminal captures after a concrete config has frozen.

    No inputs.jsonl, targets.jsonl or private root snapshots are read here. The
    capture supplies the original terminal protocol and its schedule provenance.
    """
    frozen_configuration = Path(frozen_configuration)
    if not frozen_configuration.is_file() or read(frozen_configuration) != configuration:
        raise ValueError('baseline analysis requires the exact frozen configuration')
    given = configuration.get('baseline_manifest')
    if not given:
        return {}, dict(available=False, reason='동결 설정에 역사 기준선 원본 경로 없음')
    manifest_path = Path(given)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    checksum = sha(manifest_path)
    expected = configuration.get('baseline_manifest_sha256', BASELINE_SHA256)
    if checksum != expected:
        raise ValueError('historical baseline manifest checksum mismatch')
    manifest = read(manifest_path)
    declared = {g['game_id']: g for g in manifest['games'] if g['split'] == 'test'}
    directory = manifest_path.parent
    sealed = {}
    for line in (directory / 'checksums.sha256').read_text().splitlines():
        value, name = line.split('  ', 1)
        if name in sealed:
            raise ValueError('duplicate historical seal path')
        sealed[name] = value
    if sealed.get('manifest.json') != checksum:
        raise ValueError('historical manifest missing from source seal')
    outcomes, files, errors, resolved_paths = {}, {'manifest.json': checksum}, [], {}
    namespace = manifest.get('namespace', 'EX065')
    for row in configuration['schedule']:
        game_id = row['game_id']
        name = f'games/{game_id}/capture.json'
        try:
            if game_id not in declared:
                raise ValueError('game outside historical test schedule')
            original = declared[game_id]
            _baseline_teams(configuration, manifest, row, original)
            if row.get('team_number') != original['team_number'] or row.get('seed_index') != original['seed_index']:
                raise ValueError('historical team or seed pairing differs')
            seed = row.get('battle_seed')
            simulator_seed = [int(v) for v in seed.split(',')] if isinstance(seed, str) else seed
            if simulator_seed != original['simulator_seed']:
                raise ValueError('historical simulator seed pairing differs')
            if row.get('actor_seeds') != [original['actor_seeds'][side] for side in ('p1', 'p2')]:
                raise ValueError('historical actor seed pairing differs')
            path = _baseline_capture_path(directory, name)
            if not path.is_file() or sha(path) != sealed.get(name):
                raise ValueError('historical original terminal capture seal mismatch')
            saved = read(path)
            if saved.get('passed') is not True or saved.get('game') != original:
                raise ValueError('historical original game provenance mismatch')
            # Restrict analysis to the captured original terminal outcome/log.
            raw_log = saved['public_log']
            lines = raw_log.splitlines() if isinstance(raw_log, str) else raw_log
            winners = [line.split('|')[2] for line in lines if line.startswith('|win|')]
            ties = [line for line in lines if line in ('|tie|', '|tie')]
            winner = saved.get('winner')
            if len(ties) == 1 and not winners and winner == '':
                score = .5
            elif len(winners) == 1 and not ties and winner == winners[0] and winner in (namespace+'p1', namespace+'p2'):
                score = float(winner == namespace+'p2')
            else:
                raise ValueError('historical winner differs from terminal protocol')
            outcomes[game_id] = dict(valid=True, score=score, team_number=original['team_number'])
            files[name] = sealed[name]
            resolved_paths[name] = str(path)
        except (KeyError, TypeError, ValueError, OSError) as error:
            errors.append(dict(game_id=game_id, error=str(error)))
    return outcomes, dict(available=True, directory=str(directory), files=files,
                         configuration_sha256=sha(frozen_configuration), errors=errors,
                         capture_path_policy='version-local-or-same-original-experiment-games',
                         resolved_capture_paths=resolved_paths,
                         version_seal_sha256=sha(directory / 'checksums.sha256'),
                         input_or_target_reads=0, private_root_reads=0)


def _markdown(metrics):
    counts = metrics['denominators']
    gate = '대전·감사 기준 충족' if metrics['battle_goal_met'] else '실험 미완료'
    score = '미평가' if counts['score'] is None else f"{counts['score']:.4f}"
    lines = ['# EX-081 공동 q 모델 실제 배틀 평가', '', f'판정: **{gate}**. '
             '원 EX066의 재로딩 실패·Blocked 판정과 가중치는 보존한다.', '',
             '| 예정 | 시도 | 정상 완료 | 유효 완료 | 실패 | 무효 | 미실행 |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    lines.append('| ' + ' | '.join(str(counts[k]) for k in
                 ('planned', 'attempted', 'completed', 'valid', 'failed', 'invalid', 'unrun')) + ' |')
    lines += ['', f"유효 p2 결과: {counts['wins']}승·{counts['draws']}무·{counts['losses']}패. "
              f'보정 점수 `(승+0.5×무)/유효완료`: {score}.', '',
              '실패는 시도했으나 정상 종료하지 못한 경기이며 무효는 증거 감사에 실패한 경기다. '
              '두 수는 겹칠 수 있다. 무효·실패·미실행을 패배로 세지 않는다.', '',
              '| 상대 팀 | 유효/예정 | 승·무·패 | 보정 점수 |', '|---|---:|---|---:|']
    for team, stats in metrics['teams'].items():
        value = '미평가' if stats['score'] is None else f"{stats['score']:.4f}"
        lines.append(f"| {team} | {stats['valid']}/{stats['planned']} | "
                     f"{stats['wins']}·{stats['draws']}·{stats['losses']} | {value} |")
    comparison = metrics['comparison']
    lines += ['', f"역사 기준선 공통 유효 대진: {comparison['common_valid']}개. "
              f"대응 보정 점수 차이: {comparison['difference'] if comparison['difference'] is not None else '미평가'}."]
    if comparison['interval_95']:
        lines.append(f"5팀 cluster bootstrap 20,000회(seed={BOOTSTRAP_SEED}) percentile 95% 구간: "
                     f"{comparison['interval_95']}.")
    else:
        lines.append(comparison['unavailable_reason'] or 'bootstrap은 계산하지 않았다.')
    lines += ['', LIMITATION, '',
              f"선택 Tera {metrics['tera']['selections']}회 · 실제 p2 Tera {metrics['tera']['actual_p2_uses']}회 · "
              f"후보에 Tera가 있던 결정 {metrics['tera']['eligible_decisions']}개.",
              f"배틀 모델 호출 {metrics['decisions']['http_requests']}회 · 실제 전송 {metrics['decisions']['wires']}회 · "
              f"fallback {metrics['decisions']['fallback_count']}회.",
              f"배틀 응답 대기 합계 {metrics['latency']['client_seconds']['total']:.3f}초 · "
              f"배틀 서버 추론 GPU 시간 합계 {metrics['latency']['gpu_seconds']['total']:.3f}초. "
              '재현 진단·qualification의 GPU 비용은 별도 원 receipt에 보존하며 배틀 비용과 혼합하지 않는다.', '',
              '입력은 공식 protocol에서 전수 재생하고 모든 후보·계산 증거·원 HTTP·prompt/token/readout 해시·'
              '최댓값과 동률 순서·rqid·실제 전송을 대조한다. q 자체를 CPU에서 재계산한 것은 아니다. '
              '설명 평가는 기본 제외다.', '',
              f"재로딩 qualification: {'통과' if metrics['gates']['qualification_passed'] else '미통과/미완료'}. "
              f"전수 경기 감사: {'통과' if metrics['gates']['all_games_audited'] else '미완료/실패'}.",
              '원자료 봉인·이동 후 오프라인 뷰어·소유 자원 정리는 별도 완료 receipt로 확인해야 한다.']
    if counts['attempted'] and metrics['technical_integrity_errors']:
        raw = metrics['raw_terminal_wdl']
        lines += ['', '모델/소스 무결성 입증 실패로 영향 경기의 효능 집계를 무효 처리했다. '
                  f"보존된 정상 종료 원승패는 {raw['wins']}승·{raw['draws']}무·{raw['losses']}패이며 유효 성적으로 주장하지 않는다.",
                  '무결성 사유: `' + '; '.join(metrics['technical_integrity_errors']) + '`.']
    if metrics['stopped'] or metrics['error']:
        lines += ['', '중단/미완료 사유: `' + str(metrics['error'] or metrics['status']) + '`.']
    if not counts['attempted']:
        lines += ['', '실제 배틀은 시작하지 않았다. 승률·배틀 지연·Tera 사용은 평가할 자료가 없다. '
                  '빈 합계 0은 실행 성능 측정값을 뜻하지 않는다.']
    lines += ['', '증거: [기계 판독 지표](metrics.json) · [독립 감사](audit.json) · [출처 receipt](receipt.json).', '']
    return '\n'.join(lines)


def finalize(directory, *, audit_function=None):
    """Finalize collected evidence without collecting, changing or sealing it.

    Caller stops its workers first, invokes this native CPU function, exports and
    tests the viewer, then seals the full source. Existing finalization is kept;
    changed evidence requires a separate version rather than silent overwrite.
    """
    directory = Path(directory).resolve()
    final = directory / 'final'
    existing = final / 'receipt.json'
    if existing.exists():
        receipt = read(existing)
        for name, checksum in receipt['source_files'].items():
            if sha(_inside(directory, name)) != checksum:
                raise ValueError('finalization source changed; preserve and version the prior report: ' + name)
        for name, checksum in receipt['output_files'].items():
            if sha(_inside(final, name)) != checksum:
                raise ValueError('finalization output changed: ' + name)
        return read(final / 'metrics.json')
    config_path = directory / 'configuration.json'
    configuration = read(config_path)
    if configuration.get('profile') != PROFILE or configuration.get('experiment_id') != 'EX-081':
        raise ValueError('not the frozen EX081 configuration')
    schedule = configuration['schedule']
    if len({row['game_id'] for row in schedule}) != len(schedule):
        raise ValueError('duplicate frozen game ID')
    audit_function = audit_function or audit
    root_result = read(directory / 'result.json') if (directory / 'result.json').exists() else {}
    status = read(directory / 'status.json') if (directory / 'status.json').exists() else {}
    qualification_path = directory / 'qualification/passed.json'
    qualified = read(qualification_path) if qualification_path.exists() else {}
    source_files = {'configuration.json': sha(config_path)}
    for name in ('result.json', 'status.json', 'clock.json', 'qualification/passed.json', 'model-closure.json'):
        if (directory / name).is_file():
            source_files[name] = sha(directory / name)
    closures = []
    for path in sorted((directory / 'server').glob('*/closure.json')):
        closures.append(dict(path=str(path.relative_to(directory)), **read(path)))
        source_files[str(path.relative_to(directory))] = sha(path)
    closed = root_result.get('model_closure')
    closure_disagreement = False
    if (directory / 'model-closure.json').exists():
        separate_closed = read(directory / 'model-closure.json')
        closure_disagreement = closed is not None and closed != separate_closed
        closed = separate_closed
    integrity = _integrity(configuration, qualified, closures, closed, sha(config_path))
    if closure_disagreement:
        integrity['passed'] = False
        integrity['errors'].append('root model closure receipts disagree')
    progress = []
    for path in sorted((directory / 'server').glob('*/progress.json')):
        progress.append(dict(path=str(path.relative_to(directory)), **read(path)))
        source_files[str(path.relative_to(directory))] = sha(path)
    games, audits, audit_errors = [], {}, []
    seen_live = set()
    for slot, row in enumerate(schedule, 1):
        game_id = row['game_id']
        folder = _inside(directory, row.get('directory', f'games/{slot:03}-{game_id}'))
        live = folder / 'live'
        game = dict(slot=slot, game_id=game_id, team_number=row['team_number'],
                    seed_index=row.get('seed_index'), attempted=folder.exists(), completed=False,
                    audit_passed=False, valid=False, outcome=None, turns=None,
                    live=str(live.relative_to(directory)) if live.is_dir() else None, error=None)
        if live.is_dir():
            seen_live.add(live.resolve())
            try:
                sealed = verify_seal(live, required=('manifest.json', 'events.jsonl', 'result.json'))
                for name, checksum in sealed.items():
                    source_files[str((live / name).relative_to(directory))] = checksum
                source_files[str((live / 'checksums.sha256').relative_to(directory))] = sha(live / 'checksums.sha256')
                manifest, result = read(live / 'manifest.json'), read(live / 'result.json')
                if manifest.get('game_id') != game_id or manifest.get('global_slot') != slot:
                    raise ValueError('live game identity differs from frozen global schedule')
                if manifest.get('configuration_sha256') != sha(config_path):
                    raise ValueError('live game configuration hash mismatch')
                local_row = manifest['schedule'][0]
                if any(local_row.get(k) != value for k, value in row.items() if k != 'slot'):
                    raise ValueError('live schedule differs from frozen global row')
                server_matches = all(field in qualified.get('server', {}) and
                    manifest.get('server', {}).get(field) == qualified['server'][field] for field in IDENTITY_FIELDS)
                report = audit_function(live, result)
                audits[game_id] = report
                outcomes = result.get('outcomes', [])
                if len(outcomes) != 1:
                    raise ValueError('per-game bundle needs exactly one outcome')
                outcome = outcomes[0]
                complete = outcome.get('completed') is True
                usable = _score(outcome.get('outcome')) is not None
                usable = usable and not (result.get('error') or result.get('cleanup_errors') or
                                         result.get('postprocessing_error'))
                usable = usable and result.get('valid', True) and outcome.get('valid', True)
                game.update(completed=complete, audit_passed=report.get('passed') is True,
                            outcome=outcome.get('outcome'), turns=outcome.get('turns'),
                            valid=complete and usable and report.get('passed') is True,
                            error=result.get('error'))
                game['qualified_server_matches'] = server_matches
                if not server_matches:
                    game.update(valid=False, technical_invalid=['live model differs from qualified B server'])
                if not report.get('passed'):
                    game['error'] = report.get('errors')
            except (KeyError, ValueError, TypeError, OSError) as error:
                game['error'] = str(error)
                audit_errors.append(dict(game_id=game_id, error=str(error)))
        elif game['attempted']:
            game['error'] = '경기 admission 후 완전한 live 증거 묶음 없음'
        games.append(game)
    raw_terminal = Counter(g['outcome'] for g in games if g['completed'])
    if not integrity['passed']:
        for game in games:
            if game['attempted']:
                game['valid'] = False
                game.setdefault('technical_invalid', []).extend(integrity['errors'])
    unexpected = {p.resolve() for p in (directory / 'games').glob('*/live')} - seen_live
    if unexpected:
        audit_errors.append(dict(error='동결 일정 밖 live 경기', paths=sorted(map(str, unexpected))))
    baseline, baseline_provenance = baseline_outcomes(configuration, frozen_configuration=config_path)
    all_details = [d for report in audits.values() for d in report.get('decisions', [])]
    latency = {key: _summary([d[field] for d in all_details
                            if type(d.get(field)) in (int, float) and math.isfinite(d[field])])
               for key, field in [('client_seconds', 'elapsed_seconds'), ('server_seconds', 'server_seconds'),
                                  ('gpu_seconds', 'gpu_seconds')]}
    team_numbers = list(dict.fromkeys(str(row['team_number']) for row in schedule))
    audited = all(g['audit_passed'] for g in games if g['attempted']) and not audit_errors
    counts = _counts(games)
    total_selections = sum(a.get('selections', 0) for a in audits.values())
    tera = dict(selections=sum(a.get('tera', {}).get('selections', 0) for a in audits.values()),
                eligible_decisions=sum(a.get('tera', {}).get('eligible_decisions', 0) for a in audits.values()),
                actual_p2_uses=sum(e.get('joint_q', False) for a in audits.values()
                                   for e in a.get('tera', {}).get('actual_uses', [])),
                actual_p1_uses=sum(not e.get('joint_q', False) for a in audits.values()
                                   for e in a.get('tera', {}).get('actual_uses', [])),
                post_tera_decisions=sum(a.get('tera', {}).get('post_tera_decisions', 0) for a in audits.values()))
    tera.update(selection_rate=tera['selections'] / total_selections if total_selections else None,
                eligible_selection_rate=tera['selections'] / tera['eligible_decisions'] if tera['eligible_decisions'] else None)
    clock = read(directory / 'clock.json') if (directory / 'clock.json').exists() else {}
    metrics = dict(experiment_id='EX-081', profile=PROFILE, source=str(directory),
                   created_at=datetime.now(timezone.utc).isoformat(),
                   configuration_sha256=sha(config_path), denominators=counts,
                   raw_terminal_wdl=dict(wins=raw_terminal['player_won'], draws=raw_terminal['tied'],
                                         losses=raw_terminal['player_lost'], eligible_for_efficacy=False),
                   teams={t: _counts([g for g in games if str(g['team_number']) == t]) for t in team_numbers},
                   games=games, comparison=paired_comparison(games, baseline, team_numbers),
                   baseline_provenance=baseline_provenance, tera=tera, latency=latency,
                   decisions={k: sum(a.get(k, 0) for a in audits.values()) for k in
                              ('inputs', 'http_requests', 'responses', 'selections', 'wires', 'fallback_count')},
                   clock=clock, gpu=dict(physical_gpu=0, battle_forward_seconds=latency['gpu_seconds']['total'],
                        all_closed_server_forward_seconds=sum(c.get('gpu_seconds', 0) for c in closures),
                        closed_server_requests=sum(c.get('requests', 0) for c in closures),
                        maximum_allocated_bytes=max((p.get('max_allocated_bytes', 0) for p in progress), default=None),
                        maximum_reserved_bytes=max((p.get('max_reserved_bytes', 0) for p in progress), default=None),
                        diagnostic_qualification_cost='전체 종료 서버 합계에 포함; 미종료/receipt 없는 비용은 progress 원자료 참조',
                        closures=closures, progress=progress),
                   gates=dict(qualification_passed=integrity['qualification_passed'],
                              all_games_audited=bool(counts['attempted']) and audited,
                              checkpoint_closures_unchanged=integrity['qualified_server_closure_verified'],
                              qualified_server_clean_exit=integrity['qualified_server_clean_exit'],
                              root_control_complete=root_result.get('stopped') is False and not root_result.get('error')),
                   technical_integrity_errors=integrity['errors'],
                   battle_goal_met=len(schedule) == 20 and counts['valid'] == 20 and audited and
                                   integrity['passed'] and root_result.get('stopped') is False and not root_result.get('error'),
                   stopped=root_result.get('stopped', bool(status.get('error'))),
                   error=root_result.get('error') or status.get('error'), status=status,
                   limitations=LIMITATION)
    final.mkdir(parents=True, exist_ok=True)
    atomic(final / 'metrics.json', metrics, immutable=True)
    atomic(final / 'audit.json', dict(passed=audited and integrity['passed'], raw_decision_audits_passed=audited,
                                    integrity=integrity, games=audits, errors=audit_errors,
                                    completed_matches=counts['completed'], valid_matches=counts['valid']), immutable=True)
    report_path = final / 'report.md'
    with report_path.open('x') as stream:
        stream.write(_markdown(metrics))
    # Receipt references prior outputs; neither it nor a later global seal hashes
    # itself. The caller can seal the complete directory after viewer receipts.
    atomic(existing, dict(experiment_id='EX-081', configuration_sha256=sha(config_path),
                          source_files=source_files, builder_sha256=sha(Path(__file__)),
                          audit_builder_sha256=sha(Path(__file__).with_name('audit.py')),
                          output_files={name: sha(final / name) for name in ('metrics.json', 'audit.json', 'report.md')},
                          source_seal_pending=True, viewer_pending=True, resource_cleanup_pending=True),
           immutable=True)
    return metrics


def verify_final(directory, final_directory=None, *, verify_sources=True):
    """Verify one original or corrective finalization without executing its audit."""
    directory = Path(directory).resolve()
    final = Path(final_directory).resolve() if final_directory else directory / 'final'
    if not final.is_relative_to(directory) or final == directory:
        raise ValueError('final evidence directory must remain inside the experiment')
    receipt = read(final / 'receipt.json')
    if (receipt.get('experiment_id') != 'EX-081' or
            receipt.get('configuration_sha256') != sha(directory / 'configuration.json')):
        raise ValueError('final receipt configuration identity mismatch')
    if not {'metrics.json', 'audit.json', 'report.md'} <= receipt.get('output_files', {}).keys():
        raise ValueError('final receipt omits mandatory outputs')
    for name, expected in receipt['output_files'].items():
        if sha(_inside(final, name)) != expected:
            raise ValueError('final report checksum mismatch: ' + name)
    if verify_sources:
        for name, expected in receipt['source_files'].items():
            if sha(_inside(directory, name)) != expected:
                raise ValueError('finalization source checksum mismatch: ' + name)
    metrics = read(final / 'metrics.json')
    if metrics.get('configuration_sha256') != receipt['configuration_sha256']:
        raise ValueError('final metrics configuration identity mismatch')
    return final, receipt, metrics


def _verify_baseline_sources(configuration, provenance):
    manifest_path = Path(configuration['baseline_manifest'])
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    directory = manifest_path.parent
    if (str(directory) != provenance.get('directory') or
            sha(manifest_path) != provenance['files'].get('manifest.json') or
            sha(manifest_path) != configuration.get('baseline_manifest_sha256', BASELINE_SHA256) or
            sha(directory / 'checksums.sha256') != provenance.get('version_seal_sha256')):
        raise ValueError('corrected baseline source identity changed')
    sealed = {}
    for line in (directory / 'checksums.sha256').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if name in sealed:
            raise ValueError('duplicate historical seal path')
        sealed[name] = checksum
    for name, expected in provenance['files'].items():
        path = manifest_path if name == 'manifest.json' else _baseline_capture_path(directory, name)
        if sha(path) != expected or sealed.get(name) != expected:
            raise ValueError('corrected historical source seal mismatch: ' + name)
    return True


def correct_baseline(directory, destination=None):
    """Correct only the saved EX081 historical-path analysis under RD11.1/C018.

    The first report, all raw evidence and the original source snapshot remain
    unchanged. The completed independent per-decision audit is hash-verified and
    reused byte-for-byte; this function performs no inference or battle replay.
    """
    directory = Path(directory).resolve()
    destination = (Path(destination).resolve() if destination else
                   directory / 'corrections/baseline-v2/final')
    if (not destination.is_relative_to(directory / 'corrections') or
            destination.name != 'final' or destination == directory / 'final'):
        raise ValueError('baseline correction needs a separate corrections/<version>/final directory')
    if destination.exists() or (destination.parent / 'source').exists():
        raise FileExistsError('preserve existing correction output: ' + str(destination))
    original, old_receipt, old_metrics = verify_final(directory)
    configuration = read(directory / 'configuration.json')
    audit_data = read(original / 'audit.json')
    game_ids = [row['game_id'] for row in configuration['schedule']]
    if (len(game_ids) != 20 or len(set(game_ids)) != 20 or
            [g['game_id'] for g in old_metrics['games']] != game_ids or
            old_metrics['denominators']['valid'] != 20 or not old_metrics.get('battle_goal_met') or
            audit_data.get('passed') is not True or audit_data.get('valid_matches') != 20 or
            set(audit_data.get('games', {})) != set(game_ids)):
        raise ValueError('baseline-only correction requires the already validated 20-game cohort')
    old_errors = old_metrics.get('baseline_provenance', {}).get('errors', [])
    if (old_metrics['comparison'].get('common_valid') != 0 or len(old_errors) != 20 or
            {e.get('game_id') for e in old_errors} != set(game_ids) or
            any(not e.get('error', '').startswith('evidence path leaves source directory: games/')
                for e in old_errors)):
        raise ValueError('original report does not have the isolated historical symlink-path defect')
    live_seals = {}
    for game in old_metrics['games']:
        if not (game['completed'] and game['valid'] and game['audit_passed'] and
                audit_data['games'][game['game_id']].get('passed') is True):
            raise ValueError('saved game audit is not valid: ' + game['game_id'])
        live = _inside(directory, game['live'])
        files = verify_seal(live, required=('manifest.json', 'events.jsonl', 'result.json'))
        for name, checksum in files.items():
            relative = str((live / name).relative_to(directory))
            if old_receipt['source_files'].get(relative) != checksum:
                raise ValueError('saved game seal differs from original final receipt: ' + relative)
        seal_name = str((live / 'checksums.sha256').relative_to(directory))
        if sha(live / 'checksums.sha256') != old_receipt['source_files'].get(seal_name):
            raise ValueError('saved game seal changed: ' + seal_name)
        live_seals[game['game_id']] = dict(path=seal_name, sha256=sha(live / 'checksums.sha256'))
    delta_names = ('integration/pokechamp/joint_q/battle_eval/outputs.py',
                   'integration/pokechamp/joint_q/battle_eval/viewer.py',
                   'integration/pokechamp/tests/test_joint_q_battle_outputs.py')
    source_delta = {}
    for name in delta_names:
        frozen = _inside(directory / 'source', name)
        expected = configuration['source'][name]
        if sha(frozen) != expected:
            raise ValueError('original frozen analysis source changed: ' + name)
        source_delta[name] = dict(original_sha256=expected, corrected_sha256=sha(ROOT / name))
    if source_delta[delta_names[0]]['original_sha256'] != old_receipt['builder_sha256']:
        raise ValueError('original report builder differs from frozen source')
    audit_name = 'integration/pokechamp/joint_q/battle_eval/audit.py'
    if (sha(_inside(directory / 'source', audit_name)) != configuration['source'][audit_name] or
            old_receipt['audit_builder_sha256'] != configuration['source'][audit_name]):
        raise ValueError('original audit builder differs from its frozen source')
    baseline, provenance = baseline_outcomes(configuration, frozen_configuration=directory / 'configuration.json')
    if (provenance.get('errors') or set(baseline) != set(game_ids) or
            not all(value.get('valid') for value in baseline.values())):
        raise ValueError('corrected baseline must contain all 20 valid pairs without errors: ' + str(provenance.get('errors')))
    team_numbers = list(dict.fromkeys(row['team_number'] for row in configuration['schedule']))
    comparison = paired_comparison(old_metrics['games'], baseline, team_numbers)
    if (comparison['common_valid'] != 20 or comparison['missing_pairs'] != 0 or
            comparison['bootstrap']['replicates'] != BOOTSTRAP_REPLICATES or
            comparison['bootstrap']['seed'] != BOOTSTRAP_SEED or
            comparison['bootstrap']['observed_clusters'] != 5 or comparison['interval_95'] is None):
        raise ValueError('corrected historical comparison does not meet the frozen analysis protocol')
    original_hashes = {name: sha(original / name) for name in ('metrics.json', 'report.md', 'audit.json', 'receipt.json')}
    corrected = copy.deepcopy(old_metrics)
    corrected['comparison'] = comparison
    corrected['baseline_provenance'] = dict(provenance, correction=dict(
        profile='baseline-lineage-v2', original_final=str(original), original_hashes=original_hashes,
        changed_metric_fields=['comparison', 'baseline_provenance']))
    unchanged_names = [name for name in old_metrics if name not in ('comparison', 'baseline_provenance')]
    if any(corrected[name] != old_metrics[name] for name in unchanged_names):
        raise ValueError('baseline correction changed an unrelated metric')
    _verify_baseline_sources(configuration, provenance)
    # All required checks finish before creating a separately versioned output.
    destination.mkdir(parents=True, exist_ok=False)
    corrected_source = destination.parent / 'source'
    for name in delta_names:
        target = corrected_source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write((ROOT / name).read_bytes())
        if sha(target) != source_delta[name]['corrected_sha256']:
            raise ValueError('correction source changed while copying: ' + name)
    atomic(destination / 'metrics.json', corrected, immutable=True)
    shutil.copyfile(original / 'audit.json', destination / 'audit.json')
    for name in ('metrics.json', 'report.md', 'receipt.json'):
        shutil.copyfile(original / name, destination / ('original-' + name))
    explanation = ('\n이 보고서는 RD §11.1/C-018에 따른 저장 자료 정정이다. EX065 collection-v5의 '
        '`games → ../../games`가 같은 원실험의 보존 자료를 가리키지만 최초 평가기가 버전 폴더 밖이라는 '
        '이유로 거부했다. 버전 봉인 해시와 동일 원실험 계보·팀·seed·종료 결과를 검증하여 기준선 20쌍만 '
        '재분석했다. 대전·모델 응답·전수 입력 감사·분모·승패·가중치·허용오차·bootstrap 규칙은 바꾸지 않았다. '
        '추가 배틀·모델 호출·입력 재생은 0회다. [최초 보고](original-report.md)와 '
        '[최초 지표](original-metrics.json)를 그대로 보존한다.\n')
    with (destination / 'report.md').open('x') as stream:
        stream.write(_markdown(corrected) + explanation)
    original_preserved = {name: sha(original / name) for name in original_hashes} == original_hashes
    if not original_preserved:
        raise ValueError('original finalization changed during correction')
    source_files = dict(old_receipt['source_files'])
    for name, checksum in original_hashes.items():
        source_files[str((original / name).relative_to(directory))] = checksum
    for name, values in source_delta.items():
        source_files[str((directory / 'source' / name).relative_to(directory))] = values['original_sha256']
        source_files[str((corrected_source / name).relative_to(directory))] = values['corrected_sha256']
    source_files[str((directory / 'source' / audit_name).relative_to(directory))] = configuration['source'][audit_name]
    receipt = dict(experiment_id='EX-081', correction_profile='baseline-lineage-v2', passed=True,
        created_at=datetime.now(timezone.utc).isoformat(), configuration_sha256=sha(directory / 'configuration.json'),
        original_final=str(original), original_hashes=original_hashes, original_files_preserved=original_preserved,
        source_files=source_files, builder_sha256=sha(Path(__file__)), source_delta=source_delta,
        audit_builder_sha256=old_receipt['audit_builder_sha256'],
        reused_audit=dict(path='final/audit.json', sha256=original_hashes['audit.json'],
                          games=20, decisions=old_metrics['decisions']['inputs'], input_replays=0),
        saved_live_seals=live_seals, changed_metric_fields=['comparison', 'baseline_provenance'],
        unchanged_metrics_sha256=digest({name:old_metrics[name] for name in unchanged_names}),
        defect_scope='역사 기준선 capture 경로 해석만 정정; 원 모델/배틀/전수 감사/판정 보존',
        recomputation=dict(model_calls=0, battles=0, input_replays=0, historical_games=20,
                           bootstrap_replicates=BOOTSTRAP_REPLICATES, bootstrap_seed=BOOTSTRAP_SEED),
        baseline_provenance=provenance,
        output_files={name: sha(destination / name) for name in
                      ('metrics.json', 'audit.json', 'report.md', 'original-metrics.json', 'original-report.md', 'original-receipt.json')},
        source_seal_pending=True, viewer_pending=True, resource_cleanup_pending=False)
    atomic(destination / 'receipt.json', receipt, immutable=True)
    return corrected
