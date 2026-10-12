"""EX-020 fake transport; actual actors, calculators, memory, and recorder remain live."""

import json
import os
import runpy
import sys
from pathlib import Path

from integration.pokechamp import cli
from integration.pokechamp.benchmark_player import BenchmarkBackend
from integration.pokechamp.improved_io.memory import HEADINGS

original = BenchmarkBackend.__init__


def initialize(self, **kwargs):
    def chat(**kw):
        context = getattr(self, "input_context", None)
        if self.role == "team_preview":
            content = '{"lead_slot": 3}'
        elif self.diagnostic_root and self.target is not None and not context:
            moves = list(self.target.available_moves)
            if moves and not self.target.force_switch:
                action = {"move": max(moves, key=lambda m: m.base_power).id}
            else:
                action = {"switch": self.target.available_switches[0].species}
            content = json.dumps(action)
        elif context and self.role == "self_action":
            # A deterministic test response from the supplied candidate list.
            actions = context["request"]["legal_actions"]
            scores = {}
            for entry in context["calculation_bundle"]["entries"]:
                if entry["scenario_id"].startswith("out-move-") and "damage_range_hp" in entry:
                    move = entry["scenario_id"].split("-")[2]
                    scores[move] = max(scores.get(move, 0), entry["damage_range_hp"][0])
            action = max(actions, key=lambda a: scores.get(a.get("move"), -1))
            content = "This is a deterministic local fixture action.\n" + json.dumps(action)
            if (os.environ.get("POKECHAMP_FAKE_OUTPUT_RECOVERY") == "1"
                    and not getattr(self, "_fake_recovery_exercised", False)):
                self._fake_recovery_exercised = True
                content = "A deliberately malformed local fixture response."
        elif context:
            identity = context["identity"]
            headings = "\n".join("## " + h for h in HEADINGS)
            content = (
                f"<summary>\nbattle_id: {identity['battle_id']}\n"
                f"actor_id: {identity['actor_id']}\n{headings}\n"
                f"Local fixture coverage [event:{context['source_event_ids'][-1]}].\n"
                "</summary>"
            )
        else:
            content = "fixture invalid output"
        return {
            "model": "glm-5.3-flash",
            "message": {"role": "assistant", "content": content},
            "prompt_eval_count": 1,
            "eval_count": 1,
            "done": True,
            "done_reason": "stop",
        }

    kwargs.pop("environ", None)
    environment = {**os.environ, "POKECHAMP_PROVIDER": "ollama", "OLLAMA_API_KEY": "local-fixture"}
    import httpx
    import ollama

    from integration.pokechamp.providers import ZaiChatClient

    request = json.loads((Path(sys.argv[2]) / "request.json").read_text())
    settings = request.get("provider_config", {})
    provider = settings.get("provider", "ollama")
    if provider == "zai":
        environment.update(POKECHAMP_PROVIDER="zai", ZAI_BASE_URL=settings["base_url"],
                           ZAI_API_KEY="local-fixture")
    failures = int(os.environ.get("POKECHAMP_FAKE_CONNECT_FAILURES", "0"))
    retry_errors = [e for e in os.environ.get("POKECHAMP_FAKE_RETRY_ERRORS", "").split(",") if e]
    http_calls = 0

    def handler(http_request):
        nonlocal http_calls
        http_calls += 1
        wire = json.loads(http_request.content)
        assert str(http_request.url) == settings.get("endpoint", "https://ollama.com/api/chat")
        assert wire["model"] == "glm-5.3-flash" and wire["stream"] is False
        if provider == "zai":
            assert wire["temperature"] == 0 and wire["max_tokens"] == 131072
            assert wire["thinking"] == {"type": "enabled"} and wire["reasoning_effort"] == "low"
            assert "seed" not in wire and "response_format" not in wire
        else:
            assert wire["options"]["num_predict"] == 131072 and wire["options"]["seed"] == 100
        assert 0 < http_request.extensions["timeout"]["read"] <= settings.get("request_timeout_seconds", 300)
        with (Path(sys.argv[2]) / (sys.argv[3] + "-mock-http.jsonl")).open("a") as stream:
            stream.write(json.dumps(dict(request=wire, timeout=http_request.extensions["timeout"],
                injected_connection_error=http_calls <= failures,
                injected_retry_error=retry_errors[http_calls-1] if http_calls <= len(retry_errors) else None)) + "\n")
        if http_calls <= len(retry_errors):
            error = retry_errors[http_calls - 1]
            if error == "timeout":
                raise httpx.ReadTimeout("local injected read timeout", request=http_request)
            return httpx.Response(int(error), json={"error": "local injected provider failure"},
                                  headers={"Retry-After": "60"})
        if http_calls <= failures:
            raise httpx.ConnectError("local injected connection failure", request=http_request)
        result = chat()
        if provider == "zai":
            return httpx.Response(200, json=dict(
                model="glm-5.3-flash", choices=[dict(
                    message=dict(content=result["message"]["content"], reasoning_content="local Z.ai reasoning fixture"),
                    finish_reason="stop")], usage=dict(prompt_tokens=1, completion_tokens=1),
            ))
        return httpx.Response(200, json=result)

    def factory(**kw):
        if provider == "zai":
            return ZaiChatClient(**kw, api_key="local-fixture", transport=httpx.MockTransport(handler))
        return ollama.Client(**kw, transport=httpx.MockTransport(handler))
    original(
        self,
        environ=environment,
        client_factory=factory,
        **kwargs,
    )


BenchmarkBackend.__init__ = initialize
cli._load_cloud_credential = lambda: None
runpy.run_module("integration.pokechamp.benchmark", run_name="__main__")
