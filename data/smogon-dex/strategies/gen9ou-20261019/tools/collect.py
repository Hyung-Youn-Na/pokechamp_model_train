"""Preserve every linked page and every OU strategy without filling source gaps."""
import argparse
import concurrent.futures
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import threading
import time
import urllib.request
from urllib.parse import urlsplit
from datetime import datetime, timezone

LINKS=Path('/workspace/data/smogon-dex/gen9ou_strategy_links.json')

def now():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)

class Settings(HTMLParser):
    def __init__(self):super().__init__();self.values=[]
    def handle_data(self,data):
        if data.lstrip().startswith('dexSettings = '):
            self.values.append(json.JSONDecoder().raw_decode(data.split('=',1)[1].lstrip())[0])

def extract(raw):
    parser=Settings();parser.feed(raw.decode('utf-8'))
    assert len(parser.values)==1,'missing/ambiguous embedded dexSettings'
    settings=parser.values[0];route=settings['route']
    assert route['status']=='ok' and route['view']=='pokemon' and route['gen']=='sv',route
    assert route['params']['lang']=='en',route
    entries=[(key,value) for key,value in settings['injectRpcs'] if key in route['dataKeys'] and json.loads(key)[0]=='dump-pokemon']
    assert len(entries)==1,'missing/ambiguous page Pokemon payload'
    key,payload=entries[0]
    assert json.loads(key)[1]['alias']==route['params']['alias']
    assert isinstance(payload['strategies'],list) and isinstance(payload['formeStrategies'],list)
    return route,key,payload

def main(output):
    output.mkdir(parents=True,exist_ok=True)
    rows=json.loads(LINKS.read_text());lock=threading.Lock()
    if (output/'input-links.json').exists():assert json.loads((output/'input-links.json').read_text())==rows
    else:write(output/'input-links.json',rows)
    def fetch(pair):
        number,row=pair;slug=urlsplit(row['strategy_url']).path.split('/')[4]
        folder=output/'pages'/f'{number:03d}-{slug}'
        if (folder/'receipt.json').exists():
            receipt=json.loads((folder/'receipt.json').read_text())
            if receipt.get('status')=='ok':return receipt
        attempts=[];folder.mkdir(parents=True,exist_ok=True)
        for attempt in range(1,4):
            started=now()
            try:
                req=urllib.request.Request(row['strategy_url'],headers={'User-Agent':'Mozilla/5.0 (compatible; research archive)','Accept-Language':'en','Accept-Encoding':'identity'})
                with urllib.request.urlopen(req,timeout=45) as response:
                    raw=response.read();status=response.status;resolved=response.url
                    headers=dict(response.headers.items())
                assert status==200,status
                (folder/'page.html.gz').write_bytes(gzip.compress(raw,mtime=0))
                route,key,payload=extract(raw)
                encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()
                (folder/'pokemon-payload.json.gz').write_bytes(gzip.compress(encoded,mtime=0))
                write(folder/'route.json',route)
                attempts.append(dict(attempt=attempt,started=started,finished=now(),status='ok',http_status=status))
                receipt=dict(index=number,**row,status='ok',retrieved_at_utc=started,resolved_url=resolved,
                    response_headers=headers,route=route,rpc_key=key,html_sha256=sha(raw),payload_sha256=sha(encoded),
                    raw_html=str((folder/'page.html.gz').relative_to(output)),
                    raw_payload=str((folder/'pokemon-payload.json.gz').relative_to(output)),attempts=attempts)
                write(folder/'receipt.json',receipt)
                with lock:print(json.dumps(dict(index=number,pokemon=row['pokemon'],status='ok',page_alias=route['params']['alias'])),flush=True)
                time.sleep(.15)
                return receipt
            except Exception as e:
                attempts.append(dict(attempt=attempt,started=started,finished=now(),status='error',error_type=type(e).__name__,detail=str(e)))
                if attempt<3:time.sleep(2*attempt)
        receipt=dict(index=number,**row,status='fetch_error',attempts=attempts)
        write(folder/'receipt.json',receipt)
        with lock:print(json.dumps(receipt),flush=True)
        return receipt
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        receipts=list(pool.map(fetch,enumerate(rows,1)))
    write(output/'fetch-manifest.json',dict(source_links=str(LINKS),source_links_sha256=sha(LINKS.read_bytes()),
        count=len(rows),success=sum(r['status']=='ok' for r in receipts),failed=sum(r['status']!='ok' for r in receipts),
        completed_at_utc=now(),receipts=receipts))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)
