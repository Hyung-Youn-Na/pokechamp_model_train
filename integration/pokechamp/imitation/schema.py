"""One target-free serialization boundary for restored and live decisions."""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
import re
from .config import VERSION
from .storage import canonical, digest

QUESTION = ('Choose one legal action for your side in this Generation 9 OU singles battle. '
            'Use the current observation, your original team sets, and public history. '
            'Unknown opponent information is unknown. Return the selected action ID. '
            'The probabilities represent action selection, not win probabilities.')
SNAPSHOT_KEYS = (
    'turn','decision_kind','own_team','opponent_team','own_active_slot','opponent_active_slot',
    'can_tera','opponent_can_tera','weather','field','own_side_conditions','opponent_side_conditions','history',
)
MON_KEYS = ('slot','species','hp_percent','status','boosts','item','ability','moves','types',
            'tera_type','terastallized','effects')
# D-195: kept when present; inputs without them (EX-071 prepared) stay valid and unchanged.
OPTIONAL_SNAPSHOT_KEYS = ('weather_turn',)
OPTIONAL_MON_KEYS = ('item_state','status_counter','status_source')
# D-198: opt-in events older than the four-turn `history` window, only in inputs built for models trained on them.
EXTENDED_SNAPSHOT_KEYS = ('early_history',)
SET_KEYS = ('species','item','ability','moves','nature','evs','ivs','level','gender','teraType','happiness')
FORBIDDEN = {'winner','outcome','rating','players','player','username','replay_id','sample_id',
             'label','target','targets','seed','rng','audit','provenance','metadata','future',
             'original_choice','opponent_original_set','private','source','sources','count','counts'}
KINDS = {'lead','turn_action','forced_switch','pivot_switch'}
ACTION = re.compile(r'^(?:move:[a-z0-9]+:(?:normal|tera)|(?:switch|lead):[1-6])$')


