"""CPU HTTP checks exercise the 9B profile through the shared durable service."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import threading

import httpx
import pytest

from integration.jev27b import client as old_client, server as old_server
from integration.jev9b import client, config, server
from integration.jev9b.formatting import InputTooLong, format_request

IDENTITY = '9' * 64


def payload():
    return dict(model=config.MODEL_ID, state={'text': '순서 보존'}, questions={'action': dict(
        type='choice', instructions='Choose one', criteria={'switch:6': {}, 'move:1': {}})})


class FakeModel:
    def __init__(self, *, validation_error=None):
        self.calls = 0
        self.validation_error = validation_error

    def metadata(self):
        return dict(model=config.MODEL_ID, revision=config.REVISION, loaded=True,
                    serving_identity=IDENTITY)

    def validate_input(self, body):
        format_request(body)
        if self.validation_error:
            raise self.validation_error

    def evaluate(self, body):
        self.calls += 1
        return dict(model=config.MODEL_ID, answers={'action': dict(type='choice', choice='switch:6',
            probabilities={'switch:6': .8, 'move:1': .2})}, usage=dict(input_tokens=100, output_tokens=0))


@contextmanager
def running(tmp_path, model=None):
    service = server.LocalService(model or FakeModel(), tmp_path)
    httpd = server.LocalHTTPServer(('127.0.0.1', 0), service)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    thread.start()
    try:
        yield service, f'http://127.0.0.1:{httpd.server_port}'
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)
        service.close()


def invoke(service, request_id='same', body=None):
    raw = client.request_bytes(payload() if body is None else body)
    return service.evaluate(raw, request_id=request_id, body_sha256=hashlib.sha256(raw).hexdigest(),
                            expected_identity=IDENTITY)


def test_nine_b_health_and_wire_identity_reject_old_profile(tmp_path):
    with running(tmp_path) as (service, endpoint):
        with client.LocalClient(endpoint) as connection:
            health = connection.health()
            result = connection.evaluate(payload(), request_id='identity')
        assert health['model'] == result['model'] == config.MODEL_ID
        assert health['revision'] == config.REVISION
        assert result['transport']['protocol'] == client.PROTOCOL
        assert service.model.calls == 1
        with old_client.LocalClient(endpoint) as old:
            with pytest.raises(old_client.LocalRequestError) as error:
                old.health()
            assert error.value.category == 'serving_identity'
    with pytest.raises(ValueError):
        old_client.request_bytes(payload())
    with pytest.raises(server.RegistryError):
        old_server.LocalService(FakeModel(), tmp_path/'old')


def test_duplicate_requests_and_reopened_journal_never_repeat_inference(tmp_path):
    model = FakeModel()
    service = server.LocalService(model, tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(lambda _: invoke(service), range(4)))
        assert model.calls == 1 and sum(reused for _, _, reused in results) == 3
        assert all(status == 200 and raw == results[0][1] for status, raw, _ in results)
    finally:
        service.close()
    other = FakeModel()
    reopened = server.LocalService(other, tmp_path)
    try:
        result = invoke(reopened)
        assert result[1] == results[0][1] and result[2] is True and other.calls == 0
        altered = payload()
        altered['state']['text'] = 'different bytes'
        assert invoke(reopened, body=altered)[0] == 409 and other.calls == 0
    finally:
        reopened.close()


def test_overlong_input_has_zero_actual_inference_reservations(tmp_path):
    fake = FakeModel(validation_error=InputTooLong(32769, 32768))
    service = server.LocalService(fake, tmp_path)
    try:
        status, raw, reused = invoke(service)
        assert status == 422 and reused is False and fake.calls == 0
        assert json.loads(raw)['error']['category'] == 'input_too_long'
        assert service.registry.get('same')['inference_calls'] == 0
        assert service.health()['ready'] is False
    finally:
        service.close()


def test_http_retry_keeps_original_bytes_and_request_id(monkeypatch):
    requests, delays = [], []
    monkeypatch.setattr(old_client.time, 'sleep', delays.append)
    def handler(request):
        requests.append(request)
        if len(requests) < 4:
            raise httpx.ReadTimeout('temporary', request=request)
        digest = hashlib.sha256(request.content).hexdigest()
        request_id = request.headers['X-Request-ID']
        inference_id = hashlib.sha256((IDENTITY+'\0'+request_id+'\0'+digest).encode()).hexdigest()
        return httpx.Response(200, json=dict(model=config.MODEL_ID,
            transport=dict(protocol=client.PROTOCOL, request_id=request_id, body_sha256=digest,
                serving_identity=IDENTITY, inference_id=inference_id, inference_calls=1)),
            headers={'X-Request-ID': request_id, 'X-Body-SHA256': digest,
                     'X-Serving-Identity': IDENTITY, 'X-Cache-Reused': '1'})
    with client.LocalClient(expected_identity=IDENTITY, transport=httpx.MockTransport(handler)) as connection:
        result = connection.evaluate(payload(), request_id='retry-same', retries=3)
    assert result['model'] == config.MODEL_ID and len(requests) == 4
    assert delays == [10., 30., 60.]
    assert all(r.content == client.request_bytes(payload()) for r in requests)
    assert {r.headers['X-Request-ID'] for r in requests} == {'retry-same'}
