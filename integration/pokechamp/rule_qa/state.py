"""Projection from bounded actor messages; no access to the private oracle."""
from __future__ import annotations
import copy
import json
from ..observation.runtime import OfficialClient
from ..observation.build import DEFAULT_BUILD
from ..jev_v6 import Adapter
from ...jev_planner.candidate_labels import candidate_input
from . import STATE_VERSION

CONFUSION = ('Confusion is a volatile status checked before executing the selected move. '
             'While confusion persists, there is a 33% chance of self-hit instead of executing that move; '
             'self-hit is typeless physical damage with base power 40. It is not the move Confusion.')

def correct(payload):
    result = copy.deepcopy(payload)
    edits = []
    def visit(value, path=()):
        if isinstance(value, dict):
            # Only status/volatile effect objects; never the move of the same name.
            if value.get('id') == 'confusion' and any(k in ('volatiles','volatile_statuses','effects') for k in path):
                replacements={'general_effect':CONFUSION,'name':'Confusion (volatile status)','kind':'volatile_status'}
                for field,text in replacements.items():
                    if field in value:
                        edits.append({'path':list(path)+[field],'before':value[field],'after':text})
                        value[field]=text
            for key, child in value.items(): visit(child,path+(key,))
        elif isinstance(value,list):
            for i,child in enumerate(value): visit(child,path+(i,))
    visit(result)
    result['state']['version']=STATE_VERSION
    return result, edits

def bounded_actor(actor, cutoff):
    lines=actor['protocol'].splitlines()
    if type(cutoff) is not int or not 0 < cutoff <= len(lines):
        raise ValueError('invalid public decision cutoff')
    if actor['request'].get('side',{}).get('id')!='p1':
        raise ValueError('foreign request at actor boundary')
    return dict(protocol='\n'.join(lines[:cutoff]),request=copy.deepcopy(actor['request']),own_team=actor['own_team'])

class Builder:
    def __init__(self):
        self.client=OfficialClient('p1')
        self.adapter=Adapter(json.loads((DEFAULT_BUILD/'dex.json').read_text()))
    def build(self, actor, key, *, cutoff=None):
        cutoff=len(actor['protocol'].splitlines()) if cutoff is None else cutoff
        actor=bounded_actor(actor,cutoff)
        protocol='|init|battle\n'+actor['protocol']+'\n|request|'+json.dumps(actor['request'],separators=(',',':'))
        prefix=[dict(event_seq=1,protocol=protocol)]
        official=self.client.snapshot(prefix,key)
        try:
            raw,commands,audit=self.adapter.generate(official,prefix,actor['own_team'],actor='p1')
            named=candidate_input(raw,{'executor':{'candidate_display':'names-v1'}})
            corrected,edits=correct(named)
            return {'state':corrected['state'], 'battle_actions':corrected['questions']['action']['criteria']}, {
                'boundary':{'public_lines':cutoff},'v6':named,'edits':edits,'commands':commands,'audit':audit}
        finally: self.client.drop(key)
    def close(self):
        self.client.close();self.adapter.close()
