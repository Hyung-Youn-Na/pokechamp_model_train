"""EX-126 effect knowledge: rule order, unrevealed-information handling, templates, engine agreement, Spec."""
import random

from integration.laya_imitation import effect_knowledge as ek
from integration.laya_imitation import training


def mon(species, **kw):
    return ek.mon(species, **kw)


def test_rules_follow_the_engine_order():
    ctx = ek.ctx_of()
    nine, gliscor = mon('ninetalesalola'), mon('gliscor', ability='poisonheal')
    assert ek.known_outcome('auroraveil', nine, gliscor, ctx) == 'fails'
    assert ek.known_outcome('auroraveil', nine, gliscor, ek.ctx_of(weather='snow')) == 'works'
    assert ek.known_outcome('auroraveil', nine, gliscor, ek.ctx_of(weather='snow', my_side={'aurora_veil': 1})) == 'fails'
    blissey = mon('blissey')
    assert ek.known_outcome('thunderwave', blissey, mon('garchomp', ability='roughskin'), ctx) == 'immune'
    assert ek.known_outcome('seismictoss', blissey, mon('gengar', ability='cursedbody'), ctx) == 'immune'
    assert ek.known_outcome('thunderwave', blissey, mon('lanturn', ability='voltabsorb'), ctx) == 'absorbed'
    assert ek.known_outcome('thunderwave', blissey, mon('hatterene', ability='magicbounce'), ctx) == 'reflected'
    burned = mon('clefable', ability='magicguard', status='brn')
    assert ek.known_outcome('thunderwave', blissey, burned, ctx) == 'fails'
    steel = mon('heatran', ability='flashfire', item='')
    assert ek.known_outcome('toxic', blissey, steel, ctx) == 'immune'
    assert ek.known_outcome('toxic', mon('glimmora', ability='corrosion'), steel, ctx) == 'works'
    tusk = mon('greattusk', ability='protosynthesis')
    assert ek.known_outcome('earthquake', tusk, mon('heatran', ability='flashfire', item='airballoon'), ctx) == 'immune'
    assert ek.known_outcome('earthquake', mon('excadrill', ability='moldbreaker'),
                            mon('rotomwash', ability='levitate'), ctx) == 'works'
    assert ek.known_outcome('spikes', tusk, gliscor, ek.ctx_of(opp_side={'spikes': 3})) == 'fails'
    assert ek.known_outcome('stealthrock', tusk, gliscor, ek.ctx_of(opp_side={'stealth_rock': 7})) == 'fails'
    sucker = mon('kingambit', ability='supremeoverlord')
    assert ek.known_outcome('suckerpunch', sucker, tusk, ek.ctx_of(foe_move='bulkup')) == 'fails'
    assert ek.known_outcome('suckerpunch', sucker, tusk, ek.ctx_of(foe_move='headlongrush')) == 'works'
    assert ek.known_outcome('suckerpunch', sucker, tusk, ek.ctx_of(foe_move=None)) is None
    sub = mon('blissey', hp=20)
    assert ek.known_outcome('substitute', sub, tusk, ctx) == 'fails'
    assert ek.known_outcome('substitute', mon('blissey', hp=25), tusk, ctx) is None


def test_unrevealed_ability_is_enumerated():
    tusk = mon('greattusk', ability='protosynthesis')
    hidden = dict(mon('rotomwash'), ability=None, item=None)        # Levitate is its only Ability
    assert ek.outcome('earthquake', tusk, hidden, ek.ctx_of()) == 'immune'
    lanturn = dict(mon('lanturn'), ability=None, item=None)         # Volt Absorb or Illuminate
    assert ek.outcome('thunderbolt', tusk, lanturn, ek.ctx_of()) is None
    amoonguss = dict(mon('amoonguss'), ability=None, item=None)     # Grass type: powder fails either way
    assert ek.outcome('spore', mon('brutebonnet'), amoonguss, ek.ctx_of()) == 'immune'
    garchomp = dict(mon('garchomp'), ability=None, item=None)       # unknown item: Safety Goggles possible
    assert ek.outcome('spore', mon('brutebonnet'), garchomp, ek.ctx_of()) is None


def test_selection_rules():
    me = mon('blissey', item='assaultvest')
    assert ek.selectable('toxic', me, {}) == 'no' and ek.selectable('seismictoss', me, {}) == 'yes'
    scarf = mon('dragapult', item='choicespecs')
    assert ek.selectable('shadowball', scarf, {'locked': 'dracometeor'}) == 'no'
    assert ek.selectable('dracometeor', scarf, {'locked': 'dracometeor'}) == 'yes'


def test_templates_label_in_options_and_deterministic():
    for name, fn in ek.A_FAMILIES.items():
        for held in (False, True):
            for i in range(12):
                a = fn(random.Random(i), held, i, 'x')
                b = fn(random.Random(i), held, i, 'x')
                assert a == b, name
                assert a['label'] in a['crit'], (name, a['label'])


def test_engine_agrees_with_rules_on_every_family():
    rows, errors, disagree = ek.verified_concepts(False, 8, 'test')
    assert not disagree, disagree[:3]
    assert len(rows) >= 80 and len(errors) <= 12
    assert {r['meta']['kind'] for r in rows} == set(ek.A_FAMILIES)


def test_description_rows():
    used = {'items': {'leftovers'}, 'abilities': set(), 'moves': set()}
    rows = ek.description_rows(lambda kind, key, used: (1, 1), 't', used, 'test')
    assert rows and all(r['expected']['action'] in r['questions']['action']['criteria'] for r in rows)
    forward = [r for r in rows if r['meta']['kind'].endswith('forward')]
    assert all(len(set(r['questions']['action']['criteria'].values())) == 4 for r in forward)
    av = [r for r in rows if r['meta'].get('entity') == 'auroraveil' and r['meta']['kind'].endswith('forward')][0]
    assert 'Snow only' in av['questions']['action']['criteria'][av['expected']['action']]


def test_spec_extras():
    assert training.extras(training.EX124) == (training.c.TERA_KNOWLEDGE / 'train.jsonl',)
    assert training.extras(training.EX126) == (training.c.TERA_KNOWLEDGE / 'train.jsonl',
                                               training.c.EFFECT_KNOWLEDGE / 'train.jsonl')
    assert training.extras(training.EX121) == ()
    assert training.EX126.gpu == (2, 'GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4')
