"""Unit tests for EX-222 Way A v2 guardrails (`way_a_v2.py`) reproducing exact EX-220 failure modes."""
from __future__ import annotations

from integration.laya_search import way_a_v2 as WA2


def test_walled_veto_never_forces_protect_on_gliscor_vs_corviknight():
    """EX-220 072713 T22: Laya wanted Spikes (0.53); walled_veto MUST NOT override into Protect!"""
    state = (
        'board: me 5 alive 450% | opp 5 alive 480%\n'
        'duel: me 9+ hits (none) vs opp 5 hits (bodypress), me first -> lose\n'
        'ME gliscor [ground flying] 100% | ability poisonheal\n'
    )
    p = {'move:spikes:normal': 0.53, 'move:protect:normal': 0.36, 'switch:4': 0.06, 'move:toxic:normal': 0.05}
    qm = {'move:spikes:normal': 0.535, 'move:protect:normal': 0.552, 'switch:4': 0.530, 'move:toxic:normal': 0.538}
    qv = {'move:spikes:normal': 0.500, 'move:protect:normal': 0.520, 'switch:4': 0.517, 'move:toxic:normal': 0.495}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state)
    assert pick != 'move:protect:normal', f'walled_veto must not force Protect, got {pick} ({meta})'
    assert pick == 'move:spikes:normal'
    assert meta['reason'] == 'keep_laya'


def test_high_hp_roost_blocked_from_vphi_blunder_veto():
    """EX-220 073833 T23: Dragonite 96% HP vs 1% Garchomp; vphi_blunder_veto MUST NOT force Roost over ESpeed!"""
    state = (
        'board: me 5 alive 410% | opp 5 alive 350%\n'
        'ME dragonite [dragon flying] 96% | ability multiscale\n'
    )
    p = {'move:extremespeed:normal': 0.378, 'move:roost:normal': 0.356, 'move:dragondance:normal': 0.130}
    qm = {'move:extremespeed:normal': 0.651, 'move:roost:normal': 0.661, 'move:dragondance:normal': 0.678}
    qv = {'move:extremespeed:normal': 0.737, 'move:roost:normal': 0.805, 'move:dragondance:normal': 0.729}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state)
    assert pick == 'move:extremespeed:normal', f'96% HP Roost should be blocked, got {pick} ({meta})'


def test_unanimous_veto_escapes_dragonite_8x_roost_loop():
    """EX-220 074335 T8: MCTS (+5.0%) & V_phi (+3.7%) BOTH pick switch:6 over Laya Roost (0.67) -> MUST escape!"""
    state = (
        'board: me 6 alive 550% | opp 6 alive 520%\n'
        'ME dragonite [dragon flying] 85% | ability multiscale\n'
    )
    p = {'move:roost:normal': 0.672, 'move:dragondance:normal': 0.148, 'switch:6': 0.012}
    qm = {'move:roost:normal': 0.619, 'move:dragondance:normal': 0.620, 'switch:6': 0.669}
    qv = {'move:roost:normal': 0.372, 'move:dragondance:normal': 0.375, 'switch:6': 0.409}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state)
    assert pick == 'switch:6', f'Unanimous MCTS+V_phi must escape Roost loop, got {pick} ({meta})'
    assert meta['reason'] == 'unanimous_veto'


def test_consecutive_protect_guard_escapes_protect_loop():
    """When just_protected=True and Laya wants Protect again, MCTS+V_phi preferring switch/attack breaks loop."""
    state = (
        'board: me 5 alive 450% | opp 5 alive 450%\n'
        'ME gliscor [ground flying] 100% | ability poisonheal\n'
    )
    p = {'move:protect:normal': 0.74, 'move:spikes:normal': 0.12, 'switch:4': 0.08}
    qm = {'move:protect:normal': 0.540, 'move:spikes:normal': 0.562, 'switch:4': 0.558}
    qv = {'move:protect:normal': 0.550, 'move:spikes:normal': 0.555, 'switch:4': 0.569}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state, just_protected=True)
    assert pick != 'move:protect:normal', f'Should escape consecutive Protect, got {pick} ({meta})'
    assert meta['reason'] == 'consec_protect_veto'


def test_low_hp_heal_still_allowed_when_legitimate():
    """At 35% HP, legitimate recovery veto is STILL allowed (guardrails do not break real healing)."""
    state = (
        'board: me 4 alive 220% | opp 4 alive 240%\n'
        'ME corviknight [flying steel] 35% | ability pressure\n'
    )
    p = {'move:uturn:normal': 0.55, 'move:roost:normal': 0.35}
    qm = {'move:uturn:normal': 0.48, 'move:roost:normal': 0.52}
    qv = {'move:uturn:normal': 0.42, 'move:roost:normal': 0.51}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state)
    assert pick == 'move:roost:normal', f'Low-HP legitimate heal should still fire, got {pick} ({meta})'


