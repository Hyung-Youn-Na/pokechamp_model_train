"""OpenAI 원장과 기존 v6 행동 실행기의 연결."""
import asyncio
import os
import threading
import time

import httpx

from integration.pokechamp import jev_battle as j
from integration.jev27b.battle import Session as LocalSession
from integration.jev27b.study import write_json
from .core import CALL_LIMIT, COLLECTION_SECONDS, TIMEOUT, call_http, to_request


class Session(j.Session):
    begin_decision = LocalSession.begin_decision
    end_decision = LocalSession.end_decision
    wait_decisions = LocalSession.wait_decisions

    def __init__(self, directory, *, key, first_request_at, prior_calls=0, fake=False):
        os.environ.pop('OPENAI_API_KEY', None)
        super().__init__(directory, environ={}, collection_seconds=COLLECTION_SECONDS,
                         call_limit=CALL_LIMIT, retry_policy=j.jev_retry.LEGACY, fake=fake)
        self.key = key
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
        self._ledger()

    def _ledger(self):
        write_json(self.directory/'ledger.json',dict(first_request_at=self.started,
            requests=self.calls, prior_requests=self.prior_calls, limit=CALL_LIMIT,
            deadline=self.started+COLLECTION_SECONDS, retries=0, fake=self.fake))

    async def evaluate(self, payload, *, decision):
        async with self._inference_lock:
            if not decision or decision in self._request_ids:
                raise ValueError('missing/duplicate decision identity')
            if self.failure_event.is_set() or self.remaining()<=0 or self.calls+self.prior_calls>=CALL_LIMIT:
                raise RuntimeError('OpenAI collection halted or budget reached')
            self._request_ids.add(decision)
            request=to_request(payload)
            self.calls+=1
            self._ledger()
            if self.fake:
                from .core import MODEL
                import random
                generator=random.Random(self.calls+101)
                choices=request['questions'][0]['choices']
                choice=generator.choice(choices)['value']
                def handler(req):
                    return httpx.Response(200,json=dict(model=MODEL,answers=[dict(name='action',
                        type='choice',choice=choice,confidence=1.,probabilities=[dict(value=c['value'],
                        probability=float(c['value']==choice)) for c in choices])],
                        usage=dict(input_tokens=0,output_tokens=0)))
                client=httpx.Client(transport=httpx.MockTransport(handler))
            else:
                client=self.client
            task=asyncio.create_task(asyncio.to_thread(call_http,request,self.key,self.record,
                decision=decision,request_number=self.calls,client=client))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await asyncio.gather(task,return_exceptions=True)
                raise
            finally:
                if self.fake:
                    client.close()

    async def close(self):
        self.failure_event.set()
        await self.wait_decisions()
        if getattr(self,'v6_adapter',None) is not None:
            await asyncio.to_thread(self.v6_adapter.close)
        self.client.close()


class BattleLimit(j.UnusableChoice):
    """실험의 경기별 유한 상한; 패배와 구분한다."""


def decision_limit_reached(records, username, turn):
    return turn > 300 or sum(event['type']=='input' and
        event.get('decision','').startswith(username+'-') for event in records) >= 600


def player_class():
    from integration.jev27b.battle import player_class as inherited
    from integration.pokechamp import jev_v6
    class DecisionsPlayer(inherited(input_adapter=jev_v6)):
        async def _decide(self,battle,from_teampreview_request=False,maybe_default_order=False):
            if decision_limit_reached(self.session.records, self.username, battle.turn):
                raise BattleLimit('300 turns / 600 decisions reached')
            return await super()._decide(battle,from_teampreview_request,maybe_default_order)
    return DecisionsPlayer
