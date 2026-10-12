"""C-047: EX-074의 선택 확률·승무패·입출력과 이동 가능한 오프라인 리플레이."""

from __future__ import annotations

import html
import json
import math
import re
import shutil
import tempfile
import time
from pathlib import Path

from ..imitation.reporting import jsonl
from ..imitation.storage import atomic, read, sha
from ..imitation.viewer import STYLE, _encoded
from ..imitation.viewer import decisions as imitation_decisions
from ..observability.render import _replay_html
from . import reporting

STYLE += "\n.json-string{color:#176438}.json-number{color:#7c3aa4}.json-literal{color:#925522}"

SCRIPT = r"""const data=JSON.parse(document.getElementById('data').textContent);
const rows=data.decisions;let position=0;
const q=id=>document.getElementById(id);
const percent=p=>p===null||p===undefined?'미호출/미수신':(100*p).toFixed(3)+'%';
function showJson(id,value){
 const text=value===null||value===undefined?'없음':JSON.stringify(value,null,2);
 const target=q(id);target.replaceChildren();
 const expression=/"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
 let start=0;
 for(const match of text.matchAll(expression)){
  target.append(document.createTextNode(text.slice(start,match.index)));
  const span=document.createElement('span');span.textContent=match[0];
  span.className=match[0][0]==='"'?'json-string':/^-?\d/.test(match[0])?'json-number':'json-literal';
  target.append(span);start=match.index+match[0].length;
 }target.append(document.createTextNode(text.slice(start)));
}
function render(){
 const d=rows[position];q('previous').disabled=position<=0;
 q('next').disabled=position>=rows.length-1;
 if(!d){q('status').textContent='저장된 결정이 없습니다.';return;}
 q('decision').value=String(position);
 q('status').textContent='턴 '+d.turn+' · '+d.kind+' · '+(position+1)+'/'+rows.length;
 const automatic=d.selection&&d.selection.automatic;
 q('mode').textContent=automatic?'모델 미호출 · 유일한 합법 행동':
  d.response?'모델 응답 수신':d.request?'요청 전송 · 정상 응답 미수신':'모델 호출 전 종료';
 q('sent').textContent=d.wire?'실제 전송: '+d.wire.command:'실제 전송 기록 없음';
 const head=d.response&&d.response.primary_head;
 q('head').textContent='표의 승무패 head: '+(head==='after'?'보정 후':head==='before'?'보정 전':'수집 당시 저장 head');
 const table=q('candidates');table.replaceChildren();
 for(const [id,label] of Object.entries(d.criteria)){
  const tr=document.createElement('tr');
  const chosen=d.selection&&d.selection.choice===id;
  if(chosen)tr.className='selected';
  const wdl=d.wdl_probabilities[id]||[null,null,null];
  for(const value of [id,label,percent(d.action_probabilities[id]),...wdl.map(percent),chosen?'선택':'']){
   const td=document.createElement('td');td.textContent=value;tr.append(td);
  }table.append(tr);
 }
 showJson('input',d.input);showJson('request',d.request);
 if(d.response)showJson('response',d.response);
 else q('response').textContent=d.raw_response||'응답 기록 없음';
 showJson('calibration',d.recorded_prediction);
 showJson('technical',{selection:d.selection,wire:d.wire,revalidation:d.revalidation,...d.technical});
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


def verify_source(directory):
    directory = Path(directory).resolve()
    recorded = {}
    for line in (directory / "checksums.sha256").read_text().splitlines():
        value, name = line.split("  ", 1)
        path = (directory / name).resolve()
        if name in recorded or not path.is_relative_to(directory) or sha(path) != value:
            raise ValueError("invalid source seal entry: " + name)
        recorded[name] = value
    if not {"manifest.json", "result.json", "report.md"} <= set(recorded):
        raise ValueError("source seal omits required experiment evidence")
    actual = {
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if actual != set(recorded):
        raise ValueError("source seal does not cover the complete experiment bundle")
    return recorded


def _ordered(values, ids, *, label):
    if values is None:
        return {}
    if isinstance(values, dict):
        if set(values) != set(ids):
            raise ValueError(label + " candidate identities differ")
        return {key: values[key] for key in ids}
    if len(values) != len(ids):
        raise ValueError(label + " candidate count differs")
    return dict(zip(ids, values))


def decisions(events, recorded=()):
    """실제 응답 원문은 보존하고 표시용 두 확률을 별도 필드로 만든다."""
    recorded = list(recorded)
    records = {row["decision_id"]: row for row in recorded}
    if len(records) != len(recorded):
        raise ValueError("duplicate saved decision")
    by_event = {}
    for key, record in records.items():
        prefix = record["slot_id"] + ":"
        event_id = key.removeprefix(prefix)
        if event_id in by_event:
            raise ValueError("duplicate event decision identity")
        by_event[event_id] = record
    result = imitation_decisions(events)
    for row in result:
        ids = list(row["criteria"])
        response = row["response"] or {}
        if "action_ids" in response and response["action_ids"] != ids:
            raise ValueError("response candidate order differs from actual input")
        probabilities = response.get("probabilities")
        if probabilities is None and "log_probabilities" in response:
            logs = _ordered(response["log_probabilities"], ids, label="policy")
            probabilities = {key: math.exp(value) for key, value in logs.items()}
        row["action_probabilities"] = _ordered(probabilities, ids, label="policy")
        if row["action_probabilities"]:
            values = list(row["action_probabilities"].values())
            if any(
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 1
                for value in values
            ) or not math.isclose(math.fsum(values), 1, abs_tol=1e-6, rel_tol=0):
                raise ValueError("invalid action probabilities")
        row["wdl_probabilities"] = _ordered(
            response.get("wdl_probabilities"), ids, label="W/D/L"
        )
        row["wdl_probabilities"] = {
            key: reporting._wdl(prediction)
            for key, prediction in row["wdl_probabilities"].items()
        }
        record = by_event.get(row["id"])
        if record and record.get("action_ids", ids) != ids:
            raise ValueError("recorded candidate order differs from actual input")
        row["recorded_prediction"] = (
            {
                key: record.get(key)
                for key in ("wdl_before", "wdl_after", "outcome", "model_version")
            }
            if record
            else None
        )
    return result


def _base_page(data):
    outcome = data["outcome"]
    title = "EX-074 · " + outcome["slot_id"]
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}</style><main>
<a href="../index.html">경기 목록</a><h1>{html.escape(title)}</h1>
<p>{html.escape(str(outcome.get("stage", "")))} · {html.escape(outcome["model"])} ·
{html.escape(outcome["model_side"])} · 상대 {html.escape(outcome["opponent"])} ·
{html.escape(outcome["status"])} · {html.escape(str(outcome.get("result") or "점수 없음"))}</p>
<p><strong>행동 선택 확률</strong>과 <strong>행동 이후 승·무·패 확률</strong>은 별도 값입니다.
승무패 정확성 평가는 실제 선택 행동에만 적용합니다. 자동 행동은 모델을 호출하지 않습니다.</p>
<section><div class="bar"><button id="previous">이전</button>
<select id="decision" aria-label="결정 선택"></select><button id="next">다음</button>
<button id="download">결정 JSON 저장</button></div><p id="status"></p><p id="mode"></p><p id="sent"></p><p id="head"></p>
<table><thead><tr><th>행동 ID</th><th>행동</th><th>행동 선택 확률</th>
<th>승리 확률</th><th>무승부 확률</th><th>패배 확률</th><th>실제 선택</th></tr></thead>
<tbody id="candidates"></tbody></table></section>
<div class="panes"><section><h2>모델 입력</h2><button data-copy="input">복사</button>
<pre id="input"></pre><details><summary>기록된 추론 요청</summary><pre id="request"></pre></details></section>
<section><h2>모델 응답</h2><button data-copy="response">복사</button><pre id="response"></pre></section></div>
<details><summary>같은 선택 행동의 보정 전후 승무패</summary><pre id="calibration"></pre></details>
<details><summary>관측 경계·실제 전송·진단</summary><pre id="technical"></pre></details>
<section><h2>오프라인 턴별 리플레이</h2><p>저장된 공개 로그를 턴별로 재생합니다.
<a href="showdown.log">공개 로그</a> · <a href="animation.html">외부 Showdown 자산을 사용하는 애니메이션</a></p>
<iframe src="replay.html" title="오프라인 턴별 리플레이"></iframe></section>
<p><a href="decisions.json">모든 입력·응답 JSON</a> · <a href="outcome.json">경기 결과</a></p>
<script type="application/json" id="data">{_encoded(data)}</script><script>{SCRIPT}</script></main></html>"""


