"""NHJ-20261028 regression set: fixture identity and labels, scoring classes, and a served round trip.

Opt-in (`LAYA_REGRESSION=1`): the set fixes single decisions on v1.1's own trajectory, so it cannot judge a model
that leaves that path earlier (battle 39 turn 2), and it is not part of the default suite.
"""
import json
import os
import threading

import pytest

from integration.laya_imitation import regression as rg
from integration.laya_imitation import serving
from integration.laya_imitation import config as c
from integration.laya_imitation.tests.test_serving import UniformPolicy
from integration.pokechamp.imitation.schema import ImitationInput

pytestmark = pytest.mark.skipif(os.environ.get('LAYA_REGRESSION') != '1',
                                reason='NHJ-20261028 regression set is opt-in: LAYA_REGRESSION=1')
DOC = rg.read(rg.FIXTURE)


def test_fixture_identity_and_labels():
    assert rg.digest(DOC['cases']) == DOC['digest']
    assert len(DOC['cases']) == len(rg.CASES) == 27
    assert {x['group'] for x in DOC['cases']} == set(rg.GROUPS)
    for x in DOC['cases']:
        value = ImitationInput(x['input_json'])
        ids = list(value.action_ids)
        assert value.sha256 == x['input_sha256'] and x['action_ids'] == ids and set(x['baseline']['probabilities']) == set(ids)
        assert x['preferred'] and set(x['preferred']) <= set(ids) and set(x['bad']) <= set(ids)
        assert not set(x['bad']) & set(x['preferred'])
        assert (x['group'] in ('immune', 'noop', 'tera')) == bool(x['bad'])
        assert abs(sum(x['baseline']['probabilities'].values()) - 1) < 1e-6
        assert x['baseline']['checkpoint_sha256'] == '12519d98a416b156b9813d464294788487dd9b9bdb411973bc62c5dd4707f235'
    tinglu = next(x for x in DOC['cases'] if x['id'] == 'b34-t18-tinglu')
    assert set(tinglu['bad']) == {'move:%s:%s' % (m, k) for m in ('earthquake', 'whirlwind', 'taunt')
                                  for k in ('normal', 'tera')}
    assert all(k.startswith('switch:') for k in tinglu['preferred'])
    assert all(k.endswith(':tera') for k in next(x for x in DOC['cases'] if x['id'] == 'b38-t60-tera')['bad'])


def test_v11_baseline_is_the_reported_failure():
    rows, summary = rg.baseline(DOC)
    assert summary['immune']['top_bad'] == 7 and summary['noop']['top_bad'] == 1 and summary['tera']['top_bad'] == 1
    assert summary['wall']['top_preferred'] == summary['stuck']['top_preferred'] == 0
    assert summary['control']['top_preferred'] == 3
    assert all(r['v11']['choice'] == x['baseline']['choice'] for r, x in zip(rows, DOC['cases']))


def test_case_score_classes_and_first_maximum():
    case = dict(action_ids=['a', 'b', 'c', 'd'], bad=['a'], preferred=['b', 'c'])
    assert rg.case_score(case, dict(a=0.4, b=0.3, c=0.2, d=0.1)) == dict(choice='a', bad_mass=0.4, preferred_mass=0.5,
                                                                         top='bad')
    assert rg.case_score(case, dict(d=0.3, c=0.3, b=0.3, a=0.1))['choice'] == 'b'
    assert rg.case_score(case, dict(a=0.1, b=0.1, c=0.1, d=0.7))['top'] == 'other'


@pytest.fixture()
def server():
    s = serving.create_server(c.MODEL_DIR, 'laya-initial', policy=UniformPolicy())
    thread = threading.Thread(target=s.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%d' % s.server_address[1]
    s.shutdown()
    s.server_close()


def test_score_round_trip(server, tmp_path):
    result = rg.score(server, tmp_path / 'r.json')
    assert result['model'] == 'laya-initial' and len(result['rows']) == 27 and result['identical_to_v11'] == 0
    assert all(r['model']['choice'] == ImitationInput(x['input_json']).action_ids[0]
               for r, x in zip(result['rows'], DOC['cases']))
    assert json.loads((tmp_path / 'r.json').read_text())['fixture_digest'] == DOC['digest']
    with pytest.raises(FileExistsError):
        rg.score(server, tmp_path / 'r.json')
    assert 'v1.1' in rg.table(result)
