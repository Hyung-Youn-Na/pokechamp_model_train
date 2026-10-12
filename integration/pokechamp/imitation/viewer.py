"""C-047: 기록된 행동 선택 확률과 실제 전송을 보여 주는 독립 오프라인 사본."""

from __future__ import annotations

import html
import json
import shutil
from collections import defaultdict
from pathlib import Path

from ..observability.render import _replay_html
from . import reporting
from .battle import seal
from .storage import atomic, read, sha

STYLE = """body{font:16px system-ui,sans-serif;color:#172033;background:#f4f6fa;margin:0}
main{max-width:1300px;margin:auto;padding:24px}a{color:#194da4}h1{font-size:1.7rem}
section,details{background:white;padding:18px;border-radius:10px;margin:14px 0}
.bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center}button,select{font:inherit;padding:7px}
table{border-collapse:collapse;width:100%}
th,td{padding:9px;text-align:left;border-bottom:1px solid #dce2eb}
.selected{background:#e7f2ff}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;
max-height:550px;overflow:auto;background:#f8fafc;padding:14px}
iframe{width:100%;height:570px;border:0}
.muted{color:#526278}.error{color:#a52b28}
.panes{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){main{padding:12px}.panes{display:block}td,th{padding:6px}}
"""


SCRIPT = r"""const data=JSON.parse(document.getElementById('data').textContent);
const rows=data.decisions;let position=0;
const q=id=>document.getElementById(id);
function pretty(value){return value===null||value===undefined?'없음':JSON.stringify(value,null,2)}
function render(){
 const d=rows[position];q('previous').disabled=position<=0;
 q('next').disabled=position>=rows.length-1;
 if(!d){q('status').textContent='저장된 모델 결정이 없습니다.';return;}
 q('decision').value=String(position);
 q('status').textContent='턴 '+d.turn+' · '+d.kind+' · '+(position+1)+'/'+rows.length;
 const automatic=d.selection&&d.selection.automatic;
 q('mode').textContent=automatic?'모델 미호출 · 유일한 합법 행동':
  d.response?'모델 응답 수신':d.request?'요청 전송 · 정상 응답 미수신':'모델 호출 전 종료';
 q('sent').textContent=d.wire?'실제 전송: '+d.wire.command:'실제 전송 기록 없음';
 const table=q('candidates');table.replaceChildren();
 for(const [id,label] of Object.entries(d.criteria)){
  const tr=document.createElement('tr');
  if(d.selection&&d.selection.choice===id)tr.className='selected';
  const p=d.response&&d.response.probabilities?d.response.probabilities[id]:null;
  const probability=p===null||p===undefined?'미호출/미수신':(100*p).toFixed(3)+'%';
  const selected=d.selection&&d.selection.choice===id?'선택':'';
  for(const value of [id,label,probability,selected]){
   const td=document.createElement('td');td.textContent=value;tr.append(td);
  }table.append(tr);
 }
 q('input').textContent=pretty(d.input);q('request').textContent=pretty(d.request);
 q('response').textContent=d.response?pretty(d.response):(d.raw_response||'응답 기록 없음');
 q('technical').textContent=pretty({selection:d.selection,wire:d.wire,
  revalidation:d.revalidation,...d.technical});
}
rows.forEach((d,i)=>{const o=document.createElement('option');o.value=String(i);
 o.textContent=(i+1)+' · 턴 '+d.turn+' · '+d.kind;q('decision').append(o)});
q('decision').onchange=()=>{position=Number(q('decision').value);render()};
q('previous').onclick=()=>{if(position>0){position--;render()}};
q('next').onclick=()=>{if(position<rows.length-1){position++;render()}};
document.addEventListener('keydown',e=>{
 if(/INPUT|SELECT|TEXTAREA|BUTTON/.test(document.activeElement.tagName))return;
 if(e.key==='ArrowLeft'){q('previous').click();e.preventDefault()}
 if(e.key==='ArrowRight'){q('next').click();e.preventDefault()}});
for(const b of document.querySelectorAll('[data-copy]'))b.onclick=async()=>{
 const text=q(b.dataset.copy).textContent;try{await navigator.clipboard.writeText(text)}catch(_){
 const t=document.createElement('textarea');t.value=text;document.body.append(t);
 t.select();document.execCommand('copy');t.remove()}
 b.textContent='복사됨';setTimeout(()=>b.textContent='복사',1200);
};
q('download').onclick=()=>{
 const blob=new Blob([JSON.stringify(rows[position]||{},null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download='decision-'+(position+1)+'.json';a.click();
 setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
render();"""


