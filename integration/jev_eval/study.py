"""Fresh v6 accounting and paired comparisons; baseline games never enter new totals."""
from __future__ import annotations

import copy
import hashlib
import time
from pathlib import Path

from integration.jev27b import study as inherited
from integration.jev27b.study import (
    event_rows, file_hash, seal, snapshot_sources, verify_seal, write_json,
)
from integration.jev9b.study import (
    compare_outcomes as inherited_compare, load_baseline as load_ex083,
    outcome_scores, sealed_document, valid,
)
from integration.pokechamp import jev_battle as j, jev_v4
from .config import NO_DAMAGE_VERSION, PROTOCOL, ROOT, RUNS, TRANSPORT_POLICY, experiment

POINTS = inherited.POINTS
INTERPRETATION = '공개 정보 보존과 현재 상태 교정의 결합 처치에 대한 고정 대진 탐색 평가'
REFERENCE_INTERPRETATION = 'EX-083은 2GPU 완료23경기와 4GPU 완료9경기를 계승한 평가'
NO_DAMAGE_INTERPRETATION = '피해 예측 정보와 관련 설명 제거에 대한 고정 대진 탐색 평가'
NO_DAMAGE_REFERENCE = 'EX-089의 완료32경기·16진영교환쌍·6승0무26패·점수18.75%를 재사용'
MINICPM_INTERPRETATION = 'MiniCPM5-2B-Jev 모델 패키지의 계산기 포함 고정 대진 탐색 평가'


def interpretation(config):
    cfg = experiment(config)
    if cfg.is_minicpm:
        return MINICPM_INTERPRETATION
    return (NO_DAMAGE_INTERPRETATION if cfg.input_version == NO_DAMAGE_VERSION
            else INTERPRETATION)


def reference_interpretation(config):
    return (NO_DAMAGE_REFERENCE if experiment(config).baseline == 'EX-089'
            else REFERENCE_INTERPRETATION)


def load_baseline(name='EX-083'):
    if name == 'EX-083':
        return load_ex083()
    if name not in ('EX-085', 'EX-089'):
        raise ValueError('unknown preserved baseline')
    directory = RUNS / name / 'collection'
    manifest = sealed_document(directory, 'manifest.json')
    result = sealed_document(directory, 'result.json')
    if (manifest['experiment_id'] != name or result['experiment_id'] != name
            or result['completed'] != 32 or result['completed_pairs'] != 16
            or result.get('passed') is not True or result.get('final_audit_passed') is not True):
        raise ValueError(name + ' audited completed reference is required')
    if name == 'EX-085':
        canonical, _ = load_ex083()
        for key in ('schedule', 'teams', 'prompt', 'input_data_identity', 'observation_build'):
            if manifest[key] != canonical[key]:
                raise ValueError('baseline fixed matchup identity differs: ' + key)
    else:
        # The single-model ablation reads its own completed reference. It does
        # not require another cohort to execute, close, or be re-audited.
        from integration.pokechamp.jev_study import validate_schedule
        cfg = experiment(name)
        validate_schedule(manifest['schedule'])
        if (manifest['execution_profile'] != cfg.execution_profile
                or manifest['schema_version'] != cfg.input_version
                or manifest['model']['model'] != cfg.model_id
                or manifest['model']['revision'] != cfg.revision
                or manifest['prompt'] != cfg.input_adapter.PROMPT.read_text()
                or manifest['input_data_identity'] != cfg.input_adapter.data_identity()
                or j.digest(manifest['schedule']) != manifest['schedule_sha256']):
            raise ValueError('EX-089 preserved input/model/schedule identity differs')
        for team in manifest['teams'].values():
            if hashlib.sha256(team['showdown_team'].encode()).hexdigest() != team['sha256']:
                raise ValueError('EX-089 preserved team identity differs')
    if [o['slot_id'] for o in result['outcomes']] != [r['slot_id'] for r in manifest['schedule']]:
        raise ValueError('baseline unique outcome coverage/order differs')
    scores = outcome_scores(result['outcomes'], manifest['schedule'])
    if name == 'EX-089' and (scores['completed'] != 32 or scores['completed_pairs'] != 16
            or scores['overall'] != dict(games=32, wins=6, draws=0, losses=26, score=0.1875)):
        raise ValueError('EX-089 preserved result denominator or score differs')
    return manifest, result


def source_identity():
    from . import viewer
    source = j.source_identity()
    source.update(viewer.source_identity())
    for directory in ('integration/jev_eval', 'integration/jev9b', 'integration/jev27b',
                      'integration/minicpm5_jev'):
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file() and path.suffix in ('.py', '.html', '.js', '.cjs', '.json', '.txt'):
                source[str(path.relative_to(ROOT))] = file_hash(path)
    for name in ('scripts/jev-eval', 'scripts/jev9b', 'scripts/jev27b'):
        source[name] = file_hash(ROOT / name)
    return source


