"""Joint q live player, retaining the official C-051 input and strict send boundary."""
from __future__ import annotations

import asyncio
import copy
import math
from pathlib import Path
import time
import urllib.error

from ... import jev_battle as j
from ...kev_player import InputGenerator, ensure_current
from .. import serializer
from . import client, protocol


class Session(j.Session):
    def __init__(self, directory, *, endpoint, identity, deadline_monotonic,
                 timeout=client.TIMEOUT, environ=None):
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= client.TIMEOUT:
            raise ValueError('invalid joint q request timeout')
        if type(deadline_monotonic) not in (float, int) or not math.isfinite(deadline_monotonic):
            raise ValueError('invalid battle deadline')
        self.endpoint, self.identity = client.base_url(endpoint), copy.deepcopy(identity)
        self.profile, self.timeout, self.deadline = protocol.PROFILE, timeout, deadline_monotonic
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        super().__init__(directory, environ=environ, call_limit=None, collection_seconds=3600,
                         retry_policy=j.jev_retry.LEGACY)
        self.generator = InputGenerator(self.dex)
        self.input_version = serializer.VERSION
        self.closed = False

    def remaining(self):
        return self.deadline - time.monotonic()

    async def generate(self, official, prefix, own_team, *, actor=None):
        task = asyncio.create_task(asyncio.to_thread(self.generator.generate,
            copy.deepcopy(official), copy.deepcopy(prefix), own_team, actor=actor))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await asyncio.gather(task, return_exceptions=True)
            raise

    async def evaluate(self, body, *, decision):
        if self.closed or self.failure_event.is_set() or self.remaining() <= 0:
            raise RuntimeError('joint q collection halted or expired')
        joint = protocol.validate_request(body)
        if self.started is None:
            self.started, self.monotonic_started = time.time(), time.monotonic()
        timeout = min(self.timeout, self.remaining())
        self.calls += 1
        request_number = self.calls
        self.record(dict(type='http_request', decision=decision, body=body,
            raw_body=client.request_bytes(body).decode('utf-8'), request_number=request_number,
            endpoint=self.endpoint + '/evaluate', timeout=timeout, attempt=1, profile=self.profile))
        started = time.monotonic()

        def capture(status_code, raw_body):
            self.record(dict(type='http_response', decision=decision, request_number=request_number,
                status_code=status_code, raw_body=raw_body, elapsed_seconds=time.monotonic() - started))

        def call():
            try:
                return client.request(body=body, endpoint=self.endpoint, timeout=timeout, on_response=capture)
            except urllib.error.HTTPError as exc:
                raise RuntimeError('joint q serving HTTP error ' + str(exc.code)) from exc
            except (ValueError, UnicodeError) as exc:
                raise j.UnusableChoice('malformed joint q response') from exc

        task = asyncio.create_task(asyncio.to_thread(call))
        try:
            response = await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.record(dict(type='request_expired', decision=decision, request_number=request_number,
                             elapsed_seconds=time.monotonic() - started))
            # The transport has its own bounded timeout. A late reply is evidence only.
            await asyncio.gather(task, return_exceptions=True)
            raise
        except Exception as exc:
            self.record(dict(type='request_failure', decision=decision, request_number=request_number,
                error=dict(type=type(exc).__name__, detail=str(exc)), elapsed_seconds=time.monotonic() - started))
            raise
        try:
            client.validate_identity(response, self.identity)
            if response.get('input_sha256') != protocol.input_sha256(joint):
                raise client.IdentityError('joint q response belongs to a different input')
        except client.IdentityError as exc:
            self.record(dict(type='response_rejected', decision=decision, reason=str(exc),
                             failure_scope='collection', elapsed_seconds=time.monotonic() - started))
            raise
        try:
            protocol.validate_response(response, joint.action_ids)
        except (ValueError, TypeError, KeyError) as exc:
            self.record(dict(type='response_rejected', decision=decision, reason=str(exc),
                             failure_scope='battle', elapsed_seconds=time.monotonic() - started))
            raise j.UnusableChoice(str(exc)) from exc
        self.record(dict(type='response', decision=decision, body=response,
                         q_values=response['q_values'], elapsed_seconds=time.monotonic() - started))
        return response

    def close(self):
        if not self.closed:
            self.generator.close()
            self.closed = True


