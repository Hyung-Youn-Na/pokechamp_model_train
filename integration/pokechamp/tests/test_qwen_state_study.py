"""Study denominators, append-only HTTP failures and separate prediction/rank evidence."""
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest

from integration.pokechamp import qwen_state_study as study


def saved_records():
    source = study.v.ROOT / 'exports/battle_viewers/ex063/battle-1/decisions.json'
    return [dict(decision=row['id'], body=row['request'], original_response=row['response'],
                 input_generation_seconds=.2, body_sha256=study.digest(row['request']))
            for row in json.loads(source.read_text())['decisions']]


def setup_prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'assert_preserved', lambda _: {'original': 'unchanged'})
    study.write_new(tmp_path / 'preparation.json', dict(prepared=True))
    study.write_new(tmp_path / 'preflight-tokens.json', dict(passed=True))
    records = saved_records()
    for condition in study.CONDITIONS:
        (tmp_path / condition).mkdir()
        for record in records:
            study.append(tmp_path / condition / 'inputs.jsonl', dict(record, condition=condition))
    cases = study.diagnostic_cases(records)
    study.write_new(tmp_path / 'diagnostic-cases.json', cases)
    study.write_new(tmp_path / 'rubric.json', [study.rubric_for(case) for case in cases])
    return records, cases


class Server:
    def __init__(self, evaluate=None, diagnose=None):
        self.paths = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, status, value):
                raw = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(status)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                owner.paths.append(self.path)
                self.reply(200, dict(ready=True, revision=study.v.REVISION,
                    adapter_sha256=study.v.ADAPTER_SHA, allowed_input_versions=list(study.VERSIONS)))

            def do_POST(self):
                owner.paths.append(self.path)
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                callback = evaluate if self.path == '/evaluate' else diagnose
                status, answer = callback(body)
                self.reply(status, answer)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    @property
    def endpoint(self):
        return 'http://127.0.0.1:' + str(self.http.server_port)


def test_exact_saved_scene_denominators_and_no_answer_in_scenarios():
    records = saved_records()
    cases = study.diagnostic_cases(records)
    assert len(cases) == 30
    assert sum(c['kind'] == 'lead' for c in cases) == 6
    assert sum(c['kind'] == 'forced_switch' for c in cases) == 15
    assert sum(c['kind'] == 'turn_action' for c in cases) == 9
    assert sum(len(r['body']['actions']) for r in records) == 121
    close_combat = next(c for c in cases if c['turn'] == 3 and c['kind'] == 'turn_action')
    assert 'self_defense_stage_after_move' not in json.dumps(close_combat['scenario'])
    assert 'remaining_opponent_action' not in close_combat['scenario']


def test_instructions_are_only_c2_change_without_mutating_original():
    payload = saved_records()[3]['body']['observation']
    before = copy.deepcopy(payload)
    updated = study.instruction_only(payload, lambda original, kind: 'procedure:' + kind + '\n' + original)
    assert payload == before
    assert updated['state'] == payload['state']
    diffs = study.differences(payload, updated)
    assert [r['path'] for r in diffs] == ['$.questions.action.instructions']


def test_preflight_separates_q_success_from_reserved_diagnostic_overflow(tmp_path, monkeypatch):
    from integration.pokechamp import qwen_diagnostics
    monkeypatch.setattr(study, 'assert_preserved', lambda _: {})
    study.write_new(tmp_path / 'preparation.json', dict(prepared=True))
    record = saved_records()[3]
    for condition in study.CONDITIONS:
        (tmp_path / condition).mkdir()
        study.append(tmp_path / condition / 'inputs.jsonl', record)
    case = study.diagnostic_cases(saved_records())[6]
    case = dict(case, decision=record['decision'])
    study.write_new(tmp_path / 'diagnostic-cases.json', [case])
    old = record['original_response']['candidates']
    audits = [{k: row[k] for k in ('action_id', 'tokens', 'prompt_sha256', 'token_sha256')}
              for row in old]
    monkeypatch.setattr(study.v, 'encoded_candidates', lambda *a, **k:
                        (None, [(None, audit) for audit in audits]))
    def overflow(*_):
        raise ValueError('diagnostic input has 16000 tokens plus 512 reserved output tokens; no truncation')
    monkeypatch.setattr(qwen_diagnostics, 'encode', overflow)
    result = study.token_preflight(tmp_path, object())
    assert result['q_passed']
    assert not result['diagnostics_passed'] and not result['passed']
    assert len(result['diagnostics']) == len(result['errors']) == 3
    assert all(row['stage'] == 'diagnostics' for row in result['errors'])
    assert all('error' in row for row in result['diagnostics'])
    assert result['model_calls'] == 0


def test_http_failure_keeps_raw_body_and_stops_without_retry(tmp_path, monkeypatch):
    setup_prepared(tmp_path, monkeypatch)
    with Server(evaluate=lambda _: (408, b'original timeout text')) as server:
        result = study.evaluate(tmp_path, endpoint=server.endpoint)
    assert not result['passed']
    assert result['attempted'] == result['failed'] == 1
    assert result['unattempted'] == 53
    assert server.paths == ['/health', '/evaluate']
    row = study.rows(tmp_path / 'q-evaluation/responses.jsonl')[0]
    assert row['http']['raw_body'] == 'original timeout text'
    assert row['http']['status_code'] == 408
    with pytest.raises(FileExistsError):
        study.evaluate(tmp_path, endpoint=server.endpoint)


