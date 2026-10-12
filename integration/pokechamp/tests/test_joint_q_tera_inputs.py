"""Historical public Tera consumption survives the official faint reset."""
import copy
import json

import pytest

from integration.pokechamp.joint_q.serializer import JointInput, VERSION as INPUT_VERSION
from integration.pokechamp.joint_q.tera_inputs import (
    OLD_STATE_RULE, NEW_STATE_RULE, OLD_INSTRUCTION, NEW_INSTRUCTION,
    public_tera_used, with_public_tera,
)


def observation():
    return JointInput(json.dumps(dict(version=INPUT_VERSION, instructions=OLD_INSTRUCTION,
        state=dict(actor='p2', information_rules=OLD_STATE_RULE,
            self_team=[dict(species='Mew', active=True, terastallized=False, defensive_types=['Psychic'])],
            opponent_team=[dict(species='Tornadus-Therian', active=False, fainted=True,
                                terastallized=False, defensive_types=['Flying'])]),
        actions=[dict(action_id='move_1')])))


def test_resource_survives_faint_without_rewriting_current_types():
    original=observation()
    prefix=[dict(protocol='|turn|1\n|-terastallize|p1a: Tornadus|Steel\n|turn|3\n|faint|p1a: Tornadus')]
    changed=with_public_tera(original,prefix)
    assert changed.payload['state']['terastallization_used']==dict(self=False,opponent=True)
    assert changed.payload['state']['opponent_team']==original.payload['state']['opponent_team']
    assert changed.payload['state']['self_team']==original.payload['state']['self_team']
    assert changed.payload['state']['information_rules']==NEW_STATE_RULE
    assert changed.payload['instructions']==NEW_INSTRUCTION
    assert changed.action_ids==original.action_ids and original.payload['instructions']==OLD_INSTRUCTION
    assert with_public_tera(changed,prefix)==changed


def test_private_requests_and_future_rng_never_change_public_resource_bits():
    public='|-terastallize|p2a: Mew|Fire'
    first=[dict(protocol=public+'\n|request|{"side":{"pokemon":[{"teraType":"Water"}]}}',rng=1)]
    second=[dict(protocol=public+'\n|request|{"hidden_moves":["Surf"],"future_rng":999}',rng=999)]
    assert with_public_tera(observation(),first)==with_public_tera(observation(),second)
    assert public_tera_used(first,actor='p1')==dict(self=False,opponent=True)


def test_no_public_event_is_unspent_even_with_current_type_or_private_claim():
    assert public_tera_used([dict(protocol='|request|{"terastallized":"Steel"}')])==dict(self=False,opponent=False)
    assert public_tera_used([])==dict(self=False,opponent=False)


@pytest.mark.parametrize('protocol',[
    '|-terastallize|p3a: Unknown|Fire', '|-terastallize|p1a: Mew|',
    '|-terastallize|p1a: Mew|Fire|unexpected',
    '|-terastallize|p1a: Mew|Fire\n|-terastallize|p1a: Mew|Fire',
])
def test_inconsistent_public_history_fails_closed(protocol):
    with pytest.raises(ValueError):
        public_tera_used([dict(protocol=protocol)])


def test_existing_wrong_resource_field_is_not_silently_repaired():
    payload=observation().payload
    payload['state']['terastallization_used']=dict(self=True,opponent=False)
    with pytest.raises(ValueError,match='disagree'):
        with_public_tera(JointInput(json.dumps(payload)),[])


def test_unrecognized_interpretation_is_not_silently_overridden():
    payload=observation().payload
    payload['state']['information_rules']='unspecified semantics'
    with pytest.raises(ValueError,match='semantics'):
        with_public_tera(JointInput(json.dumps(payload)),[])
