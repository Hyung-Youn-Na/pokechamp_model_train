"""C-047 researcher viewer for EX-080: one offline page per normal game (model input text re-rendered from the stored
public roots, candidates, priors rho, search policy pi, payoff matrix, value, choice) plus an index."""
from __future__ import annotations

import html
import json
from pathlib import Path

from ..storage import atomic_bytes, encoded, read, sha
from .audit import NORMAL, games, load

_REPLAY_CSP = ("default-src 'none'; script-src https://play.pokemonshowdown.com; "
               "style-src 'unsafe-inline' https://play.pokemonshowdown.com; img-src data: https://play.pokemonshowdown.com; "
               "font-src https://play.pokemonshowdown.com; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

SCRIPT = r"""const d=JSON.parse(document.getElementById('data').textContent);let n=0;const q=id=>document.getElementById(id);
const fmt=a=>a.map(x=>x.toFixed(3)).join(' ');
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const hl=s=>esc(s).replace(/("(?:\\.|[^"\\])*")(\s*:)?|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|\b(true|false|null)\b/g,
 (m,str,colon,num,lit)=>str?`<span class="${colon?'k':'s'}">${str}</span>${colon||''}`:num!==undefined?`<span class="n">${num}</span>`:`<span class="l">${lit}</span>`);
let current={input:'',response:''};
function render(){const r=d.records[n];if(!r){q('position').textContent='결정 없음';return}
q('position').textContent=`${n+1}/${d.records.length} · 턴 ${r.turn} · ${r.phase} · 선택 ${JSON.stringify(r.choices)}`;
const input=r.dynamic+'\n\n[p1 후보]\n'+r.texts.p1.join('\n')+'\n\n[p2 후보]\n'+r.texts.p2.join('\n');
const auto={};for(const s of ['p1','p2']){if(r.texts[s].length===1)auto[s]='후보 1개: 모델 미호출, 자동 선택';else if(!r.texts[s].length)auto[s]='행동 없음'}
const out={modes:r.modes,choices:r.choices};if(Object.keys(auto).length)out.auto=auto;
for(const [t,s] of Object.entries(r.search)){out['search:'+t]={rho:s.rho.map(fmt),pi:s.pi.map(fmt),q:s.q,root_value:s.root_value,
 matrix:s.matrix.map(fmt),terminal:s.terminal.map(row=>row.map(x=>x?'T':'.').join('')),solver:s.info}}
for(const [t,p] of Object.entries(r.policy)){out['policy:'+t]={rho:p.rho.map(fmt),root_value:p.root_value}}
if(r.opponent_command)out.opponent_command=r.opponent_command;
const response=JSON.stringify(out,null,2);current={input,response};q('input').textContent=input;q('response').innerHTML=hl(response);
q('previous').disabled=n===0;q('next').disabled=n+1>=d.records.length}
function copy(k){if(navigator.clipboard)navigator.clipboard.writeText(current[k])}
function save(k){const json=k==='response';const b=new Blob([current[k]],{type:json?'application/json':'text/plain'});const a=document.createElement('a');
a.href=URL.createObjectURL(b);a.download=`${d.slot}-${n+1}-${k}.${json?'json':'txt'}`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
q('previous').onclick=()=>{if(n>0)n--;render()};q('next').onclick=()=>{if(n+1<d.records.length)n++;render()};
for(const k of ['input','response']){q('copy-'+k).onclick=()=>copy(k);q('save-'+k).onclick=()=>save(k)}
document.addEventListener('keydown',e=>{const t=e.target;if(['INPUT','TEXTAREA','SELECT'].includes(t.tagName)||t.isContentEditable)return;
if(e.key==='ArrowRight')q('next').click();if(e.key==='ArrowLeft')q('previous').click()});render();"""


def _json(value):
    return encoded(value).decode().replace("<", "\\u003c").replace("&", "\\u0026")


def replay_page(slot, protocol):
    data = html.escape(protocol, quote=False)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{html.escape(_REPLAY_CSP)}"><title>{html.escape(slot)}</title>
<style>body{{font:15px system-ui;margin:0;background:#eef2f7}}main{{max-width:1180px;margin:auto;padding:1rem}}
.battle-log-data{{display:none}}pre{{white-space:pre-wrap;max-height:60vh;overflow:auto;background:#fff;padding:1rem}}</style></head>
<body><main><p>애니메이션은 공식 Showdown 자산(인터넷)이 필요하다. 아래 protocol은 오프라인으로 읽을 수 있다.</p>
<div class="wrapper replay-wrapper"><input type="hidden" name="replayid" value="{html.escape(slot)}"><div class="battle"></div>
<div class="battle-log"></div><div class="replay-controls"></div><div class="replay-controls-2"></div>
<script type="text/plain" class="battle-log-data">{data}</script></div>
<details open><summary>Static protocol</summary><pre>{data}</pre></details>
<script defer src="https://play.pokemonshowdown.com/js/replay-embed.js"></script></main></body></html>"""


def game_page(summary, records, static_text, protocol):
    job, title = summary["job"], html.escape(summary["job"]["slot_id"])
    players = html.escape(json.dumps(job["players"], ensure_ascii=False))
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>{title}</title>
<style>body{{font:15px system-ui;margin:24px;max-width:1400px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f7;padding:16px}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}button{{padding:8px;margin:4px}}iframe{{width:100%;height:520px}}
.k{{color:#0b5394}}.s{{color:#38761d}}.n{{color:#b45f06}}.l{{color:#741b47}}</style>
<a href="../index.html">경기 목록</a><h1>{title}</h1>
<p>{html.escape(job['stage'])} · {html.escape(job['assignment'])} · {html.escape(summary['status'])} · winner={html.escape(str(summary['winner']))} · {players}</p>
<p>EX-080 공개 상태 진단. 정책 확률(ρ, π)은 승률이 아니며, 가치(value, q)는 p1 관점 상태가치다. 후보가 하나면 모델을 호출하지 않는다.</p>
<details><summary>정적 접두(양 팀 원 세트)</summary><pre>{html.escape(static_text)}</pre></details>
<button id="previous">이전</button><button id="next">다음</button><p id="position"></p>
<div class="columns"><section><h2>모델 입력(동적 상태·후보)</h2><button id="copy-input">복사</button><button id="save-input">다운로드</button>
<pre id="input"></pre></section>
<section><h2>사전 정책·탐색·실제 선택</h2><button id="copy-response">복사</button><button id="save-response">다운로드</button>
<pre id="response"></pre></section></div>
<details><summary>선택적 Showdown 애니메이션 — 외부 자산 필요</summary><iframe loading="lazy" src="replay.html"></iframe></details>
<details open><summary>오프라인 공개 protocol</summary><pre id="protocol">{html.escape(protocol)}</pre></details>
<script id="data" type="application/json">{_json(dict(records=records, slot=job["slot_id"]))}</script><script>{SCRIPT}</script></html>"""


def export(run, target):
    from ..sim import Simulator
    run, target = Path(run), Path(target)
    identity = read(run / "manifest.json")["identity"]
    if (target / "provenance.json").exists() and read(target / "provenance.json")["identity"] != identity:
        raise FileExistsError(f"{target} holds another identity's export; it is never overwritten")
    statics = read(run / "static.json")
    rows, copies, total = [], [], 0
    with Simulator("search") as sim:
        for group, slot in games(run):
            summary, records, roots, evidence = load(run, group, slot)
            total += 1
            if summary["status"] not in ("completed", "censored"):
                continue
            view = []
            for record, root in zip(records, roots):
                frame = sim.describe(root)
                view.append(dict(record, dynamic=frame["dynamic"],
                                 texts={s: [c["text"] for c in frame["candidates"][s]] for s in ("p1", "p2")}))
            protocol = (evidence or {}).get("public_log") or ""
            if isinstance(protocol, list):
                protocol = "\n".join(protocol)
            folder = target / slot
            atomic_bytes(folder / "index.html", game_page(summary, view, statics[summary["job"]["assignment"]]["text"],
                                                          protocol).encode())
            atomic_bytes(folder / "replay.html", replay_page(slot, protocol).encode())
            rows.append(dict(slot=slot, group=group, stage=summary["job"]["stage"], status=summary["status"],
                             winner=summary["winner"], turns=summary["turns"], decisions=len(records)))
            copies.append(dict(slot=slot, group=group, source=f"games/{group}/{slot}/result.json",
                               source_sha256=sha(run / "games" / group / slot / "result.json"),
                               page_sha256=sha(folder / "index.html"), replay_sha256=sha(folder / "replay.html")))
    body = "".join(f"<tr data-stage='{html.escape(r['stage'])}'><td>{html.escape(r['group'])}</td><td><a href='{html.escape(r['slot'])}/index.html'>"
                   f"{html.escape(r['slot'])}</a></td><td>{html.escape(r['status'])}</td><td>{html.escape(str(r['winner']))}</td>"
                   f"<td>{r['turns']}</td><td>{r['decisions']}</td></tr>" for r in rows)
    stages = sorted({r["stage"] for r in rows})
    options = "".join(f"<option>{html.escape(s)}</option>" for s in stages)
    index = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>EX-080 경기 뷰어</title>
<style>body{{font:15px system-ui;margin:24px}}td,th{{padding:4px 8px;border-bottom:1px solid #ddd}}</style>
<h1>EX-080 Qwen3.5-0.8B 행렬 탐색 자기대국 — 정상 경기 {len(rows)}개</h1>
<p>정상 종료(승패무)와 300턴 검열 경기만 포함한다. 단계 필터: <select id="stage"><option value="">전체</option>{options}</select></p>
<p>출처: EX-080 · identity <code>{html.escape(identity)}</code> · 원본 <code>{html.escape(str(run))}</code> · 정상 {len(rows)}/전체 {total}경기.
경기별 원본(result.json)·복사본(페이지) sha256은 <a href="provenance.json">provenance.json</a>에 있다. 원본은 봉인 대상이며 이 폴더는 열람용 복사본이다.</p>
<table><thead><tr><th>묶음</th><th>경기</th><th>상태</th><th>승자</th><th>턴</th><th>결정</th></tr></thead><tbody>{body}</tbody></table>
<script>document.getElementById('stage').onchange=e=>{{for(const r of document.querySelectorAll('tbody tr'))
r.style.display=!e.target.value||r.dataset.stage===e.target.value?'':'none'}}</script></html>"""
    atomic_bytes(target / "index.html", index.encode())
    provenance = dict(experiment="EX-080", identity=identity, source=str(run), normal=len(rows), total=total, games=copies)
    atomic_bytes(target / "provenance.json", encoded(provenance))
    return dict(target=str(target), games=len(rows), total=total, stages=stages, provenance_sha256=sha(target / "provenance.json"))
