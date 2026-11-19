"""EX-177 (D-213): the fp1 renderer — the laya input built only from foul-play's tracking, set sampling and poke-engine.

Runs under the foul-play venv, on `tracker.Tracker.view()` (the battle foul-play would search on). Nothing from the
laya renderers v1–v11 is used: no laya engine judge, no @smogon/calc, no usage file, no strategy / duel / lock lines,
no turn history. Determinism: the set sampling is seeded per sample (`seed_of`), and the process must run with
`PYTHONHASHSEED=0` (foul-play iterates over Python sets in places).

State text (one block per line):
  header   turn, decision kind, both sides' tera availability, weather / field / trick room / gravity with turns
  sides    side conditions (layers / turns), wish, future sight
  ME       own active: species [types] hp/maxhp status boosts volatiles | item | ability | tera | stats | moves pp
  bench    own bench, one line each
  OPP      opponent active: species [types] hp% status boosts volatiles | item | ability | tera | revealed moves |
           speed range (foul-play inference) | ruled-out items / abilities
  sets     the opponent active's top SET_TOP sampled sets with their share of SAMPLES draws (foul-play
           `prepare_battles`): nature, EVs, item, ability, tera, speed, moves, source
  obench   opponent bench: species hp status, known item, revealed moves, its top sampled set
Options (one criterion per legal action id, the laya action ids):
  move / tera  used alone (opponent `none`) against each top sampled set: the opponent's expected HP% after the
               turn and the chance to KO (from `generate_instructions` branches); the move's non-HP effects with
               their chances; against the opponent's LIKELY likely moves (most frequent in the samples, each on a
               draw whose opponent has it): chance each side faints this turn and both HP% afterwards
  switch       entry (opponent `none`): HP% after hazards / abilities; against the likely moves: HP% after, faint
  lead         species [types], stats, moves (team preview: no engine call)
"""
from __future__ import annotations

from collections import Counter
import hashlib
import random
import re

from integration.laya_fp1.tracker import ident

VERSION = 'fp1-v1'
SAMPLES = 32
BENCH_SAMPLES = 8
SET_TOP = 3
LIKELY = 2
WATCH_ITEMS = ('choicescarf', 'choiceband', 'choicespecs', 'assaultvest', 'heavydutyboots', 'leftovers',
               'focussash', 'boosterenergy', 'airballoon', 'lifeorb', 'rockyhelmet')
BOOSTS = (('attack', 'atk'), ('defense', 'def'), ('special-attack', 'spa'), ('special-defense', 'spd'),
          ('speed', 'spe'), ('accuracy', 'acc'), ('evasion', 'eva'))
STAT_KEYS = (('attack', 'atk'), ('defense', 'def'), ('special-attack', 'spa'), ('special-defense', 'spd'),
             ('speed', 'spe'))
INSTRUCTIONS = 'Pick the action a strong player would choose for me in this Gen 9 OU singles battle.'


def seed_of(sample_id):
    return int(hashlib.sha256(('fp1:' + sample_id).encode()).hexdigest()[:16], 16)


# ----------------------------------------------------------------------------------------------- text helpers

def _pct(x):
    return '%d%%' % int(round(x))


def _p(x):
    """A probability as .xx (1 and 0 exact)."""
    if x >= 0.995:
        return '1'
    if x <= 0.005:
        return '0'
    return ('%.2f' % x).lstrip('0')


def _types(p):
    return '[%s]' % ' '.join(t for t in p.types if t and t != 'typeless')


def _boosts(p):
    parts = ['%s%+d' % (short, p.boosts[key]) for key, short in BOOSTS if p.boosts.get(key, 0)]
    return ' boosts ' + ' '.join(parts) if parts else ''


def _volatiles(p):
    vs = sorted(set(str(v) for v in p.volatile_statuses))
    return ' effects ' + ' '.join(vs) if vs else ''


