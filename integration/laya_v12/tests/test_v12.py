"""EP-237 unit checks: one per foul-play rule (`observe`), the conditioned usage entry (`sets`), and the text marks."""
from integration.laya_v12 import observe, sets

DEX = dict(
    species=dict(
        dragonite=dict(abilities=['innerfocus', 'multiscale'], base=dict(hp=91, atk=134, spa=100, spe=80), types=['dragon', 'flying']),
        greattusk=dict(abilities=['protosynthesis'], base=dict(hp=115, atk=131, spa=53, spe=87), types=['ground', 'fighting']),
        gyarados=dict(abilities=['intimidate', 'moxie'], base=dict(hp=95, atk=125, spa=60, spe=81), types=['water', 'flying']),
        zoroarkhisui=dict(abilities=['illusion'], base=dict(hp=55, atk=100, spa=125, spe=110), types=['normal', 'ghost'])),
    moves=dict(earthquake=dict(category='physical', power=100, priority=0, type='ground'),
               headlongrush=dict(category='physical', power=120, priority=0, type='ground'),
               dragondance=dict(category='status', power=0, priority=1 - 1, type='dragon'),
               roost=dict(category='status', power=0, priority=0, type='flying'),
               extremespeed=dict(category='physical', power=80, priority=2, type='normal'),
               rapidspin=dict(category='physical', power=50, priority=0, type='normal'),
               stealthrock=dict(category='status', power=0, priority=0, type='rock'),
               waterfall=dict(category='physical', power=80, priority=0, type='water')))


def own(species='greattusk', spe_ev=252, nature='jolly', item='boosterenergy'):
    return dict(species=species, slot=1, original_set=dict(evs=dict(spe=spe_ev), nature=nature, item=item, level=100))


def snap(events, opp=('dragonite',), own_mon=None):
    return dict(own_team=[own_mon or own()], opponent_team=[dict(species=s, slot=i + 1) for i, s in enumerate(opp)],
                history=events, early_history=[])


def ev(turn, event, *args):
    return dict(turn=turn, event=event, args=list(args))


def start(turn=1, opp='Dragonite'):
    return [ev(turn, 'turn', str(turn)), ev(turn, 'switch', '@self', 'Great Tusk', '100/100'),
            ev(turn, 'switch', '@opponent', opp, '100/100')]


def test_speed_bounds_from_order():
    # Great Tusk jolly 252 = 300; Dragonite moved first with a same-priority move -> its speed >= 300
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Earthquake', '@self'), ev(2, '-damage', '@self', '60/100'),
                   ev(2, 'move', '@self', 'Headlong Rush', '@opponent'), ev(2, '-damage', '@opponent', '40/100'), ev(2, 'upkeep')]
    o = observe.observe(snap(e), DEX)
    assert o.foe("dragonite").speed == [300, 10 ** 9]


def test_speed_skips_priority_and_switch_turns():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Extreme Speed', '@self'), ev(2, '-damage', '@self', '80/100'),
                   ev(2, 'move', '@self', 'Headlong Rush', '@opponent'), ev(2, '-damage', '@opponent', '40/100')]
    o = observe.observe(snap(e), DEX)
    assert o.foe('dragonite').speed == [0, 10 ** 9]


def test_two_moves_rule_out_choice_and_status_rules_out_vest():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Dragon Dance', '@opponent'), ev(2, 'upkeep'),
                   ev(3, 'turn', '3'), ev(3, 'move', '@opponent', 'Earthquake', '@self'), ev(3, '-damage', '@self', '50/100'), ev(3, 'upkeep')]
    f = observe.observe(snap(e), DEX).foe('dragonite')
    assert {'choiceband', 'choicespecs', 'choicescarf', 'assaultvest'} <= f.no_items
    assert 'lifeorb' in f.no_items          # a hit without Life Orb recoil


def test_upkeep_below_full_rules_out_leftovers_and_orbs():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@self', 'Headlong Rush', '@opponent'), ev(2, '-damage', '@opponent', '70/100'), ev(2, 'upkeep')]
    f = observe.observe(snap(e), DEX).foe('dragonite')
    assert {'leftovers', 'blacksludge', 'flameorb', 'toxicorb'} <= f.no_items


