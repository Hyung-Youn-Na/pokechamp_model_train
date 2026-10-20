"""Full public v6 State, RuleQA-shaped action questions, and legal ID mapping."""
import hashlib
import json
import random
import re
from pathlib import Path
from integration.strategist_eval.core import candidates as original_candidates, ensure_current

ROOT=Path('/workspace')
PRESERVED=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
RUN=PRESERVED/'runs/model-training/EX-108'
TRAIN=PRESERVED/'runs/model-training/EX-107'
ADAPTER=TRAIN/'adapter'
BASE=ROOT/'.pokechamp-data/tacit9b-runtime/model'
BASE_REV='884838f1698d1fd746625b3c20c8ec2be077a183'
MODEL_PY=Path('/ref/kev/.venv/bin/python')
BATTLE_PY=ROOT/'pokechamp/.venv/bin/python'
PORT=8108
SYSTEM=('Choose one legal action for the Gen9 Pokémon battle using only the supplied State and explicit conditions. '
        'Distinguish public observations from unknown facts and conditional calculations. '
        'Aim to win the battle. Give exactly one option ID on the first line and a brief reason on the next line.')
_adapter=None


def candidates(official):
    kind,legal=original_candidates(official)
    if len(legal)>10:raise ValueError('more than ten legal actions')
    return kind,[dict(row,option_id=chr(65+i)) for i,row in enumerate(legal)]


def parse(raw,legal):
    first=next((line.strip().replace('**','').replace('`','') for line in raw.splitlines() if line.strip()),'')
    if not first:return dict(parsed=False,error='empty_response',choice=None)
    first=re.sub(r'^answer\s*:\s*','',first,flags=re.I)
    match=re.match(r'^([A-Z])(?:[.):](?:\s|$)|$)',first)
    ids=re.findall(r'(?<!\w)([A-Z])(?=[.):](?:\s|$)|\s*(?:/|or\b|and\b|$))',first)
    if not match or len(ids)!=1:return dict(parsed=False,error='format_error',choice=None)
    found=[c for c in legal if c['option_id']==match[1]]
    return dict(parsed=True,error=None if len(found)==1 else 'outside_candidates',choice=found[0]['id'] if len(found)==1 else None)


def select(raw,legal,slot_id,decision_id):
    if not legal:raise ValueError('empty legal candidates')
    if len(legal)==1:return dict(choice=legal[0]['id'],automatic=True,fallback=False,parsed=None,error=None,fallback_seed=None)
    result=parse(raw,legal);seed=None
    if result['error']:
        seed=int.from_bytes(hashlib.sha256(f'20261019:{slot_id}:{decision_id}'.encode()).digest(),'big')
        result['choice']=random.Random(seed).choice(legal)['id']
    return dict(**result,automatic=False,fallback=bool(result['error']),fallback_seed=seed)


def build_input(official,prefix,actor,dex,own_team):
    from integration.pokechamp.jev_v6 import Adapter
    from integration.pokechamp.rule_qa.state import correct
    from integration.jev_planner.candidate_labels import candidate_input
    global _adapter
    if _adapter is None:_adapter=Adapter(dex)
    raw,commands,audit=_adapter.generate(official,prefix,own_team,actor=actor)
    named=candidate_input(raw,{'executor':{'candidate_display':'names-v1'}})
    public,edits=correct(named)
    kind,legal=candidates(official)
    criteria=public['questions']['action']['criteria']
    for c in legal:
        if commands[c['id']]!=c['command']:raise ValueError('v6/official command mismatch')
    actions={c['id']:criteria[c['id']] for c in legal}
    options=[dict(id=c['option_id'],text=actions[c['id']]['display_name']) for c in legal]
    user=dict(context=dict(state=public['state'],battle_actions=actions),
              conditions='Gen9 singles. Terastallization is disabled for both players. Use only public observations and your own team information. Damage estimates are conditional, not hidden-set facts.',
              question={'lead':'Which legal lead should you choose?', 'forced_switch':'Which legal replacement should you switch to?', 'turn_action':'Which legal action should you choose now to maximize your chance of winning?'}[kind],
              qa_options=options)
    return dict(messages=[dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(user,ensure_ascii=False,separators=(',',':')))],kind=kind,candidates=legal)


def close_builder():
    global _adapter
    if _adapter is not None:_adapter.close();_adapter=None