def test_ex224_tinglu_vs_ogerpon_switches_instead_of_dying_at_full_hp():
    """EX-224 Run 1 T2: 100% HP Ting-Lu vs Ogerpon-Wellspring (`duel: lose`).
    MCTS (+0.018) & V_phi v3 (+0.044) BOTH prefer switch:3 (Dragonite), and V_phi screams switch:6 (+0.096).
    High-HP duel_lose switch consensus MUST veto Laya's ruination into Dragonite (switch:3)!"""
    state = (
        'board: me 6 alive 600% | opp 6 alive 600%\n'
        'duel: me 3 hits (ruination) vs opp 2 hits (powerwhip), opp first -> lose\n'
        'ME tinglu [dark ground] 100% | ability vesselofruin\n'
    )
    p = {'move:ruination:normal': 0.4061, 'switch:3': 0.3287, 'move:whirlwind:normal': 0.1717, 'switch:6': 0.0644}
    qm = {'move:ruination:normal': 0.4604, 'switch:3': 0.4783, 'move:whirlwind:normal': 0.4133, 'switch:6': 0.4414}
    qv = {'move:ruination:normal': 0.4990, 'switch:3': 0.5430, 'move:whirlwind:normal': 0.5145, 'switch:6': 0.5945}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state)
    assert pick == 'switch:3', f'Expected Dragonite switch:3, got {pick} ({meta})'
    assert meta['reason'] == 'duel_lose_switch_consensus'


def test_high_hp_lose_switch_guard_does_not_overtrigger_when_low_hp():
    """At 30% HP (low-HP sack turn), narrow dm=+0.015, dv=+0.030 switch should NOT override Laya."""
    state = (
        'board: me 5 alive 350% | opp 5 alive 350%\n'
        'duel: me 3 hits (ruination) vs opp 1 hits (ivycudgel), opp first -> lose\n'
        'ME tinglu [dark ground] 30% | ability vesselofruin\n'
    )
    p = {'move:ruination:normal': 0.55, 'switch:3': 0.35}
    qm = {'move:ruination:normal': 0.460, 'switch:3': 0.475}
    qv = {'move:ruination:normal': 0.500, 'switch:3': 0.530}

    pick, _, _, meta = WA2.choose_way_a_v2(p, qm, qv, state=state)
    assert pick == 'move:ruination:normal' and meta['reason'] == 'keep_laya'


def test_plausible_threat_duel_catches_hidden_ohko_and_priority_2hko():
    """Verify install_plausible_threat_duel fixes revealed utility bias & preserves priority 2HKO threats."""
    from integration.laya_v13 import render_v13
    from integration.laya_v10 import strategy
    render_v13.install()
    WA2.install_plausible_threat_duel()

    class DummyCalc:
        def run(self, reqs):
            out = []
            for r in reqs:
                m = r['move']
                dmg = {
                    'knockoff': (15.0, 17.8),
                    'ivycudgel': (35.0, 42.0),
                    'powerwhip': (110.0, 130.0),
                    'thunderclap': (55.0, 65.0),
                    'dracometeor': (80.0, 94.0),
                }.get(m, (10.0, 12.0))
                out.append({'min': dmg[0], 'max': dmg[1]})
            return out

    view = {'weather': None, 'field': [], 'opponent_side_conditions': {}, 'own_side_conditions': {}}
    me = {
        'species': 'samurotthisui', 'level': 100, 'hp_percent': 76.9, 'status': '', 'ability': 'sharpness',
        'item': '', 'boosts': {}, 'terastallized': False, 'tera_type': 'poison', 'moves': [],
        'original_set': {'level': 100, 'nature': 'jolly', 'evs': {'atk': 252, 'spe': 252}, 'ivs': {}, 'ability': 'sharpness', 'item': ''},
    }
    foe_oger = {
        'species': 'ogerponwellspring', 'level': 100, 'hp_percent': 100.0, 'status': '', 'ability': 'waterabsorb',
        'item': 'wellspringmask', 'boosts': {}, 'terastallized': False, 'tera_type': 'water', 'moves': [{'id': 'knockoff'}],
    }
    strategy._cache.clear()
    lt = strategy.likely_threat(view, foe_oger, me, DummyCalc())
    assert lt is not None and lt['move'] == 'powerwhip', f'Expected hidden powerwhip OHKO, got {lt}'

    # Priority 2HKO (Thunderclap) must beat non-priority 2HKO (Draco Meteor) at 100% HP
    me2 = dict(me, species='darkrai', hp_percent=100.0)
    foe_bolt = {
        'species': 'ragingbolt', 'level': 100, 'hp_percent': 100.0, 'status': '', 'ability': 'protosynthesis',
        'item': '', 'boosts': {}, 'terastallized': False, 'tera_type': 'fairy', 'moves': [{'id': 'thunderclap'}],
    }
    strategy._cache.clear()
    lt2 = strategy.likely_threat(view, foe_bolt, me2, DummyCalc())
    assert lt2 is not None and lt2['move'] == 'thunderclap', f'Expected priority 2HKO thunderclap, got {lt2}'
