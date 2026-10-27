"""EX-120 team selection and schedule: unseen legal reviewed108 teams, rule-based archetypes, ring matchups.

Pure functions (classify, select, make_schedule) are separated from file access (collect) so the frozen
rules are unit-testable. Rules and constants mirror the EX-120 protocol text; change both together.
"""
from __future__ import annotations
from pathlib import Path
import time

from integration.pokechamp.imitation.dataset import TeamValidatorClient, signature, to_id

from . import config as c
from .storage import atomic, digest, jsonl, read, seal, sha

SEED = 20261023
ARCHETYPES = ('weather', 'offense', 'defense', 'balance')
PER_ARCHETYPE = 8
TEAMS = 32
MAX_SHARED = 3
MAX_SPECIES = 8

WEATHER_ABILITIES = {'drought', 'drizzle', 'sandstream', 'snowwarning', 'orichalcumpulse', 'hadronengine',
                     'electricsurge', 'psychicsurge', 'grassysurge', 'mistysurge'}
WEATHER_MOVES = {'sunnyday', 'raindance', 'sandstorm', 'snowscape', 'chillyreception', 'electricterrain',
                 'psychicterrain', 'grassyterrain', 'mistyterrain'}
SETUP = {'swordsdance', 'nastyplot', 'dragondance', 'calmmind', 'bulkup', 'quiverdance', 'shellsmash', 'agility',
         'rockpolish', 'bellydrum', 'tidyup', 'victorydance', 'coil', 'shiftgear', 'curse', 'irondefense',
         'filletaway', 'clangoroussoul', 'noretreat', 'workup', 'growth', 'geomancy', 'tailglow', 'cosmicpower',
         'takeheart'}
RECOVERY = {'recover', 'roost', 'slackoff', 'softboiled', 'moonlight', 'morningsun', 'synthesis', 'wish',
            'strengthsap', 'shoreup', 'milkdrink', 'rest', 'lunarblessing', 'junglehealing', 'healorder'}
OFFENSE_ITEMS = {'choiceband', 'choicespecs', 'choicescarf', 'lifeorb', 'boosterenergy'}
HAZARDS = {'stealthrock', 'spikes', 'toxicspikes', 'stickyweb'}
REMOVAL = {'rapidspin', 'defog', 'mortalspin', 'tidyup', 'courtchange'}


def features(sets):
    moves = [{to_id(m) for m in s.get('moves', [])} for s in sets]
    return dict(weather_ability=sum(to_id(s.get('ability')) in WEATHER_ABILITIES for s in sets),
                weather_moves=sum(len(m & WEATHER_MOVES) for m in moves),
                setup_mons=sum(bool(m & SETUP) for m in moves),
                recovery_mons=sum(bool(m & RECOVERY) for m in moves),
                offense_item_mons=sum(to_id(s.get('item')) in OFFENSE_ITEMS for s in sets),
                hazard=any(m & HAZARDS for m in moves), removal=any(m & REMOVAL for m in moves))


def classify(sets):
    f = features(sets)
    if f['weather_ability'] or f['weather_moves'] >= 2:
        kind = 'weather'
    elif f['setup_mons'] >= 3 or (f['offense_item_mons'] >= 4 and f['recovery_mons'] <= 1):
        kind = 'offense'
    elif f['recovery_mons'] >= 4 or (f['recovery_mons'] == 3 and f['hazard'] and f['removal']):
        kind = 'defense'
    else:
        kind = 'balance'
    return kind, f


def ranked(namespace, identity):
    return digest([SEED, namespace, identity])


def _compatible(species, chosen, counts):
    return (all(len(species & set(t['species'])) <= MAX_SHARED for t in chosen)
            and all(counts.get(s, 0) < MAX_SPECIES for s in species))


def select(candidates, check):
    """Greedy, order-preserving selection.

    `candidates` are registry entries already in hash order with excluded signatures removed.
    `check(entry)` returns a normalized team dict (species, sets, packed, archetype, ...) or a rejection dict
    with a `reason`. It is called at most once per entry and only when the entry could be selected.
    """
    chosen, rejected, counts, cache = [], [], {}, {}
    quota = {k: PER_ARCHETYPE for k in ARCHETYPES}

    def take(team):
        chosen.append(team)
        for s in team['species']:
            counts[s] = counts.get(s, 0) + 1

    for phase in ('quota', 'fill'):
        for entry in candidates:
            if len(chosen) == TEAMS:
                break
            sig = entry['signature']
            if any(t['signature'] == sig for t in chosen):
                continue
            if not _compatible(set(sig.split('|')), chosen, counts):
                continue
            if entry['path'] not in cache:
                cache[entry['path']] = check(entry)
                if 'reason' in cache[entry['path']]:
                    rejected.append(cache[entry['path']])
            team = cache[entry['path']]
            if 'reason' in team:
                continue
            if phase == 'quota' and quota[team['archetype']] == 0:
                continue
            if phase == 'quota':
                quota[team['archetype']] -= 1
            take(dict(team, fill=phase == 'fill'))
    shortfall = {k: v for k, v in quota.items() if v}
    return chosen, rejected, shortfall


