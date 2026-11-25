"""EP-247 / D-223 (EX-221): Future-Aware Antisymmetric Neural State Value Network V_phi v3.

Extends `value_model_v2.py` (EX-216) non-invasively with:
1. Dynamic PP & recent-move channels (`v3_mon[12,4]`: `heal_pp_frac`, `min_pp_frac`, `just_used_heal`,
   `just_used_protect`; `v3_glob[8]`: per-side `act_just_healed`, `act_just_protected`, `act_just_setup`,
   `team_heal_pp`), yielding `MON_IN_DIM = 42`, `GLOBAL_IN_DIM = 55`.
2. Exact zero-sum antisymmetry across BOTH primary win logit AND 5 multi-horizon future auxiliary heads:
       out_sym(s) = 0.5 * (f_phi(s) - f_phi(swap(s)))   for [z_win, h_3, h_5, h_10, h_delta5, h_boost3].
   Every head satisfies `out_sym(swap(s)) == -out_sym(s)` and `V_phi(swap(s)) == 1 - V_phi(s)` by construction.
3. Optional counterfactual pairwise ranking training (`train_value_v3.py`) so the shared encoder & primary win logit
   penalize tempo-losing high-HP heals / consecutive Protect while preserving calibrated win probability.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import torch
import torch.nn as nn

from . import featurize as F
from . import featurize_v3 as F3
from . import matchup_features as MF
from . import value_model as VM
from . import value_model_v2 as VM2

PURE_STATE_MON_INDICES = VM2.PURE_STATE_MON_INDICES  # 23
MATCHUP_PAIR_INDICES = VM2.MATCHUP_PAIR_INDICES      # 15
# Include ONLY `heal_pp_frac` (col 0 of v3_mon) — NEVER `just_used_heal`/`just_used_protect`, which acted as
# a blanket anti-heal shortcut under counterfactual ranking loss in the EX-221 v1 ablation (crushing accept_heal_low
# from 74% -> 21%). Without action-echo shortcuts, the network MUST learn true HP-vs-tempo/boost/matchup trade-offs!
V3_CLEAN_MON_DIM = 1
MON_IN_DIM = len(PURE_STATE_MON_INDICES) + len(MATCHUP_PAIR_INDICES) + V3_CLEAN_MON_DIM  # 23 + 15 + 1 = 39
GLOBAL_IN_DIM = F.GLOBAL_NUM_DIM + MF.GLOBAL_MATCHUP_DIM                                  # 35 + 12 = 47
NUM_FUT_HEADS = 5  # [fut_adv_3, fut_adv_5, fut_adv_10, fut_delta_5, fut_boost_diff_3]


def swap_v3_tensors(
    mon_x: torch.Tensor, global_x: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Exact side_one <-> side_two involution on combined v3 tensors `(mon_x[B,12,39], global_x[B,47])`."""
    s1 = mon_x[:, 6:12, :].clone()
    s2 = mon_x[:, 0:6, :].clone()
    s1[:, :, 0] = 1.0
    s2[:, :, 0] = 0.0
    swapped_mon = torch.cat([s1, s2], dim=1)
    swapped_glob = torch.cat([
        global_x[:, 11:22],       # s2 -> s1 (base)
        global_x[:, 0:11],        # s1 -> s2 (base)
        -global_x[:, 22:26],      # base diffs negated
        global_x[:, 26:35],       # symmetric field
        -global_x[:, 35:47],      # 12 matchup diffs negated
    ], dim=1)
    return swapped_mon, swapped_glob


