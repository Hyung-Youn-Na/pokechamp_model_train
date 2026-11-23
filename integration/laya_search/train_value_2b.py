"""EP-243 / D-219 (EX-207): Train & evaluate StateValueNet V_phi(poke_engine.State) -> [0, 1] on physical GPU 0 only.

    CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4 \
        PYTHONPATH=.:pokechamp .tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python \
        -m integration.laya_search.train_value_2b

Strictly pins physical GPU 0 (GPUs 2 and 3 are NEVER touched). Compares held-out LogLoss, Brier, ROC-AUC, and ECE
of `V_phi(s)` directly against `sigmoid(evaluate.rs)` overall and by game phase (early/mid/late).
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
from . import search_core as SC
from . import value_model as VM

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
DATA = SHARED / 'datasets/generated/laya-state-value/v1'
RUN = SHARED / 'runs/model-training/EX-207'


def _roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    order = np.argsort(y_prob)
    y = y_true[order]
    n_pos = float(y.sum())
    n_neg = float(len(y) - n_pos)
    if n_pos <= 0 or n_neg <= 0:
        return float('nan')
    ranks = np.arange(1, len(y) + 1, dtype=np.float64)
    # Average ranks for ties
    _, inv, cnt = np.unique(y_prob[order], return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        rank_sum = np.bincount(inv, weights=ranks)
        ranks = (rank_sum / cnt)[inv]
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1.0) / 2.0) / (n_pos * n_neg))


def _ece(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    n = len(y_true)
    if n == 0:
        return float('nan')
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob <= hi) if i == 0 else (y_prob > lo) & (y_prob <= hi)
        if mask.any():
            ece += (mask.sum() / n) * abs(float(y_prob[mask].mean()) - float(y_true[mask].mean()))
    return float(ece)


def metrics_for(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    p = np.clip(y_prob.astype(np.float64), 1e-7, 1.0 - 1e-7)
    y = y_true.astype(np.float64)
    bce = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))
    brier = float(np.mean((p - y) ** 2))
    acc = float(np.mean((p >= 0.5) == (y >= 0.5)))
    return dict(n=int(len(y)), logloss=round(bce, 5), brier=round(brier, 5),
                auc=round(_roc_auc(y, p), 5), acc=round(acc, 5), ece=round(_ece(y, p), 5))


def _load_split(path: Path) -> dict[str, np.ndarray]:
    z = np.load(path)
    return {k: z[k] for k in z.files}


@torch.no_grad()
def _predict_logits(model: VM.StateValueNet, split: dict[str, np.ndarray], device: torch.device, batch_size: int = 512) -> np.ndarray:
    model.eval()
    ds = TensorDataset(
        torch.from_numpy(split['mon_num']),
        torch.from_numpy(split['mon_cat']).long(),
        torch.from_numpy(split['global_num']),
    )
    out = []
    for mn, mc, gn in DataLoader(ds, batch_size=batch_size, shuffle=False):
        z = model(mn.to(device), mc.to(device), gn.to(device)).cpu().numpy()
        out.append(z)
    return np.concatenate(out, axis=0)


def fit_temperature(logits: np.ndarray, y_true: np.ndarray) -> float:
    z = torch.tensor(logits, dtype=torch.float64)
    y = torch.tensor(y_true, dtype=torch.float64)
    log_t = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.5, max_iter=50)
    bce = nn.BCEWithLogitsLoss()

    def closure():
        opt.zero_grad()
        t = torch.exp(log_t).clamp(min=0.1, max=10.0)
        loss = bce(z / t, y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(torch.exp(log_t).clamp(min=0.1, max=10.0).item())


def train(
    *,
    data_dir: Path = DATA,
    out_dir: Path = RUN,
    epochs: int = 16,
    batch_size: int = 512,
    samples_per_epoch: int = 40000,
    lr: float = 5e-4,
    weight_decay: float = 5e-2,
    seed: int = 20261207,
    device_str: str = 'cuda',
) -> dict:
    # Guard: never allow GPUs 2 or 3
    if device_str == 'cuda':
        cvd = os.environ.get('CUDA_VISIBLE_DEVICES', '')
        if not cvd or any(u not in SC.ALLOWED_GPU_UUIDS for u in cvd.split(',')):
            raise RuntimeError('Refusing to run CUDA without GPU 0/1 UUID pinning; got CUDA_VISIBLE_DEVICES=%r' % (cvd,))

    torch.manual_seed(seed)
    np.random.seed(seed)
    device = torch.device(device_str)
    vocab = F.Vocab.load(data_dir / 'vocab.json')
    tr = _load_split(data_dir / 'train.npz')
    cal = _load_split(data_dir / 'calib.npz')
    val = _load_split(data_dir / 'val.npz')

    model = VM.StateValueNet(vocab.sizes()).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f'[ex207-train] arch={model.cfg["arch"]} params={n_params:,} train={len(tr["win"]):,} (sub={samples_per_epoch}/ep) calib={len(cal["win"]):,} val={len(val["win"]):,} device={device}', flush=True)

    train_ds = TensorDataset(
        torch.from_numpy(tr['mon_num']),
        torch.from_numpy(tr['mon_cat']).long(),
        torch.from_numpy(tr['global_num']),
        torch.from_numpy(tr['win']),
    )
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
    started = time.time()

    for ep in range(1, epochs + 1):
        model.train()
        tot_loss, n_seen = 0.0, 0
        if eff_per_ep < len(train_ds):
            sub_idx = torch.randperm(len(train_ds))[:eff_per_ep].tolist()
            loader = DataLoader(torch.utils.data.Subset(train_ds, sub_idx), batch_size=batch_size, shuffle=True)
        else:
            loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        for mn, mc, gn, y in loader:
            mn, mc, gn, y = mn.to(device), mc.to(device), gn.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            logits = model(mn, mc, gn)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            tot_loss += float(loss.item()) * len(y)
            n_seen += len(y)
        tr_loss = tot_loss / max(1, n_seen)
        val_logits = _predict_logits(model, val, device)
        val_probs = 1.0 / (1.0 + np.exp(-val_logits))
        vm = metrics_for(val['win'], val_probs)
        row = dict(epoch=ep, train_loss=round(tr_loss, 5), val=vm, seconds=round(time.time() - started, 1))
        curve.append(row)
        print(f'[ex207-train] ep {ep:2d}/{epochs} tr={tr_loss:.5f} val_ll={vm["logloss"]:.5f} auc={vm["auc"]:.4f} brier={vm["brier"]:.5f} ece={vm["ece"]:.4f}', flush=True)
        if vm['logloss'] < best_loss:
            best_loss = vm['logloss']
            best_epoch = ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    cal_logits = _predict_logits(model, cal, device)
    temp = fit_temperature(cal_logits, cal['win'])
    model.temperature.fill_(temp)

    val_logits = _predict_logits(model, val, device)
    val_probs = 1.0 / (1.0 + np.exp(-val_logits / temp))
    # Baselines: raw and temperature-calibrated evaluate.rs
    rs_probs = 1.0 / (1.0 + np.exp(-0.0125 * val['eval_rs']))
    rs_cal_temp = fit_temperature(0.0125 * cal['eval_rs'], cal['win'])
    rs_cal_probs = 1.0 / (1.0 + np.exp(-0.0125 * val['eval_rs'] / rs_cal_temp))

    phases = {}
    turns = val['turn']
    for pname, mask in (
        ('early_t1_10', turns <= 10),
        ('mid_t11_25', (turns >= 11) & (turns <= 25)),
        ('late_t26_plus', turns >= 26),
    ):
        if mask.any():
            phases[pname] = dict(
                v_phi=metrics_for(val['win'][mask], val_probs[mask]),
                evaluate_rs=metrics_for(val['win'][mask], rs_probs[mask]),
                evaluate_rs_cal=metrics_for(val['win'][mask], rs_cal_probs[mask]),
            )

    summary = dict(
        arch=model.cfg['arch'],
        best_epoch=best_epoch,
        temperature=round(temp, 5),
        params=n_params,
        val_v_phi=metrics_for(val['win'], val_probs),
        val_evaluate_rs=metrics_for(val['win'], rs_probs),
        val_evaluate_rs_cal=metrics_for(val['win'], rs_cal_probs),
        evaluate_rs_cal_temp=round(rs_cal_temp, 5),
        phases=phases,
        curve=curve,
        seconds=round(time.time() - started, 1),
    )
    VM.save_value_checkpoint(model, vocab, out_dir / 'checkpoints/selected', meta=summary)
    (out_dir / 'selection.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(dict(
        arch=summary['arch'], best_epoch=best_epoch, temp=summary['temperature'],
        val_v_phi=summary['val_v_phi'], val_evaluate_rs=summary['val_evaluate_rs'],
        val_evaluate_rs_cal=summary['val_evaluate_rs_cal'],
    ), indent=1))
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=DATA)
    ap.add_argument('--out', type=Path, default=RUN)
    ap.add_argument('--epochs', type=int, default=16)
    ap.add_argument('--batch-size', type=int, default=512)
    ap.add_argument('--samples-per-epoch', type=int, default=40000)
    ap.add_argument('--lr', type=float, default=5e-4)
    ap.add_argument('--device', default='cuda')
    args = ap.parse_args()
    train(data_dir=args.data, out_dir=args.out, epochs=args.epochs, batch_size=args.batch_size,
          samples_per_epoch=args.samples_per_epoch, lr=args.lr, device_str=args.device)
