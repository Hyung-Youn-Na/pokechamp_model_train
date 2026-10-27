"""EX-124 Tera knowledge rows (laya choice rows) with computed, verified answers and no strategy labels.

A: concept rows on synthetic situation cards (reviewed108 species, assumed sets), one rule per template.
B: grounded rows on real EX-071 states (the `v2-all` state text), answers from the type chart and the v2
   features store (pinned calc). Rules live in `tera_rules.json` / `tera_rules.md` (Showdown engine first).
"""
from __future__ import annotations
from functools import lru_cache
import json
from pathlib import Path
import random
import shutil
import time

from . import config as c
from . import dex_v2
from .features import _nature, _stat
from .storage import atomic, digest, jsonl, seal, sha, source_identity, verify_seal, write_jsonl

SEED = 20261025
RULES = Path(__file__).with_name('tera_rules.json')
A_PER_TYPE = 3000
A_HELDOUT_PER_TYPE = 300
B_PER_TYPE = 10000
B_HELDOUT_PER_TYPE = 500
MULTS = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
MULTIHIT = {'bulletseed', 'iciclespear', 'rockblast', 'tailslap', 'scaleshot', 'tripleaxel', 'surgingstrikes',
            'dualwingbeat', 'doublehit', 'populationbomb', 'watershuriken', 'pinmissile', 'bonemerang', 'tachyoncutter',
            'twinbeam', 'dragondarts', 'triplekick', 'armthrust', 'furyswipes', 'furyattack', 'doublekick', 'dualchop',
            'geargrind', 'doubleironbash', 'tripledive', 'bonerush'}
GENERATOR = ('tera_knowledge.py', 'tera_rules.json', 'tera_rules.md', 'dex_v2.py', 'dex_gen9_v2.json',
             'assumed_sets_v2.json', 'features.py', 'data_v2.py', 'config.py')


@lru_cache(maxsize=1)
def rules():
    return json.loads(RULES.read_text())


def types_of(species):
    return list(dex_v2.load()['species'][species]['types'])


def mult(attack_type, defender_types):
    return dex_v2.multiplier(attack_type, defender_types)


def defensive_types(original, tera):
    return list(original) if tera in (None, '', 'stellar') else [tera]


def stab(move_type, original, tera, adaptability=False):
    """Showdown STAB while terastallized into `tera` (not Stellar)."""
    is_stab = move_type in original or move_type == tera
    if not is_stab:
        return 1.0
    if move_type == tera and move_type in original:
        return 2.25 if adaptability else 2.0
    return 2.0 if adaptability else 1.5


def low_power(move_id, tera):
    """Base power while terastallized into `tera` (the 60 floor and its exceptions)."""
    m = dex_v2.load()['moves'][move_id]
    lp = rules()['low_power']
    if (m['category'] != 'status' and 0 < m['power'] < lp['floor'] and m['type'] == tera and m['priority'] <= 0
            and move_id not in MULTIHIT and move_id not in lp['excludes_variable_power']):
        return lp['floor']
    return m['power']


def tera_blast(species, assumed, tera):
    base = dex_v2.load()['species'][species]['base']
    stat = lambda k: _stat(base[k], int(assumed['ivs'].get(k, 31)), int(assumed['evs'].get(k, 0)),
                           int(assumed['level']), _nature(assumed['nature'], k))
    return tera, 'physical' if stat('atk') > stat('spa') else 'special'


def _x(value):
    return 'x%g' % value


def _row(sample_id, state, instructions, criteria, label, meta):
    if label not in criteria:
        raise AssertionError('label outside options: %s' % sample_id)
    return dict(sample_id=sample_id, state=state,
                questions={'action': {'type': 'choice', 'instructions': instructions, 'criteria': criteria}},
                expected={'action': label}, meta=dict(meta, source='knowledge'))


# ----------------------------------------------------------------------------- A: concept cards