def _status(p):
    if p.hp <= 0:
        return ' fainted'
    if not p.status:
        return ''
    extra = ''
    if str(p.status) == 'slp':
        extra = ' t%d' % p.sleep_turns if not p.rest_turns else ' rest%d' % p.rest_turns
    return ' ' + str(p.status) + extra


def _item(p, known_none='none'):
    from fp import constants
    if p.item == constants.UNKNOWN_ITEM:
        return '?'
    if not p.item:
        return 'removed %s' % p.removed_item if p.removed_item else ('knocked' if p.knocked_off else known_none)
    return p.item


def _tera(p, side_can):
    if p.terastallized:
        return 'tera %s (used)' % p.tera_type
    return 'tera %s' % p.tera_type if p.tera_type else ('tera ?' if side_can else '')


# ----------------------------------------------------------------------------------------------- state blocks

def _side_conditions(side):
    out = []
    for key, value in sorted(side.side_conditions.items()):
        if value and key != 'toxic_count':
            out.append('%s%s' % (key, value if value != 1 else ''))
    if side.wish and side.wish[0]:
        out.append('wish%d' % side.wish[0])
    if side.future_sight and side.future_sight[0]:
        out.append('futuresight%d' % side.future_sight[0])
    return ' '.join(out) or 'none'


def _header(battle, kind, my_tera, opp_tera):
    field = [('weather %s %d' % (battle.weather, battle.weather_turns_remaining)) if battle.weather else 'weather none',
             ('field %s %d' % (battle.field, battle.field_turns_remaining)) if battle.field else 'field none']
    if battle.trick_room:
        field.append('trickroom %d' % battle.trick_room_turns_remaining)
    if battle.gravity:
        field.append('gravity')
    return 'turn %s | %s | my tera %s | opp tera %s | %s' % (
        battle.turn or 0, kind, 'ready' if my_tera else 'no', 'ready' if opp_tera else 'no', ' | '.join(field))


def _own_line(p, prefix, can_tera):
    stats = ' '.join('%s%d' % (short, p.stats[key]) for key, short in STAT_KEYS)
    moves = ' '.join('%s%s' % (m.name, '(x)' if m.disabled else '') + ('/%d' % m.current_pp if m.current_pp < 5 else '')
                     for m in p.moves)
    return '%s %s %s %d/%d%s%s%s | item %s | ability %s | %s | %s | moves %s' % (
        prefix, p.name, _types(p), max(0, int(p.hp)), int(p.max_hp), _status(p), _boosts(p), _volatiles(p),
        _item(p), p.ability or '?', _tera(p, can_tera) or 'tera -', stats, moves)


def _opp_line(battle, p):
    from fp.data import pokedex
    hp = 100.0 * p.hp / max(1, p.max_hp)
    moves = ' '.join(m.name for m in p.moves) or '-'
    line = 'OPP %s %s %s%s%s%s | item %s | ability %s | %s | seen %s' % (
        p.name, _types(p), _pct(hp), _status(p), _boosts(p), _volatiles(p), _item(p), p.ability or '?',
        _tera(p, True) or 'tera ?', moves)
    lo, hi = p.speed_range.min, p.speed_range.max
    if lo > 0 or hi != float('inf'):
        line += ' | speed %s-%s' % (int(lo) if lo > 0 else '?', int(hi) if hi != float('inf') else '?')
    ruled = [i for i in WATCH_ITEMS if i in p.impossible_items]
    if not p.can_have_choice_item:
        ruled += [i for i in ('choiceband', 'choicespecs', 'choicescarf') if i not in ruled]
    if ruled and _item(p) == '?':
        line += ' | not ' + ' '.join(ruled)
    abilities = [ident(a) for a in (pokedex.get(p.name, {}).get('abilities') or {}).values()]
    ruled_ab = [a for a in abilities if a in p.impossible_abilities]
    if ruled_ab and not p.ability:
        line += ' | not ' + ' '.join(ruled_ab)
    return line


