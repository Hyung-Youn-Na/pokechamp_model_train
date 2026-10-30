"""JSONL process boundary between pinned CPU Metamon and PokéChamp/Kev."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
ENV = ROOT / ".tools/metamon-imitation"
REVISION = "0a00a759c9a4382a2877088d828302ec294a05a5"


class BridgeClient:
    def __init__(self, corpus_sets=None):
        self.stderr = tempfile.TemporaryFile(mode="w+t")
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1",
                   TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   PYTHONPATH=os.pathsep.join((str(ROOT), str(ENV / "upstream"))))
        self.process = subprocess.Popen([str(ENV / ".venv/bin/python"), "-m", __name__, "--worker"],
            cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, bufsize=1)
        self.request(dict(op="hello"))
        if corpus_sets is not None:
            self.request(dict(op="corpus", entries=corpus_sets))

    def request(self, message):
        self.process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            self.stderr.seek(0)
            raise RuntimeError("Metamon CPU worker exited: " + self.stderr.read()[-3000:])
        result = json.loads(line)
        if not result.get("ok"):
            raise RuntimeError("Metamon CPU worker: " + result.get("error", "unknown error"))
        return result["result"]

    def recover(self, raw_json, replay_id, corpus_sets=None):
        if corpus_sets is not None:
            self.request(dict(op="corpus", entries=corpus_sets))
        return self.request(dict(op="recover", raw=raw_json, replay_id=replay_id))

    def snapshot(self, prefix, own_sets, perspective, decision_kind, early_history=False):
        message = dict(op="snapshot", prefix=prefix, own_sets=own_sets,
                       perspective=perspective, decision_kind=decision_kind)
        if early_history:   # D-198: only requested by models trained on it; the default request is unchanged
            message["early_history"] = True
        return self.request(message)

    def extract_teams(self, raw_json):
        from .impute import extract_teams
        return extract_teams(raw_json)

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
        self.process.stdout.close()
        self.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def worker():
    from .impute import SetCorpus, revealed_original_sets
    from .replay import recover, serialize_state
    import importlib.metadata
    commit = subprocess.check_output(["git", "-C", str(ENV / "upstream"), "rev-parse", "HEAD"], text=True).strip()
    if commit != REVISION or importlib.metadata.version("poke-env") != "0.8.3.3":
        raise RuntimeError("pinned CPU parser identity mismatch")
    if subprocess.check_output(["git", "-C", str(ENV / "upstream"), "status", "--porcelain"], text=True).strip():
        raise RuntimeError("pinned upstream checkout was modified")
    corpus = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            op = request["op"]
            if op == "hello":
                result = dict(revision=commit, poke_env=importlib.metadata.version("poke-env"), gpu=False)
            elif op == "corpus":
                corpus = SetCorpus(request["entries"])
                result = dict(entries=len(request["entries"]))
            elif op == "reveal":
                result = revealed_original_sets(request["raw"])
            elif op == "recover":
                if corpus is None:
                    raise ValueError("initialize validated corpus before recovery")
                result = recover(request["raw"], request["replay_id"], corpus)
            elif op == "snapshot":
                result = serialize_state(request["prefix"], request["own_sets"], request["perspective"], request["decision_kind"],
                                         early_history=request.get("early_history", False))
            else:
                raise ValueError("unknown bridge operation")
            response = dict(ok=True, result=result)
        except Exception as exc:
            response = dict(ok=False, error=f"{type(exc).__name__}: {exc}")
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    worker()
