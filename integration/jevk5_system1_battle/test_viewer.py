"""Portable UI semantics, replay synchronization, and hostile/missing-data boundaries."""
from copy import deepcopy
import json
import time
from pathlib import Path

import pytest
from integration.jevk5_system1_battle.viewer_ui import render, render_replay


def fixture_data():
    observation = dict(state=dict(self_team=[dict(slot=1, species='Pikachu', active=True, condition='12/24',
        current_move_slots=[dict(slot=1, name='Thunderbolt')])], opponent_team=[dict(species='Mew', hp_percent=0)]),
        questions=dict(action=dict(criteria={'move_1':dict(kind='move', slot=1, move_ref=dict(self_team_slot=1,current_move_slot=1),
        current_matchup=dict(move='Thunderbolt',type_matchup=dict(multiplier=0),public_effects=dict(result='blocked'),
                             damage=dict(percent_of_target_max_hp=[0,0])))})))
    decisions=[]
    for i, (turn, kind) in enumerate([(0,'lead'),(1,'turn_action'),(1,'forced_switch'),(3,'turn_action'),(4,'turn_action')]):
        auto = i==2
        d=dict(id=f'd{i}',turn=turn,kind=kind,automatic=auto,observation=deepcopy(observation),
               request=None if auto else {'hostile':'</script><script>window.compromised=true</script> __STYLE__'},
               raw_response=None if auto or i==4 else dict(answers=[{'type':'refusal'}] if i==3 else [{'choice':'move_1'}]),
               selection=None if i in (3,4) else dict(choice='move_1',command='/choose move 1'),
               wire=None if i in (3,4) else dict(command='/choose move 1'),response=None,diagnostics=[],
               technical=dict(http_attempt_history=[],input_boundary=dict(protocol_event_seq=1,line_index=i)),
               base_observation=deepcopy(observation))
        decisions.append(d)
    turns=[dict(turn=t,rows=[dict(sequence=1,line_index=0,text='턴 '+str(t),protocol='|turn|'+str(t)),
                            dict(sequence=1,line_index=3,text='행동 결과',protocol='|message|after')]) for t in range(5)]
    return dict(experiment='EX-123',slot=1,synthetic=True,outcome=dict(slot_id='synthetic',jev_actor='p1',outcome='output_failure'),
        decisions=decisions,turn_log=dict(turns=turns,decision_cutoffs={f'd{i}':dict(sequence=1,line_index=1 if i!=2 else 3) for i in range(5)}))


@pytest.fixture
def viewer(tmp_path):
    path=tmp_path/'moved'/'battle-1';path.mkdir(parents=True)
    data=fixture_data()
    (path/'index.html').write_text(render(data))
    (path/'replay.html').write_text(render_replay('synthetic','|init|battle\n|gen|9\n'))
    return path,data


@pytest.fixture
def browser_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport=dict(width=1440,height=1000),accept_downloads=True)
        context.set_offline(True)
        page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        yield page,errors
        browser.close()


def test_tabs_raw_state_and_missing_decisions(viewer,browser_page):
    path,data=viewer;page,errors=browser_page
    page.goto((path/'index.html').as_uri())
    assert page.get_by_role('tab').all_text_contents()==['요청 JSON','응답 원문','상태·후보 요약','턴 로그','기술 기록','실제 프롬프트','선택지 확률','선택·전송']
    assert page.get_by_role('tab',name='요청 JSON',exact=True).get_attribute('aria-selected')=='true'
    assert json.loads(page.locator('#raw').text_content())==data['decisions'][0]['request']
    assert not page.evaluate('Boolean(window.compromised)')
    page.locator('#decision').select_option('1')
    page.get_by_role('tab',name='상태·후보 요약',exact=True).click()
    assert 'Thunderbolt' in page.locator('#state-content').inner_text()
    assert '0%' in page.locator('#state-content').inner_text()
    with page.expect_download() as download:
        page.locator('#download').click()
    assert json.loads(Path(download.value.path()).read_text())==data['decisions'][1]['observation']
    page.context.grant_permissions(['clipboard-read','clipboard-write'])
    page.locator('#copy').click();page.get_by_text('복사했습니다.',exact=True).wait_for()
    assert json.loads(page.evaluate('navigator.clipboard.readText()'))==data['decisions'][1]['observation']
    page.locator('#decision').select_option('2')
    page.get_by_role('tab',name='요청 JSON',exact=True).click()
    assert '모델 미호출' in page.locator('#note').inner_text()
    assert page.locator('#raw').text_content()=='null'
    page.get_by_role('tab',name='턴 로그',exact=True).click()
    page.locator('#cutoff').check()
    assert 'after' in page.locator('#raw').text_content()  # same-turn forced switch's later cutoff
    page.locator('#decision').select_option('1')
    assert 'after' not in page.locator('#raw').text_content()
    page.locator('#turn').select_option('2')
    assert page.locator('#decision').input_value()==''
    assert page.locator('#cutoff').is_disabled()
    page.get_by_role('tab',name='요청 JSON',exact=True).click()
    assert page.locator('#raw').text_content()=='null'
    assert '결정 없음' in page.locator('#position').inner_text()
    page.locator('#next').click();assert page.locator('#decision').input_value()=='3'
    page.get_by_role('tab',name='응답 원문',exact=True).click()
    assert json.loads(page.locator('#raw').text_content())==data['decisions'][3]['raw_response']
    assert '응답 실패' in page.locator('#metrics').inner_text()
    page.locator('#next').click()
    assert '응답 미수신' in page.locator('#note').inner_text()
    # Form/tab arrows do not navigate the decision sequence.
    page.get_by_role('tab',name='응답 원문',exact=True).focus();page.keyboard.press('ArrowRight')
    assert page.locator('#decision').input_value()=='4'
    page.locator('#content').focus();page.keyboard.press('ArrowLeft')
    assert page.locator('#decision').input_value()=='3'
    assert not errors