def _seeds(identity):
    raw = bytes.fromhex(ranked('ex120_seeds', identity))
    return dict(simulator_seed=[int.from_bytes(raw[i:i + 2], 'big') for i in range(0, 8, 2)],
                opponent_seed=int.from_bytes(raw[8:12], 'big'), model_seed=int.from_bytes(raw[12:16], 'big'))


def make_schedule(teams):
    """32 ring matchups x 2 seeds x team swap = 128 slots; the swapped pair shares matchup and seed."""
    if len(teams) != TEAMS or len({t['signature'] for t in teams}) != TEAMS:
        raise ValueError('32 distinct team signatures required')
    ring = sorted(teams, key=lambda t: ranked('ex120_ring', t['signature']))
    pairs = []
    for m in range(TEAMS):
        a, b = ring[m], ring[(m + 1) % TEAMS]
        if len(set(a['species']) & set(b['species'])) > MAX_SHARED:
            raise ValueError('ring neighbours share too many species')
        matchup = 'm%02d' % (m + 1)
        for s in (1, 2):
            side = 'p1' if s == 1 else 'p2'
            other = 'p2' if side == 'p1' else 'p1'
            rows = []
            for swap, (mine, theirs) in (('a', (a, b)), ('b', (b, a))):
                rows.append(dict(slot_id='%s-s%d-%s' % (matchup, s, swap), pair_id='%s-s%d' % (matchup, s),
                                 matchup_id=matchup, seed_index=s, swap=swap, model='laya-selected',
                                 model_side=side, opponent='abyssal',
                                 team_ids={side: mine['team_id'], other: theirs['team_id']},
                                 archetypes=dict(model=mine['archetype'], opponent=theirs['archetype']),
                                 teams={side: dict(packed=mine['packed'], team_id=mine['team_id']),
                                        other: dict(packed=theirs['packed'], team_id=theirs['team_id'])},
                                 **_seeds([matchup, s, swap])))
            pairs.append(rows)
    pairs.sort(key=lambda rows: ranked('ex120_order', rows[0]['pair_id']))
    schedule = [r for rows in pairs for r in rows]
    for order, row in enumerate(schedule, 1):
        row['submission_order'] = order
    return schedule


def excluded_signatures(validator):
    """Six-species signatures that must not be selected, by source."""
    out = {}
    out['ex071_replays'] = {s for r in jsonl(c.EX071_PREPARATION / 'replays.jsonl') for s in r['signatures']}
    out['historical_reserved'] = {r['signature'] for r in read(c.EX071_PREPARATION / 'historical-teams.json')}
    battle = set()
    for row in read(c.EX071 / 'schedule.json'):
        for team in row['teams'].values():
            battle.add(signature(team['species']))
    out['ex071_battle'] = battle
    manifest = read(c.EX089_COLLECTION / 'manifest.json')
    texts = [v['showdown_team'] if isinstance(v, dict) else v for v in manifest['teams'].values()]
    parsed = validator.normalize([dict(text=t, sha256=digest(t), parse_only=True) for t in texts])
    out['ex089'] = {signature(p['species']) for p in parsed}
    return out


