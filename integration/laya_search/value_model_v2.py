"""EP-245 / D-221 (EX-216): Matchup-Aware Antisymmetric Neural State Value Network V_phi v2.

Combines EX-207's 23 pure state-dynamics features per Pokemon + 35 global features WITH `matchup_features.py`'s
37 Gen 9 mechanical matchup features per Pokemon (type chart, Tera, Air Balloon/Levitate/Absorb immunities,
items, abilities, moves, recovery/drain, speed, 6x6 coverage) + 12 global antisymmetric matchup diffs.

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
from . import matchup_features as MF
from . import value_model as VM

PURE_STATE_MON_INDICES = VM.PURE_STATE_MON_INDICES  # 23 features (excludes raw stat fingerprints 4..9)
# Select team-agnostic mechanical interaction features from `compute_matchup_features` (37 cols):
# col 22 = `entry_hazard_dmg`, cols 23..36 = 14 pairwise damage/walled/2HKO/drain/speed/6x6-coverage features.
# Excludes static per-mon kit flags (cols 0..21) which act as team fingerprints on 5.5k games (EX-216 ablation:
# pair_only achieved val AUC 0.7536 / LL 0.5848 vs all-60 AUC 0.7516 / LL 0.5865 and EX-207 AUC 0.7389 / LL 0.5967).
MATCHUP_PAIR_INDICES = (22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36)  # 15 features
MON_IN_DIM = len(PURE_STATE_MON_INDICES) + len(MATCHUP_PAIR_INDICES)  # 23 + 15 = 38
GLOBAL_IN_DIM = F.GLOBAL_NUM_DIM + MF.GLOBAL_MATCHUP_DIM              # 35 + 12 = 47


def swap_v2_tensors(
    mon_x: torch.Tensor, global_x: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Exact side_one <-> side_two involution on combined v2 tensors `(mon_x[B,12,38], global_x[B,47])`."""
    s1 = mon_x[:, 6:12, :].clone()
    s2 = mon_x[:, 0:6, :].clone()
    s1[:, :, 0] = 1.0
    s2[:, :, 0] = 0.0
    swapped_mon = torch.cat([s1, s2], dim=1)
    swapped_glob = torch.cat([
        global_x[:, 11:22],       # s2 -> s1
        global_x[:, 0:11],        # s1 -> s2
        -global_x[:, 22:26],      # original diffs negated
        global_x[:, 26:35],       # symmetric field
        -global_x[:, 35:47],      # 12 matchup diffs negated!
    ], dim=1)
    return swapped_mon, swapped_glob


