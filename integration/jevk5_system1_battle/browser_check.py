"""Validate a relocated EX-123 UI v1 export without touching its source files."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import time

from playwright.sync_api import sync_playwright, expect


def value_matches(page, expected):
    text=page.locator('#raw').text_content()
    assert (text if isinstance(expected,str) else json.loads(text))==expected


def inspect(source, receipt):
    checks=[]
    with tempfile.TemporaryDirectory(prefix='ex123-relocated-') as tmp:
        target=Path(tmp)/'viewer';shutil.copytree(source,target)
        games=[(p,json.loads(p.read_text())) for p in sorted(target.glob('battle-*/decisions.json'),key=lambda p:int(p.parent.name.split('-')[1]))]
        cases={}
        for path,data in games:
            for i,d in enumerate(data['decisions']):
                kinds=['automatic' if d['automatic'] else d['kind']]
                choice=(d.get('selection') or {}).get('choice')
                if d['observation']['questions']['action']['criteria'].get(choice,{}).get('terastallize'):kinds.append('tera')
                if d['raw_response'] is not None and d['selection'] is None:kinds.append('failure')
                if any(e['type']=='provider_retry' for e in d['technical']['http_attempt_history']):kinds.append('retry')
                for kind in kinds:cases.setdefault(kind,(path,data,i))
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport=dict(width=1440,height=1100),accept_downloads=True)
            context.set_offline(True)
            context.grant_permissions(['clipboard-read','clipboard-write'])
            page=context.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto((target/'index.html').as_uri())
            assert 'JevK5' in page.inner_text('body')
            assert page.locator('tr').count()==len(games)+1
            for path,data in games:
                page.goto((path.parent/'index.html').as_uri())
                assert page.locator('#decision option').count()==len(data['decisions'])+1
                value_matches(page,data['decisions'][0]['request'])
            for kind,(path,data,i) in cases.items():
                d=data['decisions'][i]
                page.goto((path.parent/'index.html').as_uri()+'#decision='+d['id'])
                expect(page.locator('#decision')).to_have_value(str(i))
                assert page.get_by_role('tab',name='요청 JSON',exact=True).get_attribute('aria-selected')=='true'
                value_matches(page,d['request'])
                page.get_by_role('tab',name='응답 원문',exact=True).click();value_matches(page,d['raw_response'])
                page.get_by_role('tab',name='상태·후보 요약',exact=True).click();value_matches(page,d['observation'])
                with page.expect_download() as download:page.locator('#download').click()
                assert json.loads(Path(download.value.path()).read_text())==d['observation']
                page.locator('#copy').click();page.get_by_text('복사했습니다.',exact=True).wait_for()
                assert json.loads(page.evaluate('navigator.clipboard.readText()'))==d['observation']
                page.get_by_role('tab',name='실제 프롬프트',exact=True).click();value_matches(page,d['prompt_text'])
                page.get_by_role('tab',name='선택지 확률',exact=True).click();value_matches(page,d['response'])
                page.get_by_role('tab',name='선택·전송',exact=True).click();value_matches(page,dict(selection=d['selection'],wire=d['wire']))
                page.get_by_role('tab',name='기술 기록',exact=True).click()
                tech=json.loads(page.locator('#raw').text_content())
                assert all(tech[k]==v for k,v in d['technical'].items()) and tech['normalized_response']==d['response']
                page.get_by_role('tab',name='턴 로그',exact=True).click()
                page.locator('#cutoff').uncheck()
                rows=next(t['rows'] for t in data['turn_log']['turns'] if t['turn']==d['turn'])
                expected='\n'.join(r['protocol'] for r in rows)+ ('\n' if rows else '')
                value_matches(page,expected)
                page.locator('#cutoff').check()
                cut=data['turn_log']['decision_cutoffs'][d['id']]
                before=[r for r in rows if (r['sequence'],r['line_index'])<=(cut['sequence'],cut['line_index'])]
                value_matches(page,'\n'.join(r['protocol'] for r in before)+ ('\n' if before else ''))
                assert page.locator('#replay-log').inner_text().strip()
                checks.append(dict(kind=kind,game=data['slot'],decision=d['id'],passed=True))
            path,data,i=cases['turn_action'];d=data['decisions'][i]
            page.goto((path.parent/'index.html').as_uri()+'#decision='+d['id'])
            page.get_by_role('tab',name='상태·후보 요약',exact=True).click()
            for width in (1440,768,390):
                page.set_viewport_size(dict(width=width,height=1100))
                left=page.locator('.main').bounding_box();right=page.locator('.replay').bounding_box()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                if width==1440:assert right['x']>=left['x']+left['width']
                else:assert right['y']+right['height']<=left['y']
                page.screenshot(path=str(receipt.parent/f'offline-{width}.png'))
            assert not errors,errors
            context.close()
            # Actual official replay; synthetic tests cover delayed loading separately.
            live=browser.new_context(viewport=dict(width=1440,height=1100))
            online=live.new_page();online_errors=[]
            online.on('pageerror',lambda e:online_errors.append(str(e)))
            online.goto((source/'battle-1/index.html').as_uri())
            child=online.locator('#animation').element_handle().content_frame()
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                if child.evaluate('Boolean(window.Replays?.battle)'):break
                time.sleep(.2)
            ready=child.evaluate('Boolean(window.Replays?.battle)')
            online_result=dict(animation_ready=ready,page_errors=online_errors)
            if ready:
                online.locator('#decision').select_option('1')
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and child.locator('body').get_attribute('data-selected-turn')!='1':time.sleep(.05)
                assert child.locator('body').get_attribute('data-selected-turn')=='1'
                online_result.update(selected_turn=child.evaluate('Replays.battle.turn'),paused=child.evaluate('Replays.battle.paused'))
                assert online_result['selected_turn']==1 and online_result['paused']
                online.get_by_role('tab',name='상태·후보 요약',exact=True).click()
                online.screenshot(path=str(receipt.parent/'online-1440.png'))
            browser.close()
    result=dict(passed=True,relocated_offline=True,game_pages=len(games),decisions=sum(len(d['decisions']) for _,d in games),
                cases=checks,widths=[1440,768,390],page_errors=errors,online=online_result)
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('receipt',type=Path)
    args=parser.parse_args();inspect(args.source.resolve(),args.receipt.resolve())
