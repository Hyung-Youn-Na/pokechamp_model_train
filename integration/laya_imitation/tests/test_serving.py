"""Serving contract: the unchanged EX-071 player validator accepts responses; identity and boundary refusals."""
import itertools
import json
import threading
import urllib.error

import pytest

from integration.laya_imitation import config as c
from integration.laya_imitation import serving
from integration.pokechamp.imitation.player import http_json, validate_response
from integration.pokechamp.imitation.schema import ImitationInput


class UniformPolicy:
    def predict(self, value):
        ids = list(value.action_ids)
        probs = {k: 1.0 / len(ids) for k in ids}
        return dict(input_sha256=value.sha256, action_ids=ids, probabilities=probs, choice=ids[0])


@pytest.fixture(scope='module')
def server():
    s = serving.create_server(c.MODEL_DIR, 'laya-initial', policy=UniformPolicy())
    thread = threading.Thread(target=s.serve_forever, daemon=True)
    thread.start()
    yield s, 'http://127.0.0.1:%d' % s.server_address[1]
    s.shutdown()


def body(n=1):
    with open(c.EX071_PREPARED / 'validation.jsonl') as f:
        return [json.loads(line)['input'] for line in itertools.islice(f, n)]


def test_player_validator_accepts_response(server):
    s, origin = server
    for b in body(8):
        value = ImitationInput.from_body(b)
        response = http_json(origin, '/evaluate', body=dict(model='laya-initial', input=value.body))
        choice, probabilities = validate_response(response, value, model='laya-initial',
                                                  checkpoint_sha256=s.model_identity['checkpoint_sha256'])
        assert choice in value.action_ids and abs(sum(probabilities.values()) - 1) < 1e-9


def test_model_identity_and_boundary_refusals(server):
    _, origin = server
    b = body()[0]
    with pytest.raises(Exception) as wrong_model:
        http_json(origin, '/evaluate', body=dict(model='laya-selected', input=b))
    assert '409' in str(wrong_model.value) or isinstance(wrong_model.value, urllib.error.HTTPError)
    bad = json.loads(json.dumps(b))
    state = json.loads(bad['state'])
    state['snapshot']['own_team'][0]['rating'] = 1500
    bad['state'] = json.dumps(state)
    with pytest.raises(Exception):
        http_json(origin, '/evaluate', body=dict(model='laya-initial', input=bad))


def test_health_reports_render_identity(server):
    s, origin = server
    health = http_json(origin, '/health')
    assert health['checkpoint_sha256'] == s.model_identity['checkpoint_sha256']
    assert health['render']['render'] == c.RENDER_VERSION
    assert serving.renderer_matches_dataset()