def _species_split():
    names = sorted(dex_v2.assumed())
    ranked = sorted(names, key=lambda s: digest([SEED, 'heldout_species', s]))
    held = set(ranked[:max(1, len(names) // 10)])
    return [s for s in names if s not in held], sorted(held)


def _card(rng, species, *, tera, my_flag='ready', opp_flag='ready', terastallized=False, opp=None, extra=()):
    a = dex_v2.assumed()[species]['set']
    shown = [tera] if terastallized and tera != 'stellar' else types_of(species)
    me = 'ME %s [%s] %d%% | ability %s | item %s | %s %s' % (
        species, ' '.join(shown), rng.choice((100, 100, 87, 64, 41)), a['ability'] or 'none', a['item'] or 'none',
        'terastallized' if terastallized else 'tera', tera)
    lines = ['turn %d | turn_action | my tera %s | opp tera %s | weather none | field none' % (
        rng.randint(2, 25), my_flag, opp_flag), 'my side: none | opp side: none', me]
    if opp:
        lines.append(opp)
    lines.extend(extra)
    return '\n'.join(lines)


def _opp_line(rng, species, terastallized=None):
    shown = [terastallized] if terastallized else types_of(species)
    moves = [m for m in dex_v2.assumed()[species]['set']['moves'] if m in dex_v2.load()['moves']][:rng.randint(1, 3)]
    return 'OPP %s [%s] %d%% | ability ? | item ?%s | seen %s' % (
        species, ' '.join(shown), rng.choice((100, 78, 55)), ' | terastallized %s' % terastallized if terastallized
        else '', ' '.join(moves) or 'none')


def _tera_choice(rng, species, allow_stellar=False):
    if allow_stellar and rng.random() < 0.1:
        return 'stellar'
    a = dex_v2.assumed()[species]['set']['tera']
    return a if a and a != 'stellar' and rng.random() < 0.6 else rng.choice(rules()['types'])


def a1(rng, pool, i):
    sp = rng.choice(pool)
    mate = rng.choice([s for s in pool if s != sp])
    case = i % 4
    tera = _tera_choice(rng, sp)
    if case == 0:
        hist, label = ['my team: %s [%s] 100%%' % (mate, ' '.join(types_of(mate)))], 'yes'
        state = _card(rng, sp, tera=tera, my_flag='?', extra=hist)
    elif case == 1:
        state, label = _card(rng, sp, tera=tera, my_flag='?', terastallized=True,
                             extra=['T3: me tera %s' % tera]), 'no'
    elif case == 2:
        t2 = _tera_choice(rng, mate)
        state, label = _card(rng, sp, tera=tera, my_flag='?', extra=[
            'my team: %s [%s] 62%% | terastallized %s' % (mate, t2, t2), 'T4: me in %s; me tera %s' % (mate, t2)]), 'no'
    else:
        t2 = _tera_choice(rng, mate)
        state, label = _card(rng, sp, tera=tera, my_flag='?', extra=[
            'my team: %s [%s] fainted | terastallized %s' % (mate, t2, t2), 'T6: me tera %s; me fainted' % t2]), 'no'
    crit = {'yes': 'I can still Terastallize this turn', 'no': 'my side already used its one Terastallization'}
    return state, 'Each side may Terastallize once per battle. Can I Terastallize this turn?', crit, label, dict(case=case)


def a2(rng, pool, i):
    sp = rng.choice(pool)
    orig = types_of(sp)
    tera = _tera_choice(rng, sp, allow_stellar=True)
    while tera != 'stellar' and [tera] == orig:   # mono-type into its own type: typing is unchanged, ask another
        tera = rng.choice(rules()['types'])
    other = rng.choice([t for t in rules()['types'] if t not in orig and t != tera])
    crit = {'tera': '[%s]' % ' '.join(defensive_types(orig, tera) if tera != 'stellar' else [tera]),
            'original': '[%s]' % ' '.join(orig),
            'both': '[%s]' % ' '.join(sorted(set(orig) | ({tera} if tera != 'stellar' else set()))),
            'other': '[%s]' % other}
    if len(set(crit.values())) < 4:
        crit['both'] = '[%s %s]' % (orig[0], other)
    label = 'original' if tera == 'stellar' else 'tera'
    return (_card(rng, sp, tera=tera), 'If I Terastallize now, what will my defensive typing be?', crit, label,
            dict(tera=tera))


def a3(rng, pool, i):
    for _ in range(200):
        sp, foe = rng.sample(pool, 2)
        moves = [m for m in dex_v2.assumed()[foe]['set']['moves']
                 if dex_v2.load()['moves'].get(m, {}).get('category') not in (None, 'status')]
        if not moves:
            continue
        move = rng.choice(moves)
        mtype = dex_v2.load()['moves'][move]['type']
        tera = _tera_choice(rng, sp)
        before, after = mult(mtype, types_of(sp)), mult(mtype, defensive_types(types_of(sp), tera))
        if (i % 5 < 3) == (before != after):
            break
    crit = {_x(v): '%s effectiveness' % _x(v) for v in MULTS}
    state = _card(rng, sp, tera=tera, opp=_opp_line(rng, foe))
    return (state, 'If I Terastallize now, how effective will the opponent\'s %s (%s) be against me?' % (move, mtype),
            crit, _x(after), dict(before=before, after=after, flip=before != after))


def a4(rng, pool, i):
    sp = rng.choice(pool)
    a = dex_v2.assumed()[sp]['set']
    adapt = a['ability'] == 'adaptability'
    orig = types_of(sp)
    moves = [m for m in a['moves'] if dex_v2.load()['moves'].get(m, {}).get('category') not in (None, 'status')]
    move = rng.choice(moves) if moves and rng.random() < 0.7 else rng.choice(
        sorted(k for k, v in dex_v2.load()['moves'].items() if v['category'] != 'status' and v['power'] >= 60))
    mtype = dex_v2.load()['moves'][move]['type']
    tera = [mtype, rng.choice(orig), rng.choice(rules()['types'])][i % 3]
    value = stab(mtype, orig, tera, adapt)
    crit = {'x1': 'no STAB (x1)', 'x1.5': 'STAB x1.5', 'x2': 'STAB x2', 'x2.25': 'STAB x2.25'}
    return (_card(rng, sp, tera=tera), 'If I Terastallize now, what STAB multiplier will %s (%s) get?' % (move, mtype),
            crit, _x(value), dict(adaptability=adapt, tera=tera, move_type=mtype))


def a5(rng, pool, i):
    sp = rng.choice(pool)
    if i % 2 == 0:
        low = [k for k, v in dex_v2.load()['moves'].items()
               if v['category'] != 'status' and 0 < v['power'] < 60 and not k.startswith('gmax') and not k.startswith('max')]
        move = rng.choice(sorted(low))
        m = dex_v2.load()['moves'][move]
        tera = m['type'] if rng.random() < 0.75 else rng.choice(rules()['types'])
        value = low_power(move, tera)
        crit = {str(m['power']): 'base power stays %d' % m['power'], '60': 'base power becomes 60',
                str(round(m['power'] * 1.5)): 'base power becomes %d' % round(m['power'] * 1.5)}
        if len(crit) < 3:
            crit['80'] = 'base power becomes 80'
        state = _card(rng, sp, tera=tera, terastallized=True)
        return (state, 'I am Terastallized. What is the base power of %s (%s, listed %d, priority %+d)?' % (
            move, m['type'], m['power'], m['priority']), crit, str(value), dict(kind='low_power', tera=tera))
    tera = rng.choice(rules()['types'])
    t, category = tera_blast(sp, dex_v2.assumed()[sp]['set'], tera)
    crit = {'normal special': 'Normal-type special', '%s special' % t: '%s-type special' % t.title(),
            '%s physical' % t: '%s-type physical' % t.title()}
    if t == 'normal':
        crit['fairy special'] = 'Fairy-type special'
    state = _card(rng, sp, tera=tera)
    return (state, 'If I Terastallize and use Tera Blast, what type and category will it have?', crit,
            '%s %s' % (t, category), dict(kind='tera_blast', tera=tera))


def a6(rng, pool, i):
    sp = rng.choice(pool)
    tera = rng.choice([t for t in rules()['types'] if [t] != types_of(sp)])
    crit = {'tera': '[%s]' % tera, 'original': '[%s]' % ' '.join(types_of(sp))}
    # The card shows the pre-Tera typing; only the history says it Terastallized before switching out.
    state = _card(rng, sp, tera=tera, my_flag='used',
                  extra=['T%d: me tera %s; me switched out; me in %s' % (rng.randint(2, 9), tera, sp)])
    return state, 'My Pokemon Terastallized, switched out and came back. What is its typing now?', crit, 'tera', {}


def a7(rng, pool, i):
    sp, foe = rng.sample(pool, 2)
    known = i % 2 == 0
    t2 = _tera_choice(rng, foe) if known else None
    state = _card(rng, sp, tera=_tera_choice(rng, sp), opp_flag='used' if known else 'ready',
                  opp=_opp_line(rng, foe, t2))
    crit = {'known': 'revealed because it Terastallized', 'unknown': 'hidden until it Terastallizes'}
    return state, 'Do I know the opponent %s\'s Tera Type?' % foe, crit, 'known' if known else 'unknown', {}


A_TEMPLATES = dict(A1=a1, A2=a2, A3=a3, A4=a4, A5=a5, A6=a6, A7=a7)


def concept_rows(pool, per_type, tag):
    rows = []
    for name, fn in A_TEMPLATES.items():
        rng = random.Random('%d-%s-%s' % (SEED, name, tag))
        for i in range(per_type):
            state, ins, crit, label, meta = fn(rng, pool, i)
            rows.append(_row('%s-%s-%05d' % (tag, name, i), state, ins, crit, label, dict(meta, kind=name)))
    return rows


# ----------------------------------------------------------------------------- B: real states

def grounded_rows(split, limit, tag):
    """Real EX-071 decisions with my Tera available, the `v2-all` state text and the v2 features store."""
    records = jsonl(c.EX071_PREPARED / (split + '.jsonl'))
    store = jsonl(c.V2_FEATURES / (split + '.jsonl'))
    texts = jsonl(c.V2_DATASET / (split + '.jsonl'))
    pools = {k: [] for k in ('B1', 'B2', 'B3', 'B4')}
    ko_yes = 0
    for record, facts, text in zip(records, store, texts, strict=True):
        if not (record['sample_id'] == facts['sample_id'] == text['sample_id']):
            raise ValueError('split files out of order at %s' % record['sample_id'])
        snap = json.loads(record['input']['state'])['snapshot']
        own = {m['slot']: m for m in snap['own_team']}
        opp = {m['slot']: m for m in snap['opponent_team']}
        me = own.get(snap['own_active_slot']) if snap['own_active_slot'] else None
        foe = opp.get(snap['opponent_active_slot']) if snap['opponent_active_slot'] else None
        base = dict(sample=record['sample_id'], state=text['state'])
        pools['B4'].append(dict(base, label={(True, True): 'both', (True, False): 'me', (False, True): 'opp',
                                             (False, False): 'neither'}[(bool(snap['can_tera']),
                                                                         bool(snap['opponent_can_tera']))]))
        if not (snap['can_tera'] and me is not None and foe is not None and snap['decision_kind'] == 'turn_action'):
            continue
        tera = dex_v2.to_id(me['original_set'].get('teraType') or me['tera_type'] or '')
        if not tera or tera == 'stellar':
            continue
        seen = [m['id'] for m in foe['moves'] if dex_v2.load()['moves'].get(m['id'], {}).get('category') not in (None, 'status')]
        if len(seen) >= 2:
            after = {m: mult(dex_v2.load()['moves'][m]['type'], [tera]) for m in seen}
            top = max(after.values())
            if list(after.values()).count(top) == 1 and None not in after.values():
                crit = {m: '%s (%s)' % (m, dex_v2.load()['moves'][m]['type']) for m in seen}
                pools['B1'].append(dict(base, crit=crit, label=max(after, key=after.get), tera=tera))
        dmg = facts['facts']['damage']
        moves = sorted({k.split(':')[1] for k in dmg if k.startswith('move:') and k.endswith(':tera')})
        for m in moves:
            n, t = dmg.get('move:%s:normal' % m), dmg.get('move:%s:tera' % m)
            if not n or not t or 'error' in n or 'error' in t:
                continue
            diff = t['max'] - n['max']
            pools['B2'].append(dict(base, move=m, label='more' if diff > 1 else 'less' if diff < -1 else 'same'))
            hp = foe['hp_percent'] if foe['hp_percent'] is not None else 100
            changes = (n['min'] >= hp) != (t['min'] >= hp)
            pools['B3'].append(dict(base, move=m, label='yes' if changes else 'no'))
            ko_yes += changes
    rng = random.Random('%d-B-%s' % (SEED, tag))
    rows = []
    texts_q = dict(
        B1='If I Terastallize now, which of the opponent\'s revealed attacks becomes the most effective against me?',
        B2='If I use %s while Terastallizing instead of without, how does its damage to the opponent change?',
        B3='Does Terastallizing change whether %s surely knocks out the opponent this turn?',
        B4='Which sides can still Terastallize in this battle?')
    for kind, pool in pools.items():
        if kind == 'B3':
            yes = [p for p in pool if p['label'] == 'yes']
            no = [p for p in pool if p['label'] == 'no']
            rng.shuffle(no)
            pool = yes + no[:max(len(yes), limit // 2)]
        elif kind in ('B2', 'B4'):
            groups = {}
            for p in pool:
                groups.setdefault(p['label'], []).append(p)
            share = max(1, limit // len(groups))
            pool = [p for g in groups.values() for p in rng.sample(g, min(len(g), share))]
        rng.shuffle(pool)
        for i, p in enumerate(pool[:limit]):
            if kind == 'B1':
                crit, ins = p['crit'], texts_q['B1']
            elif kind == 'B2':
                crit = {'more': 'more damage', 'less': 'less damage', 'same': 'about the same'}
                ins = texts_q['B2'] % p['move']
            elif kind == 'B3':
                crit = {'yes': 'Terastallizing changes the sure-KO outcome', 'no': 'no change'}
                ins = texts_q['B3'] % p['move']
            else:
                crit = {'both': 'both sides', 'me': 'only me', 'opp': 'only the opponent', 'neither': 'neither side'}
                ins = texts_q['B4']
            rows.append(_row('%s-%s-%s-%05d' % (tag, kind, p['sample'], i), p['state'], ins, crit, p['label'],
                             dict(kind=kind, from_sample=p['sample'])))
    return rows, {k: len(v) for k, v in pools.items()}


# ----------------------------------------------------------------------------- build

def build(output=c.TERA_KNOWLEDGE):
    from .data_v2 import _tokenizer, measure_row
    if (output / 'manifest.json').exists():
        raise FileExistsError('knowledge set already built: %s' % output)
    for path in (c.V2_FEATURES, c.V2_DATASET):
        if verify_seal(path):
            raise RuntimeError('input seal failed: %s' % path)
    output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    train_species, held_species = _species_split()
    tok = _tokenizer()
    parts = {'train-A': concept_rows(train_species, A_PER_TYPE, 'kA'),
             'heldout-A': concept_rows(held_species, A_HELDOUT_PER_TYPE, 'hA')}
    b_train, b_pool = grounded_rows('train', B_PER_TYPE, 'kB')
    b_val, _ = grounded_rows('validation', B_HELDOUT_PER_TYPE, 'hBv')
    b_test, _ = grounded_rows('test', B_HELDOUT_PER_TYPE, 'hBt')
    parts.update({'train-B': b_train, 'heldout-B': b_val + b_test})
    audit, dropped = {}, []
    for name, rows in parts.items():
        kept = []
        for r in rows:
            m = measure_row(tok, r['state'], r['questions']['action'], c.V2_HEAD_LIMIT)
            (kept if m['fits'] else dropped).append(r if m['fits'] else dict(sample_id=r['sample_id'], **m))
        parts[name] = kept
        labels = {}
        for r in kept:
            key = '%s:%s' % (r['meta']['kind'], r['expected']['action'])
            labels[key] = labels.get(key, 0) + 1
        audit[name] = dict(rows=len(kept), by_kind={k: sum(r['meta']['kind'] == k for r in kept)
                                                     for k in sorted({r['meta']['kind'] for r in kept})},
                           labels=labels)
    train = parts['train-A'] + parts['train-B']
    write_jsonl(output / 'train.jsonl', train, immutable=True)
    write_jsonl(output / 'heldout-A.jsonl', parts['heldout-A'], immutable=True)
    write_jsonl(output / 'heldout-B.jsonl', parts['heldout-B'], immutable=True)
    write_jsonl(output / 'dropped.jsonl', dropped, immutable=True)
    generator = output / 'generator-source'
    generator.mkdir(exist_ok=True)
    for name in GENERATOR:
        shutil.copy2(c.ROOT / 'integration/laya_imitation' / name, generator / name)
    manifest = dict(dataset='laya-tera-knowledge', version='v1', experiment='EX-124', seed=SEED, rules=rules()['version'],
                    rules_sha256=sha(RULES), heldout_species=held_species, train_species=len(train_species),
                    b_candidate_pool=b_pool, counts={k: len(v) for k, v in parts.items()}, dropped=len(dropped),
                    audit=audit, v2_dataset_manifest_sha256=sha(c.V2_DATASET / 'manifest.json'),
                    features_manifest_sha256=sha(c.V2_FEATURES / 'manifest.json'), source_code=source_identity(),
                    files={n: sha(output / n) for n in ('train.jsonl', 'heldout-A.jsonl', 'heldout-B.jsonl')},
                    seconds=round(time.time() - started, 1), created_at=started)
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(README % dict(train=len(train), a=len(parts['train-A']), b=len(parts['train-B']),
                                                    ha=len(parts['heldout-A']), hb=len(parts['heldout-B']),
                                                    dropped=len(dropped)))
    seal(output)
    print(json.dumps({k: v for k, v in manifest.items() if k in ('counts', 'dropped', 'b_candidate_pool', 'seconds')}))
    return manifest


README = """# laya-tera-knowledge v1 — 테라 기본 지식 행

EX-124(`project_context/research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md`)이 쓴다.
정답은 `tera_rules.json`(Showdown 엔진 근거, `tera_rules.md`), 타입표, v2 정보 캐시의 고정 calc 결과로 계산했다.
전략 판단 라벨은 없다.

- `train.jsonl`: %(train)d행 (A 개념 %(a)d, B 실제 상태 %(b)d)
- `heldout-A.jsonl`: %(ha)d행 (학습에 없는 종족 10%%)
- `heldout-B.jsonl`: %(hb)d행 (EX-071 validation과 test 상태)
- 길이 초과로 버린 행: %(dropped)d (`dropped.jsonl`)
- 행 형식은 laya choice 행(`questions.action`)이다. `meta.kind`(A1~A7, B1~B4)와 `meta.source=knowledge`
- 재현: `scripts/laya-imitation tera data` (이미 있으면 실패)
"""