def _replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("frozen viewer text does not match the registered correction")
    return text.replace(old, new, 1)


def _pretty(value):
    return (
        "없음"
        if value is None
        else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    )


def _page(data):
    """큰 JSON 정수를 숫자형 그대로 보존한다. 행동 표·선택·검증 기준은 바꾸지 않는다."""
    exact = []
    for decision in data["decisions"]:
        technical = {
            "selection": decision.get("selection"),
            "wire": decision.get("wire"),
            "revalidation": decision.get("revalidation"),
            **(decision.get("technical") or {}),
        }
        exact.append(
            {
                "input": _pretty(decision.get("input")),
                "request": _pretty(decision.get("request")),
                "response": _pretty(decision.get("response")),
                "calibration": _pretty(decision.get("recorded_prediction")),
                "technical": _pretty(technical),
                "decision": _pretty(decision),
            }
        )
    script = _replace_once(
        SCRIPT,
        "const rows=data.decisions;let position=0;",
        "const exactRows=JSON.parse(document.getElementById('exact-json').textContent);\n"
        "const rows=data.decisions;let position=0;",
    )
    script = _replace_once(
        script,
        "function showJson(id,value){\n"
        " const text=value===null||value===undefined?'없음':JSON.stringify(value,null,2);",
        "function showJson(id,text){",
    )
    script = _replace_once(
        script,
        " showJson('input',d.input);showJson('request',d.request);\n"
        " if(d.response)showJson('response',d.response);\n"
        " else q('response').textContent=d.raw_response||'응답 기록 없음';\n"
        " showJson('calibration',d.recorded_prediction);\n"
        " showJson('technical',{selection:d.selection,wire:d.wire,revalidation:d.revalidation,...d.technical});",
        " const exact=exactRows[position];\n"
        " showJson('input',exact.input);showJson('request',exact.request);\n"
        " if(d.response)showJson('response',exact.response);\n"
        " else q('response').textContent=d.raw_response||'응답 기록 없음';\n"
        " showJson('calibration',exact.calibration);\n"
        " showJson('technical',exact.technical);",
    )
    script = _replace_once(
        script,
        " const blob=new Blob([JSON.stringify(rows[position]||{},null,2)],{type:'application/json'});",
        " const blob=new Blob([exactRows[position]?exactRows[position].decision:'{}'],{type:'application/json'});",
    )
    return _replace_once(
        _base_page(data),
        "<script>" + SCRIPT + "</script>",
        '<script type="application/json" id="exact-json">'
        + _encoded(exact)
        + "</script><script>"
        + script
        + "</script>",
    )



