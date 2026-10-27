"""Three unusable-response attempts, independent of unlimited transport retries."""
import asyncio

from integration.openai_decisions_battle.retry import RetrySession, DELAYS
from integration.openai_decisions_battle.core import call_http, to_request, TransportFailure, ResponseParseFailure
from integration.pokechamp import jev_battle as j


class RecoverySession(RetrySession):
    response_recovery = True

    async def evaluate(self, payload, *, decision):
        async with self._inference_lock:
            if not decision or decision in self._request_ids:
                raise ValueError('missing/duplicate logical decision')
            self._request_ids.add(decision)
            request = to_request(payload)
            criteria = payload['questions']['action']['criteria']
            physical = response_attempt = transport_attempt = 1
            while True:
                if self.failure_event.is_set():
                    raise RuntimeError('OpenAI collection cancelled')
                self.calls += 1
                self._ledger()
                number = self.calls
                def record(event):
                    self.record(dict(event, response_attempt=response_attempt, transport_attempt=transport_attempt))
                task = asyncio.create_task(asyncio.to_thread(call_http, request, self.key, record,
                    decision=decision, request_number=number, attempt=physical, client=self.client))
                failure = None
                try:
                    body = await asyncio.shield(task)
                    try:
                        j.validate_answer(body, criteria, version=j.VALIDATION_VERSION)
                    except j.UnusableChoice as exc:
                        failure = str(exc)
                    if failure is None:
                        self.record(dict(type='response_attempt', decision=decision, request_number=number,
                            attempt=physical, response_attempt=response_attempt, usable=True, body=body))
                        return body
                except asyncio.CancelledError:
                    self.record(dict(type='request_cancelled', decision=decision, request_number=number,
                        attempt=physical, response_attempt=response_attempt))
                    await asyncio.gather(task, return_exceptions=True)
                    raise
                except TransportFailure as exc:
                    if not exc.retryable:
                        raise
                    delay = max(DELAYS[min(transport_attempt-1, len(DELAYS)-1)], exc.retry_after)
                    self.record(dict(type='provider_retry', decision=decision, request_number=number,
                        attempt=physical, response_attempt=response_attempt, next_attempt=physical+1,
                        delay_seconds=delay))
                    self.client.close()
                    self.client = self.client_factory()
                    await self._backoff(delay)
                    transport_attempt += 1
                    physical += 1
                    continue
                except ResponseParseFailure as exc:
                    body = None
                    failure = str(exc)
                self.record(dict(type='response_attempt', decision=decision, request_number=number,
                    attempt=physical, response_attempt=response_attempt, usable=False, body=body, reason=failure))
                if response_attempt == 3:
                    raise j.UnusableChoice('unusable response recovery exhausted after 3 responses: '+failure)
                self.record(dict(type='response_retry', decision=decision, request_number=number,
                    attempt=physical, response_attempt=response_attempt, next_response_attempt=response_attempt+1,
                    next_attempt=physical+1))
                response_attempt += 1
                transport_attempt = 1
                physical += 1
