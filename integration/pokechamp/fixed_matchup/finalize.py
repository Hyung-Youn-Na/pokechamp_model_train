"""All-game source audit, paired statistics and portable researcher views."""
from __future__ import annotations

from collections import defaultdict
import gzip
import html
import json
from pathlib import Path
import subprocess
import time

from ..observability.render import _replay_html
from .artifacts import load_result
from .config import ROOT
from .prepare import verify_identity
from .reporting import report
from .storage import atomic, atomic_bytes, digest, encoded, read, sha

BROWSER_PYTHON = Path("/tmp/ep037/tools/bin/python")
SCRIPT = """const d=JSON.parse(document.getElementById('data').textContent);let n=0;
const q=id=>document.getElementById(id);function render(){const r=d.records[n];
q('position').textContent=r?`${n+1}/${d.records.length} · 턴 ${r.turn} · ${r.side} · ${r.choice}`:'결정 없음';
q('input').textContent=JSON.stringify(r?r.observation:null,null,2);
q('response').textContent=JSON.stringify(r?{policy:r.target,visits:r.visits,value:r.value,search:r.search,
choice:r.choice,command:r.command,submitted:r.submitted,automatic:r.automatic}:null,null,2);
q('previous').disabled=n===0;q('next').disabled=n+1>=d.records.length;}
q('previous').onclick=()=>{if(n>0)n--;render()};q('next').onclick=()=>{if(n+1<d.records.length)n++;render()};
q('copy').onclick=async()=>{const t=JSON.stringify(d.records[n]||{},null,2);try{await navigator.clipboard.writeText(t)}
catch(_){const a=document.createElement('textarea');a.value=t;document.body.append(a);a.select();document.execCommand('copy');a.remove()}};
q('download').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(d.records[n]||{},null,2)],{type:'application/json'}));
const a=document.createElement('a');a.href=u;a.download='decision.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
document.addEventListener('keydown',e=>{if(['INPUT','BUTTON','TEXTAREA','SELECT'].includes(document.activeElement.tagName))return;
if(e.key==='ArrowRight')q('next').click();if(e.key==='ArrowLeft')q('previous').click()});render();"""