def _offline_replay(protocol):
    # The local replay remains functional without official animated assets or a server.
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>오프라인 턴별 리플레이</title>
<style>{STYLE}</style><main><div class="bar"><button id="previous-turn">이전 턴</button>
<select id="turn" aria-label="리플레이 턴"></select><button id="next-turn">다음 턴</button>
<button id="play">재생</button></div><p id="replay-status"></p><pre id="protocol"></pre></main>
<script type="application/json" id="replay-data">{_encoded(protocol)}</script><script>
const protocol=JSON.parse(document.getElementById('replay-data').textContent);
const chunks=[{{turn:0,lines:[]}}];
for(const line of protocol.split('\\n')){{
 const match=line.match(/^\\|turn\\|(\\d+)$/);
 if(match)chunks.push({{turn:Number(match[1]),lines:[]}});
 chunks[chunks.length-1].lines.push(line);
}}
const q=id=>document.getElementById(id);let cursor=0,timer=null;
function stop(){{clearInterval(timer);timer=null;q('play').textContent='재생'}}
function render(){{q('turn').value=String(cursor);
 q('previous-turn').disabled=cursor===0;q('next-turn').disabled=cursor===chunks.length-1;
 q('protocol').textContent=chunks.slice(0,cursor+1).flatMap(c=>c.lines).join('\\n');
 q('replay-status').textContent='턴 '+chunks[cursor].turn+' · '+(cursor+1)+'/'+chunks.length;
 if(cursor===chunks.length-1)stop();
}}
chunks.forEach((chunk,index)=>{{const option=document.createElement('option');option.value=String(index);
 option.textContent=chunk.turn===0?'배틀 시작':'턴 '+chunk.turn;q('turn').append(option)}});
q('turn').onchange=()=>{{stop();cursor=Number(q('turn').value);render()}};
q('previous-turn').onclick=()=>{{stop();cursor--;render()}};
q('next-turn').onclick=()=>{{stop();cursor++;render()}};
q('play').onclick=()=>{{if(chunks.length<2)return;if(timer){{stop();return}}if(cursor===chunks.length-1)cursor=0;
 render();q('play').textContent='일시정지';timer=setInterval(()=>{{cursor++;render()}},700)}};
