"""v6 정보 보존 변환과 원문을 보존하는 단일 HTTP 호출."""
from __future__ import annotations

import json
import math
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from integration.openai_decisions.client import ENDPOINT, MODEL, DecisionsError

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-109')
BASELINE = RUN.parent / 'EX-089' / 'collection'
EXPORT = ROOT / 'exports/battle_viewers/ex109'
PORT = 8109
ACTOR_PYTHON = ROOT / 'pokechamp/.venv/bin/python'
EXPERIMENT = 'EX-109'
TIMEOUT = 60.0
CALL_LIMIT = 20000
COLLECTION_SECONDS = 43200


class TransportFailure(DecisionsError):
    """새 재시도 프로필에서 통신 실패와 영구 오류를 구별한다."""
    def __init__(self, message, *, retryable, retry_after=0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def retry_after_seconds(value):
    if not value:
        return 0.0
    try:
        seconds=float(value)
        return max(0.0,seconds) if math.isfinite(seconds) else 0.0
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp()-time.time())
        except (ValueError, TypeError, OverflowError):
            return 0.0


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def to_request(payload):
    if payload['state']['version'] != 'jev-choice-v6':
        raise ValueError('v6 detailed input required')
    if set(payload) != {'state', 'questions'} or set(payload['questions']) != {'action'}:
        raise ValueError('unexpected source fields; refusing to drop information')
    question = payload['questions']['action']
    if set(question) != {'type', 'instructions', 'criteria'} or question['type'] != 'choice':
        raise ValueError('unexpected source question')
    criteria = question['criteria']
    if not 2 <= len(criteria) <= 255 or not all(isinstance(key, str) for key in criteria):
        raise ValueError('API requires 2..255 unique string choices')
    return dict(model=MODEL, input=dumps(payload['state']), questions=[dict(
        name='action', type='choice', instructions=question['instructions'],
        choices=[dict(value=key, description=dumps(value)) for key, value in criteria.items()])])


def from_request(request):
    """역변환은 원 v6 state·지시문·후보의 손실 검증용이다."""
    question, = request['questions']
    return dict(state=json.loads(request['input']), questions=dict(action=dict(
        type=question['type'], instructions=question['instructions'],
        criteria={choice['value']: json.loads(choice['description']) for choice in question['choices']})))


def normalized_response(raw):
    """공유 선택 검증용 뷰. 실제 HTTP 응답은 별도 원문에 남긴다."""
    if not isinstance(raw, dict) or raw.get('model') != MODEL:
        raise DecisionsError('API 응답 model이 요청과 다릅니다.')
    answers = raw.get('answers')
    if not isinstance(answers, list) or len(answers) != 1:
        answer = {}
    else:
        original = answers[0]
        answer = dict(original) if isinstance(original, dict) else {}
        if answer.get('name') != 'action' or answer.get('type') != 'choice':
            answer.pop('choice', None)
        probabilities = answer.get('probabilities')
        if isinstance(probabilities, list):
            valid = all(isinstance(item, dict) and isinstance(item.get('value'), str)
                        and 'probability' in item for item in probabilities)
            if valid and len({item['value'] for item in probabilities}) == len(probabilities):
                answer['probabilities'] = {item['value']: item['probability'] for item in probabilities}
            else:
                answer['probabilities'] = None
    return dict(model=raw['model'], answers=dict(action=answer), usage=raw.get('usage'),
                metadata=dict(response_view='openai-decisions-to-choice-v1'))


def call_http(request, key, record, *, decision, request_number, client=None, attempt=1):
    encoded = dumps(request).encode('utf-8')
    common = dict(decision=decision, request_number=request_number, attempt=attempt)
    record(dict(type='transport', endpoint=ENDPOINT, model=MODEL, timeout=TIMEOUT, **common))
    record(dict(type='http_request', body=request, raw_body=encoded.decode(), **common))
    owned = client is None
    client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
    started = time.monotonic()
    try:
        try:
            response = client.post(ENDPOINT, content=encoded,
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        except httpx.RequestError as exc:
            record(dict(type='attempt_failure', category='transport', status_code=None,
                        exception_type=type(exc).__name__, retryable=True,
                        elapsed_seconds=time.monotonic()-started, **common))
            raise TransportFailure('OpenAI 연결 실패/시간 초과: '+type(exc).__name__, retryable=True) from None
        text = response.text.replace(key, '[REDACTED]') if key else response.text
        record(dict(type='http_response', status_code=response.status_code, raw_body=text,
                    elapsed_seconds=time.monotonic()-started,
                    provider_request_id=response.headers.get('x-request-id'), **common))
        if not response.is_success:
            retryable=response.status_code in (408,429) or 500<=response.status_code<=599
            retry_after=retry_after_seconds(response.headers.get('retry-after'))
            record(dict(type='attempt_failure', category='http', status_code=response.status_code,
                        retryable=retryable,retry_after_seconds=retry_after,**common))
            raise TransportFailure(f'OpenAI HTTP {response.status_code}; see redacted transport evidence',
                                   retryable=retryable,retry_after=retry_after)
        try:
            raw = json.loads(text)
        except ValueError:
            raise DecisionsError('OpenAI response is not JSON') from None
        return normalized_response(raw)
    finally:
        if owned:
            client.close()