# ----------------------------------------------------------------------------------------------- sampling

def _signature(p):
    evs = getattr(p, 'evs', None) or ()
    return (getattr(p, 'nature', '') or '', tuple(evs), p.item or '', p.ability or '', p.tera_type or '',
            tuple(sorted(m.name for m in p.moves)))


def _evs_text(evs):
    names = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
    return ' '.join('%d%s' % (v, n) for v, n in zip(evs, names) if v)


def sample(view, seed, n=SAMPLES):
    """foul-play's own `prepare_battles` draws (each a full battle with the opponent's hidden slots filled).

    Within one call every draw starts from a copy of the same battle, so the candidate-set filters foul-play runs
    per opponent Pokémon and per draw (`get_all_remaining_sets`, `get_all_remaining_trait_combinations`) return the
    same list each time; they are memoized by Pokémon name for the duration of the call only. Each is called on a
    Pokémon before that Pokémon is filled in, and its result is only read, so the draws are unchanged.
    """
    mode = view.mode
    patched = []
    for owner, name in ((mode.team_datasets, 'get_all_remaining_sets'),
                        (mode.smogon_sets, 'get_all_remaining_trait_combinations')):
        original = getattr(owner, name)
        memo = {}

        def cached(pkmn, *args, _original=original, _memo=memo):
            key = (pkmn.name, args)
            if key not in _memo:
                _memo[key] = _original(pkmn, *args)
            return _memo[key]
        setattr(owner, name, cached)
        patched.append((owner, name))
    state = random.getstate()
    random.seed(seed)
    try:
        battles = mode.prepare_battles(view, n)
    finally:
        random.setstate(state)
        for owner, name in patched:
            delattr(owner, name)          # back to the class method
    return [b for b, _ in battles]


def top_sets(battles, name_of):
    """Top sets of one opponent Pokémon across the draws: [(share, signature, representative battle, mon)]."""
    counter, reps = Counter(), {}
    for b in battles:
        p = name_of(b)
        if p is None:
            continue
        sig = _signature(p)
        counter[sig] += 1
        reps.setdefault(sig, (b, p))
    total = sum(counter.values()) or 1
    return [(c / total, sig, reps[sig][0], reps[sig][1]) for sig, c in counter.most_common(SET_TOP)]


def _set_text(share, sig, p, source):
    nature, evs, item, ability, tera, moves = sig
    return '%s: %s %s | %s | %s | tera %s | spe %d | %s%s' % (
        _p(share), nature, _evs_text(evs), item or 'none', ability or '?', tera or '?', p.stats['speed'],
        ' '.join(moves), (' (%s)' % source) if source else '')


def likely_moves(battles):
    counter = Counter()
    for b in battles:
        p = b.opponent.active
        if p is not None:
            for m in p.moves:
                counter[m.name] += 1
    return [m for m, _ in counter.most_common(LIKELY)]


# ----------------------------------------------------------------------------------------------- engine

def engine_state(battle, flags=None):
    from fp.search.poke_engine_helpers import battle_to_poke_engine_state
    state = battle_to_poke_engine_state(battle)
    if flags is not None:
        silent_defaults(state, flags)
    return state


def silent_defaults(state, flags):
    """EX-177 qualification 3: values poke-engine takes without an error but changes (checked 2026-11-18): weight 0
    (Low Kick / Heavy Slam at the lightest weight), Tera type `typeless`, an ability it does not know (read back as
    `NONE`), an item it does not know (`UNKNOWNITEM`). Counted per living Pokémon of both sides. The state is read
    back through its string form: the Python object keeps the names it was given, the engine keeps what it parsed."""
    from poke_engine import State
    parsed = State.from_string(state.to_string())
    for side_name, given, side in (('me', state.side_one, parsed.side_one), ('opp', state.side_two, parsed.side_two)):
        for g, p in zip(given.pokemon, side.pokemon):
            if p.hp <= 0 or str(p.id).lower() == 'none':
                continue
            if not p.weight_kg or p.weight_kg <= 0:
                flags['weight0:%s:%s' % (side_name, str(p.id).lower())] += 1
            if str(p.tera_type).lower() == 'typeless':
                flags['tera_typeless:%s:%s' % (side_name, str(p.id).lower())] += 1
            if str(p.ability).lower() == 'none':
                flags['ability_none:%s:%s:%s' % (side_name, str(p.id).lower(), str(g.ability).lower())] += 1
            if str(p.item).lower() == 'unknownitem':
                flags['item_unknown:%s:%s:%s' % (side_name, str(p.id).lower(), str(g.item).lower())] += 1


