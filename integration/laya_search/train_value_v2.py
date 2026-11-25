"""EP-245 / D-221 (EX-216): Train & evaluate Matchup-Aware StateValueNetV2 on physical GPU 0 ONLY.

    CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4 \
        PYTHONPATH=.:pokechamp .tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python \
        -m integration.laya_search.train_value_v2

Uses the exact same leakage-controlled split as EX-207 (`datasets/generated/laya-state-value/v1`:
321,367 train / 17,448 calib / 17,699 val rows; 64 sealed Blim teams excluded) so metrics compare directly
against EX-207 (`clean_deepsets_v2`, val AUC 0.73893, LogLoss 0.59674) and calibrated `evaluate.rs`.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import time

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from . import featurize as F
from . import matchup_features as MF
from . import search_core as SC
from . import train_value_2b as T1
from . import value_model_v2 as VM2

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
DATA = SHARED / 'datasets/generated/laya-state-value/v1'
RUN = SHARED / 'runs/model-training/EX-216'


@torch.no_grad()
def precompute_split(
    split: dict[str, np.ndarray],
    vocab: F.Vocab,
    tables: MF.MatchupTables,
    keep_idx: torch.Tensor,
    device: torch.device,
    batch_size: int = 4096,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Vectorized precomputation of `(mon_x[N,12,60], global_x[N,47])` on GPU, returned on CPU."""
    n = len(split['win'])
    mx_out = torch.empty((n, 12, VM2.MON_IN_DIM), dtype=torch.float32)
    gx_out = torch.empty((n, VM2.GLOBAL_IN_DIM), dtype=torch.float32)
    for start in range(0, n, batch_size):
        end = min(n, start + batch_size)
        mn = torch.from_numpy(split['mon_num'][start:end]).to(device)
        mc_v = torch.from_numpy(split['mon_cat'][start:end]).long().to(device)
        mc = tables.remap_vocab_mon_cat(mc_v, vocab)
        gn = torch.from_numpy(split['global_num'][start:end]).to(device)
        mx, gx = VM2.build_v2_inputs(mn, mc, gn, tables, keep_idx)
        mx_out[start:end] = mx.cpu()
        gx_out[start:end] = gx.cpu()
    return mx_out, gx_out


@torch.no_grad()
def _predict_logits_v2(
    model: VM2.StateValueNetV2,
    mx: torch.Tensor,
    gx: torch.Tensor,
    device: torch.device,
    batch_size: int = 1024,
) -> np.ndarray:
    model.eval()
    out = []
    for start in range(0, len(mx), batch_size):
        z = model(mx[start:start + batch_size].to(device), gx[start:start + batch_size].to(device)).cpu().numpy()
        out.append(z)
    return np.concatenate(out, axis=0)