def _encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def verify_source(directory):
    directory = Path(directory).resolve()
    recorded = {}
    for line in (directory / "checksums.sha256").read_text().splitlines():
        value, name = line.split("  ", 1)
        path = (directory / name).resolve()
        if name in recorded or not path.is_relative_to(directory) or sha(path) != value:
            raise ValueError("invalid source seal entry: " + name)
        recorded[name] = value
    if not {"manifest.json", "result.json", "ledger.jsonl", "admission.json"} <= set(recorded):
        raise ValueError("source seal omits required battle evidence")
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if actual != set(recorded):
        raise ValueError("source seal does not cover the complete battle bundle")
    return recorded


def decisions(events):
    grouped = defaultdict(list)
    for event in events:
        if event.get("decision"):
            grouped[event["decision"]].append(event)
    result = []
    for key, records in grouped.items():
        typed = {r["type"]: r for r in records}
        if "input" not in typed:
            continue
        entry = typed["input"]
        body = entry["body"]
        state = json.loads(body["state"])
        result.append(
            dict(
                id=key,
                turn=state["snapshot"]["turn"],
                kind=state["snapshot"]["decision_kind"],
                criteria=body["questions"]["action"]["criteria"],
                input=body,
                input_body_json=entry["body_json"],
                input_sha256=entry["input_sha256"],
                request=typed.get("http_request", {}).get("body"),
                response=typed.get("response", {}).get("body"),
                raw_response=typed.get("http_response", {}).get("raw_body"),
                selection=typed.get("selection"),
                wire=typed.get("wire"),
                revalidation=typed.get("revalidation"),
                technical=dict(
                    boundary=entry["boundary"],
                    observation_identity=entry["observation_identity"],
                    commands=entry["commands"],
                    rejection=typed.get("decision_rejected"),
                    request_expired=typed.get("request_expired"),
                ),
            )
        )
    return result