render();</script></html>"""


def _validate_protocol(protocol, outcome):
    if outcome["status"] != "completed":
        return
    players, endings, turns = {}, set(), []
    for line in protocol.splitlines():
        parts = line.split("|")
        if line.startswith("|player|") and len(parts) >= 4:
            players[parts[2]] = parts[3]
        elif line.startswith("|win|"):
            endings.add(("win", parts[2]))
        elif line == "|tie|":
            endings.add(("draw", None))
        elif line.startswith("|turn|"):
            turns.append(int(parts[2]))
    if len(endings) != 1:
        raise ValueError("normal game must have one recorded terminal result")
    terminal, winner = next(iter(endings))
    if terminal == "draw":
        actual = "draw"
    else:
        side = outcome["model_side"]
        if side not in players or winner not in players.values():
            raise ValueError("replay winner cannot be mapped to model side")
        actual = "win" if players[side] == winner else "loss"
    if actual != outcome["result"]:
        raise ValueError("replay result differs from recorded outcome")
    if outcome.get("turns") is not None and max(turns, default=0) != outcome["turns"]:
        raise ValueError("replay turn count differs from recorded outcome")


def _seal(output):
    files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    atomic(
        output / "checksums.sha256",
        "".join(
            sha(path) + "  " + str(path.relative_to(output)) + "\n" for path in files
        ).encode(),
        immutable=True,
    )


def export(source, output, *, deadline=None):
    """봉인된 보고 bundle에서 새 복사본만 작성한다. 기존 내보내기는 덮어쓰지 않는다."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError("viewer export already exists; preserve the earlier copy")
    if output.is_relative_to(source):
        raise ValueError("viewer export must not mutate the sealed source tree")
    checksums = verify_source(source)
    manifest, result = read(source / "manifest.json"), read(source / "result.json")
    if manifest.get("experiment_id") != "EX-074":
        raise ValueError("not an EX-074 experiment bundle")
    outcomes = reporting._validated(result["outcomes"])
    if "schedule" in manifest:
        reconciled = reporting.complete_outcomes(manifest["schedule"], outcomes)
        if len(reconciled) != len(outcomes):
            raise ValueError("viewer source omits scheduled outcomes")
    counts = reporting._counts(outcomes)
    all_decisions = jsonl(source / "decisions.jsonl")
    output.mkdir(parents=True)
    links, matches = [], []
    for index, outcome in enumerate(outcomes, 1):
        if deadline is not None and time.time()>=deadline:
            raise TimeoutError('original budget expired during viewer export')
        slot = outcome["slot_id"]
        folder = output / f"battle-{index:03d}"
        folder.mkdir()
        events_path = source / "games" / slot / "events.jsonl"
        if not events_path.resolve().is_relative_to(source):
            raise ValueError("unsafe battle slot path")
        events = jsonl(events_path)
        if outcome["status"] == "completed" and not events:
            raise ValueError("completed game has no stored battle events")
        items = decisions(
            events, [row for row in all_decisions if row["slot_id"] == slot]
        )
        protocol = (
            "\n".join(
                line
                for event in events
                if event.get("type") == "protocol"
                for line in event["protocol"].splitlines()
                if line.startswith("|")
                and not line.startswith(("|request|", "|sentchoice|"))
            )
            + "\n"
        )
        _validate_protocol(protocol, outcome)
        data = {
            "experiment_id": "EX-074",
            "outcome": outcome,
            "decisions": items,
            "probability_meaning": {
                "policy": "action_selection_probability",
                "wdl": "action_terminal_WDL",
            },
            "source": {
                "events_sha256": checksums.get(f"games/{slot}/events.jsonl"),
            },
        }
        atomic(
            folder / "decisions.json",
            (
                json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            ).encode(),
        )
        atomic(folder / "outcome.json", outcome)
        atomic(folder / "showdown.log", protocol.encode())
        atomic(folder / "replay.html", _offline_replay(protocol).encode())
        atomic(
            folder / "animation.html",
            _replay_html(
                {
                    "battle_id": "ex074-" + slot,
                    "showdown_battle_tag": outcome.get("battle_tag"),
                    "teams": [],
                },
                protocol,
            ).encode(),
        )
        atomic(folder / "index.html", _page(data).encode())
        matches.append(
            {
                "slot_id": slot,
                "status": outcome["status"],
                "decisions": len(items),
                "candidates": sum(len(row["criteria"]) for row in items),
                "decisions_sha256": sha(folder / "decisions.json"),
                "protocol_sha256": sha(folder / "showdown.log"),
            }
        )
        links.append(
            f'<tr><td><a href="battle-{index:03d}/index.html">{html.escape(slot)}</a></td>'
            + "".join(
                f"<td>{html.escape(str(outcome.get(key) if outcome.get(key) is not None else '—'))}</td>"
                for key in (
                    "stage",
                    "model",
                    "model_side",
                    "opponent",
                    "status",
                    "result",
                    "turns",
                )
            )
            + "</tr>"
        )
    index_html = (
        '<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>EX-074 자기대국·RLCD</title><style>{STYLE}</style><main>"
        '<a href="../index.html">실험 목록</a><h1>EX-074 자기대국·RLCD 확률 보정</h1>'
        f"<p>예정 {counts['planned']} · 시도 {counts['attempted']} · 정상 {counts['completed']} · "
        f"실패 {counts['failed']} · 미완료 {counts['incomplete']} · 무효 {counts['invalid']} · "
        f"미실행 {counts['unattempted']}</p>"
        "<p>행동 선택 확률과 승무패 확률을 구분합니다. 입력·응답·선택·결과와 턴별 리플레이는 "
        "오프라인에서 열립니다. 선택 사항인 Showdown 애니메이션만 외부 자산을 사용합니다.</p>"
        '<p><a href="report.md">한국어 보고</a> · <a href="result.json">결과·분모</a> · '
        '<a href="manifest.json">동결 조건</a> · <a href="provenance.json">출처·해시</a></p>'
        "<section><table><thead><tr><th>경기</th><th>단계</th><th>모델</th><th>진영</th><th>상대</th>"
        "<th>상태</th><th>결과</th><th>턴</th></tr></thead><tbody>"
        + "".join(links)
        + "</tbody></table></section></main></html>"
    )
    atomic(output / "index.html", index_html.encode())
    for name in ("manifest.json", "result.json", "report.md"):
        shutil.copyfile(source / name, output / name)
    atomic(
        output / "provenance.json",
        {
            "experiment_id": "EX-074",
            "source": str(source),
            "source_files": checksums,
            "source_seal_sha256": sha(source / "checksums.sha256"),
            "builder_sha256": sha(Path(__file__)),
            "planned": counts["planned"],
            "completed": counts["completed"],
            "matches": matches,
            "copied_files": {
                name: sha(output / name)
                for name in ("manifest.json", "result.json", "report.md")
            },
            "local_replay": "saved public protocol, turn navigation and playback; no external asset dependency",
        },
    )
    atomic(
        output / "README.txt",
        (
            "폴더 전체를 이동한 뒤 index.html을 여세요.\n"
            "입력·응답·행동 선택 확률·승무패 확률·전송·턴별 리플레이는 오프라인에서 열립니다.\n"
            "선택 사항인 Showdown 애니메이션만 외부 자산을 사용합니다. 원본 봉인은 보존합니다.\n"
        ).encode(),
    )
    if verify_source(source) != checksums:
        raise ValueError("original source changed during viewer export")
    _seal(output)
    return {
        "index": str(output / "index.html"),
        "matches": matches,
        "planned": counts["planned"],
        "completed": counts["completed"],
        "export_sha256": sha(output / "checksums.sha256"),
    }


