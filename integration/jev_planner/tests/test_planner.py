import asyncio
import copy
import json
import threading

import httpx
import pytest

from integration.jev_planner.core import PlanOutputError, parse_plan
from integration.jev_planner.planner import MockPlanner, PlannerTransportError, ZaiPlannerClient
from integration.pokechamp.providers import CloudConfigurationError, provider_config
from integration.pokechamp.transport_policy import CURRENT, policy_fields


def config():
    return dict(provider="zai", model="glm-5.3-flash", thinking={"type": "enabled"},
                reasoning_effort="low", temperature=1, top_p=.95, max_tokens=8192,
                transport=policy_fields(CURRENT))


def response(*, content=None, reason="stop", usage=True):
    if content is None:
        content = json.dumps(dict(objective="Win with supported pressure.", priorities=["Preserve HP."],
            preserve=[], threats=[], tera_policy="Save Tera until useful.", contingencies=[]))
    body = dict(model="glm-5.3-flash", choices=[dict(finish_reason=reason,
        message={"content": content, "reasoning_content": "private reasoning"})])
    if usage:
        body["usage"] = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
    return httpx.Response(200, json=body)


def client(handler, **kwargs):
    return ZaiPlannerClient(config(), api_key="synthetic-private-key", base_url="https://example.test/api/v4",
                            transport=httpx.MockTransport(handler), environ={}, **kwargs)


def test_exact_zai_options_original_wire_usage_and_separate_reasoning():
    async def run():
        sent, records = [], []
        def handler(request):
            sent.append(request)
            return response()
        original = provider_config({"POKECHAMP_PROVIDER": "zai", "ZAI_BASE_URL": "https://example.test/api/v4"})
        async with client(handler, record=records.append) as planner:
            result = await planner.plan([{"role": "user", "content": "JSON plan please"}], request_id="decision-1")
        payload = json.loads(sent[0].content)
        assert payload == dict(model="glm-5.3-flash", messages=[{"role": "user", "content": "JSON plan please"}],
                               stream=False, thinking={"type": "enabled"}, reasoning_effort="low",
                               temperature=1, top_p=.95, max_tokens=8192, response_format={"type": "json_object"})
        assert "seed" not in payload and sent[0].headers["Authorization"] == "Bearer synthetic-private-key"
        assert result["reasoning"] == "private reasoning"
        assert result["plan"] == parse_plan(result["content"])
        assert result["usage"]["total_tokens"] == 30
        assert records[0]["request_body"].encode() == sent[0].content
        assert records[0]["usage"] == result["usage"] and records[0]["cost"] is None
        assert "synthetic-private-key" not in json.dumps(records)
        assert original["max_output_tokens"] == 131072
        assert provider_config({"POKECHAMP_PROVIDER": "zai", "ZAI_BASE_URL": "https://example.test/api/v4"}) == original
    asyncio.run(run())


@pytest.mark.parametrize("error", [429, 500, 503, httpx.ConnectError, httpx.ConnectTimeout,
                                  httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout])
@pytest.mark.parametrize("exhaust", [False, True])
def test_transport_policy_recovery_exhaustion_and_frozen_attempts(error, exhaust):
    async def run():
        sent, records, waits, admissions = [], [], [], []
        def handler(request):
            sent.append(request)
            if len(sent) <= (4 if exhaust else 3):
                if isinstance(error, int):
                    return httpx.Response(error, json={"error": "fixture"}, headers={"Retry-After": "999"})
                raise error("fixture", request=request)
            return response()
        async def sleep(seconds):
            waits.append(seconds)
        def admit(**kwargs):
            admissions.append(kwargs)
        async with client(handler, record=records.append, sleep=sleep, before_attempt=admit) as planner:
            if exhaust:
                with pytest.raises(PlannerTransportError) as failure:
                    await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
                if error == 429:
                    assert failure.value.category == "rate_limit" and failure.value.scope == "collection"
            else:
                result = await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
                assert result["http_attempts"] == 4
        assert waits == [1.0, 2.0, 4.0]
        assert len(sent) == len(admissions) == 4
        assert all(request.content == sent[0].content for request in sent)
        attempts = [row for row in records if row["type"] == "planner_transport"]
        assert [r["attempt"] for r in attempts] == [1, 2, 3, 4]
        assert all(r["request_id"] == "decision-1" for r in attempts)
        assert attempts[-1]["status"] == ("failure" if exhaust else "success")
    asyncio.run(run())


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 302])
def test_nonretryable_http_and_redirects(status):
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(status, headers={"Location": "https://other.test"})
        async with client(handler) as planner:
            with pytest.raises(PlannerTransportError):
                await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
        assert len(calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("content,reason", [("", "stop"), ("not JSON", "stop"), ("{}", "stop"), (None, "length")])
def test_bad_output_is_preserved_without_transport_retry(content, reason):
    async def run():
        calls, records = [], []
        def handler(request):
            calls.append(request)
            return response(content=content, reason=reason)
        async with client(handler, record=records.append) as planner:
            result = await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
        assert len(calls) == 1 and result["plan"] is None
        if content is not None:
            assert result["content"] == content
        with pytest.raises(PlanOutputError):
            parse_plan(result["content"], finish_reason=result["finish_reason"])
        assert records[0]["status"] == "success"
    asyncio.run(run())


def test_malformed_http_json_is_recorded_and_never_retried():
    async def run():
        calls, records = [], []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, text="malformed synthetic-private-key")
        async with client(handler, record=records.append) as planner:
            with pytest.raises(PlanOutputError):
                await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
        assert len(calls) == 1
        assert records[0]["response_body"] == "malformed [REDACTED]"
        assert records[0]["output_error"]
    asyncio.run(run())


