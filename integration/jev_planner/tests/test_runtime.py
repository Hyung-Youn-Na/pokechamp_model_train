"""CPU transport/resource declaration checks; no model loads or CUDA calls."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from integration.jev27b.client import LocalClient
from integration.jev27b.server import LocalService
from integration.jev_planner import runtime
from integration.jev_planner.config import model_spec

IDENTITY = "a" * 64


def configuration(model="jev9b"):
    spec = model_spec(model)
    return dict(executor={"model": model}, evaluation=dict(resources=dict(
        gpu_indices=spec["physical_gpus"], **{key: spec[key] for key in
        ("allocator_bytes", "gpu_bytes", "host_bytes", "disk_bytes")})))


@pytest.mark.parametrize("model", ["jev9b", "jev27b", "minicpm5-jev"])
def test_resources_are_explicit_pinned_profile_not_old_output(model):
    config = configuration(model)
    assert runtime.validate_resources(config)["model_id"] == model_spec(model)["model_id"]
    config["evaluation"]["resources"]["gpu_bytes"] += 1
    with pytest.raises(ValueError, match="pinned"):
        runtime.validate_resources(config)


class FakeModel:
    def __init__(self, spec):
        self.spec, self.calls = spec, 0
    def metadata(self):
        return dict(model=self.spec["model_id"], revision=self.spec["revision"],
                    loaded=True, serving_identity=IDENTITY)
    def validate_input(self, payload):
        assert payload["model"] == self.spec["model_id"]
    def evaluate(self, payload):
        self.calls += 1
        choice = next(iter(payload["questions"]["action"]["criteria"]))
        return dict(model=self.spec["model_id"], answers={"action": {"type": "choice", "choice": choice}},
                    usage={"input_tokens": 100, "output_tokens": 0})


def test_lost_response_retry_reuses_physical_inference_and_records_attempts(tmp_path, monkeypatch):
    config = configuration()
    spec = model_spec("jev9b")
    model = FakeModel(spec)
    service = LocalService(model, tmp_path / "service", model_id=spec["model_id"],
                           revision=spec["revision"], protocol=runtime.PROTOCOL,
                           validate_before_inference=True)
    sent = []
    def transport(request):
        if request.method == "GET":
            return httpx.Response(200, json=service.health())
        sent.append(request)
        status, raw, reused = service.evaluate(request.content,
            request_id=request.headers["X-Request-ID"], body_sha256=request.headers["X-Body-SHA256"],
            expected_identity=request.headers["X-Serving-Identity"])
        if len(sent) == 1:
            raise httpx.ReadTimeout("lost response", request=request)
        return httpx.Response(status, content=raw, headers={
            "X-Request-ID": request.headers["X-Request-ID"],
            "X-Body-SHA256": request.headers["X-Body-SHA256"],
            "X-Serving-Identity": IDENTITY, "X-Cache-Reused": str(int(reused))})
    def factory(**kwargs):
        return LocalClient(**kwargs, transport=httpx.MockTransport(transport))
    events = []
    executor = runtime.LocalExecutor(config, endpoint="http://127.0.0.1:18845",
        expected_identity=IDENTITY, directory=tmp_path, record=events.append,
        client_factory=factory)
    monkeypatch.setattr(runtime, "RETRY_DELAYS", (0, 0, 0))
    payload = dict(state={"turn": 1}, questions={"action": {"type": "choice",
                          "instructions": "Choose", "criteria": {"a": {}, "b": {}}}})
    async def execute():
        try:
            result = await executor(payload, decision="test-1")
            with pytest.raises(ValueError, match="duplicate"):
                await executor(payload, decision="test-1")
            return result
        finally:
            await executor.close()
    try:
        result = asyncio.run(execute())
        assert result["answers"]["action"]["choice"] == "a"
        assert model.calls == 1 and len(sent) == 2
        assert len({request.content for request in sent}) == 1
        assert len({request.headers["X-Request-ID"] for request in sent}) == 1
        completed = [row for row in events if row["type"] == "executor_transport"]
        assert [row["attempt"] for row in completed] == [1, 2]
        assert completed[1]["cache_reused"] is True
        assert completed[1]["usage"]["input_tokens"] == 100
    finally:
        service.close()
