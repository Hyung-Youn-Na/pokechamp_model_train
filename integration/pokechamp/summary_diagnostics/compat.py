"""D-028's isolated adapter for an effort absent from Ollama 0.6's request enum."""

from __future__ import annotations

import json

import ollama
from ollama._client import _copy_messages
from ollama._types import ChatRequest, ChatResponse

from ..cloud import CloudConfigurationError
from ..improved_io.backend import FixedBackend


class DiagnosticClient(ollama.Client):
    """Keep SDK authentication, HTTP, timeout and response parsing for both arms."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.serialized_request = None
        self._expected_body = None
        self._client.event_hooks["request"].append(self._capture_request)

    def _capture_request(self, request):
        body = json.loads(request.content)
        if body != self._expected_body:
            raise CloudConfigurationError("serialized diagnostic request drift")
        self.serialized_request = body

    def chat(
        self, *, model, messages, stream=False, think=None, format=None, options=None
    ):
        if think not in ("low", "high", "max") or stream is not False:
            raise CloudConfigurationError("unsupported diagnostic think/stream")
        # Validate every SDK field normally; only its obsolete effort enum is bypassed.
        body = ChatRequest(
            model=model,
            messages=list(_copy_messages(messages)),
            tools=[],
            stream=False,
            format=format,
            options=options,
        ).model_dump(exclude_none=True)
        body["think"] = think
        self.serialized_request = None
        self._expected_body = body
        return self._request(ChatResponse, "POST", "/api/chat", json=body, stream=False)


class DiagnosticBackend(FixedBackend):
    def _trace_llm_call(self, **payload):
        payload["serialized_request"] = self.client.serialized_request
        super()._trace_llm_call(**payload)


def fake_client_factory(content, mode):
    import httpx

    def respond(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("fake provider timeout", request=request)
        if mode == "hang":
            import time

            time.sleep(30)
        return httpx.Response(
            200,
            json=dict(
                model="glm-5.3-flash",
                message=dict(role="assistant", content=content),
                prompt_eval_count=12,
                eval_count=4,
                done=True,
                done_reason="stop",
            ),
        )

    return lambda **kwargs: DiagnosticClient(
        **kwargs, transport=httpx.MockTransport(respond)
    )
