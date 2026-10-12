"""Loopback-only, serialized inference over the unchanged EX-061 value policy."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
import subprocess
import threading
import time
import traceback

from . import qwen_value as v


class Runtime:
    def __init__(self, output, *, candidate_state=False, diagnostics=False, deadline_at=None):
        data = v.data_module()
        from rlcd import pokemon_value as pv
        self.output, self.data, self.pv = output, data, pv
        self.allowed_versions = v.SUPPORTED_VERSIONS if candidate_state else (v.OLD_VERSION,)
        self.diagnostics_enabled = diagnostics
        self.study_deadline_at = deadline_at
        self.diagnostic_requests = 0
        self.diagnostic_gpu_seconds = 0.0
        self.started = time.time()
        self.lock = threading.Lock()
        self.failed = None
        self.requests = self.forwards = 0
        self.gpu_seconds = 0.0
        self.monitor_stop = threading.Event()
        self.monitor = threading.Thread(target=self.sample_gpu, daemon=True)
        self.monitor.start()
        data.dump(output / 'startup.json', dict(pid=os.getpid(), started_at=self.started,
            allowed_input_versions=self.allowed_versions, diagnostics_enabled=diagnostics,
            study_deadline_at=deadline_at))
        data.dump(output / 'source-hashes.json', {str(p.relative_to(v.ROOT)): data.sha256(p)
            for p in [v.Path(__file__), v.Path(v.__file__), v.EVE / 'rlcd/pokemon_data.py',
                      v.EVE / 'rlcd/pokemon_value.py',
                      *([v.Path(__file__).with_name('qwen_diagnostics.py')] if diagnostics else [])]})
        self.adapter_hashes = v.verify_adapter()
        pv.environment(output)
        pv.seed_all()
        self.tok = pv.tokenizer()
        self.policy = pv.ValuePolicy(pv.load_base(output), self.tok, v.ADAPTER)
        self.policy.model.eval()
        for parameter in self.policy.model.parameters():
            parameter.requires_grad_(False)
        self.before = pv.fingerprint(self.policy.model, False)
        self.model_config_before = self.policy.model.config.to_dict()
        self.generation_config_before = self.policy.model.generation_config.to_dict()
        data.dump(output / 'weights-before.json', self.before)
        self.save_progress()

    def health(self):
        return dict(ready=self.failed is None, profile=v.PROFILE, model=v.MODEL,
                    revision=v.REVISION, adapter_sha256=v.ADAPTER_SHA, max_len=v.MAX_LEN,
                    requests=self.requests, forwards=self.forwards, error=self.failed,
                    allowed_input_versions=getattr(self, 'allowed_versions', (v.OLD_VERSION,)),
                    diagnostics_enabled=getattr(self, 'diagnostics_enabled', False),
                    diagnostic_requests=getattr(self, 'diagnostic_requests', 0))

    def bounded_deadline(self, request_deadline):
        absolute = getattr(self, 'study_deadline_at', None)
        return request_deadline if absolute is None else min(request_deadline,
            time.monotonic() + max(0, absolute - time.time()))

    def sample_gpu(self):
        with (self.output / 'gpu-samples.jsonl').open('a') as stream:
            while not self.monitor_stop.is_set():
                sample = subprocess.run(['nvidia-smi', '-i', '1',
                    '--query-gpu=uuid,memory.used,utilization.gpu,power.draw', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=10)
                stream.write(json.dumps(dict(at=time.time(), physical_gpu=1,
                    values=sample.stdout.strip(), returncode=sample.returncode)) + '\n')
                stream.flush()
                self.monitor_stop.wait(5)

    def save_progress(self):
        torch = self.pv.torch
        self.data.dump(self.output / 'progress.json', dict(**self.health(), pid=os.getpid(),
            elapsed_seconds=time.time() - self.started, gpu_compute_seconds=self.gpu_seconds,
            diagnostic_gpu_seconds=getattr(self, 'diagnostic_gpu_seconds', 0.0),
            max_allocated_bytes=torch.cuda.max_memory_allocated(),
            max_reserved_bytes=torch.cuda.max_memory_reserved()))

    def evaluate(self, body, deadline):
        # Encoding every candidate first prevents a partial GPU request on length overflow.
        received = time.monotonic()
        deadline = self.bounded_deadline(deadline)
        if not self.lock.acquire(timeout=max(0, deadline - time.monotonic())):
            raise TimeoutError('expired in serialized inference queue')
        try:
            if self.failed:
                raise RuntimeError('server halted: ' + self.failed)
            try:
                encoding_started = time.monotonic()
                queue_seconds = encoding_started - received
                actions, encoded = v.encoded_candidates(body, self.tok,
                    allowed_versions=getattr(self, 'allowed_versions', (v.OLD_VERSION,)))
                encoding_seconds = time.monotonic() - encoding_started
            except (KeyError, TypeError) as exc:
                raise ValueError('incomplete input structure') from exc
            self.requests += 1
            values, audit = {}, []
            started = time.monotonic()
            torch = self.pv.torch
            with torch.no_grad():
                for action, (ids, row) in zip(actions, encoded):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('request deadline exceeded')
                    begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                    begin.record()
                    q = float(self.policy.probabilities(ids)[0].cpu())
                    end.record()
                    torch.cuda.synchronize()
                    seconds = begin.elapsed_time(end) / 1000
                    self.gpu_seconds += seconds
                    self.forwards += 1
                    values[action['action_id']] = q
                    audit.append(dict(**row, gpu_seconds=seconds))
                    self.save_progress()
            if time.monotonic() >= deadline:
                raise TimeoutError('request deadline exceeded after forward')
            chosen = max(actions, key=lambda a: values[a['action_id']])
            result = dict(profile=v.PROFILE, model=v.MODEL, revision=v.REVISION,
                adapter_sha256=v.ADAPTER_SHA, q_values=values, choice=chosen['action_id'],
                command=chosen['command'], candidates=audit,
                total_tokens=sum(r['tokens'] for r in audit), elapsed_seconds=time.monotonic() - started,
                queue_seconds=queue_seconds, encoding_seconds=encoding_seconds,
                total_elapsed_seconds=time.monotonic() - received)
            v.validate_response(result, actions)
            self.data.write_jsonl(self.output / f'request-{self.requests:05d}.jsonl',
                                  [dict(input=body, response=result)])
            return result
        except (ValueError, TimeoutError):
            raise
        except Exception as exc:
            self.failed = str(exc)
            self.data.dump(self.output / 'halt.json', dict(error=str(exc), traceback=traceback.format_exc()))
            raise
        finally:
            self.save_progress()
            self.lock.release()

    def diagnose(self, body, deadline):
        """Development-only generation; never used by evaluate or the battle player."""
        if not getattr(self, 'diagnostics_enabled', False):
            raise ValueError('diagnostics not enabled')
        from . import qwen_diagnostics as diag
        from transformers import GenerationConfig, StoppingCriteria, StoppingCriteriaList

        received = time.monotonic()
        deadline = self.bounded_deadline(deadline)
        if not self.lock.acquire(timeout=max(0, deadline - received)):
            raise TimeoutError('expired in serialized diagnostic queue')
        try:
            if self.failed:
                raise RuntimeError('server halted: ' + self.failed)
            encoding_started = time.monotonic()
            queue_seconds = encoding_started - received
            v.validate_input({key: body[key] for key in ('observation', 'actions')},
                allowed_versions=self.allowed_versions)
            ids, audit = diag.encode(body, self.tok)
            encoding_seconds = time.monotonic() - encoding_started
            if time.monotonic() >= deadline:
                raise TimeoutError('diagnostic expired before generation')
            self.diagnostic_requests += 1
            torch = self.pv.torch
            class Deadline(StoppingCriteria):
                def __call__(self, _ids, _scores, **_kwargs):
                    return time.monotonic() >= deadline
            config = GenerationConfig.from_dict(self.generation_config_before)
            config.do_sample, config.num_beams = False, 1
            config.max_new_tokens, config.use_cache = diag.MAX_NEW_TOKENS, True
            config.return_dict_in_generate, config.output_scores = False, False
            if self.tok.pad_token_id is not None:
                config.pad_token_id = self.tok.pad_token_id
            elif config.pad_token_id is None:
                config.pad_token_id = self.tok.eos_token_id
            eos_ids = config.eos_token_id
            eos_ids = set(eos_ids if isinstance(eos_ids, (list, tuple)) else [eos_ids])
            started = time.monotonic()
            begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            begin.record()
            with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
                generated = self.policy.model.generate(
                    input_ids=torch.tensor([ids], device='cuda:0', dtype=torch.long),
                    attention_mask=torch.ones((1, len(ids)), device='cuda:0', dtype=torch.long),
                    generation_config=config,
                    stopping_criteria=StoppingCriteriaList([Deadline()]))
            end.record()
            torch.cuda.synchronize()
            gpu_seconds = begin.elapsed_time(end) / 1000
            self.diagnostic_gpu_seconds += gpu_seconds
            output_ids = generated[0, len(ids):].tolist()
            raw = self.tok.decode(output_ids, skip_special_tokens=True)
            prediction, error = None, None
            if time.monotonic() >= deadline:
                status, error = 'timeout', 'diagnostic generation deadline exceeded'
            elif len(output_ids) >= diag.MAX_NEW_TOKENS and output_ids[-1] not in eos_ids:
                status, error = 'truncated', 'maximum diagnostic output tokens reached'
            else:
                try:
                    prediction = diag.parse(raw, body['action_id'])
                    status = 'valid'
                except ValueError as exc:
                    status, error = 'invalid_json', str(exc)
            result = dict(diagnostic_profile='qwen-state-diagnostic-v1', model=v.MODEL,
                revision=v.REVISION, adapter_sha256=v.ADAPTER_SHA, action_id=body['action_id'],
                status=status, prediction=prediction, raw_output=raw, error=error,
                input_tokens=len(ids), output_tokens=len(output_ids),
                prompt_sha256=audit['prompt_sha256'], token_sha256=audit['token_sha256'],
                projection_info=audit.get('projection_info'),
                max_new_tokens=diag.MAX_NEW_TOKENS, queue_seconds=queue_seconds,
                encoding_seconds=encoding_seconds, gpu_seconds=gpu_seconds,
                elapsed_seconds=time.monotonic() - started,
                total_elapsed_seconds=time.monotonic() - received)
            self.data.write_jsonl(self.output / f'diagnostic-{self.diagnostic_requests:05d}.jsonl',
                [dict(input=body, response=result)])
            return result
        except (ValueError, KeyError, TypeError, TimeoutError):
            raise
        except Exception as exc:
            self.failed = str(exc)
            self.data.dump(self.output / 'halt.json', dict(error=str(exc), traceback=traceback.format_exc()))
            raise
        finally:
            self.save_progress()
            self.lock.release()

    def close(self):
        with self.lock:
            after = self.pv.fingerprint(self.policy.model, False)
            self.data.dump(self.output / 'weights-after.json', after)
            self.data.dump(self.output / 'closure.json', dict(weights_unchanged=after == self.before,
                optimizer_updates=0,
                all_parameters_frozen=all(not p.requires_grad for p in self.policy.model.parameters()),
                eval_unchanged=not self.policy.model.training, no_grad=True,
                adapter_files_unchanged=v.verify_adapter() == self.adapter_hashes,
                elapsed_seconds=time.time() - self.started, gpu_compute_seconds=self.gpu_seconds,
                diagnostic_gpu_seconds=self.diagnostic_gpu_seconds,
                diagnostic_requests=self.diagnostic_requests,
                model_config_unchanged=self.policy.model.config.to_dict() == self.model_config_before,
                generation_config_unchanged=self.policy.model.generation_config.to_dict() == self.generation_config_before,
                requests=self.requests, forwards=self.forwards, error=self.failed))
        self.monitor_stop.set()
        self.monitor.join(timeout=15)


def handler(runtime):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, body):
            raw = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.path == '/health':
                self.reply(200, runtime.health())
            else:
                self.reply(404, dict(error='unknown route'))

        def do_POST(self):
            if self.path not in ('/evaluate', '/diagnose') or (self.path == '/diagnose'
                    and not getattr(runtime, 'diagnostics_enabled', False)):
                self.reply(404, dict(error='unknown route'))
                return
            self.connection.settimeout(v.TIMEOUT)
            deadline = time.monotonic() + v.TIMEOUT
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8 * 1024 * 1024:
                    raise ValueError('invalid request body length')
                body = json.loads(self.rfile.read(size))
                result = (runtime.diagnose(body, deadline) if self.path == '/diagnose'
                          else runtime.evaluate(body, deadline))
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(400, dict(error=str(exc), category='invalid_input'))
            except TimeoutError as exc:
                self.reply(408, dict(error=str(exc), category='timeout'))
            except Exception as exc:
                self.reply(503, dict(error=str(exc), category='serving_failure'))
            else:
                self.reply(200, result)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner', required=True)
    parser.add_argument('--output', type=v.Path, required=True)
    parser.add_argument('--candidate-state', action='store_true', help='explicitly accept the new input profile')
    parser.add_argument('--diagnostics', action='store_true', help='enable isolated development generation')
    parser.add_argument('--deadline-at', type=float, help='absolute UNIX study deadline')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    runtime = None
    server = None
    def terminate(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        runtime = Runtime(args.output, candidate_state=args.candidate_state, diagnostics=args.diagnostics,
                          deadline_at=args.deadline_at)
        server = ThreadingHTTPServer(('127.0.0.1', 8765), handler(runtime))
        server.daemon_threads = True
        print(json.dumps(runtime.health()), flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        v.data_module().dump(args.output / 'startup-halt.json',
                             dict(error=str(exc), traceback=traceback.format_exc()))
        raise
    finally:
        if server:
            server.server_close()
        if runtime:
            runtime.close()


if __name__ == '__main__':
    main()
