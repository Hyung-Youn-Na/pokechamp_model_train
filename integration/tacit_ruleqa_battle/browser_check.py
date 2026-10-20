"""Relocate the export, inspect raw text, and exercise representative offline screens."""
import html
import json
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    output=Path('/workspace/exports/battle_viewers/ex108')
    run=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-108')
    events_path=run/'collection/events.jsonl'
    events=[json.loads(l) for l in events_path.open()] if events_path.exists() else []
    rows=json.loads((run/'collection/result.json').read_text())['outcomes'] if (run/'collection/result.json').exists() else []
    slot_paths={r['slot_id']:output/f"battle-{r['slot']}.html" for r in rows}
    inputs={e['decision']:e for e in events if e['type']=='input'}
    responses={e['decision']:e for e in events if e['type']=='response'}
    verified=0
    for decision,inp in inputs.items():
        text=slot_paths[inp['slot_id']].read_text()
        assert html.escape(json.dumps(inp['payload']['messages'],ensure_ascii=False,indent=2)) in text
        if decision in responses:assert html.escape(responses[decision]['raw']) in text
        verified+=1
    wanted={}
    for e in events:
        if e['type']=='input':wanted.setdefault(e['payload']['kind'],slot_paths[e['slot_id']].name)
        if e['type']=='selection':
            if e['fallback']:wanted.setdefault('fallback',slot_paths[inputs[e['decision']]['slot_id']].name)
            if e['automatic']:wanted.setdefault('automatic',slot_paths[inputs[e['decision']]['slot_id']].name)
    pages=list(dict.fromkeys(['index.html',*wanted.values()]))
    with tempfile.TemporaryDirectory(prefix='ex108-offline-') as temporary:
        relocated=Path(temporary)/'export';shutil.copytree(output,relocated)
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
            context=browser.new_context(offline=True)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            for name in pages:
                page.goto((relocated/name).as_uri(),wait_until='domcontentloaded')
                assert page.locator('h1').count()==1
                assert page.locator('pre').count()>0
                if name!='index.html':
                    before=page.locator('#replay').inner_text()
                    page.locator('#next').click()
                    assert len(page.locator('#replay').inner_text())>=len(before)
                    page.locator('#all').click()
                    assert page.locator('button').filter(has_text='복사').count()>0
                    with page.expect_download() as info:
                        page.locator('a[download]').first.click()
                    assert info.value.suggested_filename.startswith('record-')
                page.set_viewport_size(dict(width=390,height=844))
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2')
                page.set_viewport_size(dict(width=1280,height=900))
            assert not errors,errors
            browser.close()
    receipt=dict(passed=True,raw_decisions_verified=verified,pages=pages,categories=wanted,
                 relocated=True,offline=True,mobile=True,animated_replay_network_required=True)
    (run/'browser-check.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
