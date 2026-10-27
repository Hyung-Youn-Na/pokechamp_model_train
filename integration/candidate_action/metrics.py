"""Confirmed usage includes every HTTP body, including discarded refusals."""
import json


def response_metrics(events):
    requests = [e for e in events if e['type'] == 'transport']
    responses = {e['request_number']: e for e in events if e['type'] == 'http_response'}
    usage = dict(input_tokens=0, output_tokens=0)
    unknown = []
    for request in requests:
        number = request['request_number']
        raw = responses.get(number, {})
        try:
            body = json.loads(raw.get('raw_body', 'null'))
        except ValueError:
            body = None
        supplied = body.get('usage') if isinstance(body, dict) else None
        complete = True
        for key in usage:
            value = supplied.get(key) if isinstance(supplied, dict) else None
            if type(value) is int and value >= 0:
                usage[key] += value
            else:
                complete = False
        if not complete:
            unknown.append(number)
    attempts = [e for e in events if e['type'] == 'response_attempt']
    retries = [e for e in events if e['type'] == 'response_retry']
    recovered = {e['decision'] for e in attempts if e['usable'] and e['response_attempt'] > 1}
    exhausted = {e['decision'] for e in attempts if not e['usable'] and e['response_attempt'] == 3}
    return dict(received_usage=usage, tokens=None if unknown else usage,
        usage_unknown_attempts=len(unknown), usage_unknown_request_numbers=unknown,
        usage_unknown_requests=len({e['decision'] for e in requests if e['request_number'] in unknown}),
        transport_retries=sum(e['type']=='provider_retry' for e in events),
        response_requeries=len(retries), response_attempts=sum(200 <= e['status_code'] < 300 for e in responses.values()),
        response_recovery_decisions=len({e['decision'] for e in retries}),
        response_recovered_decisions=len(recovered), response_exhausted_decisions=len(exhausted),
        all_http_attempts=len(requests), logical_requests=len({e['decision'] for e in requests}),
        transport_retry_decisions=len({e['decision'] for e in events if e['type']=='provider_retry'}))
