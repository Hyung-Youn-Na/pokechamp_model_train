"""The single offline/live input boundary. This module accepts no teacher data."""
from __future__ import annotations
import copy
from dataclasses import dataclass
import json
from .storage import canonical, digest

VERSION = 'pokemon-joint-q-input-v1'
SYSTEM = ('Estimate an independent q in [0,1] for EVERY supplied legal first action in this '
          'Generation 9 OU singles observation. After that action both sides use the fixed Abyssal policy. '
          'q is expected terminal score (win=1, draw=0.5, loss=0). These values do not sum to one. '
          'Output only a JSON object mapping each supplied action ID to its q, in supplied order. '
          'Do not choose just one action, use A/B answers, softmax, or invent hidden facts.')
FORBIDDEN = {'target_probabilities','q_targets','q_values','targets','counts','wdl','original_action_id',
             'original_choice','provenance','snapshot','server_snapshot','simulator','simulator_seed',
             'actor_seeds','future_seed','seed','rng','root_opponent_choice','trace','trace_path',
             'trace_sha256','opponent_original_set','private','winner'}


def boundary(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k.lower() in FORBIDDEN:
                raise ValueError('teacher/private field at model boundary: '+k)
            boundary(v)
    elif isinstance(value, (tuple, list)):
        for v in value:
            boundary(v)


@dataclass(frozen=True)
class JointInput:
    """Immutable model-only bytes; no record ID, target, seed or audit fields."""
    payload_json: str

    def __post_init__(self):
        value = json.loads(self.payload_json)
        if set(value) != {'version','instructions','state','actions'} or value['version'] != VERSION:
            raise ValueError('invalid joint input schema')
        boundary(value)
        ids = [a['action_id'] for a in value['actions']]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('empty or duplicate candidate IDs')

    @property
    def payload(self):
        return json.loads(self.payload_json)

    @property
    def action_ids(self):
        return tuple(a['action_id'] for a in self.payload['actions'])


def render(value, tokenizer=None):
    if type(value) is not JointInput:
        raise TypeError('render accepts JointInput only, never a training record')
    if tokenizer is None:
        return SYSTEM + '\n\n' + value.payload_json
    messages = [dict(role='system',content=SYSTEM),dict(role='user',content=value.payload_json)]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
    ids = tokenizer.encode(prompt, add_special_tokens=False)
    return prompt, ids  # No truncation; the future model chooses its own context contract.


def _speed(value, self_target, other_target):
    if value == 'unknown':
        return value
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('unexpected effective speed pair')
    return dict(self=dict(target=self_target,value=value[0],unit='effective_speed_stat'),
                opponent=dict(target=other_target,value=value[1],unit='effective_speed_stat'))


def project(payload):
    """Resolve C3 candidate sharing without changing conditional numerical results."""
    from ..diagnostics.candidate_state import candidate_evaluation
    from ..decision_instructions import COMMON, PROCEDURES
    from ..diagnostics.jev_offline import PROMPT
    state=copy.deepcopy(payload['state'])
    criteria=payload['questions']['action']['criteria']
    own={m['slot']:m for m in state['self_team']}
    active=next((m['species'] for m in state['self_team'] if m['active']), 'unknown')
    opposing=next((m['species'] for m in state['opponent_team'] if m['active']), 'unknown')
    for assumption in state.get('candidate_assumptions',[]):
        if 'current_effective_speeds' in assumption:
            assumption['current_effective_speeds']=_speed(assumption['current_effective_speeds'],active,opposing)
    actions=[]
    for aid, candidate in criteria.items():
        a=copy.deepcopy(candidate)
        a.pop('evaluation_ref',None)
        a['action_id']=aid
        evaluation=candidate_evaluation(payload,aid)
        evaluation.pop('same_outcomes_as_action_id',None)
        target=a.get('user',active) if a['kind']=='move' else own[a['slot']]['species']
        evaluation['quantities']=dict(self_hp=dict(target=target,unit='HP'),
            target_hp_pct=dict(target=opposing,unit='percent_of_target_max_HP'),
            incoming_damage_pct=dict(target=target,unit='percent_of_target_max_HP'),
            outgoing_damage_pct=dict(target=opposing,unit='percent_of_target_max_HP'),
            entry=dict(target=target,unit='HP; status_after is a status ID'),
            scope='named assumption and scenario only; future actions/end-turn unknown')
        for row in evaluation.get('scenarios',[]):
            if 'effective_speeds_after_entry' in row:
                row['effective_speeds_after_entry']=_speed(row['effective_speeds_after_entry'],target,opposing)
        if a['kind']=='switch':
            context=state['decision_context']
            a['switch']=dict(mode='voluntary' if state['decision_kind']=='turn_action' else 'requested',
                cause='voluntary' if state['decision_kind']=='turn_action' else context['switch_cause'],
                replaces_move=state['decision_kind']=='turn_action',target=target,
                opponent_action_remaining=context['opponent_action_remaining'],
                next_effective_action='unknown', after_end_turn='unknown')
        comparison=evaluation.get('tera_comparison')
        if comparison:
            baseline=candidate_evaluation(payload,comparison['non_tera_action_id'])
            comparison['non_tera_outcomes']=baseline  # Direct object, no other action lookup required.
            if not evaluation.get('scenarios') or not baseline.get('scenarios'):
                comparison['benefit']='unknown_without_nonempty_comparison_scenarios; future_strategic_value_unknown'
        a['evaluation']=evaluation
        actions.append(a)
    for key in ('candidate_evaluations','candidate_scenario_columns','candidate_switch_columns'):
        state.pop(key,None)
    # Keep the original interpretation and mechanics verbatim, replace its
    # single-choice paragraph and obsolete compact-outcome lookup instructions.
    original=PROMPT.read_text().split('\n\n',1)[1]
    common=COMMON.read_text().split('\n\n')
    common=[p for p in common if not p.startswith(('When an action has evaluation_ref',
            'Preserve supplied legal IDs'))]
    instructions=(PROCEDURES[state['decision_kind']].read_text().strip()+'\n\n'+
        '\n\n'.join(common)+'\n\n'+original+'\n\n'+
        'Candidate outcomes are named objects inside actions[]. Resolve assumptions directly in '
        'state.candidate_assumptions. Resolve general_effect_ref in state.effect_descriptions and '
        'role scope_ref/description_ref in state.role_descriptions; these general rules do not establish activation. '
        'Unknown is not zero or safety. Do not numerically complete '
        'uncomputed future actions or end-turn effects. Return independent q for every action ID.')
    state['version']=VERSION
    value=dict(version=VERSION,instructions=instructions,state=state,actions=actions)
    return JointInput(json.dumps(value,ensure_ascii=False,separators=(',', ':'),allow_nan=False))


def generate(official, prefix, own_team, *, dex, engine, snapshot=None, roles=None):
    from ..diagnostics.jev_offline import generate_input
    from ..diagnostics.candidate_state import enrich
    base, commands, audit=generate_input(official,prefix,own_team,dex,engine=engine,snapshot=snapshot,roles=roles)
    enhanced, extra=enrich(base,official,prefix,own_team,dex,engine=engine,snapshot=snapshot)
    value=project(enhanced)
    if value.action_ids!=tuple(commands):
        raise ValueError('serializer candidate order changed')
    return value, commands, dict(base=audit,candidate=extra)


def reorder(value, action_ids):
    if type(value) is not JointInput:
        raise TypeError('JointInput required')
    payload=value.payload
    if len(action_ids)!=len(value.action_ids) or set(action_ids)!=set(value.action_ids):
        raise ValueError('reorder must be an exact candidate permutation')
    by_id={a['action_id']:a for a in payload['actions']}
    payload['actions']=[by_id[k] for k in action_ids]
    return JointInput(json.dumps(payload,ensure_ascii=False,separators=(',',':')))


def fingerprint(value):
    """Canonical semantic state: ID, slot presentation and timestamps excluded."""
    from ..candidate_descriptions import expand
    payload=expand(value.payload)
    assumptions={a['assumption_id']:a for a in payload['state'].get('candidate_assumptions',[])}
    def normalize(v, parent=''):
        if isinstance(v,dict):
            return {k:normalize(child,k) for k,child in v.items() if k not in
                    {'request_id','action_id','non_tera_action_id','timestamp','event_seq','line_index',
                     'assumption_id','slot','preview_slot','move_ref'}}
        if isinstance(v,list):
            if parent=='assumptions':
                return sorted([normalize(assumptions[x]) for x in v],key=canonical)
            children=[normalize(x) for x in v]
            if parent in {'actions','self_team','opponent_team','current_move_slots','known_move_set',
                          'candidate_assumptions','scenarios'}:
                children.sort(key=canonical)
            return children
        return v
    return digest(normalize(payload))
