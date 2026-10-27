"""Independent response-attempt state machine for the frozen recovery policy."""
import json
from integration.jev27b.audit import require
from integration.openai_decisions_battle.core import normalized_response
from integration.pokechamp import jev_battle as j


def audit_responses(attempts, criteria, group, outcome):
    expected_response = 1
    expected_transport = 1
    rows = list(attempts.values())
    for index, row in enumerate(rows):
        transport = row['transport']
        require(transport['response_attempt'] == expected_response, 'response attempt sequence differs')
        require(transport['transport_attempt'] == expected_transport, 'transport attempt sequence differs')
        response = row.get('http_response')
        success = response and 200 <= response['status_code'] < 300
        if not success:
            require('response_attempt' not in row and 'response_retry' not in row,
                    'transport failure counted as response attempt')
            expected_transport += 1
            continue
        attempt = row.get('response_attempt')
        # A permanent model/schema error may terminate the collection before a response view exists.
        if attempt is None:
            require(index == len(rows)-1 and outcome.get('failure_scope') == 'collection',
                    'successful HTTP lacks response decision')
            continue
        require(attempt['response_attempt'] == expected_response, 'response record identity differs')
        try:
            raw = json.loads(response['raw_body'])
        except ValueError:
            normalized = None
            usable = False
        else:
            normalized = normalized_response(raw)
            try:
                j.validate_answer(normalized, criteria, version=j.VALIDATION_VERSION)
                usable = True
            except j.UnusableChoice:
                usable = False
        require(attempt['body'] == normalized and attempt['usable'] == usable, 'response classification differs')
        if usable:
            require(index == len(rows)-1 and 'response_retry' not in row, 'legal selection was requeried')
            require(group.get('response', {}).get('body') == normalized, 'first legal response was not used')
        elif expected_response < 3 and index < len(rows)-1:
            retry = row.get('response_retry', {})
            require(retry.get('next_response_attempt') == expected_response+1 and
                    retry.get('next_attempt') == index+2, 'response recovery link differs')
        else:
            require(index == len(rows)-1 and not outcome.get('completed') and 'selection' not in group,
                    'exhausted response used or fourth response requested')
        expected_response += 1
        expected_transport = 1
        require(expected_response <= 4, 'more than three responses')