def _hp(state, side):
    s = state.side_one if side == 1 else state.side_two
    p = s.pokemon[int(s.active_index)]
    return p.hp, p.maxhp


def outcome(state, mine, theirs):
    """One turn: P(I faint), P(opp faints), expected HP% of my active and the opponent's active afterwards."""
    from poke_engine import generate_instructions
    branches = generate_instructions(state, mine, theirs)
    me_faint = opp_faint = me_hp = opp_hp = total = 0.0
    for b in branches:
        w = b.percentage / 100.0
        after = state.apply_instructions(b)
        hp1, max1 = _hp(after, 1)
        hp2, max2 = _hp(after, 2)
        me_faint += w * (hp1 <= 0)
        opp_faint += w * (hp2 <= 0)
        me_hp += w * 100.0 * max(0, hp1) / max(1, max1)
        opp_hp += w * 100.0 * max(0, hp2) / max(1, max2)
        total += w
    total = total or 1.0
    return me_faint / total, opp_faint / total, me_hp / total, opp_hp / total, branches


_EFFECT = [
    (re.compile(r'ChangeStatus SideTwo-P\d: NONE -> (\w+)'), lambda m: 'opp ' + m.group(1).lower()),
    (re.compile(r'ChangeStatus SideOne-P\d: NONE -> (\w+)'), lambda m: 'me ' + m.group(1).lower()),
    (re.compile(r'ChangeSideCondition SideTwo (\w+): (-?\d+)'), lambda m: 'opp side %s%s' % (m.group(1).lower(), '' if int(m.group(2)) > 0 else ' cleared')),
    (re.compile(r'ChangeSideCondition SideOne (\w+): (-?\d+)'), lambda m: 'my side %s%s' % (m.group(1).lower(), '' if int(m.group(2)) > 0 else ' cleared')),
    (re.compile(r'Boost SideOne (\w+): (-?\d+)'), lambda m: 'me %s%+d' % (m.group(1).lower(), int(m.group(2)))),
    (re.compile(r'Boost SideTwo (\w+): (-?\d+)'), lambda m: 'opp %s%+d' % (m.group(1).lower(), int(m.group(2)))),
    (re.compile(r'ApplyVolatileStatus SideTwo: (\w+)'), lambda m: 'opp ' + m.group(1).lower()),
    (re.compile(r'ApplyVolatileStatus SideOne: (\w+)'), lambda m: 'me ' + m.group(1).lower()),
    (re.compile(r'Switch SideTwo'), lambda m: 'opp switched out'),
    (re.compile(r'ChangeWeather'), lambda m: 'weather'),
    (re.compile(r'ChangeTerrain'), lambda m: 'terrain'),
    (re.compile(r'ToggleTrickRoom'), lambda m: 'trickroom'),
    (re.compile(r'ChangeItem SideTwo: (\w+) -> NONE'), lambda m: 'opp item removed'),
]
# HP changes are not listed as effects: end-of-turn healing / residual damage would be attributed to every move.
# They show in the HP% after the turn instead.
_IGNORED = {'ROOST', 'TERASTALLIZED'}


