"""Canonical and training projections with an explicit model-input whitelist."""
from __future__ import annotations
import copy
import hashlib
import json
import random
from . import SEED
SYSTEM = ('Answer the Gen9 Pokémon rules question using only the supplied State or short scenario and explicit conditions. '
          'Distinguish public observations from unknown facts and conditional calculations. '
          'Do not choose a battle action. Give the answer and a brief reason; for a multiple-choice question, give its option ID.')


def dumps(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(dumps(value).encode()).hexdigest()

def split_map():
    result={}
    for r in range(1,25):
        ids=[f'R{r:02}-{i:02}' for i in range(40)]
        random.Random(f'{SEED}:R{r:02}').shuffle(ids)
        for i,key in enumerate(ids):result[key]='train' if i<32 else 'validation' if i<36 else 'test'
    return result


def concise(value):
    if isinstance(value,dict):
        return {k:concise(v) for k,v in value.items() if k not in ('general_effect','general_rules','role_summary')}
    if isinstance(value,list):return [concise(v) for v in value]
    return value


def short_context(facts):
    def text(value):
        if isinstance(value,str):return value or 'none'
        if isinstance(value,bool):return 'yes' if value else 'no'
        return json.dumps(concise(value),ensure_ascii=False,sort_keys=True,separators=(', ', ': '))
    return ' '.join(f'{key.replace("_"," ").capitalize()}: {text(value)}.' for key,value in sorted(facts.items()))


def render(spec,payload,question,*,splits=None):
    split=(splits or split_map())[spec['group_id']]
    result=[]
    for form in ('short_qa','state_qa','state_mc'):
        row=dict(id=spec['scenario_id']+'-'+form,rule_id=spec['rule_id'],group_id=spec['group_id'],
                 scenario_id=spec['scenario_id'],representation=form,conditions=question['conditions'],
                 question=question['question'],options=[],answer=question['answer'],rationale=question['rationale'],split=split)
        if form=='short_qa':row['context']=short_context(question['facts'])
        else:row['context']=copy.deepcopy(payload)
        if form=='state_mc':
            options=[question['answer'],*question['distractors']]
            random.Random(f'{SEED}:{row["id"]}').shuffle(options)
            row['options']=[dict(id=chr(65+i),text=value) for i,value in enumerate(options)]
            row['answer_id']=next(o['id'] for o in row['options'] if o['text']==row['answer'])
        result.append(row)
    return result


def messages(row,*,include_answer=True):
    # IDs, split labels, oracle logs, raw team files, and evidence are never model input.
    user=dict(context=row['context'],conditions=row['conditions'],question=row['question'])
    if row['options']:user['qa_options']=row['options']
    result=[dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(user,ensure_ascii=False,separators=(',',':')))]
    if include_answer:
        prefix=(row['answer_id']+'. ') if row['representation']=='state_mc' else ''
        result.append(dict(role='assistant',content=prefix+row['answer']+'\n'+row['rationale']))
    return result


def choice_export(row):
    if row['representation']!='state_mc':raise ValueError('multiple-choice representation required')
    return dict(id=row['id'],state=row['context']['state'],battle_actions=row['context']['battle_actions'],
                conditions=row['conditions'],question=row['question'],options=row['options'],
                answer_id=row['answer_id'],rationale=row['rationale'],split=row['split'])
