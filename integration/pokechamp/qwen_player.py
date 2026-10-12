"""JEV official observation/cursor boundary with local candidate value decisions."""
from __future__ import annotations

import asyncio
import copy
import json
import time
import urllib.error

from . import jev_battle as j, jev_v4, qwen_value as v


class Session(j.Session):
    def __init__(self, directory, *, input_version=v.OLD_VERSION):
        super().__init__(directory, call_limit=None, collection_seconds=1,
                         retry_policy=j.jev_retry.LEGACY)
        if input_version not in v.SUPPORTED_VERSIONS:
            raise ValueError('unsupported Qwen input profile')
        self.input_version = input_version

    def remaining(self):
        return float('inf')

    async def evaluate(self, body, *, decision):
        if self.failure_event.is_set():
            raise RuntimeError('collection halted')
        if self.started is None:
            self.started, self.monotonic_started = time.time(), time.monotonic()
        self.calls += 1
        self.record(dict(type='http_request', decision=decision, body=body,
                         request_number=self.calls, endpoint=v.ENDPOINT, timeout=v.TIMEOUT))
        started = time.monotonic()
        def call():
            try:
                response = v.request('/evaluate', body)
                self.record(dict(type='http_response', decision=decision, body=response,
                                 status_code=200, elapsed_seconds=time.monotonic() - started))
                return response
            except urllib.error.HTTPError as exc:
                self.record(dict(type='http_response', decision=decision, status_code=exc.code,
                                 raw_body=exc.read().decode(), elapsed_seconds=time.monotonic() - started))
                raise RuntimeError('local serving HTTP error ' + str(exc.code)) from exc
            except (json.JSONDecodeError, UnicodeError) as exc:
                raise j.UnusableChoice('malformed local value response') from exc
        task = asyncio.create_task(asyncio.to_thread(call))
        try:
            response = await asyncio.wait_for(asyncio.shield(task), timeout=v.TIMEOUT)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.record(dict(type='request_expired', decision=decision,
                             elapsed_seconds=time.monotonic() - started))
            await asyncio.gather(task, return_exceptions=True)
            raise
        try:
            v.validate_response(response, body['actions'])
        except ValueError as exc:
            raise j.UnusableChoice(str(exc)) from exc
        return response


def ensure_current(rqid, latest_rqid, request, commands, current_commands, failed):
    if failed or latest_rqid != rqid or request.get('rqid') != rqid:
        raise ValueError('stale request; transmission forbidden')
    if commands != current_commands:
        raise ValueError('changed legal actions; transmission forbidden')


def player_class():
    base = j.player_class()
    class QwenValuePlayer(base):
        latest_rqid = None

        async def _handle_battle_message(self, messages):
            # Observe a newly delivered request before the inherited lock queues its frame.
            # A late model reply cannot be sent against an older queued request.
            for fields in messages:
                if len(fields) >= 3 and fields[1] == 'request' and fields[2]:
                    request = json.loads('|'.join(fields[2:]))
                    self.latest_rqid = request.get('rqid')
                    self.request_received_monotonic = time.monotonic()
            return await super()._handle_battle_message(messages)

        async def _handle_battle_request(self, battle, from_teampreview_request=False,
                                         maybe_default_order=False):
            if maybe_default_order:
                raise ValueError('automatic default forbidden')
            if battle.in_team_preview and from_teampreview_request and not self.request:
                battle.move_on_next_request = True
                return
            if battle.in_team_preview and not from_teampreview_request and not (self.request or {}).get('teamPreview'):
                return
            if not self.request or self.request.get('wait'):
                return
            actor = self.request['side']['id']
            if actor != self.expected_actor:
                raise ValueError('unexpected scheduled actor')
            decision_started = time.monotonic()
            if self.official is None:
                from .observation.runtime import OfficialClient
                self.official = OfficialClient(actor)
            snapshot = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix),
                                               battle.battle_tag, boundary=self.boundary)
            started = time.monotonic()
            input_version = getattr(self.session, 'input_version', v.OLD_VERSION)
            adapter = jev_v4
            if input_version == v.STATE_VERSION:
                from . import qwen_temporal
                adapter = qwen_temporal
            payload, commands, audit, _ = await adapter.generate(
                self.session, snapshot, self.prefix, self.submitted_team, actor=actor)
            rqid = self.request.get('rqid')
            decision = f'{self.username}-{rqid}-{len(self.session.records)}'
            body = dict(observation=payload, actions=v.actions_from(payload, commands))
            v.validate_input(body, allowed_versions=(input_version,))
            self.session.record(dict(type='input', decision=decision, battle=battle.battle_tag,
                actor=actor, payload=payload, commands=commands, actions=body['actions'],
                boundary=self.boundary, official=snapshot,
                observation_identity=self.official.identity,
                input_audit=jev_v4.save_audit(self.session.directory, decision, audit),
                snapshot_seconds=started - decision_started,
                input_generation_seconds=time.monotonic() - started))
            inference_started = time.monotonic()
            response = await self.session.evaluate(body, decision=decision)
            self.session.record(dict(type='response', decision=decision, body=response,
                                     elapsed_seconds=time.monotonic() - inference_started))
            choice = v.validate_response(response, body['actions'])
            current = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix),
                                              battle.battle_tag, boundary=self.boundary)
            _, current_commands = j.make_input(current, self.prefix, actor=actor, dex=self.session.dex,
                                               initial_pp_policy=self.session.initial_pp_policy)
            ensure_current(rqid, self.latest_rqid, self.request, commands, current_commands,
                           self.session.failure_event.is_set())
            if time.monotonic() - inference_started >= v.TIMEOUT:
                raise TimeoutError('expired response; transmission forbidden')
            command = commands[choice]
            self.session.record(dict(type='selection', decision=decision, choice=choice, command=command,
                automatic=False, elapsed_seconds=time.monotonic() - inference_started,
                decision_seconds=time.monotonic() - decision_started,
                request_to_selection_seconds=(time.monotonic() - self.request_received_monotonic
                    if getattr(self, 'request_received_monotonic', None) is not None else None),
                revalidated_request_id=rqid, revalidated_commands=current_commands))
            await self.ps_client.send_message(command, battle.battle_tag, str(rqid))
            self.session.record(dict(type='wire', decision=decision, command=command,
                request_id=rqid, status='sent', decision_to_send_seconds=time.monotonic() - decision_started))
    return QwenValuePlayer
