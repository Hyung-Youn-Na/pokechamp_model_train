"""Resolve experiment axes without loading models, credentials or network clients."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import re

from integration.pokechamp.transport_policy import CURRENT, policy_fields
from integration.project_context.registry import resolve_document, resolve_record

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
SCHEMA = 'jev-planner-config-v1'
POLICIES = ('off', 'initial_only', 'every_decision', 'periodic', 'events', 'events_or_periodic')
EVENTS = ('faint', 'tera', 'forced_switch', 'active_change', 'form_change')
MODEL_EXPERIMENTS = {'jev9b': 'EX-089', 'jev27b': 'EX-088', 'minicpm5-jev': 'EX-091'}
DEFAULT_TRIGGER = dict(policy='events_or_periodic', interval_turns=3,
                       events=['faint', 'tera', 'forced_switch'])
DEFAULT_PLANNER = dict(provider='zai', model='glm-5.3-flash', thinking={'type': 'enabled'},
                       reasoning_effort='low', temperature=0.0, top_p=0.95, max_tokens=8192, json_retries=5, retry_scope='response_format')
DEFAULT_LIMITS = dict(planner_http_attempts=1000, executor_calls=1000, games=8,
                      battle_seconds=600, total_seconds=1800)


class ConfigurationError(ValueError):
    """A configuration cannot be resolved into an explicit experiment."""


def json_bytes(value):
    # Candidate insertion order is part of the input, so it must survive freezing.
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    def invalid(value):
        raise ConfigurationError('non-finite JSON value: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_pairs,
                      parse_constant=invalid)


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) - set(keys):
        raise ConfigurationError(f'{label}: expected an object with keys {sorted(keys)}')
    return value


def _name(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', value):
        raise ConfigurationError(label + ' must be a simple nonempty identifier')
    return value


def _positive(value, label):
    if type(value) is not int or value < 1:
        raise ConfigurationError(label + ' must be a positive integer')
    return value


def model_spec(name):
    """Reuse verified package identities and placements; never inherit old run paths."""
    if name == 'tacit9b-vllm':
        from integration.tacit9b_vllm.config import model_spec as tacit_vllm_spec
        return tacit_vllm_spec()
    if name == 'tacit9b':
        from integration.tacit9b.config import model_spec as tacit_spec
        return tacit_spec()
    if name == 'jev-omni':
        from integration.jev_omni.config import model_spec as omni_spec
        return omni_spec()
    if name == 'jev35b-nvfp4':
        from integration.jev35b_nvfp4.config import model_spec as nvfp4_spec
        return nvfp4_spec()
    from integration.jev_eval.config import experiment
    if name not in MODEL_EXPERIMENTS:
        raise ConfigurationError('unknown executor model: ' + str(name))
    cfg = experiment(MODEL_EXPERIMENTS[name])
    modules = {'jev9b': 'integration.jev9b.formatting', 'jev27b': 'integration.jev27b.formatting',
               'minicpm5-jev': 'integration.minicpm5_jev.formatting'}
    return dict(name=name, model_id=cfg.model_id, revision=cfg.revision,
        python=str(ROOT / '.pokechamp-data/jev27b-runtime/.venv/bin/python'),
        runtime_name='planner-' + cfg.runtime_name, model_runtime_name=cfg.runtime_name,
        provenance_experiment=cfg.experiment,
        model_dir=str(cfg.model_dir), evidence_dir=str(cfg.model_evidence),
        tokenizer_dir=str(cfg.tokenizer_dir), formatter_module=modules[name],
        physical_gpus=list(cfg.runtime.physical_gpus), layers=list(cfg.layers),
        input_tokens=32768, max_options=16, allocator_bytes=cfg.runtime.allocator_bytes,
        gpu_bytes=cfg.runtime.gpu_bytes, host_bytes=cfg.runtime.host_bytes,
        disk_bytes=None)


def formatter(name):
    return importlib.import_module(model_spec(name)['formatter_module'])


def _asset(value, base, *, json_data=False, document=False):
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError('asset must be a nonempty file path')
    path = (base / value).resolve()
    if document:
        path = resolve_document(path)
    raw = path.read_bytes()
    result = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
    if json_data:
        result['data'] = read_json(path)
    else:
        result['text'] = raw.decode('utf-8')
        if not result['text'].strip():
            raise ConfigurationError('prompt file is empty: ' + str(path))
    return result


def _trigger(value):
    _object(value, DEFAULT_TRIGGER, 'trigger')
    result = dict(copy.deepcopy(DEFAULT_TRIGGER), **value)
    if result['policy'] not in POLICIES:
        raise ConfigurationError('unknown trigger policy: ' + str(result['policy']))
    _positive(result['interval_turns'], 'trigger.interval_turns')
    names = result['events']
    if (not isinstance(names, list) or any(not isinstance(name, str) or name not in EVENTS for name in names)
            or len(names) != len(set(names))):
        raise ConfigurationError('trigger.events must contain unique supported event names')
    return result


def _planner(value):
    _object(value, DEFAULT_PLANNER, 'planner')
    result = dict(copy.deepcopy(DEFAULT_PLANNER), **value)
    if result['provider'] != 'zai' or result['model'] not in ('glm-5.3-flash', 'glm-5.3'):
        raise ConfigurationError('planner requires zai / glm-5.3-flash or glm-5.3')
    if result['thinking'] != {'type': 'enabled'}:
        raise ConfigurationError('GLM-5.3 planner models require thinking enabled')
    if result['reasoning_effort'] not in ('low', 'high', 'max'):
        raise ConfigurationError('planner reasoning_effort must be low, high or max')
    for name, lower, upper in (('temperature', 0, 1), ('top_p', 0.01, 1)):
        number = result[name]
        if type(number) not in (int, float) or not math.isfinite(number) or not lower <= number <= upper:
            raise ConfigurationError('planner.' + name + ' is outside its supported range')
    if _positive(result['max_tokens'], 'planner.max_tokens') > 131072:
        raise ConfigurationError('planner.max_tokens exceeds 131072')
    if type(result['json_retries']) is not int or not 0 <= result['json_retries'] <= 5:
        raise ConfigurationError('planner.json_retries must be an integer from 0 to 5')
    if result['retry_scope'] not in ('json_syntax', 'response_format'):
        raise ConfigurationError('planner.retry_scope must be json_syntax or response_format')
    result['transport'] = policy_fields(CURRENT)
    return result


def validate_schedule(data):
    """Validate a declared paired schedule, without reading results or hidden battle state."""
    _object(data, ('schedule', 'teams'), 'schedule document')
    rows, teams = data.get('schedule'), data.get('teams')
    if not isinstance(rows, list) or not rows or not isinstance(teams, dict) or not teams:
        raise ConfigurationError('schedule document needs nonempty schedule and teams')
    for name, team in teams.items():
        if not isinstance(name, str) or not isinstance(team, dict) or not isinstance(team.get('showdown_team'), str):
            raise ConfigurationError('each schedule team requires showdown_team text')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ConfigurationError('schedule row must be an object')
        for key in ('slot_id', 'paired_slot_id'):
            _name(row.get(key), 'schedule.' + key)
        if row['slot_id'] in seen:
            raise ConfigurationError('duplicate schedule slot_id')
        seen.add(row['slot_id'])
        if row.get('jev_actor') not in ('p1', 'p2'):
            raise ConfigurationError('schedule requires jev_actor p1 or p2')
        names = row.get('teams')
        if not isinstance(names, list) or len(names) != 2 or any(name not in teams for name in names):
            raise ConfigurationError('schedule teams must name two supplied teams')
        seeds = row.get('actor_seeds')
        if not isinstance(seeds, list) or len(seeds) != 2 or any(type(v) is not int or not 0 <= v < 2**32 for v in seeds):
            raise ConfigurationError('schedule needs two uint32 actor_seeds')
        seed = row.get('battle_seed')
        if isinstance(seed, str):
            pieces = seed.split(',')
            valid = len(pieces) == 4 and all(p.isdecimal() and 0 <= int(p) < 65536 for p in pieces)
        else:
            valid = isinstance(seed, list) and len(seed) == 4 and all(type(v) is int and 0 <= v < 65536 for v in seed)
        if not valid:
            raise ConfigurationError('battle_seed must contain four uint16 values')
    return data


def load_config(path):
    path = Path(path).resolve()
    source = read_json(path)
    _object(source, ('schema_version', 'name', 'executor', 'planner', 'trigger', 'prompts',
                     'evaluation', 'matrix'), 'config')
    if source.get('schema_version', SCHEMA) != SCHEMA:
        raise ConfigurationError('unsupported planner config schema')
    executor = dict(model='jev9b', input_version='jev-choice-v6', candidate_display='names-v1')
    executor.update(_object(source.get('executor', {}), executor, 'executor'))
    model_spec(executor['model'])
    if executor['input_version'] != 'jev-choice-v6':
        raise ConfigurationError('this environment uses corrected calculator-enabled v6 input')
    if executor['candidate_display'] not in ('original', 'names-v1'):
        raise ConfigurationError('executor.candidate_display must be original or names-v1')
    prompt_paths = _object(source.get('prompts', {}), ('planner', 'executor', 'guide'), 'prompts')
    defaults = dict(planner=str(HERE / 'prompts/strategy-compact.txt'),
                    executor=str(HERE / 'prompts/executor-guidance.txt'),
                    guide=str(HERE / 'prompts/role-resource-guide-v1.txt'))
    prompts = {k: _asset(prompt_paths.get(k, v), path.parent) for k, v in defaults.items()}
    evaluation = copy.deepcopy(_object(source.get('evaluation', {}),
        ('kind', 'fixture', 'schedule', 'experiment_record', 'limits', 'resources', 'showdown_port',
         'server_port', 'executor_preflight', 'executor_repeat_policy'), 'evaluation'))
    if evaluation.get('executor_repeat_policy', 'strict') not in ('strict', 'probability_diagnostic'):
        raise ConfigurationError('unsupported executor_repeat_policy')
    if evaluation.get('executor_repeat_policy', 'strict') != 'strict' and executor['model'] not in ('jev35b-nvfp4', 'jev-omni', 'tacit9b', 'tacit9b-vllm'):
        raise ConfigurationError('executor_repeat_policy requires a model with a registered repeat gate')
    if evaluation.get('executor_preflight') is not None:
        evaluation['executor_preflight'] = _asset(evaluation['executor_preflight'], path.parent, json_data=True)
    evaluation.setdefault('kind', 'trace')
    if evaluation['kind'] not in ('trace', 'battle'):
        raise ConfigurationError('evaluation.kind must be trace or battle')
    if evaluation['kind'] == 'trace':
        evaluation['fixture'] = _asset(evaluation.get('fixture', str(HERE / 'fixtures/demo.json')),
                                       path.parent, json_data=True)
        if not isinstance(evaluation['fixture']['data'].get('cases'), list) or not evaluation['fixture']['data']['cases']:
            raise ConfigurationError('trace fixture needs nonempty cases')
    else:
        evaluation['schedule'] = _asset(evaluation.get('schedule'), path.parent, json_data=True)
        validate_schedule(evaluation['schedule']['data'])
    if evaluation.get('experiment_record') is not None:
        evaluation['experiment_record'] = _asset(
            evaluation['experiment_record'], path.parent, document=True)
    limits = _object(evaluation.get('limits', {}), DEFAULT_LIMITS, 'evaluation.limits')
    evaluation['explicit_limits'] = sorted(limits)
    evaluation['limits'] = dict(DEFAULT_LIMITS, **limits)
    for name, value in evaluation['limits'].items():
        if name in ('battle_seconds', 'total_seconds') and value is None:
            continue
        _positive(value, 'evaluation.limits.' + name)
    for name, default in (('showdown_port', 8109), ('server_port', 18845)):
        evaluation.setdefault(name, default)
        if _positive(evaluation[name], 'evaluation.' + name) > 65535:
            raise ConfigurationError('port exceeds 65535')
    if not 8100 <= evaluation['showdown_port'] <= 8109:
        raise ConfigurationError('the owned Showdown launcher supports ports 8100..8109')
    if evaluation['showdown_port'] == evaluation['server_port']:
        raise ConfigurationError('model and Showdown ports must differ')
    result = dict(schema_version=SCHEMA, name=_name(source.get('name', 'jev-planner'), 'name'),
        executor=executor, planner=_planner(source.get('planner', {})),
        trigger=_trigger(source.get('trigger', {})), prompts=prompts, evaluation=evaluation)
    if 'matrix' in source:
        matrix = _object(source['matrix'], ('triggers', 'planner_prompts'), 'matrix')
        triggers = matrix.get('triggers', [result['trigger']])
        if not isinstance(triggers, list) or not triggers:
            raise ConfigurationError('matrix.triggers must be nonempty')
        prompts_axis = matrix.get('planner_prompts', [dict(name='default', path=prompts['planner']['path'])])
        if not isinstance(prompts_axis, list) or not prompts_axis:
            raise ConfigurationError('matrix.planner_prompts must be nonempty')
        variants = []
        for variant in prompts_axis:
            _object(variant, ('name', 'path', 'guide'), 'matrix.planner_prompts item')
            if 'name' not in variant or 'path' not in variant:
                raise ConfigurationError('each planner prompt variant requires name and path')
            resolved = dict(name=_name(variant['name'], 'prompt variant'),
                            prompt=_asset(variant['path'], path.parent))
            if 'guide' in variant:
                resolved['guide'] = _asset(variant['guide'], path.parent)
            variants.append(resolved)
        result['matrix'] = dict(triggers=[_trigger({'policy': v} if isinstance(v, str) else v) for v in triggers],
                               planner_prompts=variants)
    return result


def conditions(config):
    """Cartesian axes with one unchanged off baseline, independent of prompt variants."""
    matrix = config.get('matrix')
    if not matrix:
        return [dict(name=config['name'], config=copy.deepcopy(config))]
    result, names, seen = [], set(), set()
    for trigger in matrix['triggers']:
        for variant in matrix['planner_prompts']:
            guide = variant.get('guide', config['prompts'].get('guide'))
            identity = digest(trigger) + ('' if trigger['policy'] == 'off' else
                variant['prompt']['sha256'] + (guide['sha256'] if guide else 'legacy-v6-guide'))
            if identity in seen:
                continue
            seen.add(identity)
            prefix = trigger['policy']
            if 'periodic' in prefix:
                prefix += '-' + str(trigger['interval_turns'])
            name = prefix if trigger['policy'] == 'off' else prefix + '-' + variant['name']
            if name in names:
                raise ConfigurationError('ambiguous matrix condition names; use distinct policies/prompts')
            names.add(name)
            item = copy.deepcopy(config)
            item.pop('matrix', None)
            item['name'], item['trigger'], item['prompts']['planner'] = name, copy.deepcopy(trigger), copy.deepcopy(variant['prompt'])
            if guide is not None:
                item['prompts']['guide'] = copy.deepcopy(guide)
            result.append(dict(name=name, config=item))
    return result


def validate_mode(config, mode):
    if mode not in ('mock', 'live'):
        raise ConfigurationError('execution mode must be explicit: mock or live')
    if mode == 'mock':
        return
    evaluation = config['evaluation']
    if evaluation['kind'] != 'battle':
        raise ConfigurationError('live execution requires new battles; stored trace replay is not live evaluation')
    record = evaluation.get('experiment_record')
    if not record or not re.fullmatch(r'EX-\d+-[^/]+\.md', Path(record['path']).name):
        raise ConfigurationError('live execution requires a registered EX experiment_record')
    match = re.match(r'EX-(\d+)-', Path(record['path']).name)
    try:
        registered = resolve_record('EX-' + match[1], root=ROOT)
    except (KeyError, ValueError, OSError) as exc:
        raise ConfigurationError('experiment_record must be registered in catalog/records.json') from exc
    if Path(record['path']).resolve() != registered.resolve():
        raise ConfigurationError('experiment_record must be the canonical path in catalog/records.json')
    if int(match[1]) <= 91:
        raise ConfigurationError('preserved experiments cannot be resumed through the planner runner')
    if set(evaluation['explicit_limits']) != set(DEFAULT_LIMITS):
        raise ConfigurationError('live execution requires all call/game/time limits explicitly declared')
    spec = model_spec(config['executor']['model'])
    repeat_policy = evaluation.get('executor_repeat_policy', 'strict')
    if repeat_policy not in ('strict', 'probability_diagnostic'):
        raise ConfigurationError('unsupported executor_repeat_policy')
    if repeat_policy != 'strict' and config['executor']['model'] not in ('jev35b-nvfp4', 'jev-omni', 'tacit9b', 'tacit9b-vllm'):
        raise ConfigurationError('executor_repeat_policy requires a model with a registered repeat gate')
    if config['executor']['model'] in ('jev35b-nvfp4', 'jev-omni', 'tacit9b', 'tacit9b-vllm'):
        preflight = evaluation.get('executor_preflight', {}).get('data', {}).get('requests', [])
        if (len(preflight) != 8 or preflight[0].get('payload') != preflight[-1].get('payload')
                or evaluation.get('server_port', 18845) != 18845
                or evaluation.get('showdown_port', 8109) != 8109):
            raise ConfigurationError('model preflight requires eight frozen probes and ports 18845/8109')
        if config['executor']['model'] in ('tacit9b', 'tacit9b-vllm'):
            diagnostics = evaluation['executor_preflight']['data'].get('diagnostic_requests', [])
            if (len(diagnostics) != 3 or [row.get('case') for row in diagnostics] !=
                    ['ex103-turn-2', 'ex103-turn-5', 'ex103-turn-6']):
                raise ConfigurationError('Tacit requires frozen EX-103 turn 2/5/6 diagnostics')
    expected = dict(gpu_indices=spec['physical_gpus'], **{k: spec[k] for k in
        ('allocator_bytes', 'gpu_bytes', 'host_bytes', 'disk_bytes')})
    if evaluation.get('resources') != expected:
        raise ConfigurationError('live resources must explicitly match the selected pinned model profile')


def validate_prepared(config, mode):
    """Recheck execution bounds using only frozen data, never live configuration defaults."""
    validate_mode(config, mode)
    expanded = conditions(config)
    if config['evaluation']['kind'] == 'battle':
        planned = len(config['evaluation']['schedule']['data']['schedule']) * len(expanded)
        if planned > config['evaluation']['limits']['games']:
            raise ConfigurationError(f'matrix plans {planned} games above the declared run-wide game limit')
    return expanded
