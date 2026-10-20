import json,sys,tempfile,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
source=Path(sys.argv[1]).resolve()
receipt=Path(sys.argv[2]).resolve()
checks=[]
with tempfile.TemporaryDirectory(prefix='ex111-viewer-') as temp:
 target=Path(temp)/'relocated';shutil.copytree(source,target)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
  context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
  context.set_offline(True)
  page=context.new_page()
  page.goto((target/'index.html').as_uri())
  assert 'JevK5' in page.title()
  games=sorted(target.glob('battle-*/decisions.json'),key=lambda x:int(x.parent.name.split('-')[1]))
  chosen=[]
  for f in games:
   data=json.loads(f.read_text())
   for i,d in enumerate(data['decisions']):
    candidate=d['observation']['questions']['action']['criteria'].get((d.get('selection') or {}).get('choice'),{})
    kind='tera' if candidate.get('terastallize') else 'automatic' if d['automatic'] else d['kind']
    if kind not in [c[0] for c in chosen]:chosen.append((kind,f,i))
  for kind,f,i in chosen[:5]:
   data=json.loads(f.read_text());d=data['decisions'][i]
   page.goto((f.parent/'index.html').as_uri())
   page.locator('#decisions').select_option(str(i))
   selected=d.get('selection')
   if selected:
    candidate=d['observation']['questions']['action']['criteria'][selected['choice']]
    if candidate['kind'] in ('team','switch'):
     assert candidate['pokemon'] in page.locator('#selected').inner_text()
    else:
     ref=candidate['move_ref'];team=d['observation']['state']['self_team']
     pokemon=next(p for p in team if p['slot']==ref['self_team_slot'])
     move=next(m for m in pokemon['current_move_slots'] if m['slot']==ref['current_move_slot'])
     assert (move.get('name') or move['move']) in page.locator('#selected').inner_text()
     if candidate.get('terastallize'):assert '테라' in page.locator('#selected').inner_text()
   assert json.loads(page.locator('#json').inner_text())==d['request']
   page.locator('[data-tab=response]').click()
   assert json.loads(page.locator('#json').inner_text())==d['raw_response']
   page.locator('[data-tab=state]').click()
   assert json.loads(page.locator('#json').inner_text())==d['observation']
   page.locator('[data-tab=prompt]').click()
   assert json.loads(page.locator('#json').inner_text())==d['prompt_text']
   page.locator('[data-tab=probabilities]').click()
   assert json.loads(page.locator('#json').inner_text())==d['response']
   page.locator('[data-tab=state]').click()
   with page.expect_download() as dl:
    page.locator('#download').click()
   downloaded=Path(temp)/('state-'+kind+'.json');dl.value.save_as(downloaded)
   assert json.loads(downloaded.read_text())==d['observation']
   page.locator('[data-tab=selection]').click()
   assert json.loads(page.locator('#json').inner_text())['selection']==d['selection']
   assert page.locator('#turntext').inner_text().strip()
   page.locator('#cutoff').check()
   if i+1<len(data['decisions']):
    page.locator('#next').click();assert page.locator('#decisions').input_value()==str(i+1)
   checks.append({'kind':kind,'file':str(f.relative_to(target)),'decision':i,'passed':True})
  page.screenshot(path=str(receipt.with_suffix('.png')),full_page=False)
  browser.close()
receipt.write_text(json.dumps({'passed':True,'offline_relocated':True,'checks':checks},ensure_ascii=False,indent=2))
print(json.dumps({'passed':True,'checks':len(checks)}))