def prior_execution(config):
    """Link the stopped cohort's clock/costs without inheriting its game outcomes."""
    cfg = experiment(config)
    if cfg.cohort.prior_usage_evidence is None:
        return None
    evidence, prior_run = cfg.cohort.prior_usage_evidence, cfg.cohort.prior_run
    if prior_run is None:
        raise ValueError('prior usage has no original run provenance')
    accounting = sealed_document(evidence, 'inference-accounting.json')
    execution = sealed_document(prior_run, 'execution.json')
    completion = sealed_document(prior_run, 'evidence/completion.json')
    collection = sealed_document(prior_run / 'collection', 'result.json')
    if (completion['experiment_id'] != 'EX-086'
            or accounting['total_server_inferences'] != 26
            or accounting['preflight_inferences'] != 8
            or accounting['collection_inferences'] != 18):
        raise ValueError('preserved stopped-cohort clock/usage identity differs')
    return dict(experiments=['EX-086', 'EX-087'], run=str(prior_run),
        accounting_source=str(evidence / 'inference-accounting.json'),
        accounting_sha256=file_hash(evidence / 'inference-accounting.json'),
        execution_sha256=file_hash(prior_run / 'execution.json'),
        completion_sha256=file_hash(prior_run / 'evidence/completion.json'),
        execution_started=execution['started'], execution_ended=completion['ended'],
        collection_first_request_at=collection['first_request_at'], accounting=accounting,
        inherited_game_outcomes=0, included_in_new_cost_totals=False)


def prepare_manifest(config, expected_identity, gate_receipt, *, endpoint):
    from integration.pokechamp import cli
    from .client import RETRY_DELAYS, TIMEOUT, base_url
    cfg = experiment(config)
    input_adapter = cfg.input_adapter
    baseline, _ = load_baseline(cfg.baseline)
    sources = source_identity()
    if (gate_receipt.get('passed') is not True
            or gate_receipt.get('experiment_id') != cfg.experiment
            or gate_receipt.get('serving_identity') != expected_identity
            or gate_receipt.get('source') != sources
            or gate_receipt.get('inferences') != 8 or gate_receipt.get('server_loads') != 1
            or gate_receipt.get('input_data_identity') != input_adapter.data_identity()):
        raise ValueError('same-server eight-inference v6 gate receipt required')
    if cfg.is_minicpm and (gate_receipt.get('format') != cfg.format_version
            or gate_receipt.get('physical_gpus') != list(cfg.runtime.physical_gpus)):
        raise ValueError('MiniCPM same-server format or GPU profile differs')
    journal = gate_receipt.get('server_journal')
    if not isinstance(journal, str) or not Path(journal).is_file():
        raise ValueError('the serving process request journal is required')
    baseline_file = 'combined-result.json' if cfg.baseline == 'EX-083' else 'result.json'
    baseline_dir = RUNS / cfg.baseline / 'collection'
    manifest = dict(experiment_id=cfg.experiment, execution_profile=cfg.execution_profile,
        policy_version=cfg.execution_profile,
        evaluation_cohort=dict(first=cfg.cohort.first, second=cfg.cohort.second,
                               predecessor=cfg.predecessor),
        prior_execution=prior_execution(cfg),
        version=cfg.input_version, schema_version=cfg.input_version,
        validation_version=j.VALIDATION_VERSION, initial_pp_policy=j.INITIAL_PP_POLICY,
        effect_reference_identity=j.effects.identity(), input_data_identity=input_adapter.data_identity(),
        schedule=copy.deepcopy(baseline['schedule']), teams=copy.deepcopy(baseline['teams']),
        schedule_sha256=baseline['schedule_sha256'], prompt=input_adapter.PROMPT.read_text(), source=sources,
        baseline=dict(experiment=cfg.baseline, directory=str(baseline_dir),
            manifest_sha256=file_hash(baseline_dir / 'manifest.json'),
            result_sha256=file_hash(baseline_dir / baseline_file),
            interpretation=reference_interpretation(cfg), inherited_new_outcomes=0),
        model=dict(model=cfg.model_id, revision=cfg.revision,
            endpoint=base_url(endpoint) + '/v1/systemone', serving_identity=expected_identity),
        server_journal=str(Path(journal).resolve()), fake=False, timer_enabled=False,
        transport_policy=TRANSPORT_POLICY, transport_protocol=PROTOCOL,
        provider_retries=3, retry_delays_seconds=list(RETRY_DELAYS),
        limits=dict(games=32, calls=None, collection_seconds=None, total_seconds=None,
            stage_seconds=None, battle_seconds=None, concurrency=1, inference_concurrency=1,
            request_timeout_seconds=TIMEOUT, input_tokens=32768, options=16, retries=3, recollection=0),
        submodules={name: dict(sha=c['sha']) for name, c in cli.SUBMODULES.items()},
        observation_build=baseline['observation_build'], gate_receipt_sha256=j.digest(gate_receipt),
        rng_isolation='separate-processes', created_at=time.time(), efficacy_evidence=False,
        interpretation=interpretation(cfg))
    if cfg.input_version == NO_DAMAGE_VERSION:
        from .no_damage_verify import validate_receipt
        receipt = validate_receipt(cfg, sources)
        manifest.update(damage_predictions_enabled=False, speed_comparison_retained=True,
            baseline_input_verification=dict(path=str(cfg.evidence / 'no-damage-baseline.json'),
                sha256=file_hash(cfg.evidence / 'no-damage-baseline.json'),
                checked_inputs=receipt['checked_inputs']))
    elif cfg.is_minicpm:
        from integration.minicpm5_jev.verify import validate_receipt
        receipt = validate_receipt(cfg, sources)
        manifest.update(damage_predictions_enabled=True, speed_comparison_retained=True,
            baseline_input_verification=dict(path=str(cfg.evidence / 'minicpm-baseline.json'),
                sha256=file_hash(cfg.evidence / 'minicpm-baseline.json'),
                checked_inputs=receipt['checked_inputs']),
            model_package_comparison=dict(format=cfg.format_version,
                tokenizer_directory=str(cfg.tokenizer_dir),
                differences=['model_weights', 'decision_head', 'calibration', 'tokenizer',
                             'model_input_format', 'gpu_placement'],
                official_default_server_reproduction=False),
            resource_limits=dict(physical_gpus=list(cfg.runtime.physical_gpus),
                allocator_bytes=cfg.runtime.allocator_bytes, gpu_bytes=cfg.runtime.gpu_bytes,
                host_bytes=cfg.runtime.host_bytes, disk_bytes=cfg.disk_limit_bytes))
    return manifest