def train(
    *,
    data_dir: Path = DATA,
    out_dir: Path = RUN,
    epochs: int = 24,
    batch_size: int = 512,
    samples_per_epoch: int = 40000,
    d_model: int = 64,
    dropout: float = 0.35,
    lr: float = 4e-4,
    weight_decay: float = 1e-1,
    seed: int = 20261216,
    device_str: str = 'cuda',
) -> dict:
    if device_str == 'cuda':
        cvd = os.environ.get('CUDA_VISIBLE_DEVICES', '')
        if not cvd or any(u not in SC.ALLOWED_GPU_UUIDS for u in cvd.split(',')):
            raise RuntimeError('Refusing to run CUDA without GPU 0/1 UUID pinning; got CUDA_VISIBLE_DEVICES=%r' % (cvd,))

    torch.manual_seed(seed)
    np.random.seed(seed)
    device = torch.device(device_str)
    started = time.time()

    vocab = F.Vocab.load(data_dir / 'vocab.json')
    tr = T1._load_split(data_dir / 'train.npz')
    cal = T1._load_split(data_dir / 'calib.npz')
    val = T1._load_split(data_dir / 'val.npz')

    model = VM2.StateValueNetV2(d_model=d_model, dropout=dropout).to(device)
    tables = MF.default_tables().to(device)

    print('[ex216] precomputing Gen-9 matchup features for train/calib/val...', flush=True)
    t_feat = time.time()
    tr_mx, tr_gx = precompute_split(tr, vocab, tables, model.keep_idx, device)
    cal_mx, cal_gx = precompute_split(cal, vocab, tables, model.keep_idx, device)
    val_mx, val_gx = precompute_split(val, vocab, tables, model.keep_idx, device)
    feat_sec = round(time.time() - t_feat, 2)

    # Sanity check: NaN/Inf + antisymmetry
    assert torch.isfinite(tr_mx).all() and torch.isfinite(tr_gx).all(), 'non-finite train matchup features'
    assert torch.isfinite(val_mx).all() and torch.isfinite(val_gx).all(), 'non-finite val matchup features'
    walled_rate = float((val_mx[:, 0, 23 + 1 + 3] > 0.5).float().mean().item())
    n_params = sum(p.numel() for p in model.parameters())
    print(
        f'[ex216] precomputed in {feat_sec}s | arch={model.cfg["arch"]} params={n_params:,} '
        f'mon_dim={VM2.MON_IN_DIM} glob_dim={VM2.GLOBAL_IN_DIM} val_act_walled={walled_rate:.4f} '
        f'train={len(tr["win"]):,} (sub={samples_per_epoch}/ep) val={len(val["win"]):,}',
        flush=True,
    )

    train_ds = TensorDataset(tr_mx, tr_gx, torch.from_numpy(tr['win']))
    eff_per_ep = min(len(train_ds), samples_per_epoch) if samples_per_epoch > 0 else len(train_ds)
    steps_per_ep = math.ceil(eff_per_ep / batch_size)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs * steps_per_ep), eta_min=lr * 0.05)
    criterion = nn.BCEWithLogitsLoss()

    out_dir.mkdir(parents=True, exist_ok=True)
    best_loss = float('inf')
    best_epoch = 0
    best_state = None
    curve = []

    for ep in range(1, epochs + 1):
        model.train()
        tot_loss, n_seen = 0.0, 0
        if eff_per_ep < len(train_ds):
            sub_idx = torch.randperm(len(train_ds))[:eff_per_ep].tolist()
            loader = DataLoader(torch.utils.data.Subset(train_ds, sub_idx), batch_size=batch_size, shuffle=True)
        else:
            loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        for mx, gx, y in loader:
            mx, gx, y = mx.to(device), gx.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            logits = model(mx, gx)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            tot_loss += float(loss.item()) * len(y)
            n_seen += len(y)
        tr_loss = tot_loss / max(1, n_seen)
        val_logits = _predict_logits_v2(model, val_mx, val_gx, device)
        val_probs = 1.0 / (1.0 + np.exp(-val_logits))
        vm = T1.metrics_for(val['win'], val_probs)
        row = dict(epoch=ep, train_loss=round(tr_loss, 5), val=vm, seconds=round(time.time() - started, 1))
        curve.append(row)
        print(
            f'[ex216] ep {ep:2d}/{epochs} tr={tr_loss:.5f} val_ll={vm["logloss"]:.5f} '
            f'auc={vm["auc"]:.5f} brier={vm["brier"]:.5f} ece={vm["ece"]:.4f}',
            flush=True,
        )
        if vm['logloss'] < best_loss:
            best_loss = vm['logloss']
            best_epoch = ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    cal_logits = _predict_logits_v2(model, cal_mx, cal_gx, device)
    temp = T1.fit_temperature(cal_logits, cal['win'])
    model.temperature.fill_(temp)

    val_logits = _predict_logits_v2(model, val_mx, val_gx, device)
    val_probs = 1.0 / (1.0 + np.exp(-val_logits / temp))
    rs_probs = 1.0 / (1.0 + np.exp(-0.0125 * val['eval_rs']))
    rs_cal_temp = T1.fit_temperature(0.0125 * cal['eval_rs'], cal['win'])
    rs_cal_probs = 1.0 / (1.0 + np.exp(-0.0125 * val['eval_rs'] / rs_cal_temp))

    # Load EX-207 baseline for exact side-by-side comparison on identical val split
    ex207_sel = json.loads((SHARED / 'runs/model-training/EX-207/selection.json').read_text())

    phases = {}
    turns = val['turn']
    for pname, mask in (
        ('early_t1_10', turns <= 10),
        ('mid_t11_25', (turns >= 11) & (turns <= 25)),
        ('late_t26_plus', turns >= 26),
    ):
        if mask.any():
            phases[pname] = dict(
                v_phi_v2=T1.metrics_for(val['win'][mask], val_probs[mask]),
                v_phi_ex207=ex207_sel['phases'][pname]['v_phi'],
                evaluate_rs_cal=T1.metrics_for(val['win'][mask], rs_cal_probs[mask]),
            )

    summary = dict(
        experiment='EX-216',
        decision='D-221',
        arch=model.cfg['arch'],
        best_epoch=best_epoch,
        temperature=round(temp, 5),
        params=n_params,
        feature_seconds=feat_sec,
        val_v_phi_v2=T1.metrics_for(val['win'], val_probs),
        val_v_phi_ex207=ex207_sel['val_v_phi'],
        val_evaluate_rs_cal=T1.metrics_for(val['win'], rs_cal_probs),
        phases=phases,
        curve=curve,
        seconds=round(time.time() - started, 1),
    )
    VM2.save_value_v2_checkpoint(model, out_dir / 'checkpoints/selected', meta=summary)
    (out_dir / 'selection.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(dict(
        arch=summary['arch'], best_epoch=best_epoch, temp=summary['temperature'],
        val_v_phi_v2=summary['val_v_phi_v2'],
        val_v_phi_ex207=summary['val_v_phi_ex207'],
        val_evaluate_rs_cal=summary['val_evaluate_rs_cal'],
    ), indent=1), flush=True)
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=DATA)
    ap.add_argument('--out', type=Path, default=RUN)
    ap.add_argument('--epochs', type=int, default=24)
    ap.add_argument('--batch-size', type=int, default=512)
    ap.add_argument('--samples-per-epoch', type=int, default=40000)
    ap.add_argument('--d-model', type=int, default=64)
    ap.add_argument('--dropout', type=float, default=0.35)
    ap.add_argument('--lr', type=float, default=4e-4)
    ap.add_argument('--weight-decay', type=float, default=1e-1)
    ap.add_argument('--device', default='cuda')
    args = ap.parse_args()
    train(
        data_dir=args.data, out_dir=args.out, epochs=args.epochs, batch_size=args.batch_size,
        samples_per_epoch=args.samples_per_epoch, d_model=args.d_model, dropout=args.dropout,
        lr=args.lr, weight_decay=args.weight_decay, device_str=args.device,
    )
