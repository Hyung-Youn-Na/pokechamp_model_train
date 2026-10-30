"""EX-141 / EX-142 v6 renderer (D-198): v5 identity, repetition streaks, budgeted long history, opt-in early history."""
import json
from pathlib import Path

import pytest

from integration.laya_imitation import compact_v5, compact_v6, features_v5
from integration.pokechamp.imitation.schema import ImitationInput, _snapshot

CASES = json.loads((Path(__file__).with_name('d198_cases.json')).read_text())['cases']


class StubCalc:
    def run(self, requests):
        return [dict(min=10.0 + i, max=20.0 + i) for i, _ in enumerate(requests)]


def case(name):
    return ImitationInput.from_body(CASES[name])


def render(name, modules, fit=None):
    value = case(name)
    return compact_v6.render(value, modules, features_v5.compute(value, StubCalc()), fit=fit)


def line(state, prefix):
    return next(x for x in state.split('\n') if x.startswith(prefix))


def history(state):
    return [x for x in state.split('\n') if compact_v6.HISTORY_LINE.match(x)]


def test_without_v6_modules_the_text_is_v5():
    for name in CASES:
        value = case(name)
        facts = features_v5.compute(value, StubCalc())
        assert compact_v6.render(value, compact_v5.MODULES, facts) == compact_v5.render(value, compact_v5.MODULES, facts)


def test_streak_needs_two_turns():
    state, _ = render('b126t13', compact_v6.V6S_MODULES)   # Ting-Lu used Spikes once, Corviknight just came in
    assert 'streak' not in state


def test_streak_counts_ruination_and_the_foe_hp():
    state, _ = render('b126t15', compact_v6.V6S_MODULES)   # Ruination on turns 13 and 14
    assert line(state, 'ME ').endswith(' | streak ruination x2 (opp hp 53>33)')
    assert line(state, 'OPP ').endswith(' | streak bodypress x2 (my hp 77.4>54.5)')


def test_streak_is_open_ended_at_the_window_start():
    state, _ = render('b126t18', compact_v6.V6S_MODULES)   # Ruination on turns 13..17, window is 14..17
    me = line(state, 'ME ')
    assert ' | streak ruination x4+ (opp hp ' in me
    assert me.endswith('>40)')   # Roost on turn 17 brought Corviknight back to 40%
    assert 'streak' not in line(state, 'OPP ')   # Body Press, Body Press, Roost: the last move breaks the run


def test_longhist_needs_early_history():
    with pytest.raises(ValueError):
        render('b126t37', compact_v6.V6H_MODULES)


def test_longhist_without_fit_keeps_every_turn_and_with_fit_drops_the_oldest():
    full, _ = render('b126t37_early', compact_v6.V6H_MODULES)
    v5, _ = render('b126t37_early', compact_v5.MODULES)
    turns = [int(x.split(':')[0][1:]) for x in history(full)]
    assert turns == sorted(turns) and turns[0] <= 2 and turns[-1] == 36
    assert full.split('\n')[:-len(history(full))] == v5.split('\n')[:-len(history(v5))]
    limit = len(full) - 2000
    cut, _ = render('b126t37_early', compact_v6.V6H_MODULES, fit=lambda s, q: len(s) <= limit)
    kept = history(cut)
    assert len(cut) <= limit and kept == history(full)[-len(kept):]
    tiny, _ = render('b126t37_early', compact_v6.V6H_MODULES, fit=lambda s, q: False)
    assert history(tiny) == history(v5)   # T-1 and T always stay


def test_streaks_and_longhist_are_separate():
    with pytest.raises(ValueError):
        compact_v6.normalize(compact_v6.V6S_MODULES + ('longhist',))


def test_schema_keeps_early_history_only_outside_the_window():
    snapshot = json.loads(CASES['b126t37_early']['state'])['snapshot']
    assert _snapshot(snapshot)['early_history'] == snapshot['early_history']
    bad = dict(snapshot, early_history=snapshot['early_history'] + [dict(turn=33, event='upkeep', args=[])])
    with pytest.raises(ValueError):
        _snapshot(bad)
