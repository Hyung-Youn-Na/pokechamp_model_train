"""Regenerate static battle views and experiment catalogs from source evidence."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .issues import LABELS, decorate, load_annotations
from .issues import counts as issue_counts
from .recorder import (
    EVENT_TYPES,
    SCHEMA_VERSION,
    DataRootError,
    _atomic_private_write,
    validate_identifier,
    verify_bundle,
)

_REPORT_SCRIPT = """(() => {
const navigation = document.getElementById('turn-navigation');
const panels = Array.from(document.querySelectorAll('.turn-panel'));
if (!panels.length) return;
const tabs = Array.from(navigation.querySelectorAll('[role="tab"]'));
const select = document.getElementById('turn-select');
const previous = document.getElementById('turn-previous');
const next = document.getElementById('turn-next');
let selected = 0;
function show(index) {
  selected = index;
  panels.forEach((panel, i) => { panel.hidden = i !== index; });
  tabs.forEach((tab, i) => {
    tab.setAttribute('aria-selected', String(i === index));
    tab.tabIndex = i === index ? 0 : -1;
  });
  select.value = String(index);
  previous.disabled = index === 0;
  next.disabled = index === panels.length - 1;
  const strip = tabs[index].parentElement;
  const tab = tabs[index];
  if (tab.offsetLeft < strip.scrollLeft) strip.scrollLeft = tab.offsetLeft;
  else if (tab.offsetLeft + tab.offsetWidth > strip.scrollLeft + strip.clientWidth) {
    strip.scrollLeft = tab.offsetLeft + tab.offsetWidth - strip.clientWidth;
  }
}
function restore() {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { id = ''; }
  const target = id ? document.getElementById(id) : null;
  const panel = target && target.closest('.turn-panel');
  // Global protocol links keep the current turn. An empty/unknown URL uses the first.
  show(panel ? panels.indexOf(panel) : target ? selected : 0);
  if (target) {
    for (let node = target.parentElement; node; node = node.parentElement) {
      if (node.tagName === 'DETAILS') node.open = true;
    }
    target.scrollIntoView({block: 'start'});
  }
}
function navigate(index, focusTab = false) {
  const hash = '#' + panels[index].id;
  if (location.hash !== hash) history.pushState(null, '', hash);
  show(index);
  navigation.scrollIntoView({block: 'start'});
  if (focusTab) tabs[index].focus({preventScroll: true});
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => navigate(index));
  tab.addEventListener('keydown', event => {
    let indexToSelect;
    if (event.key === 'ArrowRight') indexToSelect = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') indexToSelect = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') indexToSelect = 0;
    if (event.key === 'End') indexToSelect = tabs.length - 1;
    if (indexToSelect !== undefined) {
      event.preventDefault();
      navigate(indexToSelect, true);
    }
  });
});
select.addEventListener('change', () => navigate(Number(select.value)));
previous.addEventListener('click', () => navigate(Math.max(0, selected - 1)));
next.addEventListener('click', () => navigate(Math.min(panels.length - 1, selected + 1)));
window.addEventListener('hashchange', restore);
window.addEventListener('popstate', restore);
// Repeated clicks on the current fragment must also reveal/scroll the target.
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (link && link.hash === location.hash) {
    event.preventDefault();
    restore();
  }
});
panels.forEach((panel, i) => {
  panel.setAttribute('role', 'tabpanel');
  panel.setAttribute('aria-labelledby', tabs[i].id);
  panel.tabIndex = 0;
});
navigation.hidden = false;
restore();
})();"""

_REPORT_SCRIPT_HASH = base64.b64encode(
    hashlib.sha256(_REPORT_SCRIPT.encode()).digest()
).decode()

_REPORT_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    f"script-src 'sha256-{_REPORT_SCRIPT_HASH}'; frame-src 'self' file:; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)
_REPLAY_CSP = (
    "default-src 'none'; script-src https://play.pokemonshowdown.com; "
    "style-src 'unsafe-inline' https://play.pokemonshowdown.com; "
    "img-src data: https://play.pokemonshowdown.com; "
    "font-src https://play.pokemonshowdown.com; connect-src 'none'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _pretty(value: Any) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    return _e(text)


def _load_manifest(bundle: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        value = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {}, [f"manifest.json: {type(error).__name__}"]
    if not isinstance(value, dict):
        return {}, ["manifest.json: root must be an object"]
    if value.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported manifest schema_version {value.get('schema_version')!r}")
    return value, errors


def _load_events(bundle: Path) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = (bundle / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        return [], [f"events.jsonl: {type(error).__name__}"]
    previous_seq = 0
    required = {
        "schema_version",
        "experiment_id",
        "battle_id",
        "event_type",
        "event_seq",
        "timestamp_utc",
        "monotonic_offset_ms",
    }
    for line_number, line in enumerate(lines, 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"events.jsonl line {line_number}: invalid JSON")
            continue
        if not isinstance(event, dict):
            errors.append(f"events.jsonl line {line_number}: event must be an object")
            continue
        missing = sorted(required - event.keys())
        if missing:
            errors.append(
                f"events.jsonl line {line_number}: missing {', '.join(missing)}"
            )
        event_type = event.get("event_type")
        if event_type not in EVENT_TYPES:
            errors.append(
                f"events.jsonl line {line_number}: unsupported event_type {event_type!r}"
            )
        event_seq = event.get("event_seq")
        if not isinstance(event_seq, int) or event_seq <= previous_seq:
            errors.append(f"events.jsonl line {line_number}: event_seq is not increasing")
        elif event_seq != previous_seq + 1:
            errors.append(
                f"events.jsonl line {line_number}: event_seq gap after {previous_seq}"
            )
        if isinstance(event_seq, int):
            previous_seq = event_seq
        events.append(event)
    return events, errors


def _showdown_log(
    events: list[dict[str, Any]], manifest: dict[str, Any]
) -> str:
    header: str | None = None
    lines: list[str] = []
    for event in events:
        protocol = event.get("protocol")
        if event.get("event_type") != "protocol_in" or not isinstance(protocol, str):
            continue
        for line in protocol.splitlines():
            if line.startswith(">battle-"):
                header = header or line
            elif line:
                lines.append(line)
    if header is None and manifest.get("showdown_battle_tag"):
        header = f">{manifest['showdown_battle_tag']}"
    combined = ([header] if header else []) + lines
    return "\n".join(combined) + ("\n" if combined else "")


def _players(protocol: str, manifest: dict[str, Any]) -> tuple[str, str]:
    found: dict[str, str] = {}
    for line in protocol.splitlines():
        fields = line.split("|")
        if len(fields) >= 4 and fields[1] == "player" and fields[2] in {"p1", "p2"}:
            found[fields[2]] = fields[3]
    team_names = [
        str(team.get("username", ""))
        for team in manifest.get("teams", [])
        if isinstance(team, dict) and team.get("username")
    ]
    return (
        found.get("p1") or (team_names[0] if team_names else "Player 1"),
        found.get("p2") or (team_names[1] if len(team_names) > 1 else "Player 2"),
    )


def _replay_html(manifest: dict[str, Any], protocol: str) -> str:
    battle_tag = manifest.get("showdown_battle_tag") or manifest.get("battle_id", "battle")
    player, opponent = _players(protocol, manifest)
    # Escaping inside text/plain is still mandatory: an unescaped closing script tag
    # would terminate this element before the browser decides it is non-executable.
    protocol_data = html.escape(protocol, quote=False)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{_e(_REPLAY_CSP)}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Showdown replay — {_e(battle_tag)}</title>
<style>
body{{font:15px system-ui,sans-serif;margin:0;background:#eef2f7;color:#172033}}
main{{max-width:1180px;margin:auto;padding:1rem}} .replay-wrapper{{min-height:420px}}
.battle-log-data{{display:none}}
details{{margin-top:1rem;background:white;padding:1rem;border-radius:8px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}}
.offline{{padding:.75rem;background:#fff7d6;border-left:4px solid #d89b00}}
main:target{{padding:0}}
main:target>h1,main:target>p{{display:none}}
</style></head><body><main id="embedded">
<h1>Showdown replay</h1><p>{_e(player)} vs. {_e(opponent)} · {_e(battle_tag)}</p>
<p class="offline">The animated panel uses the official Pokémon Showdown replay asset.
If it is unavailable, the Static protocol fallback below remains fully local.</p>
<div class="wrapper replay-wrapper">
  <input type="hidden" name="replayid" value="{_e(battle_tag)}">
  <div class="battle"></div><div class="battle-log"></div>
  <div class="replay-controls"></div><div class="replay-controls-2"></div>
  <script type="text/plain" class="battle-log-data">{protocol_data}</script>
</div>
<details open><summary>Static protocol fallback</summary><pre>{protocol_data}</pre></details>
<script defer src="https://play.pokemonshowdown.com/js/replay-embed.js"></script>
</main></body></html>
"""


