"""Serialized option readout with durable physical-attempt evidence."""
import asyncio
import json
import os
import random
import threading
import time

import httpx

from integration.pokechamp import jev_battle as j
from integration.jev27b.battle import Session as LocalSession
from integration.jev27b.study import write_json
from .core import (RUN, MODEL, ENDPOINT, TIMEOUT, CALL_LIMIT, COLLECTION_SECONDS,
                   RETRY_DELAYS, to_request, normalized_response, dumps, ROOT_RUN)
from . import resource


class Session(j.Session):
    begin_decision = LocalSession.begin_decision
    end_decision = LocalSession.end_decision
    wait_decisions = LocalSession.wait_decisions

    def __init__(self, directory, *, key=None, first_request_at, prior_calls=0, fake=False):
        super().__init__(directory, environ={}, collection_seconds=COLLECTION_SECONDS,
                         call_limit=CALL_LIMIT, retry_policy=j.jev_retry.LEGACY, fake=fake)
        self.input_version = 'jev-choice-v6'
        self.started = first_request_at
        self.monotonic_started = time.monotonic() - (time.time()-first_request_at)
        self.prior_calls = prior_calls
        self.failure_event = threading.Event()
        self._decision_lock = threading.Lock()
        self._decision_count = 0
        self._decisions_idle = threading.Event()
        self._decisions_idle.set()
        self._inference_lock = asyncio.Lock()
        self._request_ids = set()
        self.client = httpx.Client(timeout=TIMEOUT, follow_redirects=False)
        self.identity = None if fake else json.loads((RUN/'external-identity.json').read_text())
        self._monitor_stop = threading.Event()
        self._monitor = None
        self._ledger()
        if not fake:
            resource.verify(self.identity, health=True)
            resource.sample(self.identity, self.directory, 'begin')
            self._monitor = threading.Thread(target=self._watch, name='ex123-resources', daemon=True)
            self._monitor.start()

    def _watch(self):
        while not self._monitor_stop.wait(2):
            try:
                resource.sample(self.identity, self.directory, 'poll')
            except BaseException as exc:
                self.fail(exc)
                return

    def _ledger(self):
        write_json(self.directory/'ledger.json',dict(first_request_at=self.started,
            requests=self.calls, prior_requests=self.prior_calls, limit=CALL_LIMIT,
            deadline=self.started+COLLECTION_SECONDS, retries=3, fake=self.fake))

    def _complete(self, payload, request, decision):
        encoded = dumps(request).encode()
        for attempt in range(1, 5):
            if (ROOT_RUN/'halt.json').exists() or self.failure_event.is_set() or self.remaining() <= 0 or self.calls+self.prior_calls >= CALL_LIMIT:
                raise RuntimeError('collection cancelled or budget reached')
            if not self.fake:
                resource.verify(self.identity)
            self.calls += 1
            self._ledger()
            common = dict(decision=decision, request_number=self.calls, attempt=attempt)
            self.record(dict(type='transport', endpoint=ENDPOINT+'/completions',
                             model=MODEL, timeout=TIMEOUT, **common))
            self.record(dict(type='http_request', body=request, raw_body=encoded.decode(), **common))
            started = time.monotonic()
            retryable = False
            if self.fake:
                winner = random.Random(self.calls+101).randrange(len(request['logprob_token_ids']))
                logits = {f'token_id:{token}':(-0.1 if i==winner else -7.)
                          for i,token in enumerate(request['logprob_token_ids'])}
                raw = dict(model=MODEL, choices=[dict(index=0,text=chr(65+winner),finish_reason='length',
                    prompt_token_ids=request['prompt'],token_ids=[request['logprob_token_ids'][winner]],
                    logprobs=dict(top_logprobs=[logits]))],usage=dict(prompt_tokens=len(request['prompt']),
                    completion_tokens=1,total_tokens=len(request['prompt'])+1))
                response = httpx.Response(200, json=raw)
            else:
                try:
                    response = self.client.post(ENDPOINT+'/completions', content=encoded,
                        headers={'Content-Type':'application/json'})
                except httpx.RequestError as exc:
                    self.record(dict(type='attempt_failure', category='transport', status_code=None,
                        exception_type=type(exc).__name__, retryable=True,
                        elapsed_seconds=time.monotonic()-started, **common))
                    retryable = True
                    response = None
            if response is not None:
                self.record(dict(type='http_response', status_code=response.status_code,
                    raw_body=response.text, elapsed_seconds=time.monotonic()-started, **common))
                if not self.fake:
                    resource.verify(self.identity)
                if response.is_success:
                    return normalized_response(response.json(), payload, request)
                retryable = response.status_code in (408,429) or 500 <= response.status_code < 600
                self.record(dict(type='attempt_failure',category='http',status_code=response.status_code,
                    retryable=retryable, elapsed_seconds=time.monotonic()-started, **common))
            if not retryable or attempt == 4:
                raise RuntimeError('external HTTP failure; retries exhausted or permanent error')
            delay = RETRY_DELAYS[attempt-1]
            self.record(dict(type='provider_retry',delay_seconds=delay,next_attempt=attempt+1,**common))
            if self.failure_event.wait(min(delay, max(0.,self.remaining()))):
                raise RuntimeError('collection cancelled during retry wait')
        raise AssertionError('unreachable')

    async def evaluate(self, payload, *, decision):
        async with self._inference_lock:
            if not decision or decision in self._request_ids:
                raise ValueError('missing/duplicate decision ID')
            self._request_ids.add(decision)
            request = to_request(payload)
            task = asyncio.create_task(asyncio.to_thread(self._complete,payload,request,decision))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                self.failure_event.set()
                await asyncio.gather(task,return_exceptions=True)
                raise

    async def close(self):
        self.failure_event.set()
        self._monitor_stop.set()
        if self._monitor:
            await asyncio.to_thread(self._monitor.join, 10)
            if self._monitor.is_alive():
                raise RuntimeError('resource monitor failed to stop')
        await self.wait_decisions()
        if getattr(self,'v6_adapter',None) is not None:
            await asyncio.to_thread(self.v6_adapter.close)
        self.client.close()
        if not self.fake:
            resource.sample(self.identity,self.directory,'end')


class BattleLimit(j.UnusableChoice):
    """Record a finite battle limit as incomplete, not as a loss."""


def player_class():
    from integration.jev27b.battle import player_class as inherited
    from integration.pokechamp import jev_v6
    class JevK5Player(inherited(input_adapter=jev_v6)):
        async def _decide(self,battle,from_teampreview_request=False,maybe_default_order=False):
            count = sum(e['type']=='input' and e.get('decision','').startswith(self.username+'-')
                        for e in self.session.records)
            if battle.turn > 300 or count >= 600:
                raise BattleLimit('300 turns / 600 decisions reached')
            return await super()._decide(battle,from_teampreview_request,maybe_default_order)
    return JevK5Player
