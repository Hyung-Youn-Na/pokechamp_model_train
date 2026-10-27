"""EX-139 (D-196): EX-124 served on D-195-corrected inputs. `v2fix` keeps the v2 format with corrected values, `v2info`
adds the v5 wording; serving identity; EX-125 same-slot verdict; Sleep Talk and Air Balloon protocol counts."""
import json
import re

import pytest

from integration.laya_imitation import comparison as cmp
from integration.laya_imitation import compact_v2, compact_v5, features, features_v5, input_variants, serving
from integration.laya_imitation import variant_battle as vb
from integration.laya_imitation import config as c
from integration.laya_imitation.tests.test_compact_v5 import CASES, StubCalc, case, line
from integration.laya_imitation.tests.test_comparison_summary import base, outcome
from integration.laya_imitation.tests.test_serving import UniformPolicy
from integration.pokechamp.imitation.schema import ImitationInput

V5_WORDING = re.compile(r'item none \(|balloon\?| (slp|tox) t\d|(weather \w+|_terrain|room|veil|screen|reflect|tailwind) t\d')


@pytest.fixture(scope='module')
def calc():
    with features.Calc() as worker:
        yield worker


def v2(value, calc):
    return compact_v2.render(value, compact_v2.MODULES, features.compute(value, calc))


def label(text):
    """A state line's label: `ME`, `OPP`, `my team:`, ... (the part before the first species/value)."""
    return text.split(' ', 1)[0]


def test_fix_keeps_the_v2_format_and_info_adds_v5_wording():
    for name in CASES:
        value = case(name)
        facts = features_v5.compute(value, StubCalc())
        (s0, q0), (s1, q1) = v2(value, StubCalc()), input_variants.renderer('v2fix', StubCalc())(value)
        assert [label(x) for x in s1.split('\n')] == [label(x) for x in s0.split('\n')]
        assert list(q1['criteria']) == list(q0['criteria'])
        assert not V5_WORDING.search(s1 + json.dumps(q1)), name
        assert (s1, q1) == compact_v5.render(value, input_variants.V2_MODULES, facts)
        info = input_variants.renderer('v2info', StubCalc())(value)
        assert info == compact_v5.render(value, input_variants.RENDERS['v2info'], facts)
        assert '; fails' not in json.dumps(info) and '; out ' not in json.dumps(info)   # no v4 modules


def test_fix_corrects_values_only(calc):
    # NHJ 23 T13: Gholdengo's balloon was popped at T10; v2 still computed Earth Power as 0%.
    value = case('nhj23_t13')
    old = v2(value, calc)[1]['criteria']['move:earthpower:normal']
    fixed_state, fixed = input_variants.renderer('v2fix', calc)(value)
    assert 'dmg 0-0%' in old
    assert fixed['criteria']['move:earthpower:normal'].startswith('ground special 90 x2;')
    assert 'dmg 0-0%' not in fixed['criteria']['move:earthpower:normal']
    assert 'item none' not in fixed_state
    # NHJ 25 T10: a revealed held balloon makes Earthquake x0; the v2 text keeps no `; fails` (a v4 module).
    _, fixed = input_variants.renderer('v2fix', calc)(case('nhj25_t10'))
    assert ' x0 ' in fixed['criteria']['move:earthquake:normal']
    assert not fixed['criteria']['move:earthquake:normal'].endswith('; fails')


def test_info_shows_item_state_and_counters(calc):
    state, _ = input_variants.renderer('v2info', calc)(case('nhj23_t13'))
    assert 'item none (popped)' in line(state, 'OPP gholdengo')
    state, _ = input_variants.renderer('v2info', calc)(case('ex131_t106'))
    assert line(state, 'OPP ').startswith('OPP dondozo [water] 94% slp t1 rest |')
    assert state.split('\n')[0].endswith('| field grassy_terrain t2')


def test_variants_refuse_inputs_without_parser_fields():
    with open(c.EX071_PREPARED / 'validation.jsonl') as f:
        value = ImitationInput.from_body(json.loads(next(f))['input'])
    for render in input_variants.RENDERS:
        with pytest.raises(ValueError):
            input_variants.renderer(render, StubCalc())(value)


def test_serving_identity_names_actual_and_trained_render():
    assert serving.renderer_matches_dataset('v2fix') and serving.renderer_matches_dataset('v2info')
    for model, render in (('laya-v2t-fix', 'v2fix'), ('laya-v2t-info', 'v2info')):
        s = serving.create_server(c.MODEL_DIR, model, policy=UniformPolicy(), render=render)
        try:
            ident = s.model_identity
            assert ident['render']['render'] == compact_v5.version_name(input_variants.RENDERS[render])
            assert ident['trained_render'] == serving.read(c.V2_DATASET / 'manifest.json')['render']
            assert set(ident['renderer_sources']) == set(serving.V5_RENDER_FILES)
            assert ident['head_limit'] == c.V2_HEAD_LIMIT
        finally:
            s.server_close()
    # the existing renders keep their identity fields
    s = serving.create_server(c.MODEL_DIR, 'laya-v2t', policy=UniformPolicy(), render='v2')
    try:
        assert 'trained_render' not in s.model_identity and 'renderer_sources' not in s.model_identity
    finally:
        s.server_close()


