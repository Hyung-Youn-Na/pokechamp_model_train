"""EX-174 collection (D-212): Blim's teams (laya-play `teams_blim.json`) for both sides, sealed before any game.

Same checks as EX-145's collection (pinned local Showdown validator, one team per six-species signature, EX-120
archetype classifier). The schedule differs from the EX-120 ring: the first 64 teams in digest order are paired into
32 disjoint matchups (0-1, 2-3, ...), each played with 2 seeds x team swap = 128 slots, so every team is played
exactly twice by each bot side. Seeds and order come from digests of `SEED`.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, digest, read, seal, sha, verify_seal

SEED = 20261074
SOURCE = c.ROOT / 'exports/laya-play/app/laya_play/teams_blim.json'
COLLECTION = c.SHARED / 'runs/model-training/EX-174/collection'
TEAMS = 64
README = """# EX-174 collection — Blim 팀 64개와 128슬롯 일정

결과를 보기 전에 생성하고 봉인했다. 규칙 원문은
`/workspace/project_context/research/policy-learning/experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md`이다.

- `teams.json`: 검증을 통과한 Blim 팀(packed/text, 원본 이름·영상·sha256, 유형과 분류 특징)
- `selection.json`: 원본 해시, 중복·거부, 쓰지 않은 팀, 유형별 수
- `schedule.json`: 128슬롯(32개 대진 × 시드 2 × 팀 교환), 시드와 진행 순서
- `manifest.json`: 파일 해시. 봉인은 `checksums.sha256`
"""


def ranked(namespace, identity):
    return digest([SEED, namespace, identity])


def _seeds(identity):
    raw = bytes.fromhex(ranked('ex174_seeds', identity))
    return dict(simulator_seed=[int.from_bytes(raw[i:i + 2], 'big') for i in range(0, 8, 2)],
                opponent_seed=int.from_bytes(raw[8:12], 'big'), model_seed=int.from_bytes(raw[12:16], 'big'))


def make_schedule(teams, model='laya-v10rt', opponent='foulplay'):
    """64 teams -> 32 disjoint matchups x 2 seeds x team swap (EX-120's row layout)."""
    if len(teams) != TEAMS or len({t['signature'] for t in teams}) != TEAMS:
        raise ValueError('64 distinct team signatures required')
    pairs = []
    for m in range(TEAMS // 2):
        a, b = teams[2 * m], teams[2 * m + 1]
        matchup = 'b%02d' % (m + 1)
        for s in (1, 2):
            side = 'p1' if s == 1 else 'p2'
            other = 'p2' if side == 'p1' else 'p1'
            rows = []
            for swap, (mine, theirs) in (('a', (a, b)), ('b', (b, a))):
                rows.append(dict(slot_id='%s-s%d-%s' % (matchup, s, swap), pair_id='%s-s%d' % (matchup, s),
                                 matchup_id=matchup, seed_index=s, swap=swap, model=model,
                                 model_side=side, opponent=opponent,
                                 team_ids={side: mine['team_id'], other: theirs['team_id']},
                                 archetypes=dict(model=mine['archetype'], opponent=theirs['archetype']),
                                 teams={side: dict(packed=mine['packed'], team_id=mine['team_id']),
                                        other: dict(packed=theirs['packed'], team_id=theirs['team_id'])},
                                 **_seeds([matchup, s, swap])))
            pairs.append(rows)
    pairs.sort(key=lambda rows: ranked('ex174_order', rows[0]['pair_id']))
    schedule = [r for rows in pairs for r in rows]
    for order, row in enumerate(schedule, 1):
        row['submission_order'] = order
    return schedule


def collect(output=COLLECTION):
    from integration.laya_imitation.teams import ARCHETYPES, classify
    from integration.pokechamp.imitation.dataset import TeamValidatorClient, signature
    output = Path(output)
    if (output / 'manifest.json').exists():
        raise FileExistsError('EX-174 collection already exists: %s' % output)
    started = time.time()
    teams, duplicates, rejected, seen = [], [], [], {}
    with TeamValidatorClient() as validator:
        for source in json.loads(SOURCE.read_text()):
            checked = validator.normalize([dict(text=source['text'], sha256=digest(source['text']))])[0]
            if not checked.get('legal'):
                rejected.append(dict(team_id=source['team_id'], problems=checked.get('problems') or checked.get('error')))
                continue
            sig = signature(checked['species'])
            if sig in seen:
                duplicates.append(dict(team_id=source['team_id'], kept=seen[sig]))
                continue
            seen[sig] = source['team_id']
            kind, feats = classify(checked['sets'])
            teams.append(dict(team_id=source['team_id'], team_set='blim', name=source.get('name'),
                              author=source.get('author'), source=source.get('source'), video=source.get('video'),
                              train_games=source.get('train_games', 0), signature=sig, species=sig.split('|'),
                              archetype=kind, features=feats, packed=checked['packed'], text=checked['text']))
    teams.sort(key=lambda t: ranked('ex174_pick', t['signature']))
    if len(teams) < TEAMS:
        raise ValueError('only %d valid distinct Blim teams (< %d); rejected %r' % (len(teams), TEAMS, rejected))
    chosen, unused = teams[:TEAMS], teams[TEAMS:]
    schedule = make_schedule(chosen)
    shared = [len(set(chosen[2 * m]['species']) & set(chosen[2 * m + 1]['species'])) for m in range(TEAMS // 2)]
    selection = dict(source=dict(path=str(SOURCE), sha256=sha(SOURCE)), valid=len(teams), used=len(chosen),
                     unused=[dict(team_id=t['team_id'], name=t['name']) for t in unused],
                     duplicates=duplicates, rejected=rejected,
                     archetypes={k: sum(t['archetype'] == k for t in chosen) for k in ARCHETYPES},
                     trained_signature=sum(1 for t in chosen if t['train_games']),
                     matchup_shared_species=dict(max=max(shared), mean=round(sum(shared) / len(shared), 2)))
    atomic(output / 'teams.json', chosen, immutable=True)
    atomic(output / 'selection.json', selection, immutable=True)
    atomic(output / 'schedule.json', schedule, immutable=True)
    atomic(output / 'manifest.json', dict(experiment_id='EX-174', seed=SEED, slots=len(schedule),
                                          pairs=len({r['pair_id'] for r in schedule}),
                                          matchups=len({r['matchup_id'] for r in schedule}),
                                          teams_sha256=sha(output / 'teams.json'),
                                          schedule_sha256=sha(output / 'schedule.json'),
                                          selection_sha256=sha(output / 'selection.json'),
                                          seconds=round(time.time() - started, 1), created_at=time.time()),
           immutable=True)
    (output / 'README.md').write_text(README)
    seal(output)
    print(json.dumps({k: v for k, v in selection.items() if k not in ('duplicates', 'unused')}, ensure_ascii=False))
    return selection


def base_schedule():
    if verify_seal(COLLECTION):
        raise RuntimeError('EX-174 collection seal failed')
    rows = read(COLLECTION / 'schedule.json')
    if len(rows) != 128:
        raise RuntimeError('EX-174 schedule is not 128 slots')
    return rows


if __name__ == '__main__':
    collect()