SHORT = {'attack': 'atk', 'defense': 'def', 'specialattack': 'spa', 'specialdefense': 'spd', 'speed': 'spe',
         'accuracy': 'acc', 'evasion': 'eva'}
EFFECT_LIMIT = 3


def _labels(branches):
    chance = Counter()
    for b in branches:
        w = b.percentage / 100.0
        seen = set()
        for instruction in b.instruction_list:
            text = repr(instruction)
            for pattern, name in _EFFECT:
                m = pattern.search(text)
                if m:
                    label = name(m)
                    if label.split()[-1].upper() not in _IGNORED:
                        seen.add(label)
        for label in seen:
            chance[label] += w
    return chance


def effects(branches, baseline=None):
    """Non-HP effects of a move used alone (opponent `none`), each with its probability, minus what the turn does
    anyway (`baseline`: both sides `none` — screens running out, end-of-turn abilities); at most EFFECT_LIMIT, most
    likely first."""
    chance = _labels(branches)
    if baseline is not None:
        for label in _labels(baseline):
            chance.pop(label, None)
    out = []
    for label, p in sorted(chance.items(), key=lambda kv: (-kv[1], kv[0]))[:EFFECT_LIMIT]:
        for long, short in SHORT.items():
            label = label.replace(' ' + long, ' ' + short)
        out.append('%s %s' % (label, _p(p)) if p < 0.995 else label)
    return out


# `poke_engine.calculate_damage` is not used: it returns (max normal, max crit) only, and 0 without an error for a
# `-tera` choice (checked 2026-11-18). Damage is read from `generate_instructions` branches instead, which also
# carry accuracy, crits, KO splits, abilities and items.


# ----------------------------------------------------------------------------------------------- options

def engine_choice(action, view, own_sets):
    """laya action id -> poke-engine choice string."""
    kind, _, rest = action.partition(':')
    if kind == 'move':
        move, _, mode = rest.partition(':')
        return move + ('-tera' if mode == 'tera' else '')
    if kind == 'switch':
        species = ident(own_sets[int(rest) - 1]['species'])
        for p in [view.user.active] + list(view.user.reserve):
            if p is not None and species in (p.name, p.base_name):
                return p.name
        return species
    return None


