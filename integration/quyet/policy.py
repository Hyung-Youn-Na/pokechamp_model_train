"""Two-stage action policy. The original observation never changes between stages."""
from __future__ import annotations

import copy
import time
from integration.pokechamp import jev_battle as j

VERSION = 'quyet-two-stage-v1'
STAGES = ('action_type', 'action_detail')
FIRST_SENTENCE = ('Choose exactly one supplied legal candidate that best improves your chance of '
                  'winning this Generation 9 OU singles battle.')
TYPE_SENTENCE = ('Choose exactly one supplied action type, move or switch, that best improves your '
                 'chance of winning this Generation 9 OU singles battle. Each type description '
                 'contains all of its legal detail candidates; consider all of them before choosing '
                 'the type. A separate decision will select one detail from that type.')


def split_candidates(payload):
    question = payload['questions']['action']
    criteria = question['criteria']
    if not criteria or any(not isinstance(v, dict) for v in criteria.values()):
        raise ValueError('nonempty candidate objects required')
    phase = payload['state']['decision_kind']
    if phase in ('lead', 'forced_switch'):
        expected = 'team' if phase == 'lead' else 'switch'
        if len(criteria) > (6 if phase == 'lead' else 5) or any(v['kind'] != expected for v in criteria.values()):
            raise ValueError('invalid direct-selection candidates')
        return None
    if phase != 'turn_action' or any(v['kind'] not in ('move', 'switch') for v in criteria.values()):
        raise ValueError('invalid action type')
    groups = {kind: {key: copy.deepcopy(value) for key, value in criteria.items() if value['kind'] == kind}
              for kind in ('move', 'switch')}
    if len(groups['move']) > 8 or len(groups['switch']) > 5:
        raise ValueError('action group exceeds frozen limit')
    return {key: value for key, value in groups.items() if value}


def type_request(payload, groups=None):
    groups = split_candidates(payload) if groups is None else groups
    if not groups:
        raise ValueError('direct selection has no type request')
    result = copy.deepcopy(payload)
    q = result['questions']['action']
    if not q['instructions'].startswith(FIRST_SENTENCE):
        raise ValueError('unknown action instruction; refuse silent rewrite')
    q['instructions'] = q['instructions'].replace(FIRST_SENTENCE, TYPE_SENTENCE, 1).replace(
        'Candidate IDs are executable choices.',
        'Choose the type ID move or switch. The nested candidate IDs identify executable detail choices.', 1)
    q['criteria'] = {kind: {'action_type': kind, 'candidates': copy.deepcopy(candidates)}
                     for kind, candidates in groups.items()}
    return result


def detail_request(payload, selected_type=None):
    groups = split_candidates(payload)
    result = copy.deepcopy(payload)
    if groups is not None:
        if selected_type not in groups:
            raise ValueError('detail branch not selected from legal types')
        result['questions']['action']['criteria'] = groups[selected_type]
    elif selected_type is not None:
        raise ValueError('direct selection cannot have a type branch')
    return result


async def select(payload, *, decision, session, check_current):
    """Persist each stage even on cancellation/failure; send no game command here."""
    original = copy.deepcopy(payload)
    groups = split_candidates(original)

    async def stage(name, request, reason=None):
        try:
            await check_current(name)
        except BaseException as error:
            session.record(dict(type='stage_failure', decision=decision, stage=name,
                error=dict(type=type(error).__name__, detail=str(error)), elapsed_seconds=0))
            raise
        candidates = request['questions']['action']['criteria']
        automatic = len(candidates) == 1
        session.record(dict(type='stage_input', decision=decision, stage=name, payload=request,
                            candidate_ids=list(candidates), will_infer=not automatic))
        started = time.monotonic()
        try:
            if automatic:
                choice, response = next(iter(candidates)), None
            else:
                response = await session.evaluate(request, decision=decision, stage=name)
                session.record(dict(type='stage_response', decision=decision, stage=name,
                                    body=response, elapsed_seconds=time.monotonic() - started))
                choice = j.validate_answer(response, candidates, version=j.VALIDATION_VERSION)
                session.record(dict(type='judgment_diagnostics', decision=decision, stage=name,
                    diagnostics=j.judgment_diagnostics(response['answers']['action'], candidates)))
            session.record(dict(type='stage_selection', decision=decision, stage=name,
                choice=choice, automatic=automatic, skipped=False,
                automatic_reason=(reason or 'single_detail_candidate') if automatic else None,
                elapsed_seconds=time.monotonic() - started,
                probability_scope='action_types' if name == 'action_type' else
                                  'conditional_on_selected_type' if groups is not None else 'direct_candidates'))
            return choice
        except BaseException as error:
            session.record(dict(type='stage_failure', decision=decision, stage=name,
                error=dict(type=type(error).__name__, detail=str(error)),
                elapsed_seconds=time.monotonic() - started))
            raise

    if groups is None:
        session.record(dict(type='stage_selection', decision=decision, stage='action_type',
            choice=None, automatic=True, skipped=True,
            automatic_reason=original['state']['decision_kind'], elapsed_seconds=0))
        chosen_type = None
    else:
        chosen_type = await stage('action_type', type_request(original, groups), 'only_legal_type')
    choice = await stage('action_detail', detail_request(original, chosen_type))
    try:
        await check_current('final_transmission')
    except BaseException as error:
        session.record(dict(type='decision_failure', decision=decision, stage='final_transmission',
            error=dict(type=type(error).__name__, detail=str(error))))
        raise
    return choice