def wait_seek(frame, turn):
    # Runtime.evaluate works under CSP; wait_for_function's string eval does not.
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        if frame.evaluate('(turn) => window.calls.includes(turn)',turn):
            return
        time.sleep(.05)
    raise AssertionError(f'replay did not seek to {turn}')


def test_replay_latest_selection_and_independence(viewer,browser_page):
    path,_=viewer;page,errors=browser_page
    page.goto((path/'index.html').as_uri())
    page.locator('#decision').select_option('1');page.locator('#decision').select_option('3')
    child=page.locator('#animation').element_handle().content_frame()
    child.evaluate("window.calls=[];window.Replays={battle:{pause(){calls.push('pause')},seekTurn(t){calls.push(t)}}}")
    wait_seek(child, 3)
    assert set(child.evaluate('calls.filter(Number.isInteger)'))=={3}
    page.locator('#decision').select_option('1');wait_seek(child, 1)
    page.locator('#decision').select_option('2');wait_seek(child, 1)
    child.evaluate('calls=[]')
    page.get_by_role('tab',name='기술 기록',exact=True).click()
    assert child.evaluate('calls')==[]
    child.evaluate('Replays.battle.seekTurn(99)')
    assert page.locator('#decision').input_value()=='2'
    page.locator('#align-replay').click();wait_seek(child, 1)
    assert child.evaluate('calls.slice(-3)')==['pause',1,'pause']
    page.evaluate("window.postMessage({type:'planner-replay-ready'},'*')")
    assert page.locator('#decision').input_value()=='2'
    assert not errors


def test_responsive_deep_link_empty_and_escape(viewer,browser_page):
    path,data=viewer;page,errors=browser_page
    page.goto((path/'index.html').as_uri()+'#decision=d2')
    assert page.locator('#decision').input_value()=='2'
    assert page.get_by_role('tab',name='요청 JSON',exact=True).get_attribute('aria-selected')=='true'
    page.goto((path/'index.html').as_uri()+'#decision=d3')
    from playwright.sync_api import expect
    expect(page.locator('#decision')).to_have_value('3')
    assert page.get_by_role('tab',name='요청 JSON',exact=True).get_attribute('aria-selected')=='true'
    for width in (1440,768,390):
        page.set_viewport_size(dict(width=width,height=1000))
        main=page.locator('.main').bounding_box();replay=page.locator('.replay').bounding_box()
        if width==1440: assert replay['x']>=main['x']+main['width']
        else: assert replay['y']+replay['height']<=main['y']
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    data['decisions']=[];data['turn_log']['decision_cutoffs']={}
    (path/'empty.html').write_text(render(data))
    page.goto((path/'empty.html').as_uri())
    assert page.locator('#previous').is_disabled() and page.locator('#next').is_disabled()
    assert '결정 없음' in page.locator('#position').inner_text()
    page.get_by_role('tab',name='턴 로그',exact=True).click()
    assert page.locator('#replay-log').inner_text()
    assert not errors



def test_normalized_names_do_not_replace_raw_http(viewer,browser_page):
    path,data=viewer;page,errors=browser_page;d=data['decisions'][1]
    d['raw_response']={'choices':[{'text':'A','logprobs':{'top_logprobs':[{'token_id:32':-1.0}]}}]}
    d['response']={'answers':{'action':{'choice':'move_1','probabilities':{'move_1':1.0}}}}
    (path/'readout.html').write_text(render(data))
    page.goto((path/'readout.html').as_uri()+'#decision=d1')
    page.get_by_role('tab',name='응답 원문',exact=True).click()
    assert 'Thunderbolt' in page.locator('#state-content').inner_text()
    assert json.loads(page.locator('#raw').text_content())==d['raw_response']
    page.get_by_role('tab',name='선택지 확률',exact=True).click()
    assert json.loads(page.locator('#raw').text_content())==d['response']
    assert not errors
