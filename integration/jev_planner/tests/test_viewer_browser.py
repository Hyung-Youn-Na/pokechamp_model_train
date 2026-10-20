"""file:// navigation, replay bridge, and delayed local packet integration."""
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from integration.jev_planner import reporting
from integration.jev_planner.tests.test_reporting import events, run, embedded
from integration.jev_eval.tests.test_damage_viewer import scenario
from integration.pokechamp.jev_battle import digest


def browser_fixture(directory):
    rows = events()
    for r in rows:
        if r.get('decision') == 'd2':
            r['turn'] = 1; r['boundary'] = dict(protocol_event_seq=1, line_index=3)
            if r['type'] == 'input':
                r['payload']['state']['turn'] = 1
                r['payload']['state']['decision_kind'] = 'forced_switch'
    new = deepcopy([r for r in rows if r.get('decision', r.get('request_id')) == 'd1'])
    for r in new:
        if 'decision' in r: r['decision'] = 'd4'
        if 'request_id' in r: r['request_id'] = 'd4'
        if 'turn' in r: r['turn'] = 3
        if 'rqid' in r: r['rqid'] = 4
        if 'boundary' in r: r['boundary'] = dict(protocol_event_seq=3, line_index=1)
        if r['type'] == 'input':
            r['payload']['state'].update(turn=3, planner_advice=dict(
                plan=dict(objective='New plan', priorities=[], preserve=[], threats=[], tera_policy='Wait', contingencies=[]),
                decision='d4', generated_turn=3, age_turns=0))
    rows.extend(new)
    rows.append(dict(type='planner_failure', decision='d5', rqid=5, actor='p1', battle='battle-a', turn=4,
        boundary=dict(protocol_event_seq=4, line_index=1), message='synthetic failure'))
    for turn in range(1,6):
        rows.append(dict(type='protocol', username='model-a', sequence=turn,
            protocol=f'>battle-a\n|turn|{turn}\n|move|p1a: Pikachu|Tackle|p2a: Mew\n|request|PRIVATE' + ('\n|win|model-a' if turn == 5 else '')))
    source = run(directory / 'source', recorded=rows)
    for r in rows:
        if r['type'] != 'input': continue
        base = deepcopy(r['payload']); base['state'].pop('planner_advice', None)
        r['base_payload'] = base
        damage = dict(version='jev-damage-sample-v1', calculations=[scenario(i) for i in range(55)])
        if r['decision'] == 'd3': damage.update(calculations=[], unchanged_reason='lead_or_forced_switch_out_of_scope')
        path = source / 'conditions/fixture' / (r['decision'] + '.json.gz')
        path.write_bytes(gzip.compress(json.dumps(dict(live_result_sha256=digest(base), damage=damage)).encode()))
        rows.append(dict(type='observation', decision=r['decision'], battle='battle-a', actor='p1', rqid=r['rqid'],
            input_audit=dict(path=path.name, sha256=sha256(path.read_bytes()).hexdigest())))
    (source / 'conditions/fixture/events.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    target = directory / 'export'; reporting.export_run(source, target)
    moved = directory / 'moved'; shutil.move(target, moved)
    return moved / 'condition-0001/battle-0001.html'


def test_portable_tabs_replay_and_latest_selection(tmp_path):
    pw = pytest.importorskip('playwright.sync_api')
    path = browser_fixture(tmp_path)
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=dict(width=1500,height=1000), accept_downloads=True)
        errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('https://**/*', lambda r: r.abort())
        page.goto(path.as_uri())
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('목표')")
        assert page.get_by_role('tab', name='GLM 계획', exact=True).get_attribute('aria-selected') == 'true'
        frame = page.frames[1]
        # Nothing is ready yet. Two selections must collapse to one pending seek.
        page.get_by_role('button', name='다음 결정 →', exact=True).click()
        page.get_by_role('button', name='다음 결정 →', exact=True).click()
        frame.evaluate("window.calls=[]; window.Replays={battle:{pause(){calls.push('pause')},seekTurn(t){calls.push(t)}}}")
        page.wait_for_function("document.querySelector('.choice')?.textContent.includes('move:1')")
        frame.wait_for_function("() => calls.includes(3)")
        assert set(frame.evaluate('calls.filter(Number.isInteger)')) == {3}  # d3 fixture is turn 3
        assert frame.evaluate('calls.slice(-3)') == ['pause', 3, 'pause']
        frame.evaluate('calls=[]')
        page.get_by_role('tab', name='JEV 요청', exact=True).click()
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('JEV 입력 원문')")
        assert frame.evaluate('calls') == []
        # Replay movement cannot navigate the info panel.
        selected = page.get_by_label('결정 선택').input_value()
        frame.evaluate('Replays.battle.seekTurn(99)')
        assert page.get_by_label('결정 선택').input_value() == selected
        page.get_by_role('button', name='선택한 턴으로 이동', exact=True).click()
        frame.wait_for_function('() => calls.includes(3)')
        page.get_by_label('턴 선택', exact=True).select_option('1')
        page.get_by_label('결정 선택', exact=True).select_option('1')
        page.get_by_role('tab', name='GLM 계획', exact=True).click()
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('이전 계획 재사용')")
        assert '강제 교체' in page.locator('[aria-live=polite]').inner_text()
        assert '현재 결정은 GLM 미호출' in page.get_by_role('tabpanel').inner_text()
        page.get_by_role('tab', name='턴 로그', exact=True).click()
        page.get_by_label('선택한 결정 전까지', exact=True).check()
        assert 'PRIVATE' not in page.get_by_role('tabpanel').inner_text()
        page.get_by_role('tab', name='JEV 응답', exact=True).click()
        page.wait_for_selector('pre[data-original="executor-response.json"]')
        expected = page.locator('pre[data-original="executor-response.json"]').text_content()
        with page.expect_download() as got:
            page.get_by_role('tabpanel').get_by_role('button', name='다운로드', exact=True).click()
        assert Path(got.value.path()).read_text() == expected
        page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page.get_by_role('tabpanel').get_by_role('button', name='복사', exact=True).click()
        page.get_by_role('tabpanel').get_by_text('복사됨', exact=True).wait_for()
        assert page.evaluate('navigator.clipboard.readText()') == expected
        page.get_by_role('tab', name='Damage-calc', exact=True).click()
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('55 / 55개')")
        assert '0–0 HP' in page.get_by_role('tabpanel').inner_text()
        page.get_by_label('방향', exact=True).select_option('incoming')
        assert '27 / 55개' in page.get_by_role('tabpanel').inner_text()
        page.get_by_role('tab', name='GLM 계획', exact=True).click()
        page.get_by_role('button', name='적용 계획 생성 결정 1 · 1턴', exact=True).click()
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('현재 결정에서 생성')")
        # Keyboard tab navigation stays inside tabs; body arrows navigate decisions.
        page.get_by_role('tab', name='GLM 계획', exact=True).focus(); page.keyboard.press('ArrowRight')
        assert page.get_by_role('tab', name='JEV 요청', exact=True).get_attribute('aria-selected') == 'true'
        page.locator('h1').click(); page.keyboard.press('ArrowRight')
        assert page.get_by_label('결정 선택').input_value() == '1'
        page.get_by_label('턴 선택', exact=True).select_option('5')
        assert '결정 없음' in page.locator('[aria-live=polite]').inner_text()
        page.get_by_role('tab', name='턴 로그', exact=True).click()
        assert 'model-a' in page.get_by_role('tabpanel').inner_text()
        box1 = page.locator('.information').bounding_box(); box2 = page.locator('.replay').bounding_box()
        assert box2['x'] > box1['x'] + box1['width'] - 1
        page.set_viewport_size(dict(width=390,height=844))
        box1 = page.locator('.information').bounding_box(); box2 = page.locator('.replay').bounding_box()
        assert box2['y'] > box1['y'] + box1['height'] - 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
        browser.close()


