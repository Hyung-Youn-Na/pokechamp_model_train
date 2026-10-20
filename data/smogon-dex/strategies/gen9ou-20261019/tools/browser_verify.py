"""Render the preserved page snapshots with Smogon's UI and check every OU text."""
import argparse
import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from collect import extract,write,sha,now
from build import text


def normalized(s):return ' '.join((s or '').split())

def verify(root,limit=None):
    receipts=[json.loads(p.read_text()) for p in sorted((root/'pages').glob('*/receipt.json'))]
    if limit:receipts=receipts[:limit]
    checks=[];cache={};errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-gpu'])
        context=browser.new_context()
        page=context.new_page()
        current={}
        def handle(route):
            url=route.request.url;parts=urlsplit(url)
            if route.request.resource_type=='document' and url==current.get('url'):
                route.fulfill(status=200,content_type='text/html; charset=utf-8',body=current['raw']);return
            if route.request.resource_type in ('image','font','media'):
                route.abort();return
            if parts.hostname=='www.smogon.com' and parts.path.startswith('/__assets/'):
                if url not in cache:
                    response=context.request.get(url,timeout=45000)
                    assert response.status==200,(url,response.status)
                    cache[url]=(response.headers.get('content-type','application/octet-stream'),response.body())
                content_type,body=cache[url]
                route.fulfill(status=200,content_type=content_type,body=body);return
            route.abort()
        context.route('**/*',handle)
        try:
            for receipt in receipts:
                if receipt['status']!='ok':
                    errors.append(dict(index=receipt['index'],error='not fetched'));continue
                current.update(url=receipt['strategy_url'],raw=gzip.decompress((root/receipt['raw_html']).read_bytes()))
                route,key,payload=extract(current['raw'])
                available=payload['strategies']
                if route['params'].get('forme'):
                    available=next(f['strategies'] for f in payload['formeStrategies'] if f['forme']==route['params']['forme'])
                strategies=[s for s in available if s['format']=='OU']
                try:
                    page.goto(current['url'],wait_until='domcontentloaded',timeout=45000)
                    page.wait_for_function("document.querySelector('#container')?.innerText.includes('Strategies')",timeout=30000)
                    body=normalized(page.locator('body').inner_text())
                    missing=[];texts=0;sets=0
                    for s in strategies:
                        for field in ('overview','comments','outdated'):
                            value=normalized(text(s.get(field)))
                            if value:
                                texts+=1
                                if value not in body:missing.append(dict(field=field,length=len(value),prefix=value[:100]))
                        for m in s['movesets']:
                            sets+=1
                            if m['name'] not in body:missing.append(dict(set_name=m['name'],field='name'))
                            value=normalized(text(m.get('description')))
                            if value:
                                texts+=1
                                if value not in body:missing.append(dict(set_name=m['name'],field='description',length=len(value),prefix=value[:100]))
                    item=dict(index=receipt['index'],pokemon=receipt['pokemon'],url=receipt['strategy_url'],strategies=len(strategies),sets=sets,nonempty_texts=texts,passed=not missing,missing=missing)
                    if missing:
                        errors.append(item)
                        folder=root/'browser-diagnostics';folder.mkdir(exist_ok=True)
                        (folder/f"{receipt['index']:03d}-body.txt").write_text(page.locator('body').inner_text())
                    checks.append(item)
                    print(json.dumps(dict(index=receipt['index'],pokemon=receipt['pokemon'],passed=not missing,missing=len(missing))),flush=True)
                except Exception as e:
                    errors.append(dict(index=receipt['index'],pokemon=receipt['pokemon'],error_type=type(e).__name__,error=str(e)))
                    print(json.dumps(errors[-1]),flush=True)
                write(root/('browser-preflight.json' if limit else 'browser-validation.json'),dict(passed=not errors,checked=len(checks),expected=len(receipts),errors=errors,checks=checks,mode='saved HTML fulfilled at original URL; official UI assets; external ads/network blocked',checked_at_utc=now()))
        finally:
            context.unroute_all(behavior='wait')
            browser.close()
    assets_dir=root/'browser-assets';assets_dir.mkdir(exist_ok=True)
    assets=[]
    for url,(mime,body) in cache.items():
        path=assets_dir/(sha(url.encode())[:16]+Path(urlsplit(url).path).suffix)
        path.write_bytes(body);assets.append(dict(url=url,content_type=mime,path=str(path.relative_to(root)),sha256=sha(body)))
    write(assets_dir/'manifest.json',assets)
    assert len(checks)==len(receipts) and not errors,errors

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--limit',type=int);a=p.parse_args();verify(a.output,a.limit)
