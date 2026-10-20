"""Journal-compatible model facade for the untouched official serving program."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from .config import MODEL_DIR, MODEL_ID, REVISION, ENGINE_PORT, EVIDENCE, engine_command
from .formatting import format_request, tokenize_request, choice_request, mapped_response


class OfficialModel:
    def __init__(self):
        self.process = self.log = self.client = None
        self.loaded = False
        self.directory = None
        self.identity = None
        self.engine_http_attempts = 0

    def load(self):
        from transformers import AutoTokenizer
        import httpx
        from .download import verify
        compatibility = json.loads((EVIDENCE / 'compatibility.json').read_text())
        if compatibility.get('passed') is not True:
            raise RuntimeError('EX-095 CUDA compatibility gate did not pass')
        receipt = verify()
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
        if self.directory is None:
            raise ValueError('official engine requires an owned serving directory')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', ENGINE_PORT))
        env = dict(os.environ, JEV_DECIDE_NO_MOE_LORA='1', JEV_DECIDE_SYSTEM2='0',
                   JEV_DECIDE_THINKING='off', JEV_DECIDE_STRATEGY='single',
                   EX095_ALLOCATOR_DIRECTORY=str(self.directory), VLLM_WORKER_MULTIPROC_METHOD='spawn')
        command = engine_command() + ['--worker-cls', 'integration.jev35b_nvfp4.worker.BoundedWorker']
        self.log = (self.directory / 'engine.log').open('x')
        self.client = httpx.Client(base_url=f'http://127.0.0.1:{ENGINE_PORT}', timeout=600, trust_env=False)
        # Remain in the journal server's owned process group, so controller cleanup
        # also terminates engine workers when startup fails or its parent is killed.
        self.process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                        stdout=self.log, stderr=subprocess.STDOUT)
        (self.directory / 'engine-process.json').write_text(json.dumps(dict(pid=self.process.pid, command=command)))
        try:
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError('official engine exited before readiness; see engine.log')
                try:
                    response = self.client.get('/v1/decide/info', timeout=1)
                    if response.status_code == 200:
                        info = response.json()
                        if (info['model'] != MODEL_ID or info['native_choice_options'] != 256
                                or info['system2_available'] is not False):
                            raise ValueError('official engine info differs from frozen System 1 profile')
                        break
                except httpx.TransportError:
                    pass
                time.sleep(.2)
            self.identity = hashlib.sha256(json.dumps(dict(revision=REVISION, files=receipt['files'],
                command=command, pid=self.process.pid), sort_keys=True).encode()).hexdigest()
            self.loaded = True
            return self
        except BaseException:
            self.close()
            raise

    def validate_input(self, payload):
        formatted = format_request(payload)
        encoded = tokenize_request(self.tokenizer, formatted)
        return formatted, encoded

    def evaluate(self, payload):
        formatted, encoded = self.validate_input(payload)
        request = choice_request(payload)
        self.engine_http_attempts += 1
        index = self.engine_http_attempts
        def journal(event):
            with (self.directory / 'engine-transport.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(at=time.time(), engine_attempt=index, **event),
                                        ensure_ascii=False, allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        journal(dict(type='engine_request', body=request))
        try:
            response = self.client.post('/v1/decide', json=request)
        except BaseException as error:
            journal(dict(type='engine_transport_failure', error=dict(type=type(error).__name__, detail=str(error)),
                         usage=None, inference_count=None))
            raise
        # Commit the untouched wire response before any schema/usage/mapping check.
        journal(dict(type='engine_response', status_code=response.status_code, raw_body=response.text))
        response.raise_for_status()
        official = response.json()
        result = mapped_response(payload, official)
        if result['usage']['input_tokens'] != len(encoded['input_ids']):
            raise ValueError('engine prompt token count differs from CPU full-input count')
        result['official_request'] = request
        result['metadata'] = self.metadata()
        return result

    def metadata(self):
        return dict(model=MODEL_ID, revision=REVISION, loaded=self.loaded,
                    serving_identity=self.identity, backend='marlin', activation_dtype='bfloat16',
                    physical_gpus=[0], engine_pid=self.process.pid if self.process else None,
                    max_input_tokens=32768, engine_length=32769, engine_http_attempts=self.engine_http_attempts)

    def close(self):
        self.loaded = False
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()
        if self.client is not None:
            self.client.close()
        if self.log is not None:
            self.log.close()