def test_diagnose_requires_completed_q_and_keeps_invalid_json_rows(tmp_path, monkeypatch):
    setup_prepared(tmp_path, monkeypatch)
    study.write_new(tmp_path / 'q-evaluation/result.json', dict(passed=False))
    with pytest.raises(ValueError, match='complete q comparison'):
        study.diagnose(tmp_path, endpoint='http://127.0.0.1:1')
    # A separate prepared ledger models a completed q batch; never rewrite failed q evidence.
    other = tmp_path / 'complete'
    other.mkdir()
    setup_prepared(other, monkeypatch)
    study.write_new(other / 'q-evaluation/result.json', dict(passed=True))
    calls = 0
    def invalid(body):
        nonlocal calls
        calls += 1
        if calls == 1:
            return 400, dict(error='diagnostic input has 16000 tokens plus 512 reserved output tokens; no truncation')
        return 200, dict(diagnostic_profile=study.DIAGNOSTIC_PROFILE,
            revision=study.v.REVISION, adapter_sha256=study.v.ADAPTER_SHA,
            action_id=body['action_id'], status='timeout' if calls == 2 else 'invalid_json', prediction=None,
            raw_output='model output is not repaired', input_tokens=10, output_tokens=7)
    with Server(diagnose=invalid) as server:
        result = study.diagnose(other, endpoint=server.endpoint)
    assert result['attempted'] == 90 and result['unattempted'] == 0
    assert result['statuses']['invalid_json'] == 88
    assert result['statuses']['timeout'] == result['statuses']['length_overflow'] == 1
    assert len(study.rows(other / 'diagnostics/responses.jsonl')) == 90
    assert server.paths.count('/diagnose') == 90
    assert '/evaluate' not in server.paths


def test_prediction_scores_are_separate_from_rank_and_allow_unknown():
    cases = study.diagnostic_cases(saved_records())
    case = next(c for c in cases if c['turn'] == 3 and c['kind'] == 'turn_action')
    rubric = study.rubric_for(case)
    prediction = dict(post_state=dict(self_defense_stage_after_move=0, target_survives=True),
        damage_applicability=dict(supplied_incoming_damage_still_applicable=False),
        survival='unknown', ko=False)
    assert all(r['verdict'] == 'correct' for r in study.score_prediction(prediction, rubric, condition='C3'))
    prediction['damage_applicability']['updated_incoming_damage'] = [41.4, 58.7]
    assert study.score_prediction(prediction, rubric, condition='C1')[-1]['verdict'] == 'incorrect'
    prediction['damage_applicability']['updated_incoming_damage'] = dict(status='unknown', reason='recalculation not supplied')
    assert study.score_prediction(prediction, rubric, condition='C2')[-1]['verdict'] == 'correct'
    rank = study.rankings(dict(q_values={'wrong': .9, 'mechanically_sound': .1}))
    assert rank[0]['action_id'] == 'wrong'
    forced = next(c for c in cases if c['kind'] == 'forced_switch')
    unknown = dict(post_state=dict(reapply_completed_attack=False, remaining_opponent_action='unknown'))
    assert study.score_prediction(unknown, study.rubric_for(forced), condition='C1')[1]['verdict'] == 'input_insufficient'
    assert study.score_prediction(unknown, study.rubric_for(forced), condition='C3')[1]['verdict'] == 'uncertain'


def test_ranking_ties_keep_original_order_and_report_missing_denominators(tmp_path, monkeypatch):
    _, cases = setup_prepared(tmp_path, monkeypatch)
    monkeypatch.setattr(study, 'read', (lambda original: lambda path:
        {'passed': False} if str(path).endswith('/result.json') and '.pokechamp-data' in str(path)
        else original(path))(study.read))
    # The original-result path remains distinct from the report result.
    manifest = study.read(tmp_path / 'preparation.json')
    manifest['source_directory'] = str(study.SOURCE)
    (tmp_path / 'preparation.json').write_text(json.dumps(manifest))
    assert [r['action_id'] for r in study.rankings(dict(q_values={'first': .5, 'second': .5}))] == ['first', 'second']
    result = study.report(tmp_path)
    assert not result['technical_completion']
    assert all(result['q'][c]['unattempted'] == 18 for c in study.CONDITIONS)
    assert all(result['diagnostics'][c]['unattempted'] == 30 for c in study.CONDITIONS)
    text = (tmp_path / 'report.md').read_text()
    assert '19.55' in text and '입력 생성 시간을 제외' in text
    assert '보정된 승률이 아니다' in text
    assert len(cases) == 30


def test_append_only_artifact_and_deadline(tmp_path):
    study.write_new(tmp_path / 'evidence.json', dict(failure='original'))
    with pytest.raises(FileExistsError):
        study.write_new(tmp_path / 'evidence.json', dict(failure='replacement'))
    with pytest.raises(TimeoutError, match='cumulative'):
        study._timeout(0)


def test_optional_frozen_inputs_detect_prompt_mutation(tmp_path):
    assert study.verify_frozen_inputs(tmp_path) is None
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('frozen instruction')
    study.write_new(tmp_path / 'frozen-inputs.json', dict(files={str(prompt): study.file_hash(prompt)}))
    assert study.verify_frozen_inputs(tmp_path)['files'] == 1
    prompt.write_text('changed after model loading')
    with pytest.raises(RuntimeError, match='frozen study input/source changed'):
        study.verify_frozen_inputs(tmp_path)