def test_delayed_packets_do_not_overwrite_new_decision(tmp_path):
    pw = pytest.importorskip('playwright.sync_api')
    path = browser_fixture(tmp_path)
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.route('https://**/*', lambda r: r.abort())
        page.add_init_script('''(() => {
          if (window !== top) return;
          const append = HTMLHeadElement.prototype.append;
          HTMLHeadElement.prototype.append = function(...nodes) {
            if (nodes.some(n => /decision-0001\\.js$/.test(n.src || ''))) {
              setTimeout(() => append.apply(this, nodes), 350);
            } else append.apply(this, nodes);
          };
        })();''')
        page.goto(path.as_uri())
        page.get_by_label('턴 선택', exact=True).select_option('3')
        page.get_by_label('결정 선택', exact=True).select_option('3')
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('New plan')")
        page.wait_for_timeout(400)  # wait beyond the deliberately delayed packet
        assert 'New plan' in page.get_by_role('tabpanel').inner_text()
        assert page.get_by_label('결정 선택').input_value() == '3'
        page.get_by_label('턴 선택', exact=True).select_option('4')
        page.get_by_role('tab', name='기술 기록', exact=True).click()
        page.wait_for_function("document.querySelector('[role=tabpanel]').textContent.includes('synthetic failure')")
        assert '실패 기록 있음' in page.locator('[aria-live=polite]').inner_text()
        browser.close()