def build_v2_inputs(
    mon_num: torch.Tensor,
    mon_cat_canon: torch.Tensor,
    global_num: torch.Tensor,
    tables: MF.MatchupTables,
    keep_idx: torch.Tensor,
    pair_idx: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    pure_mon = mon_num.index_select(-1, keep_idx)  # [B, 12, 23]
    mon_m, glob_m = MF.compute_matchup_features(mon_num, mon_cat_canon, global_num, tables)
    if pair_idx is None:
        pair_idx = torch.tensor(MATCHUP_PAIR_INDICES, dtype=torch.long, device=mon_m.device)
    pair_mon = mon_m.index_select(-1, pair_idx)    # [B, 12, 15]
    mon_x = torch.cat([pure_mon, pair_mon], dim=-1)      # [B, 12, 38]
    global_x = torch.cat([global_num, glob_m], dim=-1)   # [B, 47]
    return mon_x, global_x


class StateValueNetV2(nn.Module):
    """Matchup-aware antisymmetric DeepSets network over pure dynamics + 6x6 mechanical pairwise interactions."""

    def __init__(self, *, d_model: int = 64, dropout: float = 0.35):
        super().__init__()
        self.cfg = dict(
            arch='matchup_deepsets_v2',
            d_model=int(d_model),
            dropout=float(dropout),
            mon_in_dim=MON_IN_DIM,
            global_in_dim=GLOBAL_IN_DIM,
            pure_mon_dim=len(PURE_STATE_MON_INDICES),
            mon_matchup_dim=len(MATCHUP_PAIR_INDICES),
            global_matchup_dim=MF.GLOBAL_MATCHUP_DIM,
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
        # Pool: s1_act, s1_alive_mean, s2_act, s2_alive_mean + global_x
        head_in = d_model * 4 + GLOBAL_IN_DIM
        self.head = nn.Sequential(
            nn.Linear(head_in, d_model * 2),
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

    def _raw_logit(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> torch.Tensor:
        h = self.mon_enc(mon_x)  # [B, 12, D]
        alive = (mon_x[:, :, 2:3] > 0.5).float()  # [B, 12, 1]
        s1_act = h[:, 0]
        s1_all = (h[:, 0:6] * alive[:, 0:6]).sum(dim=1) / alive[:, 0:6].sum(dim=1).clamp(min=1.0)
        s2_act = h[:, 6]
        s2_all = (h[:, 6:12] * alive[:, 6:12]).sum(dim=1) / alive[:, 6:12].sum(dim=1).clamp(min=1.0)
        feat = torch.cat([s1_act, s1_all, s2_act, s2_all, global_x], dim=-1)
        return self.head(feat).squeeze(-1)

    def forward(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> torch.Tensor:
        """Exact antisymmetric win logit: `0.5 * (f(s) - f(swap(s)))`."""
        s_mx, s_gx = swap_v2_tensors(mon_x, global_x)
        both_m = torch.cat([mon_x, s_mx], dim=0)
        both_g = torch.cat([global_x, s_gx], dim=0)
        logits = self._raw_logit(both_m, both_g)
        n = mon_x.size(0)
        return 0.5 * (logits[:n] - logits[n:])

    def win_prob(self, mon_x: torch.Tensor, global_x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward(mon_x, global_x) / self.temperature.clamp(min=0.05))


def save_value_v2_checkpoint(model: StateValueNetV2, path: Path, meta: dict | None = None) -> None:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / 'weights.pt')
    cfg = dict(model.cfg, temperature=float(model.temperature.item()), meta=meta or {})
    (out / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1))


def load_value_v2_checkpoint(path: Path, device: str = 'cuda') -> tuple[StateValueNetV2, dict]:
    p = Path(path)
    cfg = json.loads((p / 'config.json').read_text())
    model = StateValueNetV2(d_model=cfg['d_model'], dropout=cfg['dropout'])
    state = torch.load(p / 'weights.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(state, strict=True)
    model.temperature.fill_(float(cfg.get('temperature', 1.0)))
    model.to(device)
    model.eval()
    return model, cfg


class ValueScorerV2:
    """Fast GPU/CPU batched scorer accepting raw extracted dicts from `featurize.extract_raw` (drop-in for `ValueScorer`)."""

    def __init__(self, checkpoint: Path | str, device: str = 'cuda'):
        self.device = torch.device(device)
        self.model, self.cfg = load_value_v2_checkpoint(Path(checkpoint), device=device)
        self.tables = MF.default_tables().to(self.device)

    @torch.no_grad()
    def score_raw_batch(self, raw_list: Iterable[dict], batch_size: int = 256) -> list[float]:
        raws = list(raw_list)
        if not raws:
            return []
        out: list[float] = []
        for start in range(0, len(raws), batch_size):
            chunk = raws[start:start + batch_size]
            mn = torch.tensor([r['mon_num'] for r in chunk], dtype=torch.float32, device=self.device)
            mc = self.tables.encode_raw_mon_cat([r['mon_cat'] for r in chunk], self.device)
            gn = torch.tensor([r['global_num'] for r in chunk], dtype=torch.float32, device=self.device)
            mx, gx = build_v2_inputs(mn, mc, gn, self.tables, self.model.keep_idx, self.model.pair_idx)
            probs = self.model.win_prob(mx, gx).cpu().tolist()
            out.extend(float(x) for x in probs)
        return out


def load_any_scorer(checkpoint: Path | str, device: str = 'cuda'):
    """Auto-detect v1 (`clean_deepsets_v2`) vs v2 (`matchup_deepsets_v2`) checkpoint."""
    cfg = json.loads((Path(checkpoint) / 'config.json').read_text())
    if cfg.get('arch') == 'matchup_deepsets_v2':
        return ValueScorerV2(checkpoint, device=device)
    return VM.ValueScorer(checkpoint, device=device)