def _group_decisions(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    by_id: dict[int, dict[str, Any]] = {}
    unassigned_protocol: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for event in events:
        event_type = event.get("event_type")
        if event_type == "decision_start":
            current = {
                "start": event,
                "calls": [],
                "input_snapshots": [],
                "observation_snapshots": [],
                "results": [],
                "wires": [],
                "following": [],
            }
            decisions.append(current)
            decision_seq = event.get("decision_seq")
            if isinstance(decision_seq, int):
                by_id[decision_seq] = current
        elif event_type in {"llm_call", "decision_result", "wire_action", "input_snapshot", "observation_snapshot"}:
            decision = by_id.get(event.get("decision_seq"))
            if decision is not None:
                key = {
                    "llm_call": "calls",
                    "input_snapshot": "input_snapshots",
                    "observation_snapshot": "observation_snapshots",
                    "decision_result": "results",
                    "wire_action": "wires",
                }[event_type]
                decision[key].append(event)
        elif event_type == "protocol_in":
            if current is not None and current["wires"]:
                current["following"].append(event)
            else:
                unassigned_protocol.append(event)
    return decisions, unassigned_protocol


def _unique_id(preferred: str, used: set[str]) -> str:
    candidate = preferred
    suffix = 2
    while candidate in used:
        candidate = f"{preferred}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _protocol_block(
    event: dict[str, Any], used: set[str], prefix: str = "event"
) -> str:
    anchor = _unique_id(f"{prefix}-{event.get('event_seq')}", used)
    return (
        f'<article class="protocol" id="{_e(anchor)}">'
        f'<h4>Event {_e(event.get("event_seq"))} · turn '
        f'{_e(event.get("showdown_turn"))}</h4>'
        f'<pre>{_e(event.get("protocol", ""))}</pre></article>'
    )