def page(row, records, protocol):
    title = html.escape(row["job"]["slot_id"])
    data = encoded(dict(records=records)).decode().replace("<", "\\u003c").replace("&", "\\u0026")
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>{title}</title>
<style>body{{font:15px system-ui;margin:24px;max-width:1400px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f7;padding:16px}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}button{{padding:8px;margin:4px}}iframe{{width:100%;height:520px}}</style>
<a href="../index.html">경기 목록</a><h1>{title}</h1><p>{html.escape(row['status'])} · winner={html.escape(str(row['winner']))}</p>
<p>공개 상태 진단. 정책 확률은 승률이 아니며, 가치 head는 상태가치다. 단일 후보는 모델 미호출이다.</p>
<button id="previous">이전</button><button id="next">다음</button><button id="copy">결정 복사</button><button id="download">JSON 저장</button>
<p id="position"></p><div class="columns"><section><h2>모델 입력</h2><pre id="input"></pre></section>
<section><h2>정책·탐색·실제 제출</h2><pre id="response"></pre></section></div>
<details><summary>선택적 Showdown 애니메이션 — 외부 자산 필요</summary><iframe loading="lazy" src="replay.html"></iframe></details>
<details open><summary>오프라인 공개 protocol 리플레이</summary><pre id="protocol">{html.escape(protocol)}</pre></details>
<script id="data" type="application/json">{data}</script><script>{SCRIPT}</script></html>'''


def audit_game(path):
    row = load_result(path, records=True)
    with gzip.open(Path(path) / "private-evidence.json.gz", "rt") as stream:
        evidence = json.load(stream)
    if row["status"] != "completed":
        if any(r.get("z") is not None for r in row["records"]):
            raise ValueError("failed game acquired value targets")
        return row, evidence
    if not evidence or not evidence["ended"] or evidence["winner"] != row["winner"]:
        raise ValueError("terminal evidence disagrees with result")
    seen = set()
    commands = []
    for record in row["records"]:
        if record["id"] in seen or not record.get("submitted") or record["terminal_status"] != "completed":
            raise ValueError("duplicate/unsubmitted/nonterminal decision")
        seen.add(record["id"])
        expected = 0 if not row["winner"] else 1 if record["side"] == row["winner"] else -1
        if record["z"] != expected:
            raise ValueError("value sign mismatch")
        if record["choice"] not in record["action_ids"]:
            raise ValueError("illegal recorded action")
        command = record["command"]
        if command.startswith("move "):
            parts = record["choice"].split(":")
            if len(parts) != 4 or parts[0] != "move":
                raise ValueError("move choice lacks canonical ID")
            command = f"move {parts[2]}" + (" terastallize" if parts[3] == "tera" else "")
        elif command.startswith("team "):
            command = "team " + ", ".join(command.split()[1])
        commands.append(f">{record['side']} {command}")
        if record["mode"] == "opponent":
            if record["observation"] is not None or record["target"] is not None:
                raise ValueError("opponent was assigned an unobserved model input")
            continue
        if digest(record["observation"]) != record["observation_hash"]:
            raise ValueError("input hash mismatch")
        ids = [a["id"] for a in record["observation"]["actions"]]
        if ids != record["action_ids"] or len(record["target"]) != len(ids):
            raise ValueError("candidate order mismatch")
        selected = next(a for a in record["observation"]["actions"] if a["id"] == record["choice"])
        if selected["command"] != record["command"]:
            raise ValueError("selected candidate/command mismatch")
        import math
        if any(not math.isfinite(p) or p < 0 for p in record["target"]) or abs(sum(record["target"]) - 1) > 1e-6:
            raise ValueError("invalid policy target")
        if record["mode"] == "search" and len(ids) > 1:
            visits = record["visits"]
            if (len(visits) != len(ids) or any(type(n) is not int or n < 0 for n in visits)
                    or sum(visits) != 64 or any(p != n / 64 for p, n in zip(record["target"], visits))):
                raise ValueError("visit target mismatch")
        if "value" in record and (not math.isfinite(record["value"]) or abs(record["value"]) > 1.000001):
            raise ValueError("invalid recorded state value")
    wire = [line for line in evidence["snapshot"]["inputLog"] if line.startswith((">p1 ", ">p2 "))]
    if wire != commands:
        raise ValueError("recorded commands do not match actual simulator submissions")
    return row, evidence


def write_once(path, text):
    raw = text.encode() if isinstance(text, str) else text
    path = Path(path)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("immutable export differs: " + str(path))
    else:
        atomic_bytes(path, raw, exclusive=True)


def select_browser_sample(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["job"]["stage"], row["job"]["condition"])].append(row["job"]["slot_id"])
    groups = [sorted(values) for _, values in sorted(groups.items())]
    # Cover every populated stratum first; then add its last case up to the explicit cap.
    result = []
    for position in (0, -1):
        for group in groups:
            if group[position] not in result and len(result) < 12:
                result.append(group[position])
    return result


def finalize(directory, *, check=lambda: None, browser=True, export_root=None, protocol=None):
    directory = Path(directory).resolve()
    manifest = verify_identity(directory) if protocol is None else verify_identity(directory, protocol=protocol)
    schedule = read(directory / "schedule.json")
    games = []
    for path in sorted((directory / "games").glob("*/result.json")):
        check()
        games.append(load_result(path.parent))
    planned = [*schedule["pilot"], *schedule["test"],
               *[j for group in schedule["train"] for j in group],
               *[j for group in schedule["dev"].values() for j in group]]
    from .reporting import validate_results
    validate_results(planned, games)
    summary = report(schedule["test"], [r for r in games if r["job"]["stage"].startswith("test")])
    if manifest["protocol"]["experiment"] == "EX-078":
        summary["interpretation"] = "첫1라운드 체크포인트 진단; dev/test 및 정책 개선 미평가"
    gates = {}
    for name in ("verification.json", "pilot-gate.json"):
        gates[name] = (directory / name).exists() and read(directory / name).get("passed") is True
    lock_path = directory / "evaluation-lock.json"
    gates["evaluation_lock"] = lock_path.exists()
    lock = read(lock_path) if lock_path.exists() else None
    if lock:
        if (lock["identity"] != manifest["identity"] or lock["simulations"] != 64 or lock["temperature"] != 1
                or sha(directory / "schedule.json") != lock["schedule_sha256"]
                or sha(directory / "models/P0.pt") != lock["P0"]
                or sha(directory / lock["selected_file"]) != lock["P1"]):
            raise ValueError("evaluation identity/config/model changed")
    for row in games:
        if row["job"]["stage"].startswith("test") and row["status"] == "completed":
            if not lock or row.get("model_hashes") != {key: lock[key] for key in ("P0", "P1")}:
                raise ValueError("test result does not match the evaluation lock")
    stopping = None
    if manifest["protocol"]["experiment"] == "EX-079":
        from .stopping_finalize import stopping_evidence
        gates, stopping = stopping_evidence(directory, manifest, schedule, games, lock)
    result_key = digest([(r["job"]["slot_id"], r["files"], r["status"]) for r in games])[:12]
    export = Path(export_root) if export_root else ROOT / "exports/battle_viewers" / f"{manifest['protocol']['experiment'].lower().replace('-', '')}-{manifest['identity'][:8]}-{result_key}"
    if export_root is None:
        exported = read(directory / "exports.json") if (directory / "exports.json").exists() else []
        if str(export) not in exported:
            atomic(directory / "exports.json", [*exported, str(export)])
    links, completed, decision_count = [], [], 0
    for metadata in games:
        check()
        row, evidence = audit_game(directory / "games" / metadata["job"]["slot_id"])
        decision_count += len(row["records"])
        slot = row["job"]["slot_id"]
        protocol = "\n".join(evidence["public_log"]) if evidence else "공개 protocol 미확보"
        write_once(export / slot / "index.html", page(row, row["records"], protocol))
        write_once(export / slot / "replay.html", _replay_html({"battle_id": slot}, protocol))
        write_once(export / slot / "source.json", encoded(dict(
            original=str(directory / "games" / slot), source_files=row["files"],
            result_sha256=sha(directory / "games" / slot / "result.json"))))
        links.append(f'<li><a href="{html.escape(slot)}/index.html">{html.escape(slot)}</a> · {html.escape(row["status"])}</li>')
        if row["status"] == "completed":
            completed.append(metadata)
    write_once(export / "index.html", f'<!doctype html><html lang="ko"><meta charset="utf-8"><h1>{manifest["protocol"]["experiment"]} 고정 공개 상태</h1>'
               '<p>정책 입력·방문 분포·선택·공개 protocol은 오프라인이며 선택적 애니메이션은 외부 자산을 사용합니다.</p><ul>'
               + "".join(links) + "</ul></html>")
    write_once(export / "summary.json", encoded(summary))
    sample = select_browser_sample(completed)
    browser_result = dict(passed=False, status="not_run", sampled=sample)
    if browser and sample:
        check()
        task = directory / "final" / f"browser-task-{result_key}.json"
        write_once(task, encoded(dict(export=str(export), sample=sample)))
        environment = dict(__import__("os").environ, PYTHONPATH=str(ROOT))
        proc = subprocess.Popen([str(BROWSER_PYTHON), "-m", "integration.pokechamp.fixed_matchup.browser_check", str(task)],
                                cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            while proc.poll() is None:
                check()
                time.sleep(0.1)
            stdout, stderr = proc.communicate()
            if proc.returncode:
                raise RuntimeError("browser sample failed: " + stderr[-2000:])
            browser_result = json.loads(stdout)
        finally:
            if proc.poll() is None:
                import psutil
                children = psutil.Process(proc.pid).children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                proc.kill()
                proc.wait()
    audit = dict(passed=True, games=len(games), normal_games=len(completed),
                 decisions=decision_count, browser=browser_result)
    result = dict(summary=summary, audit=audit, gates=gates, viewer=str(export / "index.html"),
                  procedure_complete=summary["complete"] and browser_result["passed"] and all(gates.values()),
                  efficacy_success=summary["policy_improved"] and browser_result["passed"] and all(gates.values()))
    if stopping is not None:
        result["stopping"] = stopping
    if manifest["protocol"]["experiment"] == "EX-078":
        checkpoint_path = directory / "checkpoint-validation.json"
        checkpoint = read(checkpoint_path) if checkpoint_path.exists() else {}
        pointer = checkpoint.get("checkpoint", {})
        checkpoint_valid = (checkpoint.get("passed") is True and checkpoint.get("updates", 0) > 0
                            and pointer.get("round") == 1
                            and pointer.get("file") == "checkpoints/round-001.pt"
                            and (directory / "checkpoints/round-001.pt").is_file()
                            and (directory / "models/round-001.pt").is_file()
                            and pointer.get("sha256") == sha(directory / "checkpoints/round-001.pt")
                            and checkpoint.get("model_sha256") == sha(directory / "models/round-001.pt")
                            and checkpoint.get("p0_sha256") == sha(directory / "models/P0.pt"))
        diagnostic = (len(planned) == 32 and not schedule["pilot"] and not schedule["test"]
                      and not schedule["dev"] and len(schedule["train"]) == 1
                      and len(completed) == 32 and len(games) == 32
                      and all(r["job"]["stage"] == "train" and r["job"]["round_id"] == 1 for r in games)
                      and gates["verification.json"] and checkpoint_valid
                      and checkpoint.get("identity") == manifest["identity"]
                      and checkpoint.get("round") == 1 and browser_result["passed"])
        result.update(procedure_complete=bool(diagnostic), diagnostic_complete=bool(diagnostic),
                      efficacy_success=False, efficacy_evaluated=False)
        summary["interpretation"] = "첫1라운드 체크포인트 진단; dev/test 및 정책 개선 미평가"
    atomic(directory / "final/result.json", result)
    text = (f"# {manifest['protocol']['experiment']} 고정 공개 상태 결과\n\n"
            f"절차 완료: {result['procedure_complete']}. 정책 개선: {result['efficacy_success']}.\n\n"
            f"정상 {len(completed)}/{len(games)}경기, test 분모 {summary['total']}.\n\n"
            f"주 비교: {summary['contrasts']['P1-P0']}.\n\n"
            f"[뷰어]({export / 'index.html'}). 브라우저는 최대12경기 표본이며 전수 검증이 아니다.\n\n"
            "공개 상태·고정 두 팀·한 학습 seed에 한정한다. 일반 비공개 Gen9 OU 효능은 미평가다.\n")
    if manifest["protocol"]["experiment"] == "EX-078":
        text = ("# EX-078 첫1라운드 체크포인트 진단\n\n"
                f"체크포인트 진단 완료: {result['procedure_complete']}. 정상 {len(completed)}/{len(planned)}경기.\n\n"
                "dev/test는 실행하지 않았으며 정책 개선은 미평가다.\n\n"
                f"[검증](../checkpoint-validation.json) · [뷰어]({export / 'index.html'}).\n"
                "브라우저는 정상 경기 첫/마지막 표본이며 전수 검증은 원자료 감사에 한정한다.\n")
    if stopping is not None:
        text += (f"\n학습 종료: {stopping['stop']}.\n\n"
                 f"개발 평가 곡선: {stopping['development']}.\n\n"
                 f"초기 모델 직접 대결 점수: {stopping.get('direct_score', '미완료')}.\n\n"
                 f"부모 계승32경기, 이번 새 수집 {stopping['new_games']}경기. "
                 "개발 목표 달성·정체·학습량 종료는 독립 효능 판정과 구분한다.\n")
    atomic_bytes(directory / "final/report.md", text.encode())
    # Seal immutable source/data/results explicitly; mutable resource/clock/control journals are excluded and named.
    folders = ["teams", "source", "models", "games", "checkpoints", "final"]
    if stopping is not None:
        folders += ["dev", "checkpoint-validation", "training"]
    files = [p for folder in folders
             for p in (directory / folder).rglob("*") if p.is_file()]
    files += [directory / name for name in ("manifest.json", "schedule.json", "catalog.json", "evaluation-lock.json", "checkpoint-validation.json", "first-round-inheritance.json")
              if (directory / name).exists()]
    if stopping is not None:
        files += [directory / name for name in ("inheritance.json", "checkpoint-inheritance.json",
                  "training-stop.json", "selection.json", "verification.json") if (directory / name).exists()]
    atomic_bytes(directory / "evidence.sha256", "".join(f"{sha(p)}  {p.relative_to(directory)}\n" for p in sorted(files)).encode())
    write_once(export / "checksums.sha256", "".join(f"{sha(p)}  {p.relative_to(export)}\n"
               for p in sorted(export.rglob("*")) if p.is_file() and p.name != "checksums.sha256"))
    if export_root is None:
        index = export.parent / "index.html"
        old = index.read_text() if index.exists() else '<!doctype html><meta charset="utf-8"><h1>배틀 실험 뷰어</h1>'
        link = f'<p><a href="{export.name}/index.html">{manifest["protocol"]["experiment"]} 고정 공개 상태 · {result_key}</a></p>'
        if link not in old:
            atomic_bytes(index, (old + "\n" + link + "\n").encode())
    return result