def test_switch_in_without_announcement():
    e = start(opp='Gyarados')
    f = observe.observe(snap(e, opp=('gyarados',)), DEX).foe('gyarados')
    assert 'intimidate' in f.no_abilities and {'airballoon', 'boosterenergy'} <= f.no_items
    e2 = [ev(1, 'turn', '1'), ev(1, 'switch', '@self', 'Great Tusk', '100/100'), ev(1, 'switch', '@opponent', 'Gyarados', '100/100'),
          ev(1, '-ability', '@opponent', 'Intimidate', 'boost')]
    assert 'intimidate' not in observe.observe(snap(e2, opp=('gyarados',)), DEX).foe('gyarados').no_abilities


def test_boots_from_stealth_rock():
    rocks = [ev(1, 'turn', '1'), ev(1, 'switch', '@self', 'Great Tusk', '100/100'), ev(1, 'switch', '@opponent', 'Gyarados', '100/100'),
             ev(1, 'move', '@self', 'Stealth Rock', '@opponent'), ev(1, '-sidestart', 'opponent', 'move: Stealth Rock')]
    took = rocks + [ev(2, 'turn', '2'), ev(2, 'switch', '@opponent', 'Dragonite', '100/100'),
                    ev(2, '-damage', '@opponent', '75/100', '[from] Stealth Rock')]
    clean = rocks + [ev(2, 'turn', '2'), ev(2, 'switch', '@opponent', 'Dragonite', '100/100')]
    assert 'heavydutyboots' in observe.observe(snap(took, opp=('gyarados', 'dragonite')), DEX).foe('dragonite').no_items
    assert observe.observe(snap(clean, opp=('gyarados', 'dragonite')), DEX).foe('dragonite').boots


def test_timers_and_illusion():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Tailwind', '@opponent'), ev(2, '-sidestart', 'opponent', 'move: Tailwind'),
                   ev(2, 'upkeep'), ev(3, 'turn', '3')]
    o = observe.observe(snap(e, opp=('dragonite', 'zoroarkhisui')), DEX)
    assert any(t['label'] == 'opp tailwind' and t['left'] == 3 for t in o.timers) and o.zoroark_hidden


def test_illusion_break_drops_facts_gathered_under_the_disguise():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Dragon Dance', '@opponent'), ev(2, 'upkeep'),
                   ev(3, 'turn', '3'), ev(3, 'replace', '@opponent', 'Zoroark-Hisui', '100/100')]
    o = observe.observe(snap(e, opp=('dragonite', 'zoroarkhisui')), DEX)
    assert o.illusion_broken and 'assaultvest' not in o.foe('dragonite').no_items


def test_conditioned_entry_filters_and_reweights():
    foe = observe.Foe(no_items={'leftovers'})
    entry = dict(items=dict(leftovers=0.5, heavydutyboots=0.3, choicescarf=0.2), abilities=dict(multiscale=1.0),
                 spreads={'Adamant:0/252/0/0/4/252': 0.5, 'Jolly:0/252/0/0/4/252': 0.5}, moves=dict(earthquake=1.0), tera_types={})
    mon = dict(species='nosuchsetspecies', moves=[], ability=None, item=None, tera_type=None, item_state=dict(state='unknown'))
    out, info = sets.conditioned(entry, mon, foe, dict(own_team=[]), None, DEX)
    assert 'leftovers' not in out['items'] and abs(sum(out['items'].values()) - 1) < 1e-9
    assert info['ruled_out'] == ['leftovers']
    # speed above any plain spread of a base-80 foe -> Choice Scarf
    fast = observe.Foe(speed=[300, 10 ** 9])
    mon2 = dict(mon, species='dragonite')
    out2, _ = sets.conditioned(entry, dict(mon2, species='nosuchsetspecies'), fast, dict(own_team=[]), None,
                               dict(DEX, species=dict(DEX['species'], nosuchsetspecies=DEX['species']['dragonite'])))
    assert out2['items'].get('choicescarf', 0) > 0.99