def _decision_card(decision: dict[str, Any], used: set[str] | None = None) -> str:
    if used is None:
        used = set()
    start = decision["start"]
    anchor = decision.get("html_id") or _unique_id(
        f"decision-{start.get('decision_seq')}", used
    )
    issue_anchor = decision.get("issue_anchor")
    issue_marker = f'<span id="{_e(issue_anchor)}"></span>' if issue_anchor else ""
    badges = " ".join(f'<span class="issue issue-{_e(k)}">{LABELS[k]}</span>'
                      for k in decision.get("issues", []))
    reviews = decision.get("explanation_reviews", [])
    review_html = (f'<h4>설명 검토</h4><pre>{_pretty(reviews)}</pre>' if reviews else "")
    calls = decision["calls"]
    results = decision["results"]
    wires = decision["wires"]
    following = decision["following"]
    final_call = calls[-1] if calls else {}
    final_result = results[-1] if results else {}
    output = final_result.get(
        "canonical_parsed_output", final_call.get("canonical_parsed_output")
    )
    validation = final_result.get("validation") or final_call.get("validation") or {}
    lead_html = ""
    if start.get("decision_kind") == "team_preview" and final_call.get("request", {}).get("call_role") == "team_preview":
        lead_html = (
            '<section class="lead-selection"><h4>선봉 선택 · 제출 슬롯</h4>'
            f'<pre>{_pretty(output)}</pre><p>후보 ID는 자기 팀의 실제 제출 슬롯(1–6)입니다. '
            '실제 전송과 성공 여부는 Actual wire action에서 확인합니다.</p></section>'
        )
    wire_text = "\n".join(
        f"{wire.get('action', '')} [{wire.get('send_status', 'unknown')}]"
        for wire in wires
    ) or "No wire action recorded"
    originals = "".join(
        "<details><summary>검증용 원본 입력 · 실제 전송 입력은 위 LLM call 참조</summary>"
        + f"<pre>{_pretty(snapshot)}</pre></details>"
        for snapshot in decision.get("input_snapshots", [])
    )
    originals += "".join(
        "<details><summary>공식 관측 · 수신 행 경계 · 계산 전 정규화</summary>"
        + f"<pre>{_pretty(snapshot)}</pre></details>"
        for snapshot in decision.get("observation_snapshots", [])
    )
    call_details = []
    for call in calls:
        prompt_versions = {
            key: call.get("request", {}).get(key)
            for key in (
                "battle_prompt_identity", "team_preview_prompt_identity", "delivery_identity"
            )
            if call.get("request", {}).get(key) is not None
        }
        call_details.append(
            f"""<article class="llm-call">
<h4>LLM call {_e(call.get('llm_call_seq'))} · {_e(call.get('status'))}</h4>
<p>최종 요청 결과: {_e(call.get('status'))} · HTTP 시도: {_e(call.get('request', {}).get('http_attempt_count', 1 if call.get('response', {}).get('network_called') else 0))}</p>
<details><summary>HTTP 시도별 결과 · 연결 재시도</summary><pre>{_pretty(call.get('request', {}).get('http_attempts', []))}</pre></details>
<h5>Provider reasoning</h5>
<pre class="llm-response">{_e(call.get('provider_reasoning') or '기록된 reasoning 없음')}</pre>
<h5>Raw response content</h5>
<pre class="llm-response">{_e(call.get('raw_content') or '기록된 응답 없음')}</pre>
<details><summary>Effective system / user prompt · 실제 전송 입력</summary>
<h5>프롬프트·효과 사전 identity</h5><pre>{_pretty(prompt_versions)}</pre>
<h5>Effective system prompt</h5><pre>{_e(call.get('system_prompt', ''))}</pre>
<h5>Effective user prompt</h5><pre>{_e(call.get('user_prompt', ''))}</pre></details>
<h5>모델에서 추출한 행동</h5><pre>{_pretty(call.get('canonical_parsed_output'))}</pre>
<h5>출력 판정 · 선택 출처 · 실행할 행동</h5><pre>{_pretty(call.get('validation', {}).get('action_resolution'))}</pre>
<details><summary>Request / response metadata · Validation</summary>
<div class="pair"><section><h5>Request metadata</h5>
<pre>{_pretty(call.get('request', {}))}</pre></section>
<section><h5>Response / token / latency metadata</h5>
<pre>{_pretty(call.get('response', {}))}</pre></section></div>
<h5>Validation</h5><pre>{_pretty(call.get('validation', {}))}</pre>
<h5>전체 호출 기록</h5><pre>{_pretty(call)}</pre></details></article>"""
        )
    followup = "".join(_protocol_block(event, used) for event in following)
    if not followup:
        followup = "<p>No subsequent protocol event was recorded before the next decision.</p>"
    return f"""<article class="decision" id="{_e(anchor)}">
{issue_marker}
<h3>Decision {_e(start.get('decision_seq'))}</h3>
<p>{badges}</p>{review_html}
<p class="meta">Turn {_e(start.get('showdown_turn'))} · {_e(start.get('decision_kind'))}</p>
{lead_html}
{''.join(call_details) or '<p class="no-calls">기록된 LLM 호출 없음</p>'}
<div class="pair"><section><h4>Battle state</h4>
<pre>{_pretty(start.get('battle_state', {}))}</pre></section>
<section><h4>Final parsed output</h4><pre>{_pretty(output)}</pre>
<h4>Validation</h4><pre>{_pretty(validation)}</pre>
<h4>Actual wire action</h4><pre>{_e(wire_text)}</pre></section></div>
{originals}
<details open><summary>Subsequent Showdown events</summary>{followup}</details>
</article>"""