def _page(data):
    outcome = data["outcome"]
    labels = dict(
        completed="정상 종료",
        failed="실패",
        incomplete="미완료",
        unattempted="미실행",
        invalid="무효",
    )
    title = f"EX-071 · {outcome['slot_id']}"
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}</style><main>
<a href="../index.html">40경기 목록</a><h1>{html.escape(title)}</h1>
<p>{html.escape(outcome["model"])} · {html.escape(outcome["model_side"])} ·
상대 {html.escape(outcome["opponent"])} ·
{labels[outcome["status"]]} · {html.escape(str(outcome.get("result") or "점수 없음"))}</p>
<p>표의 확률은 <strong>행동 선택 확률</strong>이며 승률이 아닙니다.
자동 행동은 모델을 호출하지 않습니다.</p>
<section><div class="bar"><button id="previous">이전</button>
<select id="decision" aria-label="결정 선택"></select>
<button id="next">다음</button><button id="download">결정 JSON 저장</button></div>
<p id="status"></p><p id="mode"></p><p id="sent"></p>
<table><thead><tr><th>행동 ID</th><th>행동</th><th>선택 확률</th><th>실제 선택</th></tr></thead>
<tbody id="candidates"></tbody></table></section>
<div class="panes"><section><h2>모델 입력</h2><button data-copy="input">복사</button>
<pre id="input"></pre>
<details><summary>실제 HTTP 요청</summary><pre id="request"></pre></details></section>
<section><h2>모델 응답</h2><button data-copy="response">복사</button>
<pre id="response"></pre></section></div>
<details><summary>관측 경계·실제 전송·진단</summary><pre id="technical"></pre></details>
<details><summary>배틀 리플레이</summary><p>애니메이션에는 외부 Showdown 자산이 필요합니다.
<a href="showdown.log">저장된 공개 로그</a>는 오프라인에서 열립니다.</p>
<iframe src="replay.html" loading="lazy" title="저장 배틀 리플레이"></iframe></details>
<p><a href="decisions.json">모든 입력·응답 JSON</a> · <a href="outcome.json">경기 결과</a></p>
<script type="application/json" id="data">{_encoded(data)}</script>
<script>{SCRIPT}</script></main></html>"""


def export(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError("viewer export already exists; preserve the earlier copy")
    checksums = verify_source(source)
    manifest, result = read(source / "manifest.json"), read(source / "result.json")
    if (
        manifest["experiment_id"] != "EX-071"
        or result["planned"] != 40
        or manifest.get("probability_meaning") != "action_selection_probability"
    ):
        raise ValueError("not an EX-071 imitation battle bundle")
    if len(result["outcomes"]) != len(manifest["schedule"]):
        raise ValueError("viewer must retain every scheduled slot")
    output.mkdir(parents=True)
    links, matches = [], []
    for index, outcome in enumerate(result["outcomes"], 1):
        slot = outcome["slot_id"]
        folder = output / f"battle-{index:02d}"
        folder.mkdir()
        events = reporting.jsonl(source / "games" / slot / "events.jsonl")
        items = decisions(events)
        protocol = (
            "\n".join(
                line
                for event in events
                if event["type"] == "protocol"
                for line in event["protocol"].splitlines()
                if line.startswith("|") and not line.startswith(("|request|", "|sentchoice|"))
            )
            + "\n"
        )
        data = dict(
            experiment_id="EX-071",
            outcome=outcome,
            decisions=items,
            probability_meaning="action_selection_probability",
            source=dict(
                directory=str(source),
                manifest_sha256=checksums["manifest.json"],
                events_sha256=checksums.get(f"games/{slot}/events.jsonl"),
            ),
        )
        atomic(
            folder / "decisions.json",
            (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(),
        )
        atomic(folder / "outcome.json", outcome)
        atomic(folder / "showdown.log", protocol.encode())
        atomic(
            folder / "replay.html",
            _replay_html(
                dict(
                    battle_id=f"ex071-{index}",
                    showdown_battle_tag=outcome.get("battle_tag"),
                    teams=[],
                ),
                protocol,
            ).encode(),
        )
        atomic(folder / "index.html", _page(data).encode())
        matches.append(
            dict(
                slot_id=slot,
                status=outcome["status"],
                decisions=len(items),
                candidates=sum(len(d["criteria"]) for d in items),
                decisions_sha256=sha(folder / "decisions.json"),
                protocol_sha256=sha(folder / "showdown.log"),
            )
        )
        links.append(
            f'<tr><td><a href="battle-{index:02d}/index.html">{html.escape(slot)}</a></td>'
            + "".join(
                f"<td>{html.escape(str(outcome.get(key) or '—'))}</td>"
                for key in ("model", "model_side", "opponent", "status", "result", "turns")
            )
            + "</tr>"
        )
    text = (
        '<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>EX-071 · 모방 학습 첫 배틀 평가</title><style>{STYLE}</style><main>"
        '<a href="../index.html">실험 목록</a><h1>EX-071 · 모방 학습 첫 배틀 평가</h1>'
        f"<p>예정40 · 시도{result['attempted']} · 정상{result['completed']} · "
        f"실패{result['failed']} · 미완료{result['incomplete']} · "
        f"무효{result['invalid']} · 미실행{result['unattempted']}</p>"
        "<p>행동 선택 확률을 표시합니다. 승률 추정값이 아닙니다. 입력·응답·확률·선택·실제 전송·"
        "경기 로그는 오프라인에서 열리며, 리플레이 애니메이션만 외부 자산을 사용합니다.</p>"
        f"<p>{html.escape(result['interpretation'])}</p>"
        '<p><a href="report.md">한국어 결과 보고</a> · <a href="result.json">결과·대응 누락</a> · '
        '<a href="manifest.json">동결 일정</a> · <a href="provenance.json">출처·해시</a></p>'
        "<section><table><thead><tr><th>경기</th><th>모델</th><th>진영</th><th>상대</th><th>상태</th>"
        "<th>결과</th><th>턴</th></tr></thead><tbody>"
        + "".join(links)
        + "</tbody></table></section></main></html>"
    )
    atomic(output / "index.html", text.encode())
    for name in ("manifest.json", "result.json", "report.md"):
        shutil.copyfile(source / name, output / name)
    atomic(
        output / "provenance.json",
        dict(
            experiment_id="EX-071",
            source=str(source),
            source_files=checksums,
            source_seal_sha256=sha(source / "checksums.sha256"),
            builder_sha256=sha(Path(__file__)),
            planned=40,
            completed=result["completed"],
            matches=matches,
            copied_files={
                name: sha(output / name) for name in ("manifest.json", "result.json", "report.md")
            },
        ),
    )
    atomic(
        output / "README.txt",
        (
            "폴더 전체를 이동한 뒤 index.html을 여세요.\n"
            "입력·응답·행동 선택 확률·실제 전송·공개 로그는 오프라인 열람입니다.\n"
            "리플레이 애니메이션만 외부 Showdown 자산을 사용합니다.\n"
            "미실행/미수신과 자동 선택의 모델 미호출을 별도로 표시합니다. 원본 봉인은 보존합니다.\n"
        ).encode(),
    )
    if verify_source(source) != checksums:
        raise ValueError("original source changed during viewer export")
    seal(output)
    return dict(
        index=str(output / "index.html"),
        matches=matches,
        planned=40,
        completed=result["completed"],
        export_sha256=sha(output / "checksums.sha256"),
    )
