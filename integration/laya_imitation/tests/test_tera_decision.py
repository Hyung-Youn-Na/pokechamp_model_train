"""EX-140 (D-197): Tera-pooled decision (k = 1 / 3) and Tera defence text on `v2fix`, served from the EX-124 checkpoint;
the EX-071 player's argmax check holds; EX-139 fix reproduction; schedule and baseline."""
import threading

import pytest

from integration.laya_imitation import comparison as cmp
from integration.laya_imitation import config as c
from integration.laya_imitation import input_variants, serving, tera_decision as td
from integration.laya_imitation import tera_battle as tb
from integration.laya_imitation.storage import jsonl
from integration.laya_imitation.tests.test_compact_v5 import CASES, StubCalc, case
from integration.laya_imitation.tests.test_comparison_summary import base
from integration.pokechamp.imitation.player import http_json, validate_response

IDS = ['move:a:normal', 'move:a:tera', 'move:b:normal', 'move:b:tera', 'switch:2']


def test_pooled_moves_tera_mass_onto_the_best_tera_option():
    p = dict(zip(IDS, (0.40, 0.15, 0.20, 0.10, 0.15)))
    for k, tera in ((1, False), (2, True), (3, True)):
        d = td.pooled(IDS, p, k)
        assert abs(sum(d.values()) - 1) < 1e-12 and d['move:b:tera'] == 0.0
        assert (max(IDS, key=d.get) == 'move:a:tera') is tera
        assert max(IDS, key=d.get) in ('move:a:tera', 'move:a:normal')
    assert td.pooled(IDS, p, 1)['move:a:tera'] == pytest.approx(0.25)
    # no Tera option or no Tera mass: unchanged, so plain argmax
    plain = {'move:a:normal': 0.6, 'switch:2': 0.4}
    assert td.pooled(list(plain), plain, 3) == plain
    zero = dict(p, **{'move:a:tera': 0.0, 'move:b:tera': 0.0, 'move:a:normal': 0.65})
    assert td.pooled(IDS, zero, 3) == zero


def test_pooled_keeps_argmax_when_it_is_already_tera():
    p = dict(zip(IDS, (0.10, 0.45, 0.20, 0.05, 0.20)))
    for k in (1, 3):
        d = td.pooled(IDS, p, k)
        assert max(IDS, key=d.get) == max(IDS, key=p.get) == 'move:a:tera'


class FixedPolicy:
    """Puts 0.3 on the first normal move, 0.25 on its Tera twin, the rest spread evenly."""

    def predict(self, value):
        ids = list(value.action_ids)
        first = next(k for k in ids if k.endswith(':normal'))
        rest = (1 - 0.55) / (len(ids) - 2)
        probs = {k: 0.3 if k == first else 0.25 if k == first[:-7] + ':tera' else rest for k in ids}
        return dict(input_sha256=value.sha256, action_ids=ids, probabilities=probs, choice=first)


@pytest.mark.parametrize('model,tera', [('laya-v2t-fix-tp1', True), ('laya-v2t-fix-tp3', True),
                                        ('laya-v2t-fix-tdef', False)])
def test_served_choice_passes_the_player_argmax_check(model, tera):
    value = case('nhj23_t4')
    s = serving.create_server(c.MODEL_DIR, model, policy=FixedPolicy(), render=cmp.RENDER[model])
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        url = 'http://127.0.0.1:%d' % s.server_address[1]
        body = http_json(url, '/evaluate', body=dict(model=model, input=value.body))
        choice, probabilities = validate_response(body, value, model=model,
                                                  checkpoint_sha256=s.model_identity['checkpoint_sha256'])
        assert choice.endswith(':tera') is tera
        if model in td.FACTORS:
            assert s.model_identity['decision']['factor'] == td.FACTORS[model]
            assert max(body['model_probabilities'], key=body['model_probabilities'].get).endswith(':normal')
        else:
            assert 'decision' not in s.model_identity and 'model_probabilities' not in body
    finally:
        s.shutdown()
        s.server_close()


def test_defence_text_only_on_tera_options():
    for name in CASES:
        value = case(name)
        (s0, q0), (s1, q1) = input_variants.renderer('v2fix', StubCalc())(value), td.renderer(StubCalc())(value)
        assert s0 == s1
        changed = [k for k in q0['criteria'] if q0['criteria'][k] != q1['criteria'][k]]
        assert changed == [k for k in value.action_ids if k.endswith(':tera')], name
        for k in changed:
            before, after = q0['criteria'][k], q1['criteria'][k]
            assert after.replace(td.defence_text(value)[k], '', 1) == before
            assert '; takes ' in after and after.index('; takes ') > after.index('; terastallize ')
    # NHJ 23 T4: Clodsire (Tera Dark) against Gholdengo (steel ghost)
    assert td.defence_text(case('nhj23_t4'))['move:earthquake:tera'] == '; takes steel x1 ghost x0.5; worst x0.5'


def test_tdef_identity_names_the_added_text():
    s = serving.create_server(c.MODEL_DIR, 'laya-v2t-fix-tdef', policy=FixedPolicy(), render='v2fixtd')
    try:
        ident = s.model_identity
        assert ident['render']['render'] == 'laya-compact-v5[damage,moves,speed,switch]+' + td.TEXT
        assert 'tera_decision.py' in ident['renderer_sources'] and ident['trained_render']
    finally:
        s.server_close()
    assert serving.renderer_matches_dataset('v2fixtd')


def test_ex140_schedule_and_servings():
    study = tb.EX140
    rows = cmp.make_schedule(base(), study)
    assert len(rows) == 384 and {r['model'] for r in rows} == set(study.models)
    assert {sum(r['model'] == m for r in rows) for m in study.models} == {128}
    assert set(study.models) | {study.mock_model} <= set(serving.MODELS)
    assert [cmp.RENDER[m] for m in study.models] == ['v2fix', 'v2fix', 'v2fixtd'] and cmp.RENDER[study.mock_model] == 'v2fix'
    assert {run for _, run in study.runs.values()} == {c.RUN_TERA_TRAINING}
    assert study.gpu == (1, 'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454') and study.port == 8109


def test_rule_replays_ex139_fix_counterfactual():
    """On the EX-139 fix logs the pooled rule would first pick Tera in 47 (k=1) / 95 (k=3) of 128 games, and every
    EX-139 fix slot replays itself (the rule-effect check counts `not_fired_same`)."""
    rows, outcomes = tb.baseline_rows()
    fired = {1: 0, 3: 0}
    for r in rows:
        for k in fired:
            for e in jsonl(tb.BASELINE[1] / 'games' / r['slot_id'] / 'events.jsonl'):
                if e['type'] == 'selection' and e.get('probabilities'):
                    p = e['probabilities']
                    d = td.pooled(list(p), p, k)
                    if max(p, key=d.get).endswith(':tera'):
                        fired[k] += 1
                        break
    assert fired == {1: 47, 3: 95}
    effect = tb.rule_effect(tb.BASELINE[1], rows, outcomes, rows, outcomes)['laya-v2t-fix']
    assert effect == dict(slots=128, fired=0, fired_same=0, not_fired=128, not_fired_same=128)
