"""EP-223 (D-200): loop-break weights, the stalled-loop serving rule, the v7 opponent-set facts and text."""
import json

from integration.laya_imitation import compact_v6, compact_v7, features_v5, features_v7, loop_decision, loop_weights
from integration.laya_imitation import serving
from integration.laya_imitation.tests.test_compact_v6 import StubCalc, case


def snapshot(name):
    return json.loads(case(name).body['state'])['snapshot']


def test_existing_renderers_are_unchanged():
    assert serving.renderer_matches_dataset('v6s') and serving.renderer_matches_dataset('v6h')


def test_loop_weights_classify():
    me = 'ME tinglu [dark ground] 90% | moves ruination | streak ruination x3 (opp hp 33>23>40)'
    assert loop_weights.classify(me, 'move:ruination:normal') == 'stall_repeat'
    assert loop_weights.classify(me, 'switch:2') == 'stall_break'
    assert loop_weights.classify(me.replace('33>23>40', '60>45>30'), 'switch:2') == 'progress'
    assert loop_weights.classify('ME tinglu [dark ground] 90% | moves ruination', 'switch:2') == 'none'
    weights, counts = loop_weights.weigh([dict(sample_id='a', state=me, expected=dict(action='switch:2')),
                                          dict(sample_id='b', state=me, expected=dict(action='move:ruination:tera'))])
    assert counts['stall_break'] == 1 and abs(sum(weights.values()) / 2 - 1) < 1e-9
    assert weights['a'] == loop_weights.BREAK * weights['b']


def test_rule_needs_a_stalled_run():
    assert loop_decision.stalled_move(snapshot('b126t13')) is None   # no run yet
    assert loop_decision.stalled_move(snapshot('b126t15')) is None   # 53 -> 33: progress
    assert loop_decision.stalled_move(snapshot('b126t18')) == 'ruination'   # 33 > 23 > 18 > 40 after Roost


def test_rule_choice():
    ids = ['move:ruination:normal', 'move:ruination:tera', 'move:earthquake:normal', 'switch:2']
    p = {'move:ruination:normal': 0.6, 'move:ruination:tera': 0.05, 'move:earthquake:normal': 0.08, 'switch:2': 0.27}
    assert loop_decision.choose(ids, p, None) == ('move:ruination:normal', p, False)
    choice, decision, fired = loop_decision.choose(ids, p, 'ruination')
    assert fired and choice == 'switch:2' and decision['move:ruination:normal'] == 0.0
    assert abs(sum(decision.values()) - 1) < 1e-9 and max(ids, key=decision.get) == choice
    weak = dict(p, **{'switch:2': 0.09, 'move:earthquake:normal': 0.26, 'move:ruination:normal': 0.6})
    weak = {k: v / sum(weak.values()) for k, v in weak.items()}
    assert loop_decision.choose(ids, weak, 'ruination')[0] == 'move:earthquake:normal'
    none_left = {'move:ruination:normal': 0.85, 'move:ruination:tera': 0.07, 'move:earthquake:normal': 0.05,
                 'switch:2': 0.03}
    assert loop_decision.choose(ids, none_left, 'ruination') == ('move:ruination:normal', none_left, False)
    other_best = dict(p, **{'switch:2': 0.7, 'move:ruination:normal': 0.17})
    assert loop_decision.choose(ids, other_best, 'ruination')[2] is False


def test_rule_wraps_policy_and_keeps_model_probabilities():
    value = case('b126t18')
    ids = list(value.action_ids)
    probs = {k: 0.0 for k in ids}
    probs['move:ruination:normal'], probs['move:whirlwind:normal'] = 0.7, 0.3

    class Policy:
        def predict(self, v):
            return dict(action_ids=ids, probabilities=probs, choice='move:ruination:normal')
    out = loop_decision.decide(Policy())(value)
    assert out['choice'] == 'move:whirlwind:normal' and out['model_probabilities'] == probs
    assert out['loop_rule'] == dict(stalled_move='ruination', fired=True)


def test_v7_active_set_keeps_public_facts_and_watches_trick():
    foe = dict(species='gholdengo', ability='goodasgold', item=None, item_state=dict(state='unknown', item=None,
               cause=None), terastallized=False, tera_type=None, moves=[dict(id='makeitrain')])
    shown, watch = features_v7.active_set(foe, can_tera=False)
    assert shown['item'][0][0] == 'choicescarf' and shown['tera'] == []
    assert 'makeitrain' not in [m for m, _ in shown['moves']] and len(shown['moves']) <= features_v7.MOVE_LIMIT
    assert {'trick', 'choicescarf'} <= {k for k, _ in watch}
    removed = dict(foe, item_state=dict(state='removed', item='choicescarf', cause='knockoff'))
    shown, watch = features_v7.active_set(removed, can_tera=False)
    assert shown['item'] == [] and 'choicescarf' not in {k for k, _ in watch}


def test_v7_typechange_marks_hazards_at_max_layers_only():
    view = snapshot('b126t18')
    own = {m['slot']: m for m in view['own_team']}
    me = own[view['own_active_slot']]
    ids = ['move:spikes:normal', 'move:stealthrock:normal', 'move:ruination:normal']
    me['effects'] = {'typechange': True}
    view['opponent_side_conditions'] = {'spikes': 3}
    assert features_v7.typechange_failures(view, ids) == {'move:spikes:normal': 'fails'}
    view['opponent_side_conditions'] = {'spikes': 2, 'stealth_rock': 1}
    assert features_v7.typechange_failures(view, ids) == {'move:stealthrock:normal': 'fails'}
    me['effects'] = {}
    assert features_v7.typechange_failures(view, ids) == {}


def test_v7_text_only_appends():
    value = case('b126t18')
    facts = features_v5.compute(value, StubCalc())
    base, base_q = compact_v6.render(value, compact_v6.V6S_MODULES, facts)
    v7 = features_v7.compute(value)
    state, question = compact_v7.render(value, compact_v7.MODULES, facts, v7)
    assert compact_v7.render(value, compact_v6.V6S_MODULES, facts, v7) == (base, base_q)
    kept = [x for x in state.split('\n') if not x.startswith(('opp set: ', 'opp watch: '))]
    assert len(kept) == len(base.split('\n'))
    for new, old in zip(kept, base.split('\n')):
        if new.startswith('opp team: '):
            segments = [seg.split(' | likely ')[0] for seg in new[len('opp team: '):].split(' || ')]
            assert 'opp team: ' + ' || '.join(segments) == old
        else:
            assert new == old
    assert all(question['criteria'][k].startswith(base_q['criteria'][k]) for k in base_q['criteria'])
    assert ('opp set: ' in state) == (v7['active'] is not None)