def verify_live_identity(manifest):
    cfg = experiment(manifest['experiment_id'])
    input_adapter = cfg.input_adapter
    if manifest['source'] != source_identity():
        raise ValueError('source changed during collection')
    baseline, _ = load_baseline(cfg.baseline)
    for key in ('schedule', 'teams', 'observation_build'):
        if manifest[key] != baseline[key]:
            raise ValueError('frozen identity changed: ' + key)
    if manifest['input_data_identity'] != input_adapter.data_identity():
        raise ValueError('v6 input data changed')
    if manifest['prompt'] != input_adapter.PROMPT.read_text():
        raise ValueError('v6 prompt changed')
    if (manifest['schema_version'] != cfg.input_version
            or manifest['execution_profile'] != cfg.execution_profile
            or manifest['model']['model'] != cfg.model_id
            or manifest['model']['revision'] != cfg.revision):
        raise ValueError('v6 model or input identity changed')


def summarize(session, outcomes, schedule, error=None, *, config):
    cfg = experiment(config)
    result = inherited.summarize(session, outcomes, schedule, error)
    result.update(outcome_scores(outcomes, schedule), experiment_id=cfg.experiment,
                  interpretation=interpretation(cfg))
    result.update(decisions=sum(e['type'] == 'input' for e in session.records),
        http_attempt_scope='inference_POST_only',
        inference_latency_seconds=sum(e['body'].get('metadata', {}).get('elapsed_seconds', 0)
                                      for e in session.records if e['type'] == 'response'),
        decision_latency_seconds=sum(e.get('decision_seconds', 0) for e in session.records
                                     if e['type'] == 'selection'))
    return result


def compare_outcomes(before, after, schedule, *, before_experiment, after_experiment):
    result = inherited_compare(before, after, schedule)
    cfg = experiment(after_experiment)
    result.update(before_experiment=before_experiment, after_experiment=after_experiment,
        interpretation=interpretation(cfg), baseline_interpretation=reference_interpretation(cfg),
        treatment=('damage_prediction_information_and_field_explanations_removed'
                   if cfg.input_version == NO_DAMAGE_VERSION
                   else 'model_package_with_lossless_minicpm_format'
                   if cfg.is_minicpm
                   else 'public_information_retention_and_current_state_correction'),
        pair_changes=dict(improved=sum(p['delta'] > 0 for p in result['pairs'].values()),
                          worsened=sum(p['delta'] < 0 for p in result['pairs'].values()),
                          unchanged=sum(p['delta'] == 0 for p in result['pairs'].values())),
        causal_model_size_effect=False, general_performance_claim=False)
    return result


