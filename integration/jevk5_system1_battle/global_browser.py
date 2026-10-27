"""Root index/shard links after relocation; detailed UI is checked within each shard."""
import json,shutil,tempfile,subprocess
from pathlib import Path
from .core import ROOT

def inspect(source,receipt,games):
    # Run in the existing browser environment rather than mutating the actor venv.
    code='''import json,sys,shutil,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
source,receipt,n=Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3])
with tempfile.TemporaryDirectory() as tmp:
 dest=Path(tmp)/'viewer';shutil.copytree(source,dest)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);ctx=browser.new_context();ctx.set_offline(True);page=ctx.new_page()
  page.goto((dest/'index.html').as_uri());assert page.locator('tr').count()==n+1
  links=page.locator('td a').evaluate_all('(a)=>a.map(x=>x.getAttribute("href"))');assert len(links)==n and len(set(links))==n
  for link in links:assert (dest/link).is_file()
  for gpu in [1,2,3]:
   candidates=[x for x in links if x.startswith(f'gpu{gpu}/')]
   if candidates:
    page.goto((dest/candidates[0]).as_uri());assert page.locator('#raw').count()==1;assert page.get_by_role('tab',name='요청 JSON',exact=True).get_attribute('aria-selected')=='true'
  browser.close()
receipt.write_text(json.dumps({'passed':True,'relocated_offline':True,'games':n,'unique_links':len(links)},indent=2)+'\\n')
'''
    subprocess.run(['/tmp/ep037/tools/bin/python','-c',code,str(source),str(receipt),str(games)],cwd=ROOT,check=True)