def player_class():
    base = j.player_class()

    class JointQPlayer(base):
        latest_rqid = None

        async def _handle_battle_message(self, messages):
            import json
            # See newly delivered IDs before the inherited protocol lock queues a frame.
            for fields in messages:
                if len(fields) >= 2 and fields[1] == 'request':
                    raw = '|'.join(fields[2:])
                    request = json.loads(raw) if raw else None
                    self.latest_rqid = request.get('rqid') if isinstance(request, dict) else None
                    self.request_received_monotonic = time.monotonic()
            return await super()._handle_battle_message(messages)

        async def _handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
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
            rqid = self.request.get('rqid')
            decision = f'{self.username}-{rqid}-{len(self.session.records)}'
            decision_started = time.monotonic()
            if self.official is None:
                from ...observation.runtime import OfficialClient
                self.official = OfficialClient(actor)
            snapshot = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix),
                battle.battle_tag, boundary=self.boundary)
            input_started = time.monotonic()
            joint, commands, audit = await self.session.generate(snapshot, self.prefix,
                self.submitted_team, actor=actor)
            body = protocol.request_payload(joint)
            if tuple(commands) != joint.action_ids:
                raise ValueError('joint q command order differs from JointInput')
            from ...jev_v4 import save_audit
            self.session.record(dict(type='input', decision=decision, battle=battle.battle_tag,
                actor=actor, request_id=rqid, payload=joint.payload, payload_json=joint.payload_json,
                input_sha256=protocol.input_sha256(joint), commands=commands, actions=joint.payload['actions'],
                action_ids=list(joint.action_ids), boundary=copy.deepcopy(self.boundary), official=snapshot,
                observation_identity=self.official.identity,
                input_audit=save_audit(self.session.directory, decision, audit),
                snapshot_seconds=input_started - decision_started,
                input_generation_seconds=time.monotonic() - input_started))
            inference_started = time.monotonic()
            try:
                # Singletons take exactly the same model path as multiple candidates.
                response = await self.session.evaluate(body, decision=decision)
                try:
                    choice = protocol.validate_response(response, joint.action_ids)
                except (ValueError, TypeError, KeyError) as exc:
                    raise j.UnusableChoice(str(exc)) from exc
                values = response['q_values']
                current_commands = None
                revalidation = dict(type='revalidation', decision=decision, request_id=rqid,
                    latest_request_id=self.latest_rqid, current_request_id=None,
                    boundary=copy.deepcopy(self.boundary), official=None, passed=False)
                try:
                    current = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix),
                        battle.battle_tag, boundary=self.boundary)
                    current_rqid = (current.get('request') or {}).get('rqid')
                    revalidation.update(official=current, current_request_id=current_rqid)
                    _, current_commands = j.make_input(current, self.prefix, actor=actor, dex=self.session.dex,
                        initial_pp_policy=self.session.initial_pp_policy)
                    ensure_current(rqid, self.latest_rqid, self.request, commands, current_commands,
                        self.session.failure_event.is_set(), current_rqid=current_rqid)
                    if tuple(current_commands) != tuple(commands):
                        raise ValueError('changed legal action order; transmission forbidden')
                    if (time.monotonic() - inference_started >= self.session.timeout or self.session.remaining() <= 0):
                        raise TimeoutError('expired response; transmission forbidden')
                    revalidation['passed'] = True
                except (Exception, asyncio.CancelledError) as exc:
                    revalidation['error'] = dict(type=type(exc).__name__, detail=str(exc))
                    raise
                finally:
                    revalidation.update(latest_request_id=self.latest_rqid, revalidated_commands=current_commands,
                                        elapsed_seconds=time.monotonic() - inference_started)
                    self.session.record(revalidation)
            except (Exception, asyncio.CancelledError) as exc:
                self.session.record(dict(type='decision_rejected', decision=decision, request_id=rqid,
                    latest_request_id=self.latest_rqid, error=dict(type=type(exc).__name__, detail=str(exc)),
                    elapsed_seconds=time.monotonic() - inference_started, transmission='forbidden'))
                raise
            command = commands[choice]
            self.session.record(dict(type='selection', decision=decision, choice=choice, command=command,
                q_values=values, request_id=rqid, automatic=False,
                elapsed_seconds=time.monotonic() - inference_started,
                decision_seconds=time.monotonic() - decision_started,
                request_to_selection_seconds=(time.monotonic() - self.request_received_monotonic
                    if getattr(self, 'request_received_monotonic', None) is not None else None),
                revalidated_request_id=rqid, revalidated_commands=current_commands))
            await self.ps_client.send_message(command, battle.battle_tag, str(rqid))
            self.session.record(dict(type='wire', decision=decision, command=command,
                request_id=rqid, status='sent', decision_to_send_seconds=time.monotonic() - decision_started))

    return JointQPlayer