def test_missing_usage_is_unknown_and_secrets_are_redacted_in_output_and_errors():
    async def run():
        records = []
        async with client(lambda _: response(content="synthetic-private-key", usage=False), record=records.append) as planner:
            result = await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
        assert result["usage"] is None and result["content"] == "[REDACTED]"
        assert "synthetic-private-key" not in json.dumps(records)
        async def sleep(_):
            return None
        def handler(request):
            raise httpx.ConnectError("synthetic-private-key", request=request)
        async with client(handler, record=records.append, sleep=sleep) as planner:
            with pytest.raises(PlannerTransportError) as failure:
                await planner.plan([{"role": "user", "content": "input"}], request_id="decision-2")
        assert "synthetic-private-key" not in json.dumps(failure.value.metadata)
        assert "synthetic-private-key" not in json.dumps(records)
    asyncio.run(run())


def test_cancel_and_budget_hook_prevent_next_attempt():
    async def run():
        calls, cancelled = [], [False]
        def handler(request):
            calls.append(request)
            return httpx.Response(429)
        async def sleep(_):
            cancelled[0] = True
        async with client(handler, sleep=sleep, cancelled=lambda: cancelled[0]) as planner:
            with pytest.raises(asyncio.CancelledError):
                await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
        assert len(calls) == 1
        def admission(**kwargs):
            raise RuntimeError("call budget exhausted")
        async with client(handler, before_attempt=admission) as planner:
            with pytest.raises(RuntimeError, match="budget"):
                await planner.plan([{"role": "user", "content": "input"}], request_id="decision-2")
        assert len(calls) == 1
    asyncio.run(run())


def test_private_dotenv_loader_and_process_precedence(tmp_path):
    async def run():
        path = tmp_path / ".env"
        path.write_text('ZAI_API_KEY="file-private-key"\nZAI_BASE_URL="https://example.test/api/v4"\n')
        path.chmod(0o600)
        calls = []
        env = {"ZAI_API_KEY": "process-private-key"}
        def handler(request):
            calls.append(request)
            return response()
        async with ZaiPlannerClient.from_env(config(), environ=env, path=path, transport=httpx.MockTransport(handler)) as planner:
            assert not calls
            await planner.plan([{"role": "user", "content": "input"}], request_id="decision-1")
        assert calls[0].headers["Authorization"] == "Bearer process-private-key"
        assert env == {"ZAI_API_KEY": "process-private-key"}
    asyncio.run(run())


def test_invalid_configuration_fails_before_network():
    with pytest.raises(CloudConfigurationError):
        ZaiPlannerClient(config(), api_key="", base_url="https://example.test", environ={})
    with pytest.raises(CloudConfigurationError):
        ZaiPlannerClient(config(), api_key="secret", base_url="http://example.test", environ={})
    modified = copy.deepcopy(config())
    modified["transport"]["provider_retries"] = 9
    with pytest.raises(CloudConfigurationError, match="provider-retry-v2"):
        ZaiPlannerClient(modified, api_key="secret", base_url="https://example.test", environ={})


def test_mock_is_deterministic_and_bad_response_does_not_repair():
    async def run():
        planner = MockPlanner()
        first = await planner.plan([], request_id="first")
        second = await planner.plan([], request_id="second")
        assert first == second and first["http_attempts"] == 0
        bad = await MockPlanner(bad_response="{").plan([], request_id="bad")
        assert bad["content"] == "{" and bad["plan"] is None
    asyncio.run(run())


def test_client_closes_pool_on_the_actor_loop_from_the_main_loop():
    owner = asyncio.new_event_loop()
    thread = threading.Thread(target=owner.run_forever, daemon=True)
    thread.start()
    async def run():
        planner = client(lambda _: response())
        closed_on = []
        original_close = planner._client.aclose
        async def close():
            closed_on.append(asyncio.get_running_loop())
            await original_close()
        planner._client.aclose = close
        future = asyncio.run_coroutine_threadsafe(
            planner.plan([{"role": "user", "content": "input"}], request_id="decision-1"), owner)
        assert (await asyncio.wrap_future(future))["plan"]
        await planner.aclose()
        assert closed_on == [owner]
    try:
        asyncio.run(run())
    finally:
        owner.call_soon_threadsafe(owner.stop)
        thread.join(timeout=3)
        owner.close()