def _require(condition, message):
    if not condition:
        raise ValueError("offline viewer verification: " + message)


def _nonargmax(row):
    probabilities = row["action_probabilities"]
    selection = row.get("selection") or {}
    choice = selection.get("choice")
    return bool(
        probabilities
        and not selection.get("automatic", False)
        and choice in probabilities
        and probabilities[choice] < max(probabilities.values())
    )


def _check_decision(page, row, position):
    """DOM의 실제 선택·원문·각 확률 열을 독립적으로 대조한다."""
    page.locator("#decision").select_option(str(position))
    observed = page.locator("#candidates tr").evaluate_all(
        "rows => rows.map(row => ({selected:row.classList.contains('selected'),"
        "cells:Array.from(row.cells, cell => cell.textContent)}))"
    )
    ids = list(row["criteria"])
    _require(len(observed) == len(ids), "candidate count differs")
    selection = row.get("selection") or {}
    choice = selection.get("choice")
    _require(choice in ids, "completed decision has no legal recorded selection")
    _require(
        [entry["cells"][0] for entry in observed if entry["selected"]] == [choice],
        "displayed selection differs from actual recorded choice",
    )
    automatic = selection.get("automatic", False)
    for action_id, entry in zip(ids, observed):
        cells = entry["cells"]
        _require(len(cells) == 7, "action and W/D/L columns are not separate")
        _require(
            cells[:2] == [action_id, row["criteria"][action_id]],
            "candidate order or label differs",
        )
        expected = [row["action_probabilities"].get(action_id)] + row[
            "wdl_probabilities"
        ].get(action_id, [None, None, None])
        for displayed, probability in zip(cells[2:6], expected):
            if probability is None:
                _require(
                    displayed == "미호출/미수신",
                    "missing prediction is displayed as model output",
                )
            else:
                _require(displayed.endswith("%"), "probability percentage is absent")
                _require(
                    abs(float(displayed[:-1]) / 100 - probability) <= 0.000005000001,
                    "displayed policy or W/D/L probability differs from saved response",
                )
    _require(
        json.loads(page.locator("#input").text_content()) == row["input"],
        "model input differs",
    )
    if automatic:
        _require(
            "모델 미호출" in page.locator("#mode").text_content(),
            "automatic decision shown as model call",
        )
        _require(
            not row["response"], "automatic decision has fabricated model response"
        )
    else:
        _require(bool(row["response"]), "normal model decision has no response")
        _require(
            set(row["action_probabilities"]) == set(ids),
            "normal model response lacks policy probabilities",
        )
        _require(
            set(row["wdl_probabilities"]) == set(ids),
            "normal model response lacks W/D/L probabilities",
        )
        _require(
            json.loads(page.locator("#response").text_content()) == row["response"],
            "model response differs",
        )
        head = row["response"].get("primary_head")
        if head in ("before", "after"):
            _require(
                ("보정 전" if head == "before" else "보정 후")
                in page.locator("#head").text_content(),
                "primary W/D/L head label differs",
            )
    _require(row["wire"] is not None, "normal selection has no actual transmission")
    _require(
        page.locator("#sent").text_content() == "실제 전송: " + row["wire"]["command"],
        "displayed transmission differs",
    )
    if row["recorded_prediction"] is not None:
        _require(
            json.loads(page.locator("#calibration").text_content())
            == row["recorded_prediction"],
            "before/after chosen-action predictions differ",
        )
    technical = dict(selection=row.get('selection'), wire=row.get('wire'),
                     revalidation=row.get('revalidation'), **(row.get('technical') or {}))
    for panel, expected_value in [('request', row.get('request')), ('technical', technical)]:
        text = page.locator('#' + panel).text_content()
        observed_value = None if text == '없음' else json.loads(text)
        _require(observed_value == expected_value, panel + ' exact JSON differs')
    return {
        "decision_id": row["id"],
        "index": position,
        "automatic": bool(automatic),
        "nonargmax": _nonargmax(row),
        "selected_action": choice,
        "candidates": len(ids),
    }