def _report_html(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    errors: list[str],
    verification: dict[str, Any],
    annotations=None,
) -> str:
    decisions, initial_protocol = _group_decisions(events)
    decorate(decisions, manifest, annotations or {})
    used: set[str] = set()
    for decision in decisions:
        decision["html_id"] = _unique_id(
            f"decision-{decision['start'].get('decision_seq')}", used
        )
        decision["issue_anchor"] = _unique_id(decision["issue_anchor"], used)
    problems = issue_counts(decisions)
    problem_links = "".join(
        f'<li><a href="#{_e(d["issue_anchor"])}">Turn {_e(d["start"].get("showdown_turn"))}'
        f' · Decision {_e(d["start"].get("decision_seq"))}</a> · '
        + " / ".join(LABELS[k] for k in d["issues"]) + "</li>"
        for d in decisions if d["issues"])
    status = ("완료" if manifest.get("result", {}).get("outcome")
              in ("player_won", "player_lost", "tied") else "실패 / 미완료")
    incomplete = (
        bool(errors)
        or not verification["valid"]
        or not manifest.get("evidence_complete", False)
    )
    warnings_list = [*verification.get("errors", []), *errors]
    warning_html = ""
    if incomplete:
        items = "".join(f"<li>{_e(item)}</li>" for item in warnings_list)
        if not items:
            items = "<li>Manifest marks evidence_complete=false.</li>"
        warning_html = (
            '<section class="warning"><h2>Partial or invalid evidence</h2>'
            f"<ul>{items}</ul></section>"
        )
    result = manifest.get("result", {}) if isinstance(manifest.get("result"), dict) else {}
    initial = "".join(_protocol_block(event, used) for event in initial_protocol)
    groups: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        start = decision["start"]
        turn = start.get("showdown_turn")
        if start.get("decision_kind") == "team_preview":
            label = "준비"
        elif turn is None:
            label = "턴 미상"
        else:
            label = f"턴 {turn}"
        groups.setdefault(label, []).append(decision)
    panels, tabs, options = [], [], []
    for index, (label, group) in enumerate(groups.items()):
        panel_id = f"viewer-turn-{index + 1}"
        tab_id = f"viewer-tab-{index + 1}"
        tabs.append(
            f'<button type="button" role="tab" id="{tab_id}" '
            f'aria-controls="{panel_id}" aria-selected="false" tabindex="-1">'
            f'{_e(label)} · {len(group)}</button>'
        )
        options.append(f'<option value="{index}">{_e(label)} · {len(group)}결정</option>')
        panels.append(
            f'<section class="turn-panel" id="{panel_id}"><h3>{_e(label)}</h3>'
            + "".join(_decision_card(decision, used) for decision in group)
            + '</section>'
        )
    cards = "".join(panels)
    navigation = (
        '<div id="turn-navigation" hidden>'
        '<div role="tablist" aria-label="결정 턴" class="turn-tabs">'
        + "".join(tabs) + '</div><div class="turn-controls">'
        '<label for="turn-select">턴 바로가기</label><select id="turn-select">'
        + "".join(options) + '</select>'
        '<button type="button" id="turn-previous">이전</button>'
        '<button type="button" id="turn-next">다음</button></div></div>'
    )
    timeline = "".join(
        _protocol_block(event, used, "timeline-event")
        for event in events
        if event.get("event_type") == "protocol_in"
    )
    if not cards:
        cards = "<p>No valid decision_start event was available.</p>"
    if not timeline:
        timeline = "<p>No protocol events were available.</p>"
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{_e(_REPORT_CSP)}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Battle report — {_e(manifest.get('battle_id', 'unknown'))}</title>
<style>
:root{{--ink:#172033;--muted:#5d687a;--paper:#fff;--bg:#eef2f7;--line:#ccd5e2;--accent:#2856a3}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1900px;margin:auto;padding:1.25rem}}a{{color:var(--accent)}}
.review-layout{{display:grid;grid-template-columns:minmax(0,1fr) 660px;gap:1.25rem}}
.review-content{{min-width:0;overflow-wrap:anywhere}}
[hidden]{{display:none!important}}
#turn-navigation{{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;scroll-margin-top:1rem}}
.turn-tabs{{position:relative;display:flex;flex:1 1 18rem;min-width:0;gap:.4rem;overflow-x:auto;padding:.4rem 0}}
.turn-tabs button{{flex-shrink:0}}
button,select{{font:inherit;padding:.5rem;border:1px solid var(--line);border-radius:6px}}
button{{cursor:pointer;background:var(--paper);color:var(--ink)}}
button:disabled{{cursor:default;opacity:.5}}
button[aria-selected="true"]{{background:var(--accent);color:white}}
:focus-visible{{outline:3px solid #a65300;outline-offset:3px}}
.turn-controls{{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem}}
.turn-controls select{{max-width:100%;min-width:0}}
.turn-panel,.decision,.decision>span[id],.protocol{{scroll-margin-top:1rem}}
.llm-call{{border:1px solid var(--line);border-radius:8px;padding:1rem;margin:1rem 0}}
pre.llm-response{{max-height:none;overflow:visible}}
.replay-panel{{position:sticky;top:1rem;align-self:start;height:calc(100vh - 2rem)}}
.replay-panel{{display:flex;flex-direction:column;background:white;border:1px solid var(--line)}}
.replay-panel{{border-radius:10px;overflow:hidden}}
.replay-panel header{{padding:.75rem 1rem;border-bottom:1px solid var(--line)}}
.replay-panel h2{{font-size:1rem;margin:0 0 .25rem}}
.replay-panel iframe{{width:100%;flex:1;min-height:0;border:0}}
@media(max-width:1200px){{
 .review-layout{{display:flex;flex-direction:column}}
 .replay-panel{{order:-1;width:100%;height:45vh;top:0;z-index:2;flex-shrink:0}}
 #turn-navigation,.turn-panel,.decision,.decision>span[id],.protocol{{scroll-margin-top:calc(45vh + 1rem)}}
}}
.summary,.decision,.protocol,.warning{{background:var(--paper);border:1px solid var(--line)}}
.summary,.decision,.protocol,.warning{{border-radius:10px;padding:1rem;margin:1rem 0}}
.decision{{border-left:5px solid var(--accent)}}
.issue{{display:inline-block;padding:.2rem .5rem;margin:.15rem;border-radius:4px;font-weight:650}}
.issue-output_format,.issue-execution{{color:#8c201a;background:#ffe4df}}
.issue-extracted_action{{color:#164a85;background:#dceeff}}
.issue-fallback{{color:#754200;background:#fff0c2}}
.issue-explanation{{color:#67236b;background:#f4def7}}
.warning{{border-left:5px solid #b13a2e;background:#fff5f3}}
.meta{{color:var(--muted)}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9fc}}
pre{{border:1px solid #e1e7ef;border-radius:6px;padding:.75rem;max-height:34rem;overflow:auto}}
details{{margin:.75rem 0;border-top:1px solid var(--line);padding-top:.6rem}}
summary{{cursor:pointer;font-weight:650}}
nav a{{margin-right:1rem}}@media(max-width:1200px){{.pair{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="review-layout"><div class="review-content">
<h1>PokéChamp battle report</h1>
<nav><a href="../../index.html">Battle catalog</a>
<a href="replay.html" target="_blank" rel="noopener">Animation replay</a>
<a href="showdown.log">Raw Showdown log</a></nav>
{warning_html}
<section class="summary"><h2>Battle summary</h2>
<div class="pair"><section><dl>
<dt>Experiment</dt><dd>{_e(manifest.get('experiment_id'))}</dd>
<dt>Battle</dt><dd>{_e(manifest.get('battle_id'))}</dd>
<dt>Showdown room</dt><dd>{_e(manifest.get('showdown_battle_tag'))}</dd>
<dt>Format</dt><dd>{_e(manifest.get('battle_format'))}</dd>
<dt>Started</dt><dd>{_e(manifest.get('started_at'))}</dd>
<dt>Ended</dt><dd>{_e(manifest.get('ended_at'))}</dd>
<dt>Outcome</dt><dd>{_e(result.get('outcome'))}</dd>
<dt>Evidence complete</dt><dd>{_e(manifest.get('evidence_complete'))}</dd>
<dt>Checksum integrity</dt><dd>{'valid' if verification['valid'] else 'invalid'}</dd>
</dl></section><section><h3>Model configuration</h3><pre>{_pretty(manifest.get('model', {}))}</pre>
<h3>Result</h3><pre>{_pretty(result)}</pre></section></div></section>
<section class="summary"><h2>문제 목록</h2><p>{status} · 문제 턴 {problems['problem_turns']} · 문제 결정 {problems['problem_decisions']}</p>
<ul>{problem_links or '<li>표시된 문제 없음 (설명 검토 상태는 각 결정 참조)</li>'}</ul></section>
<section><h2>Decision review</h2>{navigation}{cards}</section>
<section><h2>Protocol before first action</h2>{initial or '<p>None.</p>'}</section>
<details id="complete-timeline"><summary>Complete static turn timeline · 전체 protocol</summary>{timeline}</details>
</div><aside class="replay-panel" aria-label="Persistent animation replay">
<header><h2>Animation replay</h2>
<a href="replay.html" target="_blank" rel="noopener">Open full replay</a>
 · Scroll the decisions while the replay stays here.</header>
<iframe src="replay.html#embedded" title="Pokémon Showdown animation replay"
 sandbox="allow-scripts" referrerpolicy="no-referrer"></iframe>
</aside></div>
<script>{_REPORT_SCRIPT}</script>
</main></body></html>
"""


def rebuild_battle(bundle_path: str | os.PathLike[str]) -> dict[str, Any]:
    bundle = Path(bundle_path).resolve()
    if not bundle.is_dir():
        raise DataRootError(f"battle bundle is not a directory: {bundle}")
    manifest, manifest_errors = _load_manifest(bundle)
    events, event_errors = _load_events(bundle)
    verification = verify_bundle(bundle)
    try:
        annotations = load_annotations(bundle, manifest)
    except (ValueError, OSError, KeyError) as exc:
        annotations = {}
        event_errors.append(f"annotation integrity: {type(exc).__name__}")
    decisions, _ = _group_decisions(events)
    decorate(decisions, manifest, annotations)
    protocol = _showdown_log(events, manifest)
    _atomic_private_write(bundle / "showdown.log", protocol)
    _atomic_private_write(bundle / "replay.html", _replay_html(manifest, protocol))
    _atomic_private_write(
        bundle / "report.html",
        _report_html(
            manifest,
            events,
            [*manifest_errors, *event_errors],
            verification,
            annotations,
        ),
    )
    return {
        "bundle": str(bundle),
        **issue_counts(decisions),
        "integrity_valid": verification["valid"],
        "evidence_complete": bool(manifest.get("evidence_complete", False)),
        "event_count": len(events),
        "errors": [*verification["errors"], *manifest_errors, *event_errors],
    }


def _catalog_record(bundle: Path, render_result: dict[str, Any]) -> dict[str, Any]:
    manifest, errors = _load_manifest(bundle)
    model_value = manifest.get("model", {})
    if isinstance(model_value, dict):
        provider = model_value.get("provider")
        model_name = model_value.get("model") or model_value.get("name")
        model = "/".join(str(value) for value in (provider, model_name) if value)
    else:
        model = str(model_value)
    result = manifest.get("result", {})
    if not isinstance(result, dict):
        result = {}
    checksum_valid = bool(render_result.get("integrity_valid"))
    evidence_complete = (
        bool(manifest.get("evidence_complete"))
        and checksum_valid
        and not render_result.get("errors")
        and not errors
    )
    return {
        "experiment_id": str(manifest.get("experiment_id") or bundle.parent.parent.name),
        "battle_id": str(manifest.get("battle_id") or bundle.name),
        "started_at": manifest.get("started_at"),
        "ended_at": manifest.get("ended_at"),
        "model": model,
        "result": result.get("outcome"),
        "battle_format": manifest.get("battle_format"),
        "evidence_complete": int(evidence_complete),
        "checksum_valid": int(checksum_valid),
        "schema_version": manifest.get("schema_version"),
        "bundle_name": bundle.name,
        "problem_turns": render_result.get("problem_turns", 0),
        "problem_decisions": render_result.get("problem_decisions", 0),
        "errors": [*render_result.get("errors", []), *errors],
    }


def _write_catalog(experiment: Path, records: list[dict[str, Any]]) -> None:
    target = experiment / "catalog.sqlite"
    temporary = experiment / f".catalog.{uuid.uuid4().hex}.tmp"
    try:
        with sqlite3.connect(temporary) as database:
            database.executescript(
                """
                PRAGMA journal_mode=DELETE;
                CREATE TABLE battles (
                    experiment_id TEXT NOT NULL,
                    battle_id TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    model TEXT,
                    result TEXT,
                    battle_format TEXT,
                    evidence_complete INTEGER NOT NULL,
                    checksum_valid INTEGER NOT NULL,
                    schema_version INTEGER,
                    bundle_path TEXT NOT NULL,
                    errors_json TEXT NOT NULL,
                    PRIMARY KEY (experiment_id, battle_id)
                );
                CREATE INDEX battles_date_idx ON battles(started_at);
                CREATE INDEX battles_filter_idx
                    ON battles(model, result, battle_format, evidence_complete);
                """
            )
            database.executemany(
                """
                INSERT INTO battles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record["experiment_id"],
                        record["battle_id"],
                        record["started_at"],
                        record["ended_at"],
                        record["model"],
                        record["result"],
                        record["battle_format"],
                        record["evidence_complete"],
                        record["checksum_valid"],
                        record["schema_version"],
                        f"battles/{record['bundle_name']}",
                        json.dumps(record["errors"], ensure_ascii=False),
                    )
                    for record in records
                ],
            )
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


_CATALOG_SCRIPT = """const ids=[
'date','experiment','model','result','format','completeness'];
const inputs=Object.fromEntries(
ids.map(id=>[id,document.getElementById('filter-'+id)]));
function apply(){for(const row of document.querySelectorAll('tbody tr')){let show=true;
for(const id of ids){const wanted=inputs[id].value.trim().toLowerCase();
if(wanted&&!String(row.dataset[id]||'').toLowerCase().includes(wanted)){show=false;break;}}
row.hidden=!show;}}
for(const input of Object.values(inputs)){
input.addEventListener('input',apply);
input.addEventListener('change',apply);}"""


def _index_html(experiment_id: str, records: list[dict[str, Any]]) -> str:
    digest = base64.b64encode(hashlib.sha256(_CATALOG_SCRIPT.encode()).digest()).decode()
    csp = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        f"script-src 'sha256-{digest}'; img-src data:; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    rows = []
    for record in records:
        completeness = "complete" if record["evidence_complete"] else "incomplete"
        href = f"battles/{quote(record['bundle_name'], safe='')}/report.html"
        date = str(record["started_at"] or "")
        rows.append(
            f"""<tr data-date="{_e(date)}" data-experiment="{_e(record['experiment_id'])}"
data-model="{_e(record['model'])}" data-result="{_e(record['result'])}"
data-format="{_e(record['battle_format'])}" data-completeness="{completeness}">
<td><a href="{_e(href)}">{_e(record['battle_id'])}</a></td><td>{_e(date)}</td>
<td>{_e(record['experiment_id'])}</td><td>{_e(record['model'])}</td>
<td>{_e(record['result'])}<br>{'완료' if record['result'] in ('player_won', 'player_lost', 'tied') else '실패 / 미완료'}</td>
<td>{_e(record.get('problem_turns', 0))}턴 / {_e(record.get('problem_decisions', 0))}결정</td><td>{_e(record['battle_format'])}</td>
<td>{completeness}</td><td>{'valid' if record['checksum_valid'] else 'invalid'}</td></tr>"""
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{_e(csp)}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Battle catalog — {_e(experiment_id)}</title><style>
body{{font:15px system-ui,sans-serif;margin:0;background:#eef2f7;color:#172033}}
main{{max-width:1300px;margin:auto;padding:1.25rem}}
.filters{{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;background:white;padding:1rem;border-radius:9px}}
label{{display:grid;gap:.25rem}}input,select{{font:inherit;padding:.45rem}}table{{width:100%;border-collapse:collapse;background:white;margin-top:1rem}}
th,td{{padding:.6rem;text-align:left;border-bottom:1px solid #d8e0ea}}
th{{position:sticky;top:0;background:#e5ebf3}}tr[hidden]{{display:none}}
@media(max-width:760px){{.filters{{grid-template-columns:1fr}}.table-wrap{{overflow-x:auto}}}}
</style></head><body><main><h1>Battle catalog</h1><p>Experiment: {_e(experiment_id)}</p>
<section class="filters">
<label>Date <input id="filter-date" type="search"></label>
<label>Experiment <input id="filter-experiment" type="search" value=""></label>
<label>Model <input id="filter-model" type="search"></label>
<label>Result <input id="filter-result" type="search"></label>
<label>Battle format <input id="filter-format" type="search"></label>
<label>Completeness <select id="filter-completeness"><option value="">all</option>
<option>complete</option><option>incomplete</option></select></label>
</section><div class="table-wrap"><table><thead><tr>
<th>Battle</th><th>Date</th><th>Experiment</th><th>Model</th>
<th>Result / 상태</th><th>문제 턴 / 결정</th><th>Format</th><th>Evidence</th><th>Checksum</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div><script>{_CATALOG_SCRIPT}</script></main></body></html>"""


def rebuild_experiment(
    data_root: str | os.PathLike[str], experiment_id: str
) -> dict[str, Any]:
    validate_identifier(experiment_id, "experiment_id")
    experiment = Path(data_root).expanduser().resolve() / "experiments" / experiment_id
    battles = experiment / "battles"
    if not battles.is_dir() or battles.is_symlink():
        raise DataRootError(f"research experiment has no safe battles directory: {experiment_id}")
    records: list[dict[str, Any]] = []
    for bundle in sorted(battles.iterdir(), key=lambda path: path.name):
        if not bundle.is_dir() or bundle.is_symlink():
            continue
        try:
            render_result = rebuild_battle(bundle)
        except Exception as error:
            render_result = {
                "integrity_valid": False,
                "evidence_complete": False,
                "errors": [f"render failed: {type(error).__name__}"],
            }
        records.append(_catalog_record(bundle, render_result))
    _write_catalog(experiment, records)
    _atomic_private_write(experiment / "index.html", _index_html(experiment_id, records))
    return {
        "experiment_id": experiment_id,
        "battle_count": len(records),
        "complete_count": sum(record["evidence_complete"] for record in records),
        "catalog": str(experiment / "catalog.sqlite"),
        "index": str(experiment / "index.html"),
    }