def _boundary(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in FORBIDDEN:
                raise ValueError('non-input field: ' + key)
            _boundary(item)
    elif isinstance(value, list):
        for item in value:
            _boundary(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite model input')


def _snapshot(value):
    if not isinstance(value, dict) or set(SNAPSHOT_KEYS) - set(value):
        raise ValueError('incomplete normalized snapshot')
    result = {key: value[key] for key in SNAPSHOT_KEYS + OPTIONAL_SNAPSHOT_KEYS + EXTENDED_SNAPSHOT_KEYS if key in value}
    if result['decision_kind'] not in KINDS:
        raise ValueError('label-dependent or unsupported decision kind')
    if type(result['turn']) is not int or result['turn'] < 0:
        raise ValueError('invalid turn')
    for side in ('own_team','opponent_team'):
        team = result[side]
        if not isinstance(team, list) or len(team) != 6:
            raise ValueError('expected six preview slots')
        if [m.get('slot') for m in team] != list(range(1, 7)):
            raise ValueError('unstable team slot order')
        clean = []
        for mon in team:
            if set(MON_KEYS) - set(mon):
                raise ValueError('incomplete public pokemon state')
            row = {key: mon[key] for key in MON_KEYS + OPTIONAL_MON_KEYS if key in mon}
            if side == 'own_team':
                if not isinstance(mon.get('original_set'), dict):
                    raise ValueError('missing original own set')
                row['original_set'] = {key:mon['original_set'][key] for key in SET_KEYS if key in mon['original_set']}
            clean.append(row)
        result[side] = clean
    # History is already public and ident-normalized by the single parser bridge.
    result['history'] = [{key: event[key] for key in ('turn','event','args')} for event in result['history']]
    if any(e['turn'] < max(0, result['turn'] - 4) or e['turn'] > result['turn'] for e in result['history']):
        raise ValueError('history is outside the four previous turns/current prefix')
    if 'early_history' in result:
        result['early_history'] = [{key: event[key] for key in ('turn','event','args')} for event in result['early_history']]
        if any(type(e['turn']) is not int or e['turn'] < 0 or e['turn'] >= result['turn'] - 4
               for e in result['early_history']):
            raise ValueError('early history overlaps the four-turn window')
    _boundary(result)
    return result


@dataclass(frozen=True)
class ImitationInput:
    body_json: str

    def __post_init__(self):
        body = json.loads(self.body_json)
        if set(body) != {'state','questions'} or not isinstance(body['state'], str):
            raise ValueError('invalid model boundary')
        state = json.loads(body['state'])
        if set(state) != {'version','snapshot'} or state['version'] != VERSION:
            raise ValueError('invalid input version')
        if _snapshot(state['snapshot']) != state['snapshot']:
            raise ValueError('unexpected snapshot fields at model boundary')
        if set(body['questions']) != {'action'}:
            raise ValueError('expected one Choice question')
        question = body['questions']['action']
        if set(question) != {'type','instructions','criteria'} or question['type'] != 'choice' or question['instructions'] != QUESTION:
            raise ValueError('unexpected Choice question')
        criteria = question['criteria']
        if not isinstance(criteria, dict) or not 1 <= len(criteria) <= 14:
            raise ValueError('invalid number of action candidates')
        for action_id, description in criteria.items():
            if not ACTION.fullmatch(action_id) or not isinstance(description, str) or not description:
                raise ValueError('invalid action ID/description')
        _boundary(body['questions'])

    @property
    def body(self):
        return json.loads(self.body_json)

    @property
    def payload_json(self):
        return self.body_json

    @property
    def action_ids(self):
        return tuple(self.body['questions']['action']['criteria'])

    @property
    def sha256(self):
        return digest(self.body_json.encode())

    @classmethod
    def from_body(cls, body):
        # Preserve criterion insertion order: it defines tie breaking and readout mapping.
        return cls(json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def describe_actions(snapshot, actions):
    """Canonical candidate wording: same normalized IDs in offline/live paths."""
    own = {row['slot']:row for row in snapshot['own_team']}
    described = []
    for action in actions:
        aid = action['id']
        if not isinstance(aid,str) or not ACTION.fullmatch(aid):
            raise ValueError('unsupported action identifier')
        parts = aid.split(':')
        kind = parts[0]
        if action.get('kind',kind) != kind:
            raise ValueError('action ID/kind mismatch')
        if kind == 'move':
            if action.get('move_id',parts[1]) != parts[1] or action.get('tera',parts[2]=='tera') != (parts[2]=='tera'):
                raise ValueError('move ID/metadata mismatch')
            description = 'Use ' + parts[1]
            if parts[2] == 'tera':
                active = own[snapshot['own_active_slot']]
                tera_type = active['original_set'].get('teraType',active['tera_type'])
                description += '; Terastallize into ' + str(tera_type)
        else:
            slot = int(parts[1])
            if action.get('slot',slot) != slot:
                raise ValueError('action ID/original slot mismatch')
            verb = 'Lead with' if kind == 'lead' else 'Switch to'
            description = f"{verb} slot {slot}: {own[slot]['species']}"
        described.append(dict(action,description=description))
    return described


def from_snapshot(snapshot, actions):
    snapshot = _snapshot(snapshot)
    criteria = {}
    for action in describe_actions(snapshot,actions):
        aid = action['id']
        if aid in criteria:
            raise ValueError('duplicate action ID')
        criteria[aid] = action['description']
    body = dict(state=canonical(dict(version=VERSION, snapshot=snapshot)),
                questions=dict(action=dict(type='choice', instructions=QUESTION, criteria=criteria)))
    return ImitationInput.from_body(body)


def permute(value, order):
    if type(value) is not ImitationInput or sorted(order) != list(range(len(value.action_ids))):
        raise ValueError('invalid candidate permutation')
    body = value.body
    criteria = body['questions']['action']['criteria']
    keys = list(criteria)
    body['questions']['action']['criteria'] = {keys[i]:criteria[keys[i]] for i in order}
    return ImitationInput.from_body(body)