def _check_replay(page, protocol):
    """이동 사본에서 시작·다음·이전·마지막 턴과 실제 타이머 재생을 확인한다."""
    chunks = [[]]
    for line in protocol.split("\n"):
        if re.fullmatch(r"\|turn\|\d+", line):
            chunks.append([])
        chunks[-1].append(line)
    frame = page.frame_locator("iframe")
    _require(
        page.locator("iframe").get_attribute("src") == "replay.html",
        "replay is not a relative local file",
    )
    frame.locator("#turn").wait_for(state="visible")
    _require(
        frame.locator("#turn option").count() == len(chunks),
        "replay turn count differs",
    )
    _require(
        frame.locator("#turn").input_value() == "0",
        "replay does not start at battle start",
    )
    _require(
        frame.locator("#protocol").text_content() == "\n".join(chunks[0]),
        "replay start log differs",
    )
    _require(
        json.loads(frame.locator("#replay-data").text_content()) == protocol,
        "embedded replay protocol differs",
    )
    advanced = len(chunks) > 1
    if advanced:
        frame.locator("#next-turn").click()
        _require(
            frame.locator("#turn").input_value() == "1", "next-turn control failed"
        )
        _require(
            frame.locator("#protocol").text_content()
            == "\n".join(chunks[0] + chunks[1]),
            "next-turn public log differs",
        )
        frame.locator("#previous-turn").click()
        _require(
            frame.locator("#turn").input_value() == "0", "previous-turn control failed"
        )
        frame.locator("#play").click()
        replay_frame = page.frame(url=page.url.rsplit("/", 1)[0] + "/replay.html")
        _require(replay_frame is not None, "local replay frame missing")
        replay_frame.wait_for_function(
            "document.getElementById('turn').value !== '0'", timeout=3000
        )
        if frame.locator("#play").text_content() == "일시정지":
            frame.locator("#play").click()
        _require(
            int(frame.locator("#turn").input_value()) >= 1,
            "play control did not advance",
        )
    else:
        _require(
            frame.locator("#next-turn").is_disabled(),
            "single-segment replay allows invalid next turn",
        )
    frame.locator("#turn").select_option(str(len(chunks) - 1))
    _require(
        frame.locator("#protocol").text_content() == protocol,
        "final replay omits terminal protocol",
    )
    return {
        "segments": len(chunks),
        "start_verified": True,
        "next_previous_verified": advanced,
        "timer_playback_verified": advanced,
        "full_protocol_verified": True,
    }


def browser_sample(outcomes):
    """승인된 여섯 단계의 슬롯 ID 순 첫·마지막 정상 경기만 반환한다."""
    groups = {stage: [] for stage in (
        'train', 'dev', 'calibration', 'calibration_dev', 'test-initial', 'test-selected')}
    for row in outcomes:
        if row['status'] != 'completed':
            continue
        stage = row['stage']
        if stage == 'test':
            stage += '-' + row['model']
        if stage not in groups:
            raise ValueError('unregistered browser sample stage: ' + stage)
        groups[stage].append(row['slot_id'])
    selected = set()
    for values in groups.values():
        if values:
            values.sort()
            selected.update((values[0], values[-1]))
    return sorted(selected)