@pytest.mark.parametrize('finish,forced', [('natural', False), ('length', True), ('eos', True)])
@pytest.mark.parametrize('external', [False, True])
def test_tacit_thinking_offline_originals(tmp_path, finish, forced, external):
    pw = pytest.importorskip('playwright.sync_api')
    rows = events()
    response = next(r for r in rows if r['type'] == 'response')
    body = response['body']
    body.update(first_pass=dict(choice='move:2', probabilities={'move:1': .1, 'move:2': .9}),
                thinking=dict(seed=123, token_ids=[42, 43], text='Reason <tag> & </script> 원문',
                              finish_reason=finish, forced_close=forced),
                stages=dict(thinking=dict(seconds=1.2, input_tokens=10, processed_input_tokens=11, forward_calls=2)),
                physical_forward_calls=4, original_input_tokens=dict(first_pass=10, thinking=10))
    body['answers']['action']['probabilities'] = {'move:1': .8, 'move:2': .2}
    if external:
        body.update(external_http_calls=3, physical_forward_calls=None, processed_input_tokens=None,
            measurement_unavailable_reason='external_vllm_does_not_expose_physical_forward_allocator_or_processed_tokens',
            metadata=dict(backend='vllm', external_identity=dict(model='tacit9b', physical_gpu=1)),
            usage=dict(input_tokens=32, output_tokens=4),
            stages={name: dict(seconds=1, input_tokens=10, output_tokens=output,
                              processed_input_tokens=None, forward_calls=None, http_calls=1)
                    for name, output in [('first_pass', 1), ('thinking', 2), ('final_read', 1)]})
    source = run(tmp_path / 'source', recorded=rows)
    export = tmp_path / 'export'; reporting.export_run(source, export)
    moved = tmp_path / 'moved'; shutil.move(export, moved)
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('https://**/*', lambda r: r.abort())
        page.goto((moved / 'condition-0001/battle-0001.html').as_uri())
        page.get_by_role('tab', name='JEV 응답', exact=True).click()
        page.wait_for_selector('pre[data-original="tacit-thinking.txt"]')
        assert '선택 변경' in page.get_by_role('tabpanel').inner_text()
        if external:
            panel_text = page.get_by_role('tabpanel').inner_text()
            assert '실제 forward 미관측' in panel_text
            assert '외부 HTTP 3회 · thinking 생성 2토큰 · 첫/최종 판독 생성 2토큰 · 전체 출력 4토큰' in panel_text
            assert 'HTTP 횟수나 출력 토큰으로 추정하지 않습니다' in panel_text
            assert '미관측' in page.get_by_role('tabpanel').locator('table').nth(1).inner_text()
        assert ('강제 마감: 예' if forced else '강제 마감: 아니요') in page.get_by_role('tabpanel').inner_text()
        assert page.locator('pre[data-original="tacit-thinking.txt"]').text_content() == body['thinking']['text']
        page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        for filename, value in [('executor-response.json', body), ('tacit-thinking.txt', body['thinking']['text']),
                                ('tacit-thinking-token-ids.json', body['thinking']['token_ids'])]:
            pre = page.locator(f'pre[data-original="{filename}"]')
            details = pre.locator('..')
            details.evaluate('(node) => node.open = true')
            expected = pre.text_content()
            assert (expected if isinstance(value, str) else json.loads(expected)) == value
            with page.expect_download() as got:
                details.get_by_role('button', name='다운로드', exact=True).click()
            assert Path(got.value.path()).read_text() == expected
            details.get_by_role('button', name='복사', exact=True).click()
            details.get_by_text('복사됨', exact=True).wait_for()
            assert page.evaluate('navigator.clipboard.readText()') == expected
        assert not errors
        browser.close()
