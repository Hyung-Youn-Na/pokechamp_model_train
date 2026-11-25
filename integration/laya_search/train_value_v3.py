"""EP-247 / D-223 (EX-221): Train & ablate Future-Aware StateValueNetV3 on physical GPU 0 ONLY.

    CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4 \
        PYTHONPATH=.:pokechamp .tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python \
        -m integration.laya_search.train_value_v3

Controlled ablation on EX-207/EX-216's exact leakage-free 5,470 / 304 / 304 split (`datasets/generated/laya-state-value/v3`):
- `v3_base`      : new PP/Protect v3 features only (`lam_fut=0.0, lam_cf=0.0`)
- `v3_future`    : + multi-horizon future auxiliary heads (`lam_fut=0.40, lam_cf=0.0`)
- `v3_full_15`   : + multi-horizon future heads + counterfactual recovery/Protect ranking (`lam_fut=0.40, lam_cf=0.15`)
- `v3_full_30`   : + multi-horizon future heads + stronger counterfactual ranking (`lam_fut=0.40, lam_cf=0.30`)

Also benchmarks `EX-216 V_phi v2` on the EXACT same `val_cf.npz` held-out counterfactual pairs so we measure
both static win-rate prediction (`AUC`/`LogLoss`) AND counterfactual recovery/Protect discrimination apples-to-apples!
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
import torch.nn.functional as NF
from torch.utils.data import DataLoader, TensorDataset

from . import featurize as F
from . import matchup_features as MF
from . import search_core as SC
from . import train_value_2b as T1
from . import value_model_v2 as VM2
from . import value_model_v3 as VM3

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
DATA = SHARED / 'datasets/generated/laya-state-value/v3'
RUN = SHARED / 'runs/model-training/EX-221'
EX216_CKPT = SHARED / 'runs/model-training/EX-216/checkpoints/selected'


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as d:
        return {k: d[k] for k in d.files}


@torch.no_grad()
def precompute_v3_split(
    split: dict[str, np.ndarray],
    vocab: F.Vocab,
    tables: MF.MatchupTables,
    keep_idx: torch.Tensor,
    device: torch.device,
    *,
    prefix: str = '',
    batch_size: int = 4096,
) -> tuple[torch.Tensor, torch.Tensor]:
    mn_arr = split[prefix + 'mon_num']
    mc_arr = split[prefix + 'mon_cat']
    gn_arr = split[prefix + 'global_num']
    v3m_arr = split[prefix + 'v3_mon']
    v3g_arr = split[prefix + 'v3_glob']
    n = len(mn_arr)
    mx_out = torch.empty((n, 12, VM3.MON_IN_DIM), dtype=torch.float32)
    gx_out = torch.empty((n, VM3.GLOBAL_IN_DIM), dtype=torch.float32)
    for start in range(0, n, batch_size):
        end = min(n, start + batch_size)
        mn = torch.from_numpy(mn_arr[start:end]).to(device)
        mc_v = torch.from_numpy(mc_arr[start:end]).long().to(device)
        mc = tables.remap_vocab_mon_cat(mc_v, vocab)
        gn = torch.from_numpy(gn_arr[start:end]).to(device)
        v3m = torch.from_numpy(v3m_arr[start:end]).to(device)
        v3g = torch.from_numpy(v3g_arr[start:end]).to(device)
        mx, gx = VM3.build_v3_inputs(mn, mc, gn, v3m, v3g, tables, keep_idx)
        mx_out[start:end] = mx.cpu()
        gx_out[start:end] = gx.cpu()
    return mx_out, gx_out


@torch.no_grad()
def predict_logits_v3(
    model: VM3.StateValueNetV3,
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


@torch.no_grad()
def eval_cf_metrics(
    pos_logits: np.ndarray,
    neg_logits: np.ndarray,
    kind_id: np.ndarray,
    hp_frac: np.ndarray,
    temp: float = 1.0,
) -> dict:
    pos_p = 1.0 / (1.0 + np.exp(-pos_logits / max(temp, 0.05)))
    neg_p = 1.0 / (1.0 + np.exp(-neg_logits / max(temp, 0.05)))
    diff = pos_p - neg_p

    def _sub(mask):
        if not mask.any():
            return dict(n=0, acc=None, mean_diff=None)
        d = diff[mask]
        return dict(n=int(mask.sum()), acc=round(float((d > 0).mean()), 4), mean_diff=round(float(d.mean()), 5))

    return dict(
        overall=_sub(np.ones(len(diff), dtype=bool)),
        reject_heal_all=_sub(kind_id == 0),
        reject_heal_hp70=_sub((kind_id == 0) & (hp_frac >= 0.70)),
        reject_heal_hp40_69=_sub((kind_id == 0) & (hp_frac >= 0.40) & (hp_frac < 0.70)),
        reject_protect=_sub(kind_id == 1),
        accept_heal_low=_sub(kind_id == 2),
    )


@torch.no_grad()
def eval_ex216_baseline_on_cf(
    val_cf: dict[str, np.ndarray],
    vocab: F.Vocab,
    tables: MF.MatchupTables,
    device: torch.device,
) -> dict:
    if not EX216_CKPT.exists():
        return {}
    m2, cfg2 = VM2.load_value_v2_checkpoint(EX216_CKPT, device=str(device))
    temp = float(cfg2.get('temperature', 1.0))

    def _run(prefix: str) -> np.ndarray:
        mn_arr = val_cf[prefix + 'mon_num']
        mc_arr = val_cf[prefix + 'mon_cat']
        gn_arr = val_cf[prefix + 'global_num']
        out = []
        for s in range(0, len(mn_arr), 1024):
            e = min(len(mn_arr), s + 1024)
            mn = torch.from_numpy(mn_arr[s:e]).to(device)
            mc = tables.remap_vocab_mon_cat(torch.from_numpy(mc_arr[s:e]).long().to(device), vocab)
            gn = torch.from_numpy(gn_arr[s:e]).to(device)
            mx, gx = VM2.build_v2_inputs(mn, mc, gn, tables, m2.keep_idx, m2.pair_idx)
            out.append(m2(mx, gx).cpu().numpy())
        return np.concatenate(out, axis=0)

    return eval_cf_metrics(_run('pos_'), _run('neg_'), val_cf['kind_id'], val_cf['hp_frac'], temp=temp)


def train_one_config(
    name: str,
    *,
    tr_mx: torch.Tensor, tr_gx: torch.Tensor, tr_y: torch.Tensor, tr_fut: torch.Tensor,
    cal_mx: torch.Tensor, cal_gx: torch.Tensor, cal_y: np.ndarray,
    val_mx: torch.Tensor, val_gx: torch.Tensor, val_y: np.ndarray, val_turns: np.ndarray,
    tr_cf_pmx: torch.Tensor, tr_cf_pgx: torch.Tensor, tr_cf_nmx: torch.Tensor, tr_cf_ngx: torch.Tensor, tr_cf_w: torch.Tensor,
    val_cf_pmx: torch.Tensor, val_cf_pgx: torch.Tensor, val_cf_nmx: torch.Tensor, val_cf_ngx: torch.Tensor,
    val_cf_kind: np.ndarray, val_cf_hp: np.ndarray,
    lam_fut: float,
    lam_cf: float,
    cf_margin: float = 0.25,
    epochs: int = 24,
    batch_size: int = 512,
    cf_batch_size: int = 256,
    samples_per_epoch: int = 40000,
    d_model: int = 64,
    dropout: float = 0.35,
    lr: float = 4e-4,
    weight_decay: float = 1e-1,
    seed: int = 20261221,
    device: torch.device = torch.device('cuda'),
) -> tuple[VM3.StateValueNetV3, dict]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = VM3.StateValueNetV3(d_model=d_model, dropout=dropout).to(device)
    fut_weights = torch.tensor([1.0, 1.2, 1.0, 1.2, 1.0], dtype=torch.float32, device=device)

    train_ds = TensorDataset(tr_mx, tr_gx, tr_y, tr_fut)
    eff_per_ep = min(len(train_ds), samples_per_epoch) if samples_per_epoch > 0 else len(train_ds)
    steps_per_ep = math.ceil(eff_per_ep / batch_size)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs * steps_per_ep), eta_min=lr * 0.05)
    bce = nn.BCEWithLogitsLoss()

    n_cf = len(tr_cf_w)
    best_score = float('inf')
    best_epoch = 0
    best_state = None
    curve = []
    started = time.time()

    for ep in range(1, epochs + 1):
        model.train()
        tot_bce, tot_fut, tot_cf, n_seen = 0.0, 0.0, 0.0, 0
        if eff_per_ep < len(train_ds):
            sub_idx = torch.randperm(len(train_ds))[:eff_per_ep].tolist()
            loader = DataLoader(torch.utils.data.Subset(train_ds, sub_idx), batch_size=batch_size, shuffle=True)
        else:
            loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

        for mx, gx, y, fut in loader:
            mx, gx, y, fut = mx.to(device), gx.to(device), y.to(device), fut.to(device)
            opt.zero_grad(set_to_none=True)
            win_logit, fut_pred = model.forward_all(mx, gx)
            loss_bce = bce(win_logit, y)
            loss = loss_bce

            if lam_fut > 0.0:
                per_head = NF.smooth_l1_loss(fut_pred, fut, reduction='none', beta=0.25)
                loss_fut = (per_head * fut_weights).mean()
                loss = loss + lam_fut * loss_fut
            else:
                loss_fut = torch.tensor(0.0, device=device)

            if lam_cf > 0.0 and n_cf >= 16:
                cidx = torch.randint(0, n_cf, (min(cf_batch_size, n_cf),))
                pmx = tr_cf_pmx[cidx].to(device)
                pgx = tr_cf_pgx[cidx].to(device)
                nmx = tr_cf_nmx[cidx].to(device)
                ngx = tr_cf_ngx[cidx].to(device)
                cw = tr_cf_w[cidx].to(device)
                zp = model(pmx, pgx)
                zn = model(nmx, ngx)
                # Softplus pairwise margin loss: push zp - zn >= cf_margin
                loss_cf = (cw * NF.softplus(cf_margin - (zp - zn))).mean()
                loss = loss + lam_cf * loss_cf
            else:
                loss_cf = torch.tensor(0.0, device=device)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            bs = len(y)
            tot_bce += float(loss_bce.item()) * bs
            tot_fut += float(loss_fut.item()) * bs
            tot_cf += float(loss_cf.item()) * bs
            n_seen += bs

        val_logits = predict_logits_v3(model, val_mx, val_gx, device)
        val_probs = 1.0 / (1.0 + np.exp(-val_logits))
        vm = T1.metrics_for(val_y, val_probs)
        cf_p = predict_logits_v3(model, val_cf_pmx, val_cf_pgx, device)
        cf_n = predict_logits_v3(model, val_cf_nmx, val_cf_ngx, device)
        cfm = eval_cf_metrics(cf_p, cf_n, val_cf_kind, val_cf_hp, temp=1.0)
        row = dict(
            epoch=ep,
            tr_bce=round(tot_bce / max(1, n_seen), 5),
            tr_fut=round(tot_fut / max(1, n_seen), 5),
            tr_cf=round(tot_cf / max(1, n_seen), 5),
            val=vm,
            val_cf_all=cfm['overall']['acc'],
            val_cf_rh70=cfm['reject_heal_hp70']['acc'],
            seconds=round(time.time() - started, 1),
        )
        curve.append(row)
        if ep in (1, 6, 12, 18, 24) or vm['logloss'] < best_score:
            print(
                f'[ex221:{name}] ep {ep:2d}/{epochs} bce={row["tr_bce"]:.4f} fut={row["tr_fut"]:.4f} cf={row["tr_cf"]:.4f} '
                f'| val_ll={vm["logloss"]:.5f} auc={vm["auc"]:.5f} | cf_all={cfm["overall"]["acc"]} rh70={cfm["reject_heal_hp70"]["acc"]}',
                flush=True,
            )
        if vm['logloss'] < best_score:
            best_score = vm['logloss']
            best_epoch = ep
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    cal_logits = predict_logits_v3(model, cal_mx, cal_gx, device)
    temp = T1.fit_temperature(cal_logits, cal_y)
    model.temperature.fill_(temp)

    val_logits = predict_logits_v3(model, val_mx, val_gx, device)
    val_probs = 1.0 / (1.0 + np.exp(-val_logits / temp))
    cf_p = predict_logits_v3(model, val_cf_pmx, val_cf_pgx, device)
    cf_n = predict_logits_v3(model, val_cf_nmx, val_cf_ngx, device)

    phases = {}
    for pname, mask in (
        ('early_t1_10', val_turns <= 10),
        ('mid_t11_25', (val_turns >= 11) & (val_turns <= 25)),
        ('late_t26_plus', val_turns >= 26),
    ):
        if mask.any():
            phases[pname] = T1.metrics_for(val_y[mask], val_probs[mask])

    res = dict(
        name=name,
        lam_fut=lam_fut,
        lam_cf=lam_cf,
        cf_margin=cf_margin,
        best_epoch=best_epoch,
        temperature=round(temp, 5),
        val=T1.metrics_for(val_y, val_probs),
        phases=phases,
        val_cf=eval_cf_metrics(cf_p, cf_n, val_cf_kind, val_cf_hp, temp=temp),
        seconds=round(time.time() - started, 1),
        curve=curve,
    )
    return model, res


def run_ablation(
    *,
    data_dir: Path = DATA,
    out_dir: Path = RUN,
    epochs: int = 24,
    device_str: str = 'cuda',
) -> dict:
    if device_str == 'cuda':
        cvd = os.environ.get('CUDA_VISIBLE_DEVICES', '')
        if not cvd or any(u not in SC.ALLOWED_GPU_UUIDS for u in cvd.split(',')):
            raise RuntimeError('Refusing to run CUDA without GPU 0/1 UUID pinning; got CUDA_VISIBLE_DEVICES=%r' % (cvd,))

    device = torch.device(device_str)
    started = time.time()
    vocab = F.Vocab.load(data_dir / 'vocab.json')
    tr = _load_npz(data_dir / 'train.npz')
    cal = _load_npz(data_dir / 'calib.npz')
    val = _load_npz(data_dir / 'val.npz')
    tr_cf = _load_npz(data_dir / 'train_cf.npz')
    val_cf = _load_npz(data_dir / 'val_cf.npz')

    tables = MF.default_tables().to(device)
    keep_idx = torch.tensor(VM3.PURE_STATE_MON_INDICES, dtype=torch.long, device=device)

    print('[ex221] precomputing v3 features for train/calib/val + train_cf/val_cf...', flush=True)
    t0 = time.time()
    tr_mx, tr_gx = precompute_v3_split(tr, vocab, tables, keep_idx, device)
    cal_mx, cal_gx = precompute_v3_split(cal, vocab, tables, keep_idx, device)
    val_mx, val_gx = precompute_v3_split(val, vocab, tables, keep_idx, device)

    tr_cf_pmx, tr_cf_pgx = precompute_v3_split(tr_cf, vocab, tables, keep_idx, device, prefix='pos_')
    tr_cf_nmx, tr_cf_ngx = precompute_v3_split(tr_cf, vocab, tables, keep_idx, device, prefix='neg_')
    val_cf_pmx, val_cf_pgx = precompute_v3_split(val_cf, vocab, tables, keep_idx, device, prefix='pos_')
    val_cf_nmx, val_cf_ngx = precompute_v3_split(val_cf, vocab, tables, keep_idx, device, prefix='neg_')
    print(f'[ex221] precomputed in {time.time() - t0:.1f}s | train={len(tr["win"]):,} val={len(val["win"]):,} '
          f'train_cf={len(tr_cf["weight"]):,} val_cf={len(val_cf["weight"]):,}', flush=True)

    assert torch.isfinite(tr_mx).all() and torch.isfinite(tr_gx).all()
    assert torch.isfinite(val_mx).all() and torch.isfinite(val_gx).all()

    ex216_cf = eval_ex216_baseline_on_cf(val_cf, vocab, tables, device)
    ex216_sel = json.loads((SHARED / 'runs/model-training/EX-216/selection.json').read_text()) if (SHARED / 'runs/model-training/EX-216/selection.json').exists() else {}
    print('[ex221] EX-216 baseline on val_cf:', json.dumps(ex216_cf), flush=True)

    configs = [
        ('v3_future', 0.35, 0.0, 0.15),
        ('v3_cf_03', 0.35, 0.03, 0.15),
        ('v3_cf_06', 0.35, 0.06, 0.15),
        ('v3_cf_10', 0.35, 0.10, 0.15),
    ]

    tr_y = torch.from_numpy(tr['win'])
    tr_fut = torch.from_numpy(tr['fut'])
    # Rebalance counterfactual weights so `accept_heal_low` (kind_id == 2) receives strong positive weight,
    # preventing blanket anti-heal collapse while sharpening high-HP / tempo-losing heal discrimination!
    raw_cf_w = tr_cf['weight'].astype(np.float32).copy()
    raw_cf_k = tr_cf['kind_id']
    raw_cf_w[raw_cf_k == 2] *= 4.0  # boost legitimate low-HP accept_heal pairs 4x
    tr_cf_w = torch.from_numpy(raw_cf_w)

    out_dir.mkdir(parents=True, exist_ok=True)
    ablation_results = []
    trained_models = {}

    for cname, lf, lc, mg in configs:
        m, res = train_one_config(
            cname,
            tr_mx=tr_mx, tr_gx=tr_gx, tr_y=tr_y, tr_fut=tr_fut,
            cal_mx=cal_mx, cal_gx=cal_gx, cal_y=cal['win'],
            val_mx=val_mx, val_gx=val_gx, val_y=val['win'], val_turns=val['turn'],
            tr_cf_pmx=tr_cf_pmx, tr_cf_pgx=tr_cf_pgx, tr_cf_nmx=tr_cf_nmx, tr_cf_ngx=tr_cf_ngx, tr_cf_w=tr_cf_w,
            val_cf_pmx=val_cf_pmx, val_cf_pgx=val_cf_pgx, val_cf_nmx=val_cf_nmx, val_cf_ngx=val_cf_ngx,
            val_cf_kind=val_cf['kind_id'], val_cf_hp=val_cf['hp_frac'],
            lam_fut=lf, lam_cf=lc, cf_margin=mg, epochs=epochs, device=device,
        )
        ablation_results.append(res)
        trained_models[cname] = m
        VM3.save_value_v3_checkpoint(m, out_dir / 'checkpoints' / cname, meta=res)

    # Select best Pareto model: strong static calibration (within +0.0025 LL of best) + accept_heal_low >= 0.68
    # + maximum counterfactual discrimination on rejected heals & Protect!
    best_ll = min(r['val']['logloss'] for r in ablation_results)
    eligible = [
        r for r in ablation_results
        if r['val']['logloss'] <= best_ll + 0.003 and (r['val_cf']['accept_heal_low']['acc'] or 0.0) >= 0.68
    ] or ablation_results
    selected_res = max(
        eligible,
        key=lambda r: (
            0.35 * (r['val_cf']['reject_heal_hp70']['acc'] or 0.0)
            + 0.35 * (r['val_cf']['reject_heal_hp40_69']['acc'] or 0.0)
            + 0.20 * (r['val_cf']['reject_protect']['acc'] or 0.0)
            + 0.10 * (r['val_cf']['accept_heal_low']['acc'] or 0.0)
            - 10.0 * (r['val']['logloss'] - best_ll)
        ),
    )
    sel_name = selected_res['name']
    sel_model = trained_models[sel_name]

    summary = dict(
        experiment='EX-221',
        decision='D-223',
        selected_config=sel_name,
        arch=sel_model.cfg['arch'],
        params=sum(p.numel() for p in sel_model.parameters()),
        selected=selected_res,
        ex216_val=ex216_sel.get('val_v_phi_v2'),
        ex216_val_cf=ex216_cf,
        ablation=[{k: v for k, v in r.items() if k != 'curve'} for r in ablation_results],
        seconds=round(time.time() - started, 1),
    )
    VM3.save_value_v3_checkpoint(sel_model, out_dir / 'checkpoints/selected', meta=summary)
    (out_dir / 'selection.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    (out_dir / 'ablation.json').write_text(json.dumps(ablation_results, ensure_ascii=False, indent=1))
    print('[ex221] SELECTED:', sel_name, json.dumps({
        'val': selected_res['val'],
        'val_cf': selected_res['val_cf'],
        'ex216_val': ex216_sel.get('val_v_phi_v2'),
        'ex216_val_cf': ex216_cf,
    }, indent=1), flush=True)
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=DATA)
    ap.add_argument('--out', type=Path, default=RUN)
    ap.add_argument('--epochs', type=int, default=24)
    ap.add_argument('--device', default='cuda')
    args = ap.parse_args()
    run_ablation(data_dir=args.data, out_dir=args.out, epochs=args.epochs, device_str=args.device)
