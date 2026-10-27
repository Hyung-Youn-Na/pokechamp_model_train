"""Token accounting for compact rows with the laya tokenizer and laya's own sequence builder."""
from __future__ import annotations

from laya.common import build_head, encode_text, serialize_state
from laya.train import to_internal

from .config import HEAD_LIMIT, TOKEN_LIMIT


def measure(tok, state, question):
    """Full untruncated length and whether the row fits laya's budgets without any cut."""
    q = to_internal('action', question)
    head_full, _, _ = build_head(tok, q, 10 ** 6)
    head_ids, markers, stats = build_head(tok, q, HEAD_LIMIT)
    state_ids = encode_text(tok, serialize_state(state), add_special_tokens=False)['input_ids']
    total = len(head_full) + len(state_ids) + 1
    head_cut = len(head_full) > HEAD_LIMIT + 2  # +[CLS]/[SEP] around the budgeted part
    collapsed = stats['options_distinct'] < stats['options']
    return dict(total=total, head=len(head_full), state=len(state_ids), options=stats['options'],
                fits=total <= TOKEN_LIMIT and not head_cut and not collapsed,
                head_cut=head_cut, collapsed=collapsed)