def comparison(manifest, result):
    cfg = experiment(manifest['experiment_id'])
    before_manifest, before = load_baseline(cfg.baseline)
    for key in ('schedule', 'teams', 'observation_build'):
        if manifest[key] != before_manifest[key]:
            raise ValueError('comparison fixed matchup drift: ' + key)
    if result.get('final_audit_passed') is not True:
        return dict(available=False, reason='최종 기술 감사 미통과로 성적 비교 보류',
                    before_experiment=cfg.baseline, after_experiment=cfg.experiment)
    compared = compare_outcomes(before['outcomes'], result['outcomes'], manifest['schedule'],
                                before_experiment=cfg.baseline, after_experiment=cfg.experiment)
    if cfg.input_version == NO_DAMAGE_VERSION:
        compared['collection_metrics'] = dict(before=collection_metrics(before),
                                             after=collection_metrics(result))
        compared['length_and_battle_trajectory_are_part_of_treatment'] = True
        compared['separate_information_vs_length_effect_claim'] = False
        compared['equivalence_claim'] = False
    elif cfg.is_minicpm:
        compared.update(collection_metrics=dict(before=collection_metrics(before),
                                               after=collection_metrics(result)),
            package_differences=['model_weights', 'decision_head', 'calibration', 'tokenizer',
                                 'model_input_format', 'gpu_placement'],
            battle_input_information_preserved=True,
            official_default_server_reproduction=False, equivalence_claim=False)
    return compared


def collection_metrics(result):
    """Report saved lengths, latency and progress without regenerating baseline inputs."""
    from statistics import median
    def distribution(values):
        return dict(count=len(values), total=sum(values),
                    mean=sum(values) / len(values) if values else None,
                    median=median(values) if values else None,
                    minimum=min(values) if values else None, maximum=max(values) if values else None)
    good = [o for o in result.get('outcomes', []) if valid(o)]
    return dict(
        denominators={k: result.get(k) for k in
            ('planned', 'attempted', 'completed', 'failed', 'invalid', 'unattempted', 'completed_pairs')},
        completion_rate=result.get('completion_rate'), overall=result.get('overall'),
        decisions=result.get('decisions'), model_requests=result.get('logical_requests'),
        http_attempts=result.get('requests'), retry_attempts=result.get('retry_attempts'),
        automatic_actions=result.get('automatic_actions'), usage=result.get('received_usage'),
        usage_unknown_requests=result.get('usage_unknown_requests'),
        input_tokens=distribution(result.get('input_tokens', [])),
        input_generation_seconds=distribution(result.get('input_generation_seconds', [])),
        response_latency_seconds=distribution(result.get('latency_seconds', [])),
        inference_latency_seconds=result.get('inference_latency_seconds'),
        decision_latency_seconds=result.get('decision_latency_seconds'),
        completed_game_turns=distribution([o['turns'] for o in good if 'turns' in o]),
        elapsed_collection_seconds=result.get('elapsed_collection_seconds'),
        metric_scope='각 실행의 실제 수집 분모; 경기 진행/입력 길이 변화 포함')


def cross_comparison(config, manifest, result):
    """Write in the cohort's second output; never reopen the first run's seal."""
    cfg = experiment(config)
    before_id, after_id = cfg.cohort.first, cfg.cohort.second
    if after_id is None:
        return dict(available=False, applicable=False, experiment_id=cfg.experiment,
                    reason='단독 실행이며 추가 모델/후속 코호트 비교 없음')
    labels = dict(before_experiment=before_id, after_experiment=after_id)
    if cfg.predecessor is None:
        return dict(available=False, reason=after_id + ' 결과 대기', **labels)
    directory = experiment(before_id).run / 'collection'
    if not (directory / 'result.json').is_file():
        return dict(available=False, reason=before_id + ' 본수집 미진입', **labels)
    before_manifest = sealed_document(directory, 'manifest.json')
    before = sealed_document(directory, 'result.json')
    if before_manifest['experiment_id'] != before['experiment_id'] or before['experiment_id'] != before_id:
        raise ValueError('cross-model predecessor experiment identity differs')
    for key in ('schedule', 'teams', 'schema_version', 'prompt', 'input_data_identity'):
        if before_manifest[key] != manifest[key]:
            raise ValueError('cross-model frozen treatment drift: ' + key)
    if not before.get('final_audit_passed') or not result.get('final_audit_passed'):
        return dict(available=False, reason='최종 기술 감사 미통과로 성적 비교 보류', **labels)
    return compare_outcomes(before['outcomes'], result['outcomes'], manifest['schedule'],
                            **labels)