def test_ex139_schedule_and_served_models():
    study = vb.EX139
    rows = cmp.make_schedule(base(), study)
    assert len(rows) == 256 and {r['model'] for r in rows} == set(study.models)
    assert all(r['slot_id'].startswith(('v2t-fix-', 'v2t-info-')) for r in rows)
    assert set(study.models) | {study.mock_model} <= set(serving.MODELS)
    assert {cmp.RENDER[m] for m in study.models} == set(input_variants.RENDERS)
    assert cmp.RENDER[study.mock_model] == 'v2info'
    assert {run for _, run in study.runs.values()} == {c.RUN_TERA_TRAINING}
    assert study.gpu == (1, 'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454') and study.port == 8109


def test_versus_baseline_and_verdict():
    rows = cmp.make_schedule(base(), vb.EX139)
    fix = [r for r in rows if r['model'] == 'laya-v2t-fix']
    baseline = {r['base_slot_id']: 0.0 for r in fix}
    outcomes = [outcome(r, 'win') for r in fix]
    block = vb.versus_baseline(rows, outcomes, 'laya-v2t-fix', baseline)
    assert block['slots'] == 128 and block['mean_diff'] == 1.0 and block['variant_better'] == 128
    summary = dict(status=dict(completed=128))
    assert vb.verdict(summary, block) == vb.EX139.verdicts[0]
    block = vb.versus_baseline(rows, [outcome(r, 'loss') for r in fix], 'laya-v2t-fix', {k: 1.0 for k in baseline})
    assert vb.verdict(summary, block) == vb.EX139.verdicts[1]
    mixed = [outcome(r, 'win' if i % 2 else 'loss') for i, r in enumerate(fix)]
    block = vb.versus_baseline(rows, mixed, 'laya-v2t-fix', {k: 0.5 for k in baseline})
    assert vb.verdict(summary, block) == vb.EX139.verdicts[2]
    assert vb.verdict(dict(status=dict(completed=119)), block).startswith('판정 보류')


def _game(tmp_path, slot, protocol):
    game = tmp_path / 'games' / slot
    game.mkdir(parents=True)
    (game / 'events.jsonl').write_text(json.dumps(dict(type='protocol', protocol='\n'.join(protocol))) + '\n')
    return dict(slot_id=slot, model='laya-v2t-info'), dict(slot_id=slot, model_side='p1')


def test_sleep_talk_failure_causes(tmp_path):
    row, out = _game(tmp_path, 'v2t-info-m01-s1-a', [
        '|turn|5', '|-curestatus|p1a: Dondozo|slp|[msg]', '|move|p1a: Dondozo|Sleep Talk|p1a: Dondozo',
        '|-fail|p1a: Dondozo',
        '|turn|6', '|move|p1a: Dondozo|Sleep Talk|p1a: Dondozo', '|-fail|p1a: Dondozo',
        '|turn|7', '|cant|p1a: Dondozo|slp', '|move|p1a: Dondozo|Sleep Talk|p1a: Dondozo',
        '|move|p1a: Dondozo|Wave Crash|p2a: Gliscor|[from] move: Sleep Talk',
        '|turn|8', '|-curestatus|p2a: Gliscor|slp|[msg]', '|move|p2a: Gliscor|Sleep Talk|p2a: Gliscor',
        '|-fail|p2a: Gliscor'])
    got = vb.sleep_talk(tmp_path, [row], [out])['laya-v2t-info']
    assert got == dict(games=1, used=3, failed=2, woke=1, asleep=0, awake=1)


def test_ground_moves_into_a_revealed_balloon(tmp_path):
    row, out = _game(tmp_path, 'v2t-info-m01-s1-a', [
        '|switch|p2a: Gholdengo|Gholdengo, L100|100/100', '|-item|p2a: Gholdengo|Air Balloon',
        '|turn|1', '|move|p1a: Garchomp|Earthquake|p2a: Gholdengo', '|-immune|p2a: Gholdengo',
        '|turn|2', '|move|p1a: Garchomp|Stone Edge|p2a: Gholdengo', '|-enditem|p2a: Gholdengo|Air Balloon',
        '|turn|3', '|move|p1a: Garchomp|Earthquake|p2a: Gholdengo', '|-damage|p2a: Gholdengo|40/100'])
    got = vb.balloon_ground(tmp_path, [row], [out])['laya-v2t-info']
    assert got == dict(games=1, ground=2, immune=1, vs_balloon=1, vs_balloon_immune=1)