def collect(output=None):
    output = Path(output or c.RUN_GENERAL / 'collection')
    if (output / 'manifest.json').exists():
        raise FileExistsError('EX-120 collection already exists: %s' % output)
    started = time.time()
    registry = read(c.TEAM_REGISTRY)
    reviewed = set(registry['reviewed_species_ids'])
    root = Path(registry['default_team_root'])
    with TeamValidatorClient() as validator:
        excluded = excluded_signatures(validator)
        blocked = set().union(*excluded.values())
        candidates, skipped = [], dict(excluded=0, malformed=0)
        for entry in registry['teams']:
            try:
                sig = signature(entry['species'])
            except ValueError:
                skipped['malformed'] += 1
                continue
            if sig in blocked:
                skipped['excluded'] += 1
                continue
            candidates.append(dict(entry, signature=sig))
        candidates.sort(key=lambda e: ranked('ex120_team', e['path']))

        def check(entry):
            path = root / entry['path']
            if sha(path) != entry['sha256']:
                raise ValueError('reviewed team changed: %s' % path)
            team = validator.normalize([dict(text=path.read_text(), sha256=entry['sha256'])])[0]
            base = dict(path=entry['path'], sha256=entry['sha256'])
            if not team.get('legal'):
                return dict(base, reason='illegal', problems=team.get('problems') or team.get('error'))
            sig = signature(team['species'])
            if set(sig.split('|')) - reviewed:
                return dict(base, reason='normalized_form_outside_reviewed108')
            if sig != entry['signature']:
                return dict(base, reason='normalization_changed_signature')
            kind, feats = classify(team['sets'])
            return dict(team_id='t' + digest(team['packed'])[:10], signature=sig, species=sig.split('|'),
                        archetype=kind, features=feats, packed=team['packed'], text=team['text'],
                        source=str(path), source_sha256=entry['sha256'])
        teams, rejected, shortfall = select(candidates, check)
    if len(teams) != TEAMS:
        raise ValueError('only %d teams satisfy the EX-120 rules' % len(teams))
    for team in teams:
        if team['signature'] in blocked:
            raise AssertionError('excluded signature selected')
    schedule = make_schedule(teams)
    overlap = {k: len(v & {t['signature'] for t in teams}) for k, v in excluded.items()}
    selection = dict(registry=str(c.TEAM_REGISTRY), registry_sha256=sha(c.TEAM_REGISTRY), registry_teams=len(registry['teams']),
                     excluded_signatures={k: len(v) for k, v in excluded.items()}, skipped=skipped,
                     candidates=len(candidates), rejected=rejected,
                     rejected_by_reason={r: sum(x['reason'] == r for x in rejected) for r in {x['reason'] for x in rejected}},
                     overlap_with_excluded=overlap, shortfall=shortfall,
                     archetypes={k: sum(t['archetype'] == k for t in teams) for k in ARCHETYPES},
                     max_species_count=max(sum(s in t['species'] for t in teams) for t in teams for s in t['species']),
                     max_shared_species=max(len(set(a['species']) & set(b['species']))
                                            for i, a in enumerate(teams) for b in teams[i + 1:]))
    if any(overlap.values()):
        raise AssertionError('selected team overlaps an excluded set')
    atomic(output / 'teams.json', teams, immutable=True)
    atomic(output / 'selection.json', selection, immutable=True)
    atomic(output / 'schedule.json', schedule, immutable=True)
    atomic(output / 'manifest.json', dict(experiment_id='EX-120', seed=SEED, rules=dict(
        per_archetype=PER_ARCHETYPE, teams=TEAMS, max_shared=MAX_SHARED, max_species=MAX_SPECIES,
        weather_abilities=sorted(WEATHER_ABILITIES), weather_moves=sorted(WEATHER_MOVES), setup=sorted(SETUP),
        recovery=sorted(RECOVERY), offense_items=sorted(OFFENSE_ITEMS), hazards=sorted(HAZARDS),
        removal=sorted(REMOVAL)), slots=len(schedule), pairs=len({r['pair_id'] for r in schedule}),
        matchups=len({r['matchup_id'] for r in schedule}), teams_sha256=sha(output / 'teams.json'),
        schedule_sha256=sha(output / 'schedule.json'), selection_sha256=sha(output / 'selection.json'),
        seconds=round(time.time() - started, 1), created_at=time.time()), immutable=True)
    (output / 'README.md').write_text(README)
    seal(output)
    return selection


README = """# EX-120 collection — 새 팀 32개와 128슬롯 일정

결과를 보기 전에 생성하고 봉인했다. 규칙 원문은
`/workspace/project_context/research/policy-learning/experiments/EX-120-laya-team-generalization128.md`이다.

- `teams.json`: 선정 팀 32개(packed/text, 원본 경로·sha256, 유형과 분류 특징)
- `selection.json`: 제외 서명 수, 거부 사유, 유형별 수, 부족분, 다양성 확인값
- `schedule.json`: 128슬롯(32조합 × 시드2 × 팀 교환), 시드와 진행 순서
- `manifest.json`: 동결 규칙과 파일 해시. 봉인은 `checksums.sha256`
- 생성 명령: `/workspace/scripts/laya-imitation general collect` (이미 있으면 실패)
"""
