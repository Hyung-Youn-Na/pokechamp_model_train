"""Metamon CPU worker for EX-166: `metamon_bridge.worker` with the D-208 ability provenance fix in `recover`."""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile

from integration.pokechamp.imitation import metamon_bridge


class Client(metamon_bridge.BridgeClient):
    """`BridgeClient` whose worker is this module (same pinned Metamon env, same JSONL protocol)."""

    def __init__(self, corpus_sets=None):   # BridgeClient.__init__ with this module as the worker entry point
        self.stderr = tempfile.TemporaryFile(mode='w+t')
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                   OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   PYTHONPATH=os.pathsep.join((str(metamon_bridge.ROOT), str(metamon_bridge.ENV / 'upstream'))))
        self.process = subprocess.Popen([str(metamon_bridge.ENV / '.venv/bin/python'), '-m', __name__, '--worker'],
                                        cwd=metamon_bridge.ROOT, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr, text=True, bufsize=1)
        self.request(dict(op='hello'))
        if corpus_sets is not None:
            self.request(dict(op='corpus', entries=corpus_sets))


if __name__ == '__main__' and sys.argv[1:2] == ['--worker']:
    from integration.pokechamp.imitation import replay
    from . import abilities
    replay.revealed_original_sets = abilities.revealed_original_sets
    metamon_bridge.worker()
