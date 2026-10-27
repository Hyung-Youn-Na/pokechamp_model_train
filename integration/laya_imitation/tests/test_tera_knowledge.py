"""EX-124 Tera knowledge: engine rules, verified labels, held-out species and determinism."""
import random

from integration.laya_imitation import tera_knowledge as tk


def test_engine_rules():
    assert tk.defensive_types(['steel', 'ghost'], 'normal') == ['normal']
    assert tk.defensive_types(['steel', 'ghost'], 'stellar') == ['steel', 'ghost']
    assert tk.mult('fighting', ['steel', 'ghost']) == 0 and tk.mult('fighting', ['normal']) == 2
    assert tk.stab('steel', ['steel', 'ghost'], 'steel') == 2.0
    assert tk.stab('fighting', ['steel', 'ghost'], 'fighting') == 1.5
    assert tk.stab('steel', ['steel', 'ghost'], 'fighting') == 1.5
    assert tk.stab('water', ['water'], 'water', adaptability=True) == 2.25
    assert tk.stab('fire', ['water'], 'grass') == 1.0
    assert tk.low_power('rapidspin', 'normal') == 60          # tera type, under 60
    assert tk.low_power('rapidspin', 'water') == 50           # not the tera type
    assert tk.low_power('aquajet', 'water') == 40             # priority excluded
    assert tk.low_power('bulletseed', 'grass') == 25          # multi-hit excluded


def test_templates_label_in_options_and_deterministic():
    train, held = tk._species_split()
    assert not set(train) & set(held) and len(held) >= 1
    for name, fn in tk.A_TEMPLATES.items():
        for i in range(40):
            a = fn(random.Random(i), train, i)
            b = fn(random.Random(i), train, i)
            assert a == b
            state, ins, crit, label, meta = a
            assert label in crit and len(set(crit.values())) == len(crit)


def test_answers_not_leaked_in_persistence_card():
    train, _ = tk._species_split()
    for i in range(20):
        state, _, crit, label, _ = tk.a6(random.Random(i), train, i)
        me = [line for line in state.split('\n') if line.startswith('ME ')][0]
        assert crit['tera'] not in me and label == 'tera'


def test_flip_quota_in_a3():
    train, _ = tk._species_split()
    flips = sum(tk.a3(random.Random(i), train, i)[4]['flip'] for i in range(200))
    assert 90 <= flips <= 150