def build_v3_inputs(
    mon_num: torch.Tensor,
    mon_cat_canon: torch.Tensor,
    global_num: torch.Tensor,
    v3_mon: torch.Tensor | None,
    v3_glob: torch.Tensor | None,
    tables: MF.MatchupTables,
    keep_idx: torch.Tensor,
    pair_idx: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    mx2, gx2 = VM2.build_v2_inputs(mon_num, mon_cat_canon, global_num, tables, keep_idx, pair_idx)
    bsz = mon_num.size(0)
    if v3_mon is None:
        heal_pp = torch.zeros((bsz, 12, 1), dtype=mon_num.dtype, device=mon_num.device)
    else:
        heal_pp = v3_mon[:, :, 0:1]  # heal_pp_frac only (no just_used_* shortcut!)
    mon_x = torch.cat([mx2, heal_pp], dim=-1)  # [B, 12, 39]
    return mon_x, gx2                          # [B, 47]


class StateValueNetV3(nn.Module):
    """Future-aware antisymmetric DeepSets with primary win logit + 5 multi-horizon future auxiliary heads."""

    def __init__(self, *, d_model: int = 64, dropout: float = 0.35):
        super().__init__()
        self.cfg = dict(
            arch='future_deepsets_v3',
            d_model=int(d_model),
            dropout=float(dropout),
            mon_in_dim=MON_IN_DIM,
            global_in_dim=GLOBAL_IN_DIM,
            num_fut_heads=NUM_FUT_HEADS,
        )
        self.register_buffer('keep_idx', torch.tensor(PURE_STATE_MON_INDICES, dtype=torch.long), persistent=False)
        self.register_buffer('pair_idx', torch.tensor(MATCHUP_PAIR_INDICES, dtype=torch.long), persistent=False)
        self.mon_enc = nn.Sequential(
            nn.Linear(MON_IN_DIM, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
        )
        head_in = d_model * 4 + GLOBAL_IN_DIM
        self.trunk = nn.Sequential(
            nn.Linear(head_in, d_model * 2),
            nn.LayerNorm(d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        # 1 primary win logit + 5 multi-horizon future predictions
        self.out_head = nn.Linear(d_model, 1 + NUM_FUT_HEADS)
        self.register_buffer('temperature', torch.tensor(1.0))

    def _raw_outputs(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> torch.Tensor:
        h = self.mon_enc(mon_x)  # [B, 12, D]
        alive = (mon_x[:, :, 2:3] > 0.5).float()
        s1_act = h[:, 0]
        s1_all = (h[:, 0:6] * alive[:, 0:6]).sum(dim=1) / alive[:, 0:6].sum(dim=1).clamp(min=1.0)
        s2_act = h[:, 6]
        s2_all = (h[:, 6:12] * alive[:, 6:12]).sum(dim=1) / alive[:, 6:12].sum(dim=1).clamp(min=1.0)
        feat = torch.cat([s1_act, s1_all, s2_act, s2_all, global_x], dim=-1)
        return self.out_head(self.trunk(feat))  # [B, 6]

    def forward_all(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return `(win_logit[B], fut_preds[B, 5])`, ALL exact zero-sum antisymmetric."""
        s_mx, s_gx = swap_v3_tensors(mon_x, global_x)
        both_m = torch.cat([mon_x, s_mx], dim=0)
        both_g = torch.cat([global_x, s_gx], dim=0)
        raw = self._raw_outputs(both_m, both_g)
        n = mon_x.size(0)
        sym = 0.5 * (raw[:n] - raw[n:])
        win_logit = sym[:, 0]
        fut_preds = torch.tanh(sym[:, 1:])  # bounded in (-1, 1), odd function preserves exact antisymmetry!
        return win_logit, fut_preds

    def forward(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> torch.Tensor:
        win_logit, _ = self.forward_all(mon_x, global_x)
        return win_logit

    def win_prob(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward(mon_x, global_x) / self.temperature.clamp(min=0.05))


def save_value_v3_checkpoint(model: StateValueNetV3, path: Path, meta: dict | None = None) -> None:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / 'weights.pt')
    cfg = dict(model.cfg, temperature=float(model.temperature.item()), meta=meta or {})
    (out / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1))


def load_value_v3_checkpoint(path: Path, device: str = 'cuda') -> tuple[StateValueNetV3, dict]:
    p = Path(path)
    cfg = json.loads((p / 'config.json').read_text())
    model = StateValueNetV3(d_model=cfg['d_model'], dropout=cfg['dropout'])
    state = torch.load(p / 'weights.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(state, strict=True)
    model.temperature.fill_(float(cfg.get('temperature', 1.0)))
    model.to(device)
    model.eval()
    return model, cfg


class ValueScorerV3:
    """Fast GPU/CPU batched scorer for `StateValueNetV3` (drop-in compatible with `ValueScorerV2`)."""

    def __init__(self, checkpoint: Path | str, device: str = 'cuda'):
        self.device = torch.device(device)
        self.model, self.cfg = load_value_v3_checkpoint(Path(checkpoint), device=device)
        self.tables = MF.default_tables().to(self.device)

    @torch.no_grad()
    def score_raw_batch(self, raw_list: Iterable[dict], batch_size: int = 256) -> list[float]:
        raws = list(raw_list)
        if not raws:
            return []
        default_m, default_g = F3.default_v3_arrays()
        out: list[float] = []
        for start in range(0, len(raws), batch_size):
            chunk = raws[start:start + batch_size]
            mn = torch.tensor([r['mon_num'] for r in chunk], dtype=torch.float32, device=self.device)
            mc = self.tables.encode_raw_mon_cat([r['mon_cat'] for r in chunk], self.device)
            gn = torch.tensor([r['global_num'] for r in chunk], dtype=torch.float32, device=self.device)
            v3m = torch.tensor([r.get('v3_mon', default_m) for r in chunk], dtype=torch.float32, device=self.device)
            v3g = torch.tensor([r.get('v3_glob', default_g) for r in chunk], dtype=torch.float32, device=self.device)
            mx, gx = build_v3_inputs(mn, mc, gn, v3m, v3g, self.tables, self.model.keep_idx, self.model.pair_idx)
            probs = self.model.win_prob(mx, gx).cpu().tolist()
            out.extend(float(x) for x in probs)
        return out


def load_any_scorer_v3(checkpoint: Path | str, device: str = 'cuda'):
    """Auto-detect v1 (`clean_deepsets_v2`), v2 (`matchup_deepsets_v2`), or v3 (`future_deepsets_v3`)."""
    cfg = json.loads((Path(checkpoint) / 'config.json').read_text())
    arch = cfg.get('arch')
    if arch == 'future_deepsets_v3':
        return ValueScorerV3(checkpoint, device=device)
    if arch == 'matchup_deepsets_v2':
        return VM2.ValueScorerV2(checkpoint, device=device)
    return VM.ValueScorer(checkpoint, device=device)