def test_damage_consistency_margins():
    hit = dict(before=100.0, after=60.0)
    assert sets._consistent(dict(min=35.0, max=42.0), hit)
    assert not sets._consistent(dict(min=50.0, max=60.0), hit)
    ko = dict(before=30.0, after=0.0)
    assert sets._consistent(dict(min=20.0, max=29.0), ko) and not sets._consistent(dict(min=10.0, max=20.0), ko)


def test_screen_timer_records_setter_and_extension():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Reflect', '@opponent'),
                   ev(2, '-sidestart', 'opponent', 'Reflect'), ev(2, 'upkeep'), ev(3, 'turn', '3')]
    t = next(t for t in observe.observe(snap(e), DEX).timers if t['label'] == 'opp reflect')
    assert (t['left'], t['ext_left'], t['ext_item'], t['setter']) == (4, 7, 'lightclay', ('opp', 'dragonite'))


def test_wish_and_future_sight_turns():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Wish', '@opponent'),
                   ev(2, 'move', '@self', 'Future Sight', '@opponent'), ev(2, '-start', '@self', 'move: Future Sight'),
                   ev(2, 'upkeep'), ev(3, 'turn', '3')]
    t = {x['label']: x['left'] for x in observe.observe(snap(e), DEX).timers}
    assert t['opp wish'] == 1 and t['my futuresight'] == 2


def test_joint_sets_need_public_information():
    foe = observe.Foe()
    entry = dict(items=dict(leftovers=1.0), abilities=dict(multiscale=1.0), spreads={}, moves=dict(earthquake=1.0), tera_types={})
    mon = dict(species='dragonite', moves=[], ability=None, item=None, tera_type=None, item_state=dict(state='unknown'))
    out, info = sets.conditioned(entry, mon, foe, dict(own_team=[]), None, DEX)
    assert out['items'] == dict(leftovers=1.0) and info['sets'] == 0


def test_my_speed_ability_skips_the_turn():
    e = [ev(1, 'turn', '1'), ev(1, 'switch', '@self', 'Venusaur', '100/100'), ev(1, 'switch', '@opponent', 'Dragonite', '100/100'),
         ev(1, '-weather', 'SunnyDay'), ev(2, 'turn', '2'), ev(2, 'move', '@self', 'Earthquake', '@opponent'),
         ev(2, '-damage', '@opponent', '60/100'), ev(2, 'move', '@opponent', 'Earthquake', '@self'), ev(2, '-damage', '@self', '60/100')]
    dex = dict(DEX, species=dict(DEX['species'], venusaur=dict(abilities=['chlorophyll'], base=dict(spe=80), types=['grass'])))
    own_mon = dict(species='venusaur', slot=1, ability='chlorophyll', original_set=dict(evs=dict(spe=252), nature='timid', level=100))
    assert observe.observe(snap(e, own_mon=own_mon), dex).foe('dragonite').speed == [0, 10 ** 9]


def test_damage_cache_overflow_keeps_lookups_valid():
    class Calc:
        def run(self, reqs):
            return [dict(min=30.0, max=40.0) for _ in reqs]
    hit = dict(direction='dealt', move='earthquake', me='greattusk', me_boosts={}, foe_boosts={}, me_status='',
               foe_status='', me_hp=100.0, foe_hp=100.0, before=100.0, after=65.0, me_tera=None, foe_tera=None,
               weather=None, terrain=None, screens=dict(self={}, opp={}))
    foe = observe.Foe(hits=[hit])
    cand = dict(tera='', ability='multiscale', item='leftovers', nature='adamant', evs=dict(atk=252), moves=frozenset(), w=1.0)
    snap_ = dict(own_team=[dict(own(), ability='protosynthesis', item='boosterenergy', boosts={}, status=None,
                                hp_percent=100.0, terastallized=False, tera_type='ground')])
    mon = dict(species='dragonite')
    sets._damage_cache.clear()
    sets.damage_fit([cand], mon, foe, snap_, Calc())
    old = sets.CACHE_LIMIT
    try:
        sets.CACHE_LIMIT = 0
        kept, removed = sets.damage_fit([cand, dict(cand, item='choiceband')], mon, foe, snap_, Calc())
        assert len(kept) == 2 and removed == 0
    finally:
        sets.CACHE_LIMIT = old


