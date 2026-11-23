"""EP-243 / D-219 (2-B): Antisymmetric Pure-State-Dynamics Neural Value Network V_phi(poke_engine.State) -> [0, 1].

Ablation on EX-207 (321k train rows / 5,470 games, 17.7k held-out val rows / 304 games) showed that including raw
species/ability/item/move IDs or exact raw stats (maxhp/atk/def/spa/spd/spe) causes severe game-signature
memorization (val AUC 0.645 vs evaluate.rs 0.723), whereas a compact DeepSets network over the 23 pure state-dynamics
features per Pokemon + 35 global/hazard/field features generalizes cleanly across unseen teams and beats even
temperature-calibrated `evaluate.rs` on every metric and every game phase (val AUC ~0.741, LogLoss ~0.593, ECE ~0.017).

Guarantees exact zero-sum antisymmetry by construction:
    logit_sym(s) = 0.5 * (f_phi(s) - f_phi(swap(s)))
    V_phi(s)     = sigmoid(logit_sym(s) / temperature)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn

from . import featurize as F

# Exclude raw stat fingerprint indices 4..9 (maxhp, atk, def, spa, spd, spe)
PURE_STATE_MON_INDICES = (0, 1, 2, 3, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28)


def swap_batch_tensors(
    mon_num: torch.Tensor, mon_cat: torch.Tensor, global_num: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Vectorized side_one <-> side_two swap involution on batched GPU/CPU tensors."""
    mn_s1 = mon_num[:, 6:12, :].clone()
    mn_s2 = mon_num[:, 0:6, :].clone()
    mn_s1[:, :, 0] = 1.0
    mn_s2[:, :, 0] = 0.0
    swapped_mn = torch.cat([mn_s1, mn_s2], dim=1)
    swapped_mc = torch.cat([mon_cat[:, 6:12, :], mon_cat[:, 0:6, :]], dim=1)
    swapped_gn = torch.cat([
        global_num[:, 11:22],
        global_num[:, 0:11],
        -global_num[:, 22:26],
        global_num[:, 26:35],
    ], dim=1)
    return swapped_mn, swapped_mc, swapped_gn


class StateValueNet(nn.Module):
    """Antisymmetric pure-state-dynamics DeepSets network predicting side_one win logit from `poke_engine.State`."""

    def __init__(
        self,
        vocab_sizes: dict[str, int] | None = None,
        *,
        d_model: int = 64,
        dropout: float = 0.25,
    ):
        super().__init__()
        self.cfg = dict(
            arch='clean_deepsets_v2',
            vocab_sizes=dict(vocab_sizes or {}),
            d_model=int(d_model),
            dropout=float(dropout),
            mon_num_dim=F.MON_NUM_DIM,
            pure_mon_dim=len(PURE_STATE_MON_INDICES),
            global_num_dim=F.GLOBAL_NUM_DIM,
        )
        self.register_buffer('keep_idx', torch.tensor(PURE_STATE_MON_INDICES, dtype=torch.long), persistent=False)
        self.mon_enc = nn.Sequential(
            nn.Linear(len(PURE_STATE_MON_INDICES), d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
        )
        self.head = nn.Sequential(
            nn.Linear(d_model * 4 + F.GLOBAL_NUM_DIM, d_model * 2),
            nn.LayerNorm(d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, 1),
        )
        self.register_buffer('temperature', torch.tensor(1.0))

    def _raw_logit(self, mon_num: torch.Tensor, mon_cat: torch.Tensor, global_num: torch.Tensor) -> torch.Tensor:
        x = mon_num.index_select(-1, self.keep_idx)
        h = self.mon_enc(x)                                   # [B, 12, D]
        s1_act = h[:, 0]
        s1_all = h[:, 0:6].mean(dim=1)
        s2_act = h[:, 6]
        s2_all = h[:, 6:12].mean(dim=1)
        feat = torch.cat([s1_act, s1_all, s2_act, s2_all, global_num], dim=-1)
        return self.head(feat).squeeze(-1)

    def forward(self, mon_num: torch.Tensor, mon_cat: torch.Tensor, global_num: torch.Tensor) -> torch.Tensor:
        """Exact antisymmetric win logit: `0.5 * (f(s) - f(swap(s)))`."""
        s_mn, s_mc, s_gn = swap_batch_tensors(mon_num, mon_cat, global_num)
        both_mn = torch.cat([mon_num, s_mn], dim=0)
        both_mc = torch.cat([mon_cat, s_mc], dim=0)
        both_gn = torch.cat([global_num, s_gn], dim=0)
        logits = self._raw_logit(both_mn, both_mc, both_gn)
        n = mon_num.size(0)
        return 0.5 * (logits[:n] - logits[n:])

    def win_prob(self, mon_num: torch.Tensor, mon_cat: torch.Tensor, global_num: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward(mon_num, mon_cat, global_num) / self.temperature.clamp(min=0.05))


def save_value_checkpoint(model: StateValueNet, vocab: F.Vocab, path: Path, meta: dict | None = None) -> None:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / 'weights.pt')
    vocab.save(out / 'vocab.json')
    cfg = dict(model.cfg, temperature=float(model.temperature.item()), meta=meta or {})
    (out / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1))


def load_value_checkpoint(path: Path, device: str = 'cuda') -> tuple[StateValueNet, F.Vocab, dict]:
    p = Path(path)
    cfg = json.loads((p / 'config.json').read_text())
    vocab = F.Vocab.load(p / 'vocab.json')
    model = StateValueNet(
        cfg.get('vocab_sizes'),
        d_model=cfg['d_model'],
        dropout=cfg['dropout'],
    )
    state = torch.load(p / 'weights.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(state, strict=True)
    model.temperature.fill_(float(cfg.get('temperature', 1.0)))
    model.to(device)
    model.eval()
    return model, vocab, cfg


class ValueScorer:
    """Fast GPU batched scorer accepting raw extracted feature dicts from `featurize.extract_raw`."""

    def __init__(self, checkpoint: Path | str, device: str = 'cuda'):
        self.device = torch.device(device)
        self.model, self.vocab, self.cfg = load_value_checkpoint(Path(checkpoint), device=device)

    @torch.no_grad()
    def score_raw_batch(self, raw_list: Iterable[dict], batch_size: int = 256) -> list[float]:
        raws = list(raw_list)
        if not raws:
            return []
        out: list[float] = []
        for start in range(0, len(raws), batch_size):
            chunk = raws[start:start + batch_size]
            mn = torch.tensor([r['mon_num'] for r in chunk], dtype=torch.float32, device=self.device)
            mc = torch.zeros((len(chunk), F.NUM_SLOTS, F.MON_CAT_DIM), dtype=torch.long, device=self.device)
            gn = torch.tensor([r['global_num'] for r in chunk], dtype=torch.float32, device=self.device)
            probs = self.model.win_prob(mn, mc, gn).cpu().tolist()
            out.extend(float(x) for x in probs)
        return out
