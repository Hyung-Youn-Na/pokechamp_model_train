"""EP-248 / D-224 (EX-226, Way B): Build prompt-injected `eval: mcts ... || vphi ...` dataset with Tool Dropout
and Human Anchor Preservation (`datasets/generated/laya-v14w-wayb/v1/`).

Implements DESIGN.md#laya-main-abc-roadmap Way B safeguards against shortcut collapse:
1. Scale-invariant relative-delta formatting (`render_eval_line`):
   `eval: mcts <top1> <p>% | <a2> -<d>% | ... || vphi <top1> <p>% | <a2> -<d>% | ...`
   (shows top-4 actions by each tool using compact short names like `roost`, `eq:tera`, `sw3`, generalizing cleanly
   across offline 5k/50k and live 50k + 2-ply).
2. Tool Dropout (`35%` on `hard_train` and `general_train`, plus `100%` of `150k` human `anchor_train` naturally
   without `eval:`): forces Laya to retain standalone board-reading skill when tools are absent or noisy.
3. Non-Blunder Human Anchor Preservation:
   - On turns where the human pro's actual move `a_human` is within `BLUNDER_GAP = 0.030` of the teacher's best
     move AND the turn is NOT `walled`/`absorb`, preserve a 50/50 blend of human label + clean teacher target
     (so Laya learns WHEN to trust human macro judgment over 1–2% noisy eval margins!).
   - On clear tactical blunders (`gap >= 0.030` or `walled` or `absorb`), use the purified `EX-225` soft target!
4. Dual Held-out Evaluation Sets:
   - `hard_heldout_with_eval.jsonl`: 100% tool-injected (`mcts50k || vphi3_2ply`),
   - `hard_heldout_no_eval.jsonl`: 0% tool-injected (tests Tool-Dropout standalone robustness!).
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic
from integration.laya_search import matchup_eval as ME
from integration.laya_search import way_a as WA

SRC_C1V3 = c.SHARED / 'datasets/generated/laya-v14w-c1v3/v1'
OUT = c.SHARED / 'datasets/generated/laya-v14w-wayb/v1'

TOOL_DROPOUT_FRAC = 0.35
BLUNDER_GAP = 0.030
TOP_N_TOOL = 4


def short_action_label(aid: str) -> str:
    """Compact deterministic label for `eval:` line (e.g. `move:roost:normal` -> `roost`, `switch:3` -> `sw3`)."""
    if aid.startswith('switch:'):
        return 'sw' + aid.split(':', 1)[1]
    if aid.startswith('move:'):
        parts = aid.split(':')
        if len(parts) >= 3 and parts[2] == 'tera':
            return parts[1] + ':tera'
        return parts[1] if len(parts) >= 2 else aid
    return aid


def _fmt_tool_segment(prefix: str, q_map: dict[str, float] | None, valid_ids: set[str], top_n: int = TOP_N_TOOL) -> str:
    if not q_map:
        return ''
    items = [(float(v), a) for a, v in q_map.items() if a in valid_ids and math.isfinite(v)]
    if not items:
        return ''
    items.sort(key=lambda x: (-x[0], x[1]))
    best_v, best_a = items[0]
    parts = [f'{prefix} {short_action_label(best_a)} {round(100.0 * best_v)}%']
    for v, a in items[1:top_n]:
        diff_pct = round(100.0 * (v - best_v))
        if diff_pct == 0:
            parts.append(f'{short_action_label(a)} =')
        else:
            parts.append(f'{short_action_label(a)} {diff_pct:+d}%')
    return ' | '.join(parts)


def render_eval_line(
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    valid_ids: set[str] | list[str],
    *,
    absorb_penalties: dict[str, float] | None = None,
    top_n: int = TOP_N_TOOL,
) -> str:
    """Format compact, scale-invariant `eval:` line for Way B prompt injection (usable both offline & live!)."""
    vset = set(valid_ids)
    pen = absorb_penalties or {}
    qm_adj = {a: float(v) - float(pen.get(a, 0.0)) for a, v in (q_mcts or {}).items()} if q_mcts else None
    s_m = _fmt_tool_segment('mcts', qm_adj, vset, top_n=top_n)
    s_v = _fmt_tool_segment('vphi', q_vphi, vset, top_n=top_n)
    if s_m and s_v:
        return f'eval: {s_m} || {s_v}'
    if s_m:
        return f'eval: {s_m}'
    if s_v:
        return f'eval: {s_v}'
    return ''


def _drop_tool(sample_id: str, frac: float = TOOL_DROPOUT_FRAC) -> bool:
    h = int(hashlib.sha256(('wayb-drop:' + sample_id).encode()).hexdigest()[:8], 16) / float(0xFFFFFFFF)
    return h < frac


def _blend_human_nonblunder(
    gold_probs: dict[str, float],
    human_label: str | None,
    q_ref: dict[str, float] | None,
    *,
    is_walled: bool,
    has_absorb: bool,
    gap_thresh: float = BLUNDER_GAP,
) -> tuple[dict[str, float], bool]:
    """Preserve human pro judgment (50/50 blend) on non-blunder turns to prevent blind tool-copying."""
    if is_walled or has_absorb or not human_label or human_label not in gold_probs or not q_ref:
        return gold_probs, False
    h_q = q_ref.get(human_label)
    if h_q is None or not math.isfinite(h_q):
        return gold_probs, False
    best_q = max(float(v) for v in q_ref.values() if math.isfinite(v))
    if (best_q - float(h_q)) < gap_thresh:
        blended = {k: 0.5 * float(v) for k, v in gold_probs.items()}
        blended[human_label] = blended.get(human_label, 0.0) + 0.5
        tot = sum(blended.values())
        if tot > 0.0:
            blended = {k: v / tot for k, v in blended.items()}
        return blended, True
    return gold_probs, False


def render_tool_lines(
    q_mcts: dict[str, float] | None,
    q_vphi: dict[str, float] | None,
    valid_ids: set[str] | list[str],
    *,
    absorb_penalties: dict[str, float] | None = None,
    top_n: int = TOP_N_TOOL,
) -> str:
    """Format graded `matchup:` (from MCTS 50k + V_phi v3 2-ply, replacing calc `duel: win/lose`) + `eval:` lines."""
    m_line = ME.render_matchup_line(q_mcts, q_vphi, valid_ids=valid_ids, absorb_penalties=absorb_penalties)
    e_line = render_eval_line(q_mcts, q_vphi, valid_ids, absorb_penalties=absorb_penalties, top_n=top_n)
    return '\n'.join(x for x in (m_line, e_line) if x)


def _strip_and_inject_row(row: dict, tool_lines: str) -> dict:
    """Remove calc-based `duel: ... -> win|lose` line from state and optionally append search+value `matchup:` + `eval:`."""
    out = dict(row)
    st = ME.strip_calc_duel(out['state']).rstrip('\n')
    if tool_lines:
        st = st + '\n' + tool_lines
    out['state'] = st
    out['input_sha256'] = hashlib.sha256(st.encode('utf-8')).hexdigest()
    return out


def _strip_jsonl_calc_duel(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(src) as fin, open(dst, 'w') as fout:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            if 'state' in r and 'duel:' in r['state']:
                r['state'] = ME.strip_calc_duel(r['state'])
                r['input_sha256'] = hashlib.sha256(r['state'].encode('utf-8')).hexdigest()
            fout.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
            n += 1
    return n


def build_way_b_dataset(force: bool = False) -> dict:
    """Build `datasets/generated/laya-v14w-wayb/v1/` from EX-225's purified `laya-v14w-c1v3/v1/`.

    Removes deterministic calc-based `duel: win/lose` from ALL splits (including anchor) and injects
    MCTS 50k + EX-221 V_phi v3 2-ply graded `matchup:` (favorable/even/unfavorable) + `eval:` lines
    with 35% Tool Dropout & Non-Blunder Human Anchor Preservation.
    """
    if not force and (OUT / 'manifest.json').exists():
        print('[wayb-data] already built:', OUT / 'manifest.json', flush=True)
        return json.loads((OUT / 'manifest.json').read_text())

    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    stats = Counter()

    # 0. Build calc-duel-free human anchor & foe-anchor (so EX-226 NEVER sees calc-based `duel: win/lose`)
    anchor_src = (SRC_C1V3 / 'anchor').resolve()
    anchor_dst = OUT / 'anchor_noduel'
    anchor_dst.mkdir(parents=True, exist_ok=True)
    for item in anchor_src.iterdir():
        dst_item = anchor_dst / item.name
        if item.suffix == '.jsonl':
            stats[f'anchor_{item.stem}'] = _strip_jsonl_calc_duel(item, dst_item)
        else:
            if dst_item.exists() or dst_item.is_symlink():
                dst_item.unlink()
            os.symlink(item, dst_item)
    stats['foe_anchor'] = _strip_jsonl_calc_duel((SRC_C1V3 / 'foe-anchor.jsonl').resolve(), OUT / 'foe-anchor_noduel.jsonl')

    # 1. Hard train (MCTS 50k + EX-221 V_phi v3 2-ply): 65% with matchup+eval, 35% Tool Dropout + non-blunder human blend
    with open(SRC_C1V3 / 'hard_train.jsonl') as fin, open(OUT / 'hard_train.jsonl', 'w') as fout:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            sid = r['sample_id']
            cids = list(r['questions']['action']['criteria'])
            m = (r.get('meta') or {}).get('ex225') or {}
            drop = _drop_tool(sid)
            tool_lines = '' if drop else render_tool_lines(
                m.get('q_mcts50'), m.get('q_vphi3_2ply'), cids,
                absorb_penalties=m.get('absorb_penalties'),
            )
            g = r['gold']['action']['probabilities']
            has_abs = bool(m.get('absorb_penalties')) or any('; heals opp 25%' in v or '; boosts opp' in v for v in r['questions']['action']['criteria'].values())
            g_new, preserved = _blend_human_nonblunder(
                g, m.get('label'), m.get('q_teacher'),
                is_walled=bool(m.get('walled')), has_absorb=has_abs,
            )
            r['gold'] = dict(action=dict(probabilities=g_new))
            r.setdefault('meta', {})['ex226'] = dict(
                has_eval=bool(tool_lines), human_preserved=preserved,
                label=m.get('label'), walled=bool(m.get('walled')),
                laya_argmax=m.get('laya_argmax'), calc_duel_stripped=True,
            )
            r = _strip_and_inject_row(r, tool_lines)
            fout.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
            stats['train_hard'] += 1
            stats['train_hard_with_eval' if tool_lines else 'train_hard_dropout'] += 1
            if preserved:
                stats['train_hard_human_preserved'] += 1

    # 2. General train (MCTS 5k): 65% with matchup+eval, 35% Tool Dropout + non-blunder human blend
    with open(SRC_C1V3 / 'general_train.jsonl') as fin, open(OUT / 'general_train.jsonl', 'w') as fout:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            sid = r['sample_id']
            cids = list(r['questions']['action']['criteria'])
            m = (r.get('meta') or {}).get('ex209') or {}
            is_walled = WA.is_walled_state(r['state'])
            drop = _drop_tool(sid)
            tool_lines = '' if drop else render_tool_lines(m.get('q_mcts'), None, cids)
            g = r['gold']['action']['probabilities']
            g_new, preserved = _blend_human_nonblunder(
                g, m.get('label'), m.get('q_mcts'),
                is_walled=is_walled, has_absorb=False,
            )
            r['gold'] = dict(action=dict(probabilities=g_new))
            r.setdefault('meta', {})['ex226'] = dict(
                has_eval=bool(tool_lines), human_preserved=preserved,
                label=m.get('label'), walled=is_walled,
                laya_argmax=m.get('laya_argmax'), calc_duel_stripped=True,
            )
            r = _strip_and_inject_row(r, tool_lines)
            fout.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
            stats['train_general'] += 1
            stats['train_general_with_eval' if tool_lines else 'train_general_dropout'] += 1
            if preserved:
                stats['train_general_human_preserved'] += 1

    # 3. Held-out hard: BOTH 100% with_eval (matchup+eval, no calc duel) AND 0% no_eval (no calc duel)
    with open(SRC_C1V3 / 'hard_heldout.jsonl') as fin, \
            open(OUT / 'hard_heldout_with_eval.jsonl', 'w') as fw, \
            open(OUT / 'hard_heldout_no_eval.jsonl', 'w') as fn:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            cids = list(r['questions']['action']['criteria'])
            m = (r.get('meta') or {}).get('ex225') or {}
            tool_lines = render_tool_lines(
                m.get('q_mcts50'), m.get('q_vphi3_2ply'), cids,
                absorb_penalties=m.get('absorb_penalties'),
            )
            fn.write(json.dumps(_strip_and_inject_row(r, ''), ensure_ascii=False, separators=(',', ':')) + '\n')
            fw.write(json.dumps(_strip_and_inject_row(r, tool_lines), ensure_ascii=False, separators=(',', ':')) + '\n')
            stats['heldout_hard'] += 1

    # 4. Held-out general (with matchup+eval + no_eval, both calc-duel-free)
    with open(SRC_C1V3 / 'heldout.jsonl') as fin, \
            open(OUT / 'heldout_with_eval.jsonl', 'w') as fw, \
            open(OUT / 'heldout_no_eval.jsonl', 'w') as fn:
        for line in fin:
            if not line.strip():
                continue
            r = json.loads(line)
            cids = list(r['questions']['action']['criteria'])
            m = (r.get('meta') or {}).get('ex209') or {}
            tool_lines = render_tool_lines(m.get('q_mcts'), None, cids)
            fn.write(json.dumps(_strip_and_inject_row(r, ''), ensure_ascii=False, separators=(',', ':')) + '\n')
            fw.write(json.dumps(_strip_and_inject_row(r, tool_lines), ensure_ascii=False, separators=(',', ':')) + '\n')
            stats['heldout_general'] += 1

    manifest = dict(
        experiment='EX-226',
        decision='D-224',
        way='B (Calc duel: win/lose stripped; MCTS50k + V_phi3_2ply graded matchup: favorable/even/unfavorable + eval: injected + 35% Tool Dropout + Human Anchor)',
        calc_duel_stripped=True,
        matchup_format='matchup: <very unfavorable|unfavorable|even|favorable|very favorable> (stay X% vs switch Y%, +/-Z%)',
        tool_dropout_frac=TOOL_DROPOUT_FRAC,
        blunder_gap=BLUNDER_GAP,
        stats=dict(stats),
        seconds=round(time.time() - started, 1),
        at=time.time(),
    )
    atomic(OUT / 'manifest.json', manifest)
    print('[wayb-data] COMPLETE:', json.dumps(manifest, indent=1), flush=True)
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('build',))
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    build_way_b_dataset(force=args.force)
