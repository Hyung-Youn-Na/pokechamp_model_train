"""Token layout of fixed-matchup-qwen-text-v1 (CPU only; no torch).

static prefix : [STATIC] static text                         (positions 0..P-1, cached per snapshot)
child row     : [DYN] dynamic text [VALUE]                    (value-only search children)
root row      : child row + per side ([OPEN] text [CLOSE])* [DECIDE_side]   (p1 block then p2 block)

Each text piece is tokenized on its own and delimiter ids are inserted directly, so no BPE merge crosses a
boundary and caller text can never produce a delimiter (Kev user_tokens rule).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re

from .config import MARKERS, PROTOCOL, SNAPSHOT

_SPECIAL = re.compile(r"<\|([A-Za-z0-9_]+)\|>")


@dataclass(frozen=True)
class Readout:
    value: int
    decide: tuple      # (p1 index, p2 index)
    closes: tuple      # (p1 close indices, p2 close indices)


class Tokens:
    def __init__(self, snapshot=SNAPSHOT):
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(snapshot / "tokenizer.json"))
        self.ids = {name: self.tokenizer.token_to_id(token) for name, token in MARKERS.items()}
        if any(value is None for value in self.ids.values()) or len(set(self.ids.values())) != len(self.ids):
            raise ValueError("delimiter tokens missing or duplicated")
        config = json.loads((snapshot / "tokenizer_config.json").read_text())
        pad = config.get("pad_token")
        pad = pad.get("content") if isinstance(pad, dict) else pad
        self.pad_id = self.tokenizer.token_to_id(pad) if pad else 0
        if self.pad_id is None:
            raise ValueError("pad token missing")
        self.limit = PROTOCOL["max_tokens"]

    def text(self, value):
        ids = self.tokenizer.encode(_SPECIAL.sub(r"<¦\1¦>", value), add_special_tokens=False).ids
        if any(i in self.ids.values() for i in ids):
            raise ValueError("delimiter produced by caller text")
        return ids

    def static(self, text):
        return [self.ids["static"], *self.text(text)]

    def child(self, dynamic):
        return [self.ids["dynamic"], *self.text(dynamic), self.ids["value"]]

    def root(self, dynamic, candidates):
        """candidates = {"p1": [text...], "p2": [text...]} in legal-action order -> (ids, Readout)."""
        ids = self.child(dynamic)
        value, decide, closes = len(ids) - 1, [], []
        for side in ("p1", "p2"):
            side_closes = []
            for text in candidates[side]:
                ids += [self.ids["open"], *self.text(text), self.ids["close"]]
                side_closes.append(len(ids) - 1)
            ids.append(self.ids[f"decide_{side}"])
            decide.append(len(ids) - 1)
            closes.append(tuple(side_closes))
        return ids, Readout(value, tuple(decide), tuple(closes))

    def check(self, prefix_length, row):
        if prefix_length + len(row) > self.limit:
            raise ValueError(f"row exceeds {self.limit} tokens: {prefix_length + len(row)}; no truncation")
        return row
