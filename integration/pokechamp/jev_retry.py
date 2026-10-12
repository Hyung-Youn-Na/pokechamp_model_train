"""Fixed JEV provider retry policy; legacy is only for sealed execution profiles."""
CURRENT = 'jev-provider-retry-v2'
V1 = 'jev-provider-retry-v1'
LEGACY = 'jev-no-retry-v1'
DELAYS = (10., 30., 60.)
RETRY_POLICIES = (V1, CURRENT)


def delays_for(version):
    if version == CURRENT:
        return DELAYS
    if version == V1:
        return (1., 2., 4.)
    if version == LEGACY:
        return ()
    raise ValueError('unknown JEV retry policy')


def retryable(error):
    from .jev import JevRequestError
    return isinstance(error, JevRequestError) and (error.category in ('timeout', 'transport') or
        error.category == 'http' and (error.status_code == 429 or
            isinstance(error.status_code, int) and 500 <= error.status_code <= 599))


def audit_attempts(events, inputs, result, *, checkpoint=False, version=CURRENT):
    """Verify physical attempts without treating retries as new decisions."""
    from .jev import JevRequestError
    delays = delays_for(version)
    transports = [e for e in events if e['type'] == 'transport']
    numbers = [e['request_number'] for e in transports]
    assert not numbers or numbers == list(range(numbers[0], numbers[0] + len(numbers))), 'HTTP attempt numbering'
    if not checkpoint:
        assert not numbers or numbers[0] == 1
        assert len(transports) == result['requests'], 'HTTP attempt denominator'
    requests = [e for e in events if e['type'] == 'http_request']
    by_number = {e['request_number']: e for e in requests}
    assert len(by_number) == len(requests) and set(by_number) == set(numbers), 'HTTP attempt payload coverage'
    failures = {e['request_number']: e for e in events if e['type'] == 'attempt_failure'}
    retries = {e['request_number']: e for e in events if e['type'] == 'provider_retry'}
    previous = {}
    for transport in transports:
        key, number = transport['decision'], transport['request_number']
        request = by_number[number]
        assert request['decision'] == key
        assert request['body'] == dict(model=transport['model'], **inputs[key]['payload']), 'HTTP retry input drift'
        assert 0 < transport['timeout'] <= 60
        old = previous.get(key)
        assert transport['attempt'] == (old['attempt'] + 1 if old else 1) <= 4, 'HTTP retry count'
        if old:
            old_number = old['request_number']
            failure, retry = failures[old_number], retries[old_number]
            assert retryable(JevRequestError(failure['category'], status_code=failure['status_code'])), 'nonretryable attempt'
            assert retry['next_attempt'] == transport['attempt']
            assert retry['delay_seconds'] == delays[old['attempt'] - 1]
            assert old['model'] == transport['model'] and old['endpoint'] == transport['endpoint']
            assert by_number[old_number]['body'] == request['body']
            assert failure['event_seq'] < retry['event_seq'] < transport['event_seq']
        previous[key] = transport
    raw = {e['request_number']: e for e in events if e['type'] == 'http_response'}
    import json
    for event in events:
        if event['type'] == 'response':
            number = previous[event['decision']]['request_number']
            assert number not in failures, 'failed attempt used as model response'
            if number in raw:
                assert 200 <= raw[number]['status_code'] < 300
                assert json.loads(raw[number]['raw_body']) == event['body']
    return dict(physical_attempts=len(transports), logical_requests=len(previous),
                retries=len(transports) - len(previous))
