"""EX-161 training and scoring with the v10 per-option cap, without editing laya_imitation.

laya_imitation's training (`training.run`) and scoring (`Policy`, `evaluation.evaluate`, `evaluation_tera.knowledge`)
import laya's functions at call time, so this process threads `option_max_len` through them here:
- `laya.train.items_from_rows` / `train_model` / `calibration_records` / `encode_item` get the cap as a keyword;
- every checkpoint saved records it (`option_max_len` in its config), and `train-config.json` / `TrainConfig` carry it;
- `laya_imitation.policy.Policy` becomes `Policy10`, which scores at the checkpoint's own token, head and option caps.
The laya with `option_max_len` must come first on `sys.path` (`paths.LAYA_SOURCE`, see `require_laya`).
"""
from __future__ import annotations
import functools
import inspect

from integration.laya_imitation import config as c
from integration.laya_imitation.policy import Policy as _Policy, render as _render

from . import paths

_installed = None


def require_laya():
    import laya.common
    if 'option_max_len' not in inspect.signature(laya.common.build_head).parameters or \
            not str(laya.common.__file__).startswith(str(paths.LAYA_SOURCE)):
        raise RuntimeError('laya with option_max_len is not first on PYTHONPATH (%s): %s'
                           % (paths.LAYA_SOURCE, laya.common.__file__))


def install(option):
    """Thread `option` through laya and laya_imitation in this process (idempotent for the same value)."""
    global _installed
    if _installed is not None:
        if _installed != option:
            raise RuntimeError('option cap already installed as %d' % _installed)
        return
    require_laya()
    import laya.train as T
    for name in ('items_from_rows', 'train_model', 'calibration_records', 'encode_item'):
        setattr(T, name, functools.partial(getattr(T, name), option_max_len=option))
    save = T.save_checkpoint

    def save_checkpoint(model, tok, cfg, path, *args, **kw):
        return save(model, tok, dict(cfg, option_max_len=option), path, *args, **kw)
    T.save_checkpoint = save_checkpoint
    from integration.laya_imitation import policy, training
    base = training._train
    training._train = lambda spec: dict(base(spec), option_max_len=option)
    policy.Policy = Policy10
    _installed = option


def spec(budget):
    """EX-161: EX-149's settings with the v10 rows, 2,048 tokens and the measured head, GPU0, no time limit."""
    from integration.laya_imitation.training import Spec
    return Spec('EX-161', paths.V10_DATASET, paths.RUN_V10_TRAINING, budget['head'], 'ex161', max_exclusion_rate=0.005,
                extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', gpu=paths.GPU, hours=None, max_len=paths.TOKEN_LIMIT)


class Policy10(_Policy):
    """`Policy` at a v10 checkpoint's own caps (`max_len`, `head_max_len`, `option_max_len` from its config).

    A checkpoint without `option_max_len` (the base model for mock games, older checkpoints) is scored at the caps
    the caller passes, with laya's default 48 per option."""

    def __init__(self, checkpoint, device='cuda', head_limit=None, renderer=None, token_limit=None):
        super().__init__(checkpoint, device=device, head_limit=head_limit or c.V2_HEAD_LIMIT,
                         renderer=renderer or _render, token_limit=token_limit)
        self.option_max_len = self.cfg.get('option_max_len', 48)
        if 'option_max_len' in self.cfg:   # a v10 checkpoint is always scored at its own caps
            self.max_len, self.head_max_len = self.cfg['max_len'], self.cfg['head_max_len']

    def logits(self, items, batch_size=16):
        import torch
        from laya.common import collate_items
        from laya.train import _forward, encode_item
        encode = getattr(encode_item, 'func', encode_item)
        out = []
        with torch.no_grad():
            for start in range(0, len(items), batch_size):
                chunk = items[start:start + batch_size]
                batch = collate_items([[encode(self.tok, it, self.max_len, self.head_max_len,
                                               option_max_len=self.option_max_len) for it in chunk]],
                                      self.tok.pad_token_id)
                rows = _forward(self.model, batch, self.device, amp=False, detach_encoder=False).cpu().double()
                out.extend(row[:it['k']].tolist() for row, it in zip(rows, chunk))
        return out
