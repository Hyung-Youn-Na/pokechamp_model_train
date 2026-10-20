"""Lossless OU source records plus text and normalized, deduplicated tables."""
import argparse
import csv
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from collect import extract,write,sha,now

class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('p','div','h1','h2','h3','h4','h5','h6','li','br','tr'):self.parts.append('\n')
        if tag=='a':
            href=dict(attrs).get('href')
            if href:self.links.append(urljoin('https://www.smogon.com',href))
    def handle_endtag(self,tag):
        if tag in ('p','div','h1','h2','h3','h4','h5','h6','li','tr'):self.parts.append('\n')
    def handle_data(self,data):self.parts.append(data)

def text(value):
    if value is None:return None
    assert isinstance(value,str)
    parser=Text();parser.feed(value)
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())

def linked_urls(value):
    parser=Text();parser.feed(value or '')
    return list(dict.fromkeys(parser.links))

def identity(alias,forme,strategy_index):
    return f'{alias}:{forme or "base"}:OU:{strategy_index}'

def transform(output):
    manifest=json.loads((output/'fetch-manifest.json').read_text())
    source_rows=json.loads((output/'input-links.json').read_text())
    assert len(manifest['receipts'])==len(source_rows)==110
    pokemon=[];strategies={};sets={};sections=[];issues=[]
    for receipt,source in zip(manifest['receipts'],source_rows):
        assert all(receipt[k]==v for k,v in source.items())
        entry=dict(link_index=receipt['index'],**source,retrieved_at_utc=receipt.get('retrieved_at_utc'),
                   resolved_url=receipt.get('resolved_url'),status=receipt['status'],strategy_ids=[])
        if receipt['status']!='ok':
            issues.append(dict(kind='fetch_error',**entry));pokemon.append(entry);continue
        raw=gzip.decompress((output/receipt['raw_html']).read_bytes());assert sha(raw)==receipt['html_sha256']
        route,key,payload=extract(raw)
        stored=json.loads(gzip.decompress((output/receipt['raw_payload']).read_bytes()))
        assert payload==stored and route==receipt['route'] and key==receipt['rpc_key']
        alias=route['params']['alias'];forme=route['params'].get('forme','')
        if forme:
            candidates=[(i,f) for i,f in enumerate(payload['formeStrategies']) if f['forme']==forme]
            assert len(candidates)==1,'unknown selected forme'
            fi,f=candidates[0];available=f['strategies'];source_prefix=f'/formeStrategies/{fi}/strategies'
        else:
            available=payload['strategies'];source_prefix='/strategies'
        entry.update(page_alias=alias,selected_forme=forme or None,
            requested_alias=urlsplit(source['strategy_url']).path.split('/')[4],
            page_alias_differs=urlsplit(source['strategy_url']).path.split('/')[4]!=alias,
            forme_strategy_inventory=[dict(forme=f['forme'],forme_name=f['formeName'],formats=[s['format'] for s in f['strategies']]) for f in payload['formeStrategies']],
            available_formats=list(dict.fromkeys(s['format'] for s in available)),
            raw_html=receipt['raw_html'],raw_payload=receipt['raw_payload'])
        for index,strategy in enumerate(available):
            if strategy['format']!='OU':continue
            sid=identity(alias,forme,index);entry['strategy_ids'].append(sid)
            ref=dict(link_index=receipt['index'],strategy_url=source['strategy_url'],raw_payload=receipt['raw_payload'],json_pointer=f'{source_prefix}/{index}')
            if sid in strategies:
                assert strategies[sid]['source_strategy']==strategy,'same canonical strategy changed within snapshot'
                strategies[sid]['source_refs'].append(ref)
                continue
            record=dict(strategy_id=sid,page_alias=alias,selected_forme=forme or None,format='gen9ou',language='en',
                added=strategy.get('added'),edited=strategy.get('edited'),source_refs=[ref],
                overview_html=strategy.get('overview'),overview_text=text(strategy.get('overview')),
                comments_html=strategy.get('comments'),comments_text=text(strategy.get('comments')),
                outdated_html=strategy.get('outdated'),outdated_text=text(strategy.get('outdated')),
                credits=strategy.get('credits'),set_ids=[],source_strategy=strategy)
            strategies[sid]=record
            for section in ('overview','comments','outdated'):
                sections.append(dict(strategy_id=sid,set_id=None,section_kind=section,html=strategy.get(section),text=text(strategy.get(section)),source_field_present=section in strategy))
            for si,source_set in enumerate(strategy['movesets']):
                set_id=f'{sid}:set:{si}';record['set_ids'].append(set_id)
                description=source_set.get('description');plain=text(description)
                description_status='present' if plain and plain.strip() else 'empty_in_source' if 'description' in source_set else 'field_absent_in_source'
                set_record=dict(set_id=set_id,strategy_id=sid,set_index=si,page_alias=alias,format='gen9ou',
                    pokemon=source_set.get('pokemon'),name=source_set.get('name'),description_status=description_status,
                    description_html=description,description_text=plain,referenced_urls=linked_urls(description),
                    source_set=source_set,
                    **{k:v for k,v in source_set.items() if k not in ('pokemon','name','description')})
                sets[set_id]=set_record
                sections.append(dict(strategy_id=sid,set_id=set_id,section_kind='set_description',html=description,text=plain,source_field_present='description' in source_set))
                if description_status!='present':issues.append(dict(kind=description_status,page_alias=alias,pokemon=source_set.get('pokemon'),set_name=source_set.get('name'),set_id=set_id,strategy_id=sid,source_ref=ref))
        entry['status']='ok' if entry['strategy_ids'] else 'no_ou_strategy_in_source'
        if not entry['strategy_ids']:issues.append(dict(kind=entry['status'],**entry))
        pokemon.append(entry)
    strategy_rows=list(strategies.values());set_rows=list(sets.values())
    for row in set_rows:
        parent=strategies[row['strategy_id']]
        row.update(strategy_outdated=bool(parent['outdated_text']),strategy_added=parent['added'],strategy_edited=parent['edited'],
            source_urls=list(dict.fromkeys(ref['strategy_url'] for ref in parent['source_refs'])))
    # Full nested view retains the original source objects and all requested URL rows.
    full=[dict(p,strategies=[dict(strategies[sid],sets=[sets[x] for x in strategies[sid]['set_ids']]) for sid in p['strategy_ids']]) for p in pokemon]
    tables=dict(pokemon=pokemon,strategies=strategy_rows,sets=set_rows,sections=sections,issues=issues)
    for name,rows in tables.items():
        write(output/f'{name}.json',rows)
        with (output/f'{name}.jsonl').open('w') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    write(output/'pokemon_strategies.json',full)
    with (output/'pokemon_strategies.jsonl').open('w') as f:
        for row in full:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (output/'coverage.csv').open('w',newline='') as f:
        keys=['pokemon','strategy_url','page_alias','status','strategy_count','set_count','empty_descriptions']
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for row in pokemon:
            actual=[sets[x] for sid in row['strategy_ids'] for x in strategies[sid]['set_ids']]
            writer.writerow(dict(pokemon=row['pokemon'],strategy_url=row['strategy_url'],page_alias=row.get('page_alias'),status=row['status'],strategy_count=len(row['strategy_ids']),set_count=len(actual),empty_descriptions=sum(x['description_status']!='present' for x in actual)))
    validation=[]
    # Independent pointer traversal of preserved payloads checks every original field and set count.
    for entry in full:
        if entry['status']=='fetch_error':continue
        payload=json.loads(gzip.decompress((output/entry['raw_payload']).read_bytes()))
        for s in entry['strategies']:
            ref=next(r for r in s['source_refs'] if r['link_index']==entry['link_index'])
            node=payload
            for part in ref['json_pointer'].strip('/').split('/'):node=node[int(part)] if isinstance(node,list) else node[part]
            assert s['source_strategy']==node
            assert [x['source_set'] for x in s['sets']]==node['movesets']
            for x in s['sets']:
                assert x['description_html']==x['source_set'].get('description')
                for field,value in x['source_set'].items():
                    if field not in ('description',):assert x[field]==value,(x['set_id'],field)
            validation.append(dict(link_index=entry['link_index'],strategy_id=s['strategy_id'],sets=len(s['sets']),all_source_fields_equal=True))
    for name,rows in {**tables,'pokemon_strategies':full}.items():
        assert json.loads((output/f'{name}.json').read_text())==[json.loads(l) for l in (output/f'{name}.jsonl').open()]==rows
    counts=dict(input_links=len(source_rows),fetched=manifest['success'],fetch_errors=manifest['failed'],
        links_with_ou_strategy=sum(p['status']=='ok' for p in pokemon),links_without_ou_strategy=sum(p['status']=='no_ou_strategy_in_source' for p in pokemon),
        unique_page_aliases=len({p['page_alias'] for p in pokemon if 'page_alias' in p}),
        shared_page_links=[dict(pokemon=p['pokemon'],strategy_url=p['strategy_url'],page_alias=p['page_alias']) for p in pokemon if p.get('page_alias_differs')],
        unique_ou_strategies=len(strategies),unique_sets=len(sets),
        current_strategies=sum(not s['outdated_text'] for s in strategy_rows),
        current_sets=sum(not s['strategy_outdated'] for s in set_rows),
        current_sets_with_description=sum(not s['strategy_outdated'] and s['description_status']=='present' for s in set_rows),
        current_sets_without_description=sum(not s['strategy_outdated'] and s['description_status']!='present' for s in set_rows),sets_with_description=sum(s['description_status']=='present' for s in set_rows),
        sets_without_description=sum(s['description_status']!='present' for s in set_rows),
        nonempty_overviews=sum(bool(s['overview_text']) for s in strategy_rows),nonempty_comments=sum(bool(s['comments_text']) for s in strategy_rows),
        outdated_strategies=sum(bool(s['outdated_text']) for s in strategy_rows),sections=len(sections),
        description_words_whitespace=sum(len((s['description_text'] or '').split()) for s in set_rows))
    write(output/'statistics.json',counts)
    write(output/'validation.json',dict(passed=manifest['failed']==0,checked_at_utc=now(),input_coverage=True,
        raw_html_payload_match=True,all_strategy_and_set_fields_match=True,json_jsonl_equal=True,
        checked_link_strategies=validation,counts=counts))
    print(json.dumps(counts,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();transform(a.output)
