"""EX-110: 일시적 통신 오류로 수집을 끝내지 않는 별도 프로필."""
import asyncio
import time

import httpx

from integration.jev27b.study import write_json
from .core import TIMEOUT, TransportFailure, call_http, to_request
from .session import Session

DELAYS=(2.,5.,10.,20.,30.,60.)


class RetrySession(Session):
    unlimited_retries=True

    def __init__(self,*args,client_factory=None,**kwargs):
        if kwargs.get('fake') and client_factory is None:
            raise ValueError('mock retry session requires an explicit mock client')
        super().__init__(*args,**kwargs)
        self.call_limit=None
        self.collection_seconds=None
        self.client_factory=client_factory or (lambda:httpx.Client(timeout=TIMEOUT,follow_redirects=False))
        if client_factory is not None:
            self.client.close()
            self.client=client_factory()
        self._ledger()

    def remaining(self):
        return float('inf')

    def _ledger(self):
        write_json(self.directory/'ledger.json',dict(first_request_at=self.started,
            requests=self.calls,prior_requests=self.prior_calls,limit=None,deadline=None,retries=None,
            retry_policy='openai-transient-unlimited-v1',fake=self.fake))

    async def _backoff(self,seconds):
        end=time.monotonic()+seconds
        while True:
            if self.failure_event.is_set():raise RuntimeError('collection cancelled during retry wait')
            remaining=end-time.monotonic()
            if remaining<=0:return
            await asyncio.sleep(min(1.,remaining))

    async def evaluate(self,payload,*,decision):
        async with self._inference_lock:
            if not decision or decision in self._request_ids:
                raise ValueError('missing/duplicate logical decision')
            self._request_ids.add(decision)
            request=to_request(payload)
            attempt=1
            while True:
                if self.failure_event.is_set():raise RuntimeError('OpenAI collection cancelled')
                self.calls+=1
                self._ledger()
                task=asyncio.create_task(asyncio.to_thread(call_http,request,self.key,self.record,
                    decision=decision,request_number=self.calls,attempt=attempt,client=self.client))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    self.record(dict(type='request_cancelled',decision=decision,request_number=self.calls,attempt=attempt))
                    await asyncio.gather(task,return_exceptions=True)
                    raise
                except TransportFailure as exc:
                    if not exc.retryable:raise
                    delay=max(DELAYS[min(attempt-1,len(DELAYS)-1)],exc.retry_after)
                    self.record(dict(type='provider_retry',decision=decision,request_number=self.calls,
                        attempt=attempt,next_attempt=attempt+1,delay_seconds=delay))
                    # A failed pooled connection is never carried into the next attempt.
                    self.client.close()
                    self.client=self.client_factory()
                    await self._backoff(delay)
                    attempt+=1


def player_class():
    from integration.jev27b.battle import player_class as original
    from integration.pokechamp import jev_v6
    return original(input_adapter=jev_v6)