def render(view, sample_id, actions, decision_kind, own_sets):
    """-> (state text, {action id: criterion text}, diagnostics)."""
    diag = dict(engine_errors=0, defaults=Counter())
    user, opp = view.user, view.opponent
    me = user.active
    my_tera = bool(me is not None and getattr(me, 'can_terastallize', False))
    opp_all = ([opp.active] if opp.active else []) + list(opp.reserve)
    opp_tera = not any(p.terastallized for p in opp_all)
    lines = [_header(view, decision_kind, my_tera, opp_tera),
             'my side: %s | opp side: %s' % (_side_conditions(user), _side_conditions(opp))]
    lead = decision_kind == 'lead'
    criteria = {}
    if lead:
        for i, p in enumerate(user.reserve + ([me] if me else [])):
            lines.append(_own_line(p, 'MINE', True))
        for p in opp_all:
            lines.append('OPP %s %s' % (p.name, _types(p)))
        for action in actions:
            slot = int(action['id'].split(':')[1]) - 1
            species = ident(own_sets[slot]['species'])
            criteria[action['id']] = 'lead %s' % species
        return '\n'.join(lines), criteria, diag

    lines.append(_own_line(me, 'ME', my_tera))
    for p in user.reserve:
        lines.append(_own_line(p, 'bench', False) if p.hp > 0 else 'bench %s fainted' % p.name)
    seed = seed_of(sample_id)
    battles = sample(view, seed) if opp.active is not None else []
    sets = top_sets(battles, lambda b: b.opponent.active) if battles else []
    if opp.active is not None:
        lines.append(_opp_line(view, opp.active))
        for share, sig, b, p in sets:
            lines.append('set ' + _set_text(share, sig, p, None))
    bench_battles = battles[:BENCH_SAMPLES]
    for index, p in enumerate(opp.reserve):
        if p.hp <= 0:
            lines.append('obench %s fainted' % p.name)
            continue
        hp = 100.0 * p.hp / max(1, p.max_hp)
        seen = ' '.join(m.name for m in p.moves) or '-'
        text = 'obench %s %s %s%s | item %s | seen %s' % (p.name, _types(p), _pct(hp), _status(p), _item(p), seen)
        top = top_sets(bench_battles, lambda b, n=p.name: next((q for q in b.opponent.reserve if q.name == n), None))
        if top:
            share, sig, _, q = top[0]
            text += ' | likely ' + _set_text(share, sig, q, None)
        lines.append(text)
    likely = likely_moves(battles)
    if sets:
        lines.append('opp likely: ' + ' '.join(likely))

    states = []                                     # one engine state per top set (the representative draw)
    for share, sig, b, p in sets:
        try:
            states.append((share, engine_state(b, diag["defaults"])))
        except Exception:
            diag['engine_errors'] += 1
    versus = []                                     # per likely move: a draw whose opponent has that move
    for move in likely:
        b = next((b for b in battles if b.opponent.active is not None
                  and any(m.name == move for m in b.opponent.active.moves)), None)
        try:
            versus.append((move, engine_state(b, diag["defaults"]))) if b is not None else None
        except Exception:
            diag['engine_errors'] += 1
    for action in actions:
        aid = action['id']
        choice = engine_choice(aid, view, own_sets)
        parts = []
        try:
            if aid.startswith('move:') and states:
                alone = [outcome(s, choice, 'none') for _, s in states]
                weight = sum(sh for sh, _ in states) or 1.0
                ko = sum(sh * a[1] for (sh, _), a in zip(states, alone)) / weight
                now = 100.0 * opp.active.hp / max(1, opp.active.max_hp)
                if ko > 0 or any(abs(a[3] - now) >= 0.5 for a in alone):
                    values = [_n(a[3]) for a in alone]
                    text = 'solo opp ' + (values[0] if len(set(values)) == 1 else '/'.join(values))
                    if ko > 0:
                        text += ' ko' + _p(ko)
                    parts.append(text)
                from poke_engine import generate_instructions
                eff = effects(alone[0][4], generate_instructions(states[0][1], 'none', 'none'))
                if eff:
                    parts.append(', '.join(eff))
            elif aid.startswith('switch:') and states:
                _, _, me_hp, _, _ = outcome(states[0][1], choice, 'none')
                parts.append('in ' + _n(me_hp))
            if decision_kind == 'turn_action':
                for move, state in versus:
                    me_f, opp_f, me_hp, opp_hp, _ = outcome(state, choice, move)
                    parts.append('v %s me%s%s opp%s%s' % (
                        move, _n(me_hp), (' f' + _p(me_f)) if me_f > 0 else '',
                        _n(opp_hp), (' f' + _p(opp_f)) if opp_f > 0 else ''))
        except Exception as exc:
            diag['engine_errors'] += 1
            diag.setdefault('engine_error_samples', []).append('%s %s: %s' % (aid, type(exc).__name__, exc))
            parts.append('engine ?')
        label = _label(aid, own_sets, me)
        criteria[aid] = '; '.join(([label] if label else []) + parts)
    return '\n'.join(lines), criteria, diag


def _n(x):
    """An HP percentage as a bare integer (the criteria legend: numbers after `me` / `opp` / `in` are HP%)."""
    return '%d' % int(round(x))


def _label(aid, own_sets, me):
    """The action's own words: the option id already names the move; tera adds its type, a switch its species."""
    kind, _, rest = aid.partition(':')
    if kind == 'move' and rest.endswith(':tera'):
        return 'tera %s' % (me.tera_type if me is not None and me.tera_type else '?')
    if kind in ('switch', 'lead'):
        return ident(own_sets[int(rest) - 1]['species'])
    return ''