def verify_browser(source, export_root, receipt):
    """실제 봉인 자료를 이동한 사본에서 검사한다. 파일/브라우저 불일치는 실패로 올린다.

    receipt는 export() 반환 dict 또는 해당 JSON 경로다. 검증 결과는 반환만 하며,
    봉인 원본·내보내기 안에 쓰지 않는다. Playwright가 있는 CPU 환경에서 호출한다.
    """
    source, export_root = Path(source).resolve(), Path(export_root).resolve()
    receipt = read(receipt) if isinstance(receipt, (str, Path)) else receipt
    source_files, export_files = verify_source(source), verify_source(export_root)
    source_seal, export_seal = (
        sha(source / "checksums.sha256"),
        sha(export_root / "checksums.sha256"),
    )
    _require(receipt["export_sha256"] == export_seal, "export receipt seal differs")
    _require(
        Path(receipt["index"]).resolve() == export_root / "index.html",
        "export receipt index differs",
    )
    provenance = read(export_root / "provenance.json")
    _require(provenance["experiment_id"] == "EX-074", "wrong exported experiment")
    _require(
        Path(provenance["source"]).resolve() == source, "export source path differs"
    )
    _require(
        provenance["source_files"] == source_files, "export source file hashes differ"
    )
    _require(
        provenance["source_seal_sha256"] == source_seal, "export source seal differs"
    )
    for name in ("manifest.json", "result.json", "report.md"):
        _require(
            source_files[name]
            == export_files[name]
            == provenance["copied_files"][name],
            "copied source file differs: " + name,
        )
    outcomes = reporting._validated(read(source / "result.json")["outcomes"])
    counts = reporting._counts(outcomes)
    _require(
        read(source / "manifest.json")["experiment_id"] == "EX-074",
        "wrong source experiment",
    )
    _require(
        receipt["planned"] == provenance["planned"] == counts["planned"],
        "planned denominator differs",
    )
    _require(
        receipt["completed"] == provenance["completed"] == counts["completed"],
        "normal-game denominator differs",
    )
    _require(receipt["matches"] == provenance["matches"], "match receipt differs")
    _require(
        len(receipt["matches"]) == len(outcomes), "match receipt omits scheduled slots"
    )
    all_records = {}
    for record in jsonl(source / "decisions.jsonl"):
        all_records.setdefault(record["slot_id"], []).append(record)
    sample_slots = set(browser_sample(outcomes))
    checked_pages, errors, external_requests = [], [], []
    from playwright.sync_api import sync_playwright

    try:
        with tempfile.TemporaryDirectory(prefix="ex074-moved-viewer-") as temporary:
            moved = Path(temporary) / "independent-location" / "ex074"
            shutil.copytree(export_root, moved)
            _require(
                verify_source(moved) == export_files, "moved export file hashes differ"
            )
            _require(
                sha(moved / "checksums.sha256") == export_seal,
                "moved export seal differs",
            )
            with sync_playwright() as work:
                browser = work.chromium.launch(headless=True)
                try:
                    context = browser.new_context(offline=True)
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on(
                        "request",
                        lambda request: (
                            external_requests.append(request.url)
                            if request.url.startswith(("http://", "https://"))
                            else None
                        ),
                    )
                    page.goto(
                        (moved / "index.html").as_uri(), wait_until="domcontentloaded"
                    )
                    index_rows = page.locator("tbody tr").evaluate_all(
                        "rows => rows.map(row => Array.from(row.cells, cell => cell.textContent))"
                    )
                    _require(
                        len(index_rows) == len(outcomes), "index omits scheduled slots"
                    )
                    for index, (outcome, match) in enumerate(
                        zip(outcomes, receipt["matches"]), 1
                    ):
                        slot = outcome["slot_id"]
                        _require(
                            match["slot_id"] == slot
                            and match["status"] == outcome["status"],
                            "match receipt identity differs",
                        )
                        _require(
                            index_rows[index - 1][0] == slot, "index slot order differs"
                        )
                        _require(
                            index_rows[index - 1][5] == outcome["status"],
                            "index terminal status differs",
                        )
                        if slot not in sample_slots:
                            continue
                        folder = moved / f"battle-{index:03d}"
                        data = read(folder / "decisions.json")
                        _require(
                            sha(folder / "decisions.json") == match["decisions_sha256"],
                            "decision copy hash differs",
                        )
                        _require(
                            sha(folder / "showdown.log") == match["protocol_sha256"],
                            "protocol copy hash differs",
                        )
                        _require(
                            data["outcome"] == outcome == read(folder / "outcome.json"),
                            "page outcome differs",
                        )
                        events_path = source / "games" / slot / "events.jsonl"
                        _require(
                            events_path.resolve().is_relative_to(source),
                            "unsafe source slot path",
                        )
                        events = jsonl(events_path)
                        expected_decisions = decisions(
                            events, all_records.get(slot, [])
                        )
                        _require(
                            data["decisions"] == expected_decisions,
                            "export decisions differ from source events",
                        )
                        items = data["decisions"]
                        _require(
                            len(items) == match["decisions"],
                            "decision denominator differs",
                        )
                        _require(
                            sum(len(row["criteria"]) for row in items)
                            == match["candidates"],
                            "candidate denominator differs",
                        )
                        protocol = (folder / "showdown.log").read_text()
                        source_protocol = (
                            "\n".join(
                                line
                                for event in events
                                if event.get("type") == "protocol"
                                for line in event["protocol"].splitlines()
                                if line.startswith("|")
                                and not line.startswith(("|request|", "|sentchoice|"))
                            )
                            + "\n"
                        )
                        _require(
                            protocol == source_protocol,
                            "public replay differs from source events",
                        )
                        _validate_protocol(protocol, outcome)
                        cached = _cached_page(source, slot, folder)
                        if cached is not None:
                            checked_pages.append(dict(cached, reused_verified_cache=True))
                            continue
                        page.goto(
                            (folder / "index.html").as_uri(),
                            wait_until="domcontentloaded",
                        )
                        _require(
                            json.loads(page.locator("#data").text_content()) == data,
                            "embedded page data differs",
                        )
                        _require(
                            page.locator("#decision option").count() == len(items),
                            "decision navigation omits records",
                        )
                        _require(
                            page.locator("th").all_text_contents()
                            == [
                                "행동 ID",
                                "행동",
                                "행동 선택 확률",
                                "승리 확률",
                                "무승부 확률",
                                "패배 확률",
                                "실제 선택",
                            ],
                            "policy and W/D/L labels differ",
                        )
                        nonargmax = [
                            i for i, row in enumerate(items) if _nonargmax(row)
                        ]
                        model = [
                            i
                            for i, row in enumerate(items)
                            if row["response"]
                            and not (row.get("selection") or {}).get("automatic")
                        ]
                        automatic = [
                            i
                            for i, row in enumerate(items)
                            if (row.get("selection") or {}).get("automatic")
                        ]
                        representatives = list(range(len(items)))
                        inspected = [
                            _check_decision(page, items[i], i)
                            for i in dict.fromkeys(representatives)
                        ]
                        replay = _check_replay(page, protocol)
                        _require(
                            not errors,
                            "browser JavaScript errors: " + "; ".join(errors),
                        )
                        _require(
                            not external_requests,
                            "offline page requested external assets",
                        )
                        checked_pages.append(
                            {
                                "slot_id": slot,
                                "decisions": len(items),
                                "model_decisions": len(model),
                                "automatic_decisions": len(automatic),
                                "nonargmax_decisions": len(nonargmax),
                                "checked_decisions": inspected,
                                "replay": replay,
                                "passed": True,
                            }
                        )
                    context.close()
                finally:
                    browser.close()
            _require(
                verify_source(moved) == export_files, "browser modified moved export"
            )
    finally:
        _require(
            verify_source(source) == source_files
            and sha(source / "checksums.sha256") == source_seal,
            "sealed source changed during browser verification",
        )
        _require(
            verify_source(export_root) == export_files
            and sha(export_root / "checksums.sha256") == export_seal,
            "original export changed during browser verification",
        )
    _require(
        {row["slot_id"] for row in checked_pages} == sample_slots, "sample coverage differs"
    )
    checked = [row for page in checked_pages for row in page["checked_decisions"]]
    return {
        "experiment_id": "EX-074",
        "passed": True,
        **counts,
        "browser_scope": "first_last_slot_per_stage_max12",
        "full_browser_verification_skipped": True,
        "sample_slots": sorted(sample_slots),
        "checked_completed_pages": len(checked_pages),
        "checked_decisions": len(checked),
        "checked_nonargmax_decisions": sum(row["nonargmax"] for row in checked),
        "available_nonargmax_decisions": sum(
            page["nonargmax_decisions"] for page in checked_pages
        ),
        "source_seal_sha256": source_seal,
        "export_seal_sha256": export_seal,
        "verifier_sha256": sha(Path(__file__)),
        "source_unchanged": True,
        "export_unchanged": True,
        "moved_copy_verified": True,
        "offline": True,
        "browser": "chromium",
        "javascript_errors": errors,
        "external_requests": external_requests,
        "pages": checked_pages,
    }


def _files(directory):
    return {p.name: sha(p) for p in sorted(Path(directory).iterdir()) if p.is_file()}


def _cached_page(source, slot, folder):
    return None


def incremental(directory):
    raise RuntimeError('EX-074 forbids incremental full browser verification')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--incremental', type=Path)
    for name in ('source', 'export', 'receipt', 'report'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.incremental:
        result = incremental(args.incremental)
        print(json.dumps(result, ensure_ascii=False))
    else:
        if not all((args.source, args.export, args.receipt, args.report)):
            parser.error('source/export/receipt/report are required for final verification')
        result = verify_browser(args.source, args.export, read(args.receipt))
        atomic(args.report, result, immutable=True)
