"""EP-227 v10: history and lock rules on hand-built events, lock marks on edited real rows, render invariants."""
import json

import pytest

from integration.laya_imitation import compact_v7, data_v6, features, features_v5
from integration.laya_imitation.storage import canonical
from integration.laya_threat import spreads
from integration.laya_v10 import data_v10, history, lock, render_v10, strategy
from integration.pokechamp.imitation.schema import ImitationInput


def ev(turn, event, *args):
    return dict(turn=turn, event=event, args=list(args))


def test_since_switch_in_and_called_moves():
    evts = [ev(1, 'switch', '@opponent', 'Kyurem', '100/100'), ev(1, 'move', '@opponent', 'Ice Beam', '@self'),
            ev(2, 'switch', '@opponent', 'Gholdengo', '100/100'), ev(2, 'move', '@opponent', 'Make It Rain', '@self'),
            ev(3, 'move', '@opponent', 'Shadow Ball', '@self', '[from] move: Sleep Talk'),
            ev(3, 'move', '@opponent', 'Make It Rain', '@self')]
    assert history.since_switch_in(evts, '@opponent') == ['makeitrain', 'makeitrain']
    assert history.since_switch_in(evts, '@self') == []
    assert history.last_turn_move(evts, '@opponent', 4) == 'makeitrain'


def test_max_pp_and_pressure():
    assert history.max_pp('roost') == 8 and history.max_pp('kowtowcleave') == 16
    assert history.max_pp('notamove') is None
    snap = dict(own_team=[dict(species='corviknight', ability='pressure', original_set={})],
                early_history=[ev(0, 'switch', '@self', 'Corviknight, M', '100/100'),
                               ev(0, 'switch', '@opponent', 'Gliscor, F', '100/100')],
                history=[ev(1, 'move', '@opponent', 'Earthquake', '@self'), ev(1, 'move', '@opponent', 'Roost', '@opponent'),
                         ev(2, 'move', '@opponent', 'Roost', '@opponent')])
    # Pressure doubles a use aimed at the Pressure user, not a self-targeted Roost
    assert history.opp_pp_used(snap) == {'gliscor': {'earthquake': 2, 'roost': 2}}


def test_fatigue_ends_a_lock():
    evts = [ev(4, 'move', '@opponent', 'Outrage', '@self'), ev(4, '-start', '@opponent', 'confusion', '[fatigue]')]
    assert lock._locked(evts, '@opponent', 5, None) is None
    assert lock._locked(evts[:1], '@opponent', 5, None) == ('outrage', '2-3t')


@pytest.fixture(scope='module')
def rows():
    out = []
    for record, extra, cached, hist, judged in data_v10._rows('validation'):
        value, ext = data_v6._value(record, extra, hist, 'v6h')
        out.append((record, value, ext, judged))
        if len(out) == 40:
            break
    return out


@pytest.fixture(scope='module')
def calc():
    with features.Calc() as c:
        yield c


def edit(value, fn):
    state = json.loads(value.body['state'])
    fn(state['snapshot'])
    return ImitationInput.from_body(dict(value.body, state=canonical(state)))


def _turn_row(rows):
    return next((v, e) for r, v, e, _ in rows if r['decision_kind'] == 'turn_action' and
                any(a.startswith('move:') for a in v.action_ids))


def _me(snapshot):
    return next(m for m in snapshot['own_team'] if m['slot'] == snapshot['own_active_slot'])


def test_choice_item_marks(rows):
    value, _ = _turn_row(rows)

    def scarf(s, **extra):
        _me(s).update(item='choicescarf', ability='intimidate', **extra)
    marks = lock.compute(edit(value, scarf))['options']
    moves = [a for a in value.action_ids if a.startswith('move:') and a.split(':')[1] not in lock.CONSECUTIVE]
    assert all(marks.get(a) == 'locks' for a in moves if a.split(':')[1] not in lock.HANDS_OVER)
    assert lock.compute(edit(value, lambda s: scarf(s) or _me(s).update(ability='klutz')))['options'] == {} or \
        all(a.split(':')[1] in lock.CONSECUTIVE for a in lock.compute(edit(value, lambda s: scarf(s) or
                                                                          _me(s).update(ability='klutz')))['options'])
    magic = lock.compute(edit(value, lambda s: scarf(s) or s['field'].update(magic_room=s['turn'])))['options']
    assert all(a.split(':')[1] in lock.CONSECUTIVE for a in magic)


def test_render_keeps_every_v7_line(rows, calc):
    """v10 only appends: each v7 line (on v9 spreads and v8 marks) is a prefix of a v10 line, in the same order."""
    for record, value, ext, judged in rows:
        facts = render_v10.compute(value, calc, judged, ext)
        state, question = render_v10.render(ext, facts)
        assert (state, question) == render_v10.render(ext, facts)
        v5 = dict(facts['facts'], v4=dict(facts['facts']['v4'], fails=facts['shown']))
        base, base_q = compact_v7.render(value, compact_v7.MODULES, v5, dict(facts['v7'], fails_tc={}))
        lines, at = state.split('\n'), 0
        for line in base.split('\n'):
            head = line.split(' | seen ')[0].split(' | moves ')[0]
            if line.startswith('opp team: '):
                head = 'opp team: '
            while at < len(lines) and not lines[at].startswith(head):
                at += 1
            assert at < len(lines), (record['sample_id'], line)
            if line.startswith('opp team: '):   # v10 appends `| answer ...` to each bench segment
                mine = lines[at][len(head):].split(' || ')
                for seg, new in zip(line[len(head):].split(' || '), mine, strict=True):
                    assert new.startswith(seg), (record['sample_id'], seg)
            at += 1
        for a, text in base_q['criteria'].items():
            assert question['criteria'][a].startswith(text), (record['sample_id'], a)


def test_cache_clear_keeps_the_call(monkeypatch):
    """EX-161 data-v1 defect: a full cache must not lose keys the same call found cached."""
    class Stub:
        def run(self, requests):
            return [dict(min=r['n'], max=r['n']) for r in requests]
    monkeypatch.setattr(strategy, 'CACHE', 3)
    strategy._cache.clear()
    strategy._run(Stub(), [dict(n=1), dict(n=2)])
    assert [r['max'] for r in strategy._run(Stub(), [dict(n=1), dict(n=3)])] == [1, 3]
    strategy._cache.clear()


def test_strategy_needs_spreads(rows, calc):
    record, value, ext, judged = rows[0]
    with pytest.raises(RuntimeError):
        strategy.compute(value, features_v5.compute(value, calc), {'active': None, 'switch': {}}, set(), calc)
    with spreads.patched():
        assert strategy.board(features_v5.resolved(value)[1])['me'] >= 1
