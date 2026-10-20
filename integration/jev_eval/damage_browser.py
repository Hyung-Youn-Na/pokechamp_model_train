"""At most five offline representative screens per damage-viewer edition."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from integration.jev27b.study import file_hash, write_json
from . import damage_data, viewer


def _packet(folder, data, index):
    return damage_data.read_script(folder / data['damage_index'][data['decisions'][index]['id']]['src'])


def _samples(output):
    maximum = None
    same = None
    zero = None
    branches = None
    for path in sorted(output.glob('battle-*/decisions.json'), key=lambda p: int(p.parent.name.split('-')[1])):
        data = json.loads(path.read_text())
        for index, decision in enumerate(data['decisions']):
            count = data['damage_index'][decision['id']]['calculations']
            if maximum is None or count > maximum[0]:
                maximum = (count, path.parent, index)
            if same is None and decision['kind'] == 'turn_action' and any(
                    d['turn'] == decision['turn'] and d['kind'] == 'forced_switch' for d in data['decisions']):
                same = (path.parent, index)
            if count and (zero is None or branches is None):
                packet = _packet(path.parent, data, index)
                rows = packet['damage']['calculations']
                if zero is None and any(r.get('result', {}).get('damage_range_hp') == [0, 0] for r in rows):
                    zero = (path.parent, index)
                if branches is None and {r['direction'] for r in rows} == {'incoming', 'outgoing'} and {
                        r['branch'] for r in rows} == {'current', 'self_tera', 'opponent_tera', 'both_tera'}:
                    branches = (path.parent, index)
    if maximum is None or same is None or zero is None or branches is None:
        raise ValueError('required actual damage representative category is missing')
    return dict(maximum_scenarios=maximum[1:], same_turn=same, zero_damage=zero, bidirectional_tera=branches)


def _synthetic(data, original_packet, target):
    """Explicitly marked display-only examples for errors absent from these real runs."""
    value = copy.deepcopy(data)
    base = next(d for d in value['decisions'] if d['kind'] == 'turn_action')
    value.update(synthetic=True, decisions=[], damage_index={})
    value['turn_log'].update(terminal=None, terminal_label='합성 표시 검사', row_count=0,
        turns=[dict(turn=n, label=f'합성 {n}턴', rows=[], decision_ids=[]) for n in range(3)], decision_cutoffs={})
    packets = []
    for ordinal, status in enumerate(('not_calculated', 'available', 'not_calculated', 'missing', 'unsupported_format'), 1):
        d = copy.deepcopy(base)
        d.update(id=f'synthetic-{ordinal}', turn=0 if ordinal == 1 else 1,
                 kind='lead' if ordinal == 1 else 'forced_switch' if ordinal == 3 else 'turn_action')
        p = d['request'] or d['observation']
        p['state'].update(turn=d['turn'], decision_kind=d['kind'])
        value['decisions'].append(d)
        value['turn_log']['turns'][d['turn']]['decision_ids'].append(d['id'])
        value['turn_log']['decision_cutoffs'][d['id']] = dict(sequence=0, line_index=0)
        packet = dict(version=damage_data.VERSION, experiment=value['experiment'], decision_id=d['id'],
            input_audit=None, status=status, reason=None, damage=None, synthetic=True)
        if status == 'not_calculated':
            packet.update(reason='lead_or_forced_switch_out_of_scope',
                damage=dict(version='jev-damage-sample-v1', calculations=[], unchanged_reason='lead_or_forced_switch_out_of_scope'))
        elif status == 'available':
            packet['damage'] = copy.deepcopy(original_packet['damage'])
            rows = packet['damage']['calculations'][:55]
            if len(rows) < 5:
                raise ValueError('synthetic display needs an actual scenario template')
            template = next(r for r in rows if isinstance(r.get('result', {}).get('damage_range_hp'), list))
            for n in (0, 1, 4):
                rows[n]['result'] = copy.deepcopy(template['result'])
                rows[n].pop('error', None)
            rows[0]['result'].update(damage_range_hp=[0, 0], ko_chance_given_hit=None, survival_given_hit=None)
            rows[1]['result'].update(damage_range_hp=None, defender_max_hp=None)
            rows[2] = dict(direction='outgoing', move='synthetic_failure', branch='current',
                           candidate_id=rows[0]['candidate_id'], error='synthetic_calculation_failed')
            rows[3]['result'] = dict(excluded_with_reason='synthetic_unsupported')
            rows[4]['result'].update(damage_range_hp=[20, 60], ko_chance_given_hit=0, survival_given_hit=1,
                damage_variants=[dict(hits=2, damage_range_hp=[20, 40], damage_rolls=[10, 20]),
                                 dict(hits=3, damage_range_hp=[30, 60], damage_rolls=[10, 20])])
            packet['damage']['calculations'] = rows
        elif status == 'missing':
            packet['reason'] = 'damage_not_recorded'
        else:
            packet.update(reason='unsupported_saved_damage_format', damage=dict(version='synthetic-unsupported'))
        reference = damage_data.descriptor(packet, ordinal)
        path = target / reference['src']; path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(damage_data.script_text(packet))
        value['damage_index'][d['id']] = dict(reference, sha256=file_hash(path))
        packets.append(packet)
    (target / 'index.html').write_text(viewer.render_data(value))
    write_json(target / 'decisions.json', value)
    return value, packets


def _ready(page, state='available'):
    page.wait_for_function('(state) => document.getElementById("damage-status").dataset.state === state', arg=state)


def _visible_indices(page):
    return page.locator('[data-damage-index]').evaluate_all('rows => rows.map(r => Number(r.dataset.damageIndex))')


def _check_summary(page, decision):
    state = (decision['request'] or decision['observation'])['state']
    expected = []
    for team in ('self_team', 'opponent_team'):
        for mon in state[team]:
            moves = mon.get('current_move_slots') or mon.get('moves')
            if mon.get('active') and isinstance(moves, list):
                expected.extend(m for m in moves if 'damage' in m)
    rows = page.locator('#damage-summary tbody tr')
    assert rows.count() == len(expected), 'visible model damage summary denominator differs'
    for index, move in enumerate(expected):
        text = rows.nth(index).inner_text()
        assert (move.get('name') or move.get('move') or move['id']) in text
        ranges = move['damage']['ranges']
        if isinstance(ranges, dict):
            for value in ranges.values():
                if value is not None:
                    assert f'{value[0]:g}–{value[1]:g}%' in text
        if ranges is None:
            assert '미제공' in text
            if isinstance(move['damage'].get('reason'), str):
                assert move['damage']['reason'] in text


def _check_filters(page, packet):
    rows = packet['damage']['calculations']
    assert _visible_indices(page) == list(range(min(50, len(rows))))
    if len(rows) > 50:
        page.click('#damage-next')
        assert _visible_indices(page) == list(range(50, min(100, len(rows))))
        page.click('#damage-previous')
    for field, selector in (('direction', 'direction'), ('move', 'move'), ('branch', 'branch'), ('candidate_id', 'candidate')):
        values = list(dict.fromkeys(r.get(field) for r in rows if r.get(field)))
        # One option for each direction and every Tera branch; one for move/set filters.
        chosen = values if field in ('direction', 'branch') else values[-1:]
        for choice in chosen:
            page.select_option('#damage-' + selector, choice)
            expected = [i for i, row in enumerate(rows) if row.get(field) == choice]
            assert _visible_indices(page) == expected[:50], 'filter changed the original scenario order'
            assert '1 /' in page.locator('#damage-page').inner_text()
        page.select_option('#damage-' + selector, '')
    # Combined filter intersections, including a valid row and an empty result if available.
    selected = rows[-1]
    for field, name in (('direction','direction'),('move','move'),('branch','branch'),('candidate_id','candidate')):
        page.select_option('#damage-' + name, selected[field])
    expected = [i for i,r in enumerate(rows) if all(r.get(k) == selected[k] for k in ('direction','move','branch','candidate_id'))]
    assert _visible_indices(page) == expected[:50]
    other = next((r['move'] for r in rows if r['move'] != selected['move'] and not any(
        t['move'] == r['move'] and all(t[k] == selected[k] for k in ('direction','branch','candidate_id')) for t in rows)), None)
    if other:
        page.select_option('#damage-move', other)
        assert not _visible_indices(page) and '필터에 맞는' in page.locator('#damage-table').inner_text()
    page.click('#damage-reset')
    assert _visible_indices(page) == list(range(min(50, len(rows))))


def _copy_download(page, kind, expected, temporary):
    page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true,value:{writeText:async text=>{window.copiedDamage=text}}})")
    page.click(f'[data-copy="{kind}"]')
    assert json.loads(page.evaluate('window.copiedDamage')) == expected
    with page.expect_download() as pending:
        page.click(f'[data-download="{kind}"]')
    download = pending.value
    path = temporary / download.suggested_filename
    download.save_as(path)
    assert json.loads(path.read_text()) == expected
    path.unlink()


def _detail(page, ordinal, row):
    element = page.locator(f'[data-damage-index="{ordinal}"] details')
    element.evaluate('node => node.open = true')
    page.wait_for_function('(n) => document.querySelector(`[data-damage-index="${n}"] details`).dataset.rendered === "true"', arg=ordinal)
    raw = element.locator('pre').last.inner_text()
    assert json.loads(raw) == row, 'scenario detail lost condition/result/error fields'
    return element


def check_saved_screen(page, folder, data, index, temporary, *, filters=False):
    """Check saved calculations within an existing representative battle screen."""
    if index is None:
        page.click('#damage-tab')
        _ready(page, 'no_decision')
        assert page.evaluate('window.jevDamageView.value()') is None
        assert all(button.is_disabled() for button in page.locator(
            '[data-copy="damage"],[data-download="damage"]').all())
        return dict(decision=None, status='no_decision', calculations=0, filters_checked=False,
                    exact_json_copy_download=False)
    d = data['decisions'][index]
    packet = _packet(folder, data, index)
    page.select_option('#decision', str(index))
    page.click('#damage-tab')
    _ready(page, packet['status'])
    assert d['id'] in page.locator('#damage-status').inner_text()
    _check_summary(page, d)
    copied = packet['damage'] is not None
    if copied:
        _copy_download(page, 'damage', packet['damage'], temporary)
    else:
        assert all(button.is_disabled() for button in page.locator(
            '[data-copy="damage"],[data-download="damage"]').all())
    rows = packet['damage'].get('calculations', []) if isinstance(packet['damage'], dict) else []
    if not isinstance(rows, list):
        rows = []
    checked_filters = bool(filters and packet['status'] == 'available' and rows)
    if checked_filters:
        _check_filters(page, packet)
        _detail(page, 0, rows[0])
        page.click('#request-tab')
        _copy_download(page, 'request', d['request'] or d['observation'], temporary)
        if d['response'] is not None:
            page.click('#response-tab')
            _copy_download(page, 'response', d['response'], temporary)
    elif packet['status'] != 'available':
        assert page.locator('#damage-loaded').is_hidden() and not _visible_indices(page)
    return dict(decision=d['id'], status=packet['status'], calculations=len(rows),
                filters_checked=checked_filters, exact_json_copy_download=copied)


def _check_synthetic(page, data, packets, temporary):
    page.click('#damage-tab'); _ready(page, 'not_calculated')
    # Delay two real local-script insertions and complete them in reverse order.
    page.evaluate("""() => {
        window.originalHeadAppend = document.head.append.bind(document.head);
        document.head.append = (...nodes) => {
            if (nodes[0]?.tagName === 'SCRIPT' && nodes[0].src.includes('/damage/')) return;
            window.originalHeadAppend(...nodes);
        };
    }""")
    page.select_option('#decision', '1')
    page.select_option('#decision', '2')
    page.evaluate('packet => window.__jevDamageLoaded(packet)', packets[2]); _ready(page, 'not_calculated')
    page.evaluate('packet => window.__jevDamageLoaded(packet)', packets[1])
    assert 'synthetic-3' in page.locator('#damage-status').inner_text()
    assert page.locator('#damage-loaded').is_hidden()
    assert page.evaluate('window.jevDamageView.value()') == packets[2]['damage']
    page.evaluate('document.head.append = window.originalHeadAppend')
    page.select_option('#decision', '1'); _ready(page)
    assert _visible_indices(page) == list(range(50))
    assert page.locator('[data-damage-index="0"] .damage-hp').inner_text() == '0–0'
    assert page.locator('[data-damage-index="1"] .damage-hp').inner_text() == '미제공'
    assert page.locator('[data-damage-index="1"] .damage-pct').inner_text() == '미제공'
    assert '계산 실패' in page.locator('[data-damage-index="2"]').inner_text()
    assert '미지원/제외' in page.locator('[data-damage-index="3"]').inner_text()
    for n in (0, 2, 3, 4):
        element = _detail(page, n, packets[1]['damage']['calculations'][n])
        if n == 0:
            assert '미제공 (null)' in element.inner_text()
        if n == 4:
            assert '"hits": 2' in element.inner_text() and '"hits": 3' in element.inner_text()
            cells = element.locator('table').last.locator('tbody td').all_text_contents()
            assert cells == ['명중 조건 KO', '0', '명중 조건 생존', '1']
    _copy_download(page, 'damage', packets[1]['damage'], temporary)
    page.select_option('#turn', '2'); _ready(page, 'no_decision')
    assert page.locator('[data-copy="damage"]').is_disabled()
    assert not _visible_indices(page) and page.evaluate('window.jevDamageView.value()') is None
    page.select_option('#decision', '3'); _ready(page, 'missing')
    assert page.locator('[data-download="damage"]').is_disabled()
    page.select_option('#decision', '4'); _ready(page, 'unsupported_format')
    assert not page.locator('[data-download="damage"]').is_disabled()
    _copy_download(page, 'damage', packets[4]['damage'], temporary)
    page.select_option('#decision', '1'); _ready(page)


def verify_browser(output, *, evidence=None, resource_check=None):
    from playwright.sync_api import sync_playwright
    from .reexport import check_disk
    output = Path(output).resolve()
    experiment = json.loads((output / 'provenance.json').read_text())['experiment']
    size = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    measure = resource_check or (lambda **kwargs: check_disk(experiment, **kwargs))
    initial = measure(reserve=size)
    errors, results = [], []
    with tempfile.TemporaryDirectory(prefix='ep142-damage-browser-') as temporary_name:
        temporary = Path(temporary_name); moved = temporary / 'moved'
        shutil.copytree(output, moved)
        samples = _samples(moved)
        folder, index = samples['maximum_scenarios']
        normal_data = json.loads((folder / 'decisions.json').read_text())
        synthetic, packets = _synthetic(normal_data, _packet(folder, normal_data, index), moved / 'synthetic-errors')
        peak = measure(extra_roots=(temporary,))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
            context = browser.new_context(offline=True, viewport=dict(width=1440, height=1000))
            page = context.new_page(); page.set_default_timeout(20000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            # Index links still work after the full folder has moved.
            page.goto((moved / 'index.html').as_uri(), wait_until='domcontentloaded')
            assert page.locator('a[href^="battle-"]').count() == 32
            for name, (folder, index) in samples.items():
                data = json.loads((folder / 'decisions.json').read_text())
                d = data['decisions'][index]; packet = _packet(folder, data, index)
                loaded = []
                def received(request):
                    if '/damage/decision-' in request.url:
                        loaded.append(request.url)
                page.on('request', received)
                page.goto((folder / 'index.html').as_uri(), wait_until='domcontentloaded')
                assert not loaded, 'damage loaded before opening the tab'
                page.select_option('#decision', str(index))
                assert not loaded, 'closed tab fetched a different decision'
                assert json.loads(page.locator('#request-json').inner_text()) == (d['request'] or d['observation'])
                if d['response'] is not None:
                    assert json.loads(page.locator('#response-json').inner_text()) == d['response']
                assert (d.get('wire') or {}).get('command', '') in page.locator('#metrics').inner_text()
                page.click('#damage-tab'); _ready(page)
                assert len(loaded) == 1
                assert d['id'] in page.locator('#damage-status').inner_text()
                _check_summary(page, d)
                if name in ('maximum_scenarios', 'bidirectional_tera'):
                    _check_filters(page, packet)
                    _detail(page, 0, packet['damage']['calculations'][0])
                if name == 'maximum_scenarios':
                    _copy_download(page, 'damage', packet['damage'], temporary)
                    page.click('#request-tab'); _copy_download(page, 'request', d['request'] or d['observation'], temporary)
                    if d['response'] is not None:
                        page.click('#response-tab'); _copy_download(page, 'response', d['response'], temporary)
                    viewer._assert_summary(page, d)
                    viewer._check_turn_screen(page, data, d, temporary)
                    page.select_option('#decision', str(index)); page.click('#damage-tab'); _ready(page)
                if name == 'same_turn':
                    other = next(i for i, item in enumerate(data['decisions']) if item['turn'] == d['turn'] and item['kind'] == 'forced_switch')
                    turn = page.locator('#turn').input_value()
                    page.select_option('#decision', str(other)); _ready(page, 'not_calculated')
                    assert page.locator('#turn').input_value() == turn
                    assert 'lead_or_forced_switch_out_of_scope' in page.locator('#damage-status').inner_text()
                    assert not _visible_indices(page)
                    _copy_download(page, 'damage', _packet(folder, data, other)['damage'], temporary)
                    lead = next(i for i,item in enumerate(data['decisions']) if item['kind'] == 'lead')
                    page.select_option('#decision', str(lead)); _ready(page, 'not_calculated')
                    page.select_option('#decision', str(index)); _ready(page)
                if name == 'zero_damage':
                    n = next(i for i,r in enumerate(packet['damage']['calculations']) if r.get('result',{}).get('damage_range_hp') == [0,0])
                    for _ in range(n // 50):
                        page.click('#damage-next')
                    assert page.locator(f'[data-damage-index="{n}"] .damage-hp').inner_text() == '0–0'
                    assert page.locator(f'[data-damage-index="{n}"] .damage-pct').inner_text() == '0.00–0.00%'
                    _detail(page, n, packet['damage']['calculations'][n])
                if evidence:
                    page.screenshot(path=str(Path(evidence) / (name + '.png')), full_page=True)
                page.remove_listener('request', received)
                results.append(dict(name=name, battle=data['slot'], decision=d['id'], synthetic=False))
            page.goto((moved / 'synthetic-errors/index.html').as_uri(), wait_until='domcontentloaded')
            _check_synthetic(page, synthetic, packets, temporary)
            if evidence:
                page.screenshot(path=str(Path(evidence) / 'synthetic-errors.png'), full_page=True)
            results.append(dict(name='synthetic_errors_missing_multihit_and_race', synthetic=True))
            context.close(); browser.close()
        if errors:
            raise ValueError('offline browser errors: ' + repr(errors))
        final_peak = measure(extra_roots=(temporary,))
    return dict(passed=True, experiment=experiment, representative_screens=results, screen_count=len(results),
        offline_relocated=True, full_browser_replay=False, errors=errors,
        lazy_loading=True, stale_response_isolation=True, filters_and_pagination=True,
        exact_json_copy_download=True, original_io_and_turn_log_regression=True,
        synthetic_only=['calculation_failure','unsupported','multihit','missing','no_decision_turn'],
        disk_before=initial, disk_with_temporary_copy=peak, disk_after_browser=final_peak, temporary_copy_bytes=size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    write_json(args.receipt, verify_browser(args.output, evidence=args.receipt.parent))