def test_sideend_with_from_move_clears_stealth_rock():
    e = [ev(1, 'turn', '1'), ev(1, 'switch', '@self', 'Great Tusk', '100/100'), ev(1, 'switch', '@opponent', 'Gyarados', '100/100'),
         ev(1, '-sidestart', 'opponent', 'move: Stealth Rock'), ev(1, 'upkeep'),
         ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Rapid Spin', '@self'),
         ev(2, '-sideend', 'opponent', 'Stealth Rock', '[from] move: Rapid Spin', '[of] @opponent'), ev(2, 'upkeep'),
         ev(3, 'turn', '3'), ev(3, 'switch', '@opponent', 'Dragonite', '100/100')]
    assert not observe.observe(snap(e, opp=('gyarados', 'dragonite')), DEX).foe('dragonite').boots


def test_paralysis_threshold_direction():
    # my Great Tusk (300) moved second against a paralysed foe: its effective speed > 300, so its own speed > 600
    e = start() + [ev(1, '-status', '@opponent', 'par'), ev(1, 'upkeep'), ev(2, 'turn', '2'),
                   ev(2, 'move', '@opponent', 'Earthquake', '@self'), ev(2, '-damage', '@self', '60/100'),
                   ev(2, 'move', '@self', 'Headlong Rush', '@opponent'), ev(2, '-damage', '@opponent', '40/100')]
    assert observe.observe(snap(e), DEX).foe('dragonite').speed == [600, 10 ** 9]


def test_revealed_leftovers_keeps_the_joint_sets():
    # Leftovers healed before upkeep and the foe is still below full: the held item is known, nothing is ruled out
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@self', 'Headlong Rush', '@opponent'), ev(2, '-damage', '@opponent', '50/100'),
                   ev(2, '-heal', '@opponent', '56/100', '[from] item: Leftovers'), ev(2, 'upkeep')]
    f = observe.observe(snap(e), DEX).foe('dragonite')
    assert f.item_seen and 'leftovers' not in f.no_items


def test_residual_damage_after_full_hp_does_not_rule_out_leftovers():
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@self', 'Rapid Spin', '@opponent'), ev(2, '-fail', '@opponent'),
                   ev(2, '-damage', '@opponent', '94/100 brn', '[from] brn'), ev(2, 'upkeep')]
    assert 'leftovers' not in observe.observe(snap(e), DEX).foe('dragonite').no_items


def test_move_result_window_stops_at_the_next_move():
    # my move misses; the foe's next move crits: my move's window must not take the crit or the foe's damage
    e = start() + [ev(2, 'turn', '2'), ev(2, 'move', '@opponent', 'Earthquake', '@self', '[miss]'), ev(2, '-miss', '@opponent', '@self'),
                   ev(2, 'move', '@self', 'Headlong Rush', '@opponent'), ev(2, '-crit', '@opponent'), ev(2, '-damage', '@opponent', '30/100')]
    f = observe.observe(snap(e), DEX).foe('dragonite')
    assert 'lifeorb' not in f.no_items and not f.hits


def test_known_item_candidates_ignore_item_rules():
    foe = observe.Foe(no_items={'leftovers'}, item_seen=True)
    mon = dict(species='dragonite', moves=[], ability=None, item='leftovers', tera_type=None,
               item_state=dict(state='held', item='leftovers'))
    sets.load.cache_clear()
    orig = sets.load
    sets.load = lambda: dict(dragonite=[dict(tera='normal', ability='multiscale', item='leftovers', nature='adamant',
                                             evs=dict(spe=252), moves=frozenset(), w=1.0)])
    try:
        assert len(sets.candidates(mon, foe, None)) == 1
    finally:
        sets.load = orig
