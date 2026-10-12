"""Local fixture worker only: never imports/resolves a real credential."""

import runpy
from types import SimpleNamespace

from integration.pokechamp import cli
from integration.pokechamp.benchmark_player import BenchmarkBackend

original = BenchmarkBackend.__init__


def initialize(self, **kwargs):
    def chat(**kw):
        # Exhaust every IO; ensure every turn exercises the actual fallback wire path.
        return {
            "model": "glm-5.3-flash",
            "message": {"content": "fixture invalid output"},
            "prompt_eval_count": 1,
            "eval_count": 1,
        }

    original(
        self,
        environ={"OLLAMA_API_KEY": "local-fixture"},
        client_factory=lambda **_: SimpleNamespace(chat=chat),
        **kwargs,
    )


BenchmarkBackend.__init__ = initialize
cli._load_cloud_credential = lambda: None
runpy.run_module("integration.pokechamp.benchmark", run_name="__main__")
