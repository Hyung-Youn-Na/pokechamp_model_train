"""EP-055 actor-local, decision-boundary tracker comparison (no model calls)."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import logging
import re
import selectors
import subprocess
from collections import Counter
from pathlib import Path

from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.diagnostics.ex042_public_facts import PublicFacts, ident, token
from integration.pokechamp.improved_io import state
from integration.pokechamp.improved_io.delivery.exclusions import prune
from integration.pokechamp.observability import verify_bundle
from integration.pokechamp.observability.player import snapshot_battle

ROOT = Path(__file__).resolve().parents[3]
CLIENT = Path(__file__).with_name("observation_client.cjs")
CATEGORIES = ("일치", "표현 차이", "의미 불일치", "지원되지 않음")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def canonical(value):
    if hasattr(value, "name"):
        return value.name
    if isinstance(value, dict):
        return {str(canonical(k)): canonical(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical(v) for v in value]
    return value


def replay_prefix(prefix, actor):
    """Only received actor-local protocol enters the current parser."""
    from poke_env.environment.battle import Battle
    from poke_env.player.player import Player

    username = next(line.split("|")[3] for e in prefix for line in e["protocol"].splitlines()
                    if line.startswith("|player|" + actor + "|"))
    battle = Battle("battle-gen9ou-diagnostic", username, logging.getLogger("ep055"), gen=9)
    battle._format = "gen9ou"
    request = None
    for e in prefix:
        for line in e["protocol"].splitlines():
            parts = line.split("|")
            if len(parts) < 2 or parts[1] in Player.MESSAGES_TO_IGNORE:
                continue
            kind = parts[1]
            if kind == "request":
                if parts[2] and parts[2] != "null":
                    request = json.loads("|".join(parts[2:]))
                    if request.get("side", {}).get("id", actor) != actor:
                        raise ValueError("Foreign private request")
                    battle.parse_request(request)
            elif kind == "win":
                battle.won_by(parts[2])
            elif kind == "tie":
                battle.tied()
            elif kind not in ("error", "sentchoice"):
                battle.parse_message(parts)
    return battle, request


def parser_snapshot(battle):
    def mon(key, p):
        return dict(ident=key, species=p.species, active=p.active, fainted=p.fainted,
                    hp=p.current_hp, max_hp=p.max_hp, status=canonical(p.status),
                    boosts=dict(p.boosts), moves=sorted(p.moves), item=p.item, ability=p.ability,
                    types=canonical(p.types), effects=canonical(p.effects))
    opponents = [mon(k, p) for k, p in battle.opponent_team.items()]
    if battle.in_team_preview:
        # Upstream returns an unordered set-derived preview mapping. Serialize
        # its members deterministically; own submission/request order is kept.
        opponents.sort(key=lambda p: p["ident"])
    return dict(turn=battle.turn, request_id=battle.rqid,
                self_team=[mon(k, p) for k, p in battle.team.items()],
                opponent_team=opponents,
                weather=canonical(battle.weather), field=canonical(battle.fields),
                self_side_conditions=canonical(battle.side_conditions),
                opponent_side_conditions=canonical(battle.opponent_side_conditions),
                preview_opponent=sorted(p.species for p in battle._teampreview_opponent_team))


def comparable_snapshot(snapshot):
    value = copy.deepcopy(snapshot)
    value.pop("showdown_battle_tag", None)
    # Preview opponent_team is produced from a set; iteration order is not an
    # observable team order or identity. Own request/candidate order stays intact.
    if value.get("in_team_preview"):
        value["opponent_team"] = sorted(value["opponent_team"], key=lambda m: m["species"])
    return value


def bounded_prefix(events, decision, boundary=None):
    prefix = [dict(event_seq=e["event_seq"], protocol=e["protocol"]) for e in events
              if e["event_type"] == "protocol_in" and e["event_seq"] < decision["event_seq"]]
    if not prefix:
        raise ValueError("Missing protocol before decision")
    last = prefix[-1]
    lines = last["protocol"].splitlines()
    if boundary:
        if boundary["protocol_event_seq"] != last["event_seq"]:
            raise ValueError("Live cursor is not in latest received frame")
        row = boundary["line_index"]
        if not 0 <= row < len(lines):
            raise ValueError("Invalid cursor")
    elif decision["battle_state"].get("team_preview_policy") == "llm_lead":
        snapshots = [e["original_input"] for e in events if e["event_type"] == "input_snapshot"
                     and e.get("decision_seq") == decision["decision_seq"]]
        if len(snapshots) != 1:
            raise ValueError("Missing historical lead input cutoff")
        ref = snapshots[0]["identity"]["protocol_cutoff"]
        if ref["event_seq"] != last["event_seq"]:
            raise ValueError("Historical lead cutoff differs from last frame")
        row = ref["line"] - 1  # production lead references are one-based
    else:
        # Historical traces predate the cursor. Locate the triggering request or
        # preview row and verify its entire state against the recorded live state.
        candidates = []
        for i, line in enumerate(lines):
            if decision["decision_kind"] == "team_preview":
                if line.startswith("|teampreview"):
                    candidates.append(i)
            elif line.startswith("|request|") and line[9:]:
                request = json.loads(line[9:])
                if request and request.get("rqid") == decision["battle_state"]["request_id"]:
                    candidates.append(i)
        if len(candidates) != 1:
            raise ValueError(f"Ambiguous historical decision trigger: {candidates}")
        row = candidates[0]
    last["protocol"] = "\n".join(lines[:row + 1])
    return prefix, dict(protocol_event_seq=last["event_seq"], line_index=row,
                        boundary_method="live_cursor" if boundary else "historical_trigger_verified_by_live_snapshot")


class OfficialClient:
    def __init__(self, build):
        build = build.resolve()
        provenance = json.loads((build / "provenance.json").read_text())
        for filename, key in (("client.js", "client_js_sha256"), ("dex.json", "data_sha256")):
            if hashlib.sha256((build / filename).read_bytes()).hexdigest() != provenance[key]:
                raise ValueError("Modified official build: " + filename)
        if provenance["client_commit"] != "f2faebd6892b314d785a0038f77309afed36970c":
            raise ValueError("Unexpected official client")
        self.process = subprocess.Popen(["node", str(CLIENT), "replay", str(build)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def replay(self, prefix, actor):
        lines = [line for e in prefix for line in e["protocol"].splitlines()]
        self.process.stdin.write(json.dumps(dict(actor=actor, lines=lines)) + "\n")
        self.process.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=30):
                self.process.kill()
                self.process.wait()
                raise TimeoutError("Official client replay exceeded 30 seconds")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Official client exited")
        response = json.loads(line)
        if not response["ok"]:
            raise RuntimeError(response["error"])
        return response["state"]

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()


def source_rows(prefix):
    return [dict(event_seq=e["event_seq"], line_index=i, line=line)
            for e in prefix for i, line in enumerate(e["protocol"].splitlines())]


def evidence_for(rows, key, field, actor):
    kinds = {
        "species": {"switch", "drag", "replace", "detailschange", "-formechange"},
        "active": {"switch", "drag", "replace", "faint"},
        "fainted": {"switch", "drag", "faint", "-damage"},
        "hp": {"switch", "drag", "-damage", "-heal", "-sethp", "faint"},
        "status": {"switch", "drag", "-damage", "-heal", "-status", "-curestatus", "faint"},
        "boosts": {"switch", "drag", "-boost", "-unboost", "-setboost", "-clearboost", "-clearallboost", "-swapboost", "-copyboost"},
        "moves": {"move", "-activate", "-start", "cant"},
        "ability": {"-ability", "-activate", "-damage", "-heal", "-immune", "move", "-boost", "-status", "-weather"},
        "item": {"-item", "-enditem", "-damage", "-heal", "-status", "-activate"},
    }
    result = []
    for row in rows:
        p = row["line"].split("|")
        if len(p) < 2:
            continue
        if p[1] == "request" and key.startswith(actor + ":"):
            result.append(row)
        elif p[1] in kinds.get(field, set()) and (key in re.sub(r"(p[12])[a-z]:", r"\1:", row["line"]) or field == "active"):
            result.append(row)
    # HP/status/current request use their latest direct evidence, while moves,
    # identity, boosts, and changing held info need a history.
    requests = [r for r in result if r["line"].startswith("|request|")]
    return [r for r in result if not r["line"].startswith("|request|")] + requests[-1:]


def norm_status(value, fainted=False):
    return "fnt" if fainted else token(value) if value else None


def hp_condition(condition):
    value = condition.split()[0]
    return [int(v) for v in value.split("/")] if "/" in value else [0, None]


def own_official(official, actor):
    public = {m["ident"]: m for s in official["sides"] if s["id"] == actor for m in s["pokemon"]}
    request = official.get("request") or {}
    result = {}
    for raw in request.get("side", {}).get("pokemon", []):
        p = dict(public.get(raw["ident"], {}))
        p.update(ident=raw["ident"], species=raw["speciesForme"], hp=raw["hp"],
                 max_hp=raw["maxhp"], status=raw.get("status"), fainted=raw.get("fainted", False),
                 active=raw["active"], moves=raw["moves"], ability=raw.get("ability", raw.get("baseAbility")),
                 item=raw.get("item"), boosts=p.get("boosts", {}))
        result[p["ident"]] = p
    return result


def normalized_mon(mon, own=False, b2=False):
    if b2 and own:
        hp = hp_condition(mon["condition"])
        fainted = "fnt" in mon["condition"]
        status = mon["condition"].split()[1:]
        return dict(species=token(mon["species"]), active=mon["active"] and not fainted, fainted=fainted,
                    hp=hp, status=norm_status(status[0] if status else None, fainted),
                    boosts={k: v for k, v in mon["boosts"].items() if v} if not fainted else {},
                    moves=sorted(token(m) for m in mon["moves"]),
                    ability=token(mon.get("ability", mon.get("baseAbility")) or "") or None,
                    item=token(mon.get("item") or "") or None)
    fainted = bool(mon.get("fainted"))
    moves = mon.get("moves", [])
    moves = [m[0] if isinstance(m, list) else m for m in moves]
    item = mon.get("item")
    return dict(species=token(mon["species"]), active=bool(mon.get("active")) and not fainted, fainted=fainted,
                hp=[mon.get("hp"), mon.get("max_hp")],
                status=norm_status(mon.get("status"), fainted),
                boosts={k: v for k, v in mon.get("boosts", {}).items() if v} if not fainted else {},
                moves=sorted(token(m) for m in moves),
                ability=token(mon.get("ability") or "") or None,
                item=token(item or "") or None)


def facts_for(prefix):
    facts = PublicFacts()
    for row in source_rows(prefix):
        facts.feed(row["line"])
        p = row["line"].split("|")
        # The original EP-051 reducer intentionally excluded this event class.
        # Magic Bounce is explicitly attributed to the reflected move's actor.
        if len(p) > 4 and p[1] == "move":
            ability = next((s[16:] for s in p[4:] if s.startswith("[from] ability: ")), None)
            if ability:
                facts.mon(ident(p[2]))["ability"] = token(ability)
        if len(p) > 4:
            holder = next((s[5:] for s in p[3:] if s.startswith("[of] p")), None)
            item = next((s[len("[from] item: "):] for s in p[3:] if s.startswith("[from] item: ")), None)
            if item and holder:
                facts.mon(ident(holder))["item"] = token(item)
    return facts


def compare_fields(parser, b2, official, prefix, actor, request):
    rows = source_rows(prefix)
    facts = facts_for(prefix)
    output = []

    def emit(path, values, normalized, evidence, *, expected=None, has_expected=False, knowledge="confirmed", supported=True, note=None):
        comparable = [v for v in normalized.values()]
        equal = all(v == comparable[0] for v in comparable[1:])
        if not supported:
            category = "지원되지 않음"
        elif not equal or (has_expected and any(v != expected for v in comparable)):
            category = "의미 불일치"
        elif len({json.dumps(v, sort_keys=True) for v in values.values()}) > 1:
            category = "표현 차이"
        else:
            category = "일치"
        references = [dict(event_seq=e["event_seq"], line_index=e["line_index"],
                           line_sha256=hashlib.sha256(e["line"].encode()).hexdigest(),
                           excerpt=e["line"] if not e["line"].startswith("|request|") else "|request| (received.jsonl 원문 참조)") for e in evidence]
        output.append(dict(path=path, classification=category, knowledge=knowledge,
                           values=values, normalized=normalized, expected=expected,
                           raw_evidence_checked=has_expected, evidence=references, note=note))

    observation = b2.get("current_observation", {}) if b2 else {}
    if b2 is None:
        for side in official["sides"]:
            own = side["id"] == actor
            p = sorted(m["species"] for m in parser["self_team"]) if own else parser["preview_opponent"]
            o = sorted(token(m["species"]) for m in side["pokemon"])
            raw = [r for r in rows if r["line"].startswith("|poke|" + side["id"] + "|")]
            expected = sorted(token(r["line"].split("|")[3].split(",")[0]) for r in raw)
            emit("preview." + side["id"], {"poke_env": p, "official": o}, {"poke_env": p, "official": o},
                 raw, expected=expected, has_expected=True,
                 note="Public preview only; no future private request is consumed")
        emit("b2.team_preview", {"poke_env": None, "b2": None, "official": official.get("request")},
             {"poke_env": None, "b2": None, "official": None}, [], supported=False,
             note="B2 battle observation is undefined for preview; random lead may precede own private request")
        return output
    for own, collection in ((True, "self_team"), (False, "opponent_team")):
        pm = {m["ident"]: m for m in parser[collection]}
        bm = {m["ident"]: m for m in observation.get("self_team" if own else "opponent_confirmed", [])}
        om = own_official(official, actor) if own else {
            m["ident"]: m for s in official["sides"] if s["id"] != actor for m in s["pokemon"] if m["ident"]}
        expected_keys = sorted(m["ident"] for m in request["side"]["pokemon"]) if own else sorted(
            key for key, m in facts.mons.items() if not key.startswith(actor + ":") and "species" in m)
        emit(collection + ".identities", {"poke_env": sorted(pm), "b2": sorted(bm), "official": sorted(om)},
             {"poke_env": sorted(pm), "b2": sorted(bm), "official": sorted(om)},
             [r for r in rows if r["line"].startswith(("|switch|", "|drag|", "|replace|"))],
             expected=expected_keys, has_expected=True)
        keys = sorted(pm.keys() | bm.keys() | om.keys())
        for key in keys:
            if key not in pm or key not in om or key not in bm:
                emit(f"{collection}.{key}.identity", {"poke_env": pm.get(key), "b2": bm.get(key), "official": om.get(key)},
                     {"poke_env": key if key in pm else None, "b2": key if key in bm else None, "official": key if key in om else None},
                     evidence_for(rows, key, "species", actor), supported=bool(b2), note="Identified members only; anonymous preview is separate")
                continue
            pn, bn, on = normalized_mon(pm[key], own), normalized_mon(bm[key], own, True), normalized_mon(om[key], own)
            # A zero-only faint condition conveys no new maximum; retain the
            # parser/client's prior maximum, but do not invent a B2 exact max.
            if own and bn["hp"][1] is None and bn["hp"][0] == 0:
                pn["hp"] = [0, None] if pn["hp"][0] == 0 else pn["hp"]
                on["hp"] = [0, None] if on["hp"][0] == 0 else on["hp"]
            fact = facts.mons.get(key, {})
            for field in pn:
                knowledge = "confirmed"
                expected = None
                has_expected = False
                if own and field in ("species", "active", "fainted", "hp", "status", "moves", "ability", "item"):
                    raw = next(m for m in request["side"]["pokemon"] if m["ident"] == key)
                    hp = hp_condition(raw["condition"])
                    fainted = "fnt" in raw["condition"]
                    status = raw["condition"].split()[1:]
                    values = dict(species=token(raw["details"].split(",")[0]),
                                  active=raw["active"] and not fainted, fainted=fainted, hp=hp,
                                  status=norm_status(status[0] if status else None, fainted),
                                  moves=sorted(raw["moves"]), item=token(raw.get("item") or "") or None,
                                  ability=token(raw.get("ability", raw.get("baseAbility")) or "") or None)
                    expected, has_expected = values[field], True
                elif field == "moves" and not own:
                    expected, has_expected = sorted(fact.get("moves", [])), "moves" in fact
                elif field in ("ability", "item") and not own:
                    known = fact.get(field)
                    if known is None and field == "ability" or known == "unknown_item" or field not in fact:
                        possible = {token(v) for v in facts.dex.get(pn["species"], {}).get("abilities", {}).values()}
                        knowledge = {tracker: "unknown" if value in (None, "unknownitem")
                                     else "inferred_species_single_ability" if field == "ability" and len(possible) == 1 and value in possible
                                     else "inferred_or_unattributed"
                                     for tracker, value in (("poke_env", pn[field]), ("b2", bn[field]), ("official", on[field]))}
                        if field == "ability":
                            knowledge["b2_declares_ability_known"] = bm[key].get("ability_known")
                        # Unknown representations remain unknown, not an empty held item claim.
                        for current in (pn, bn, on):
                            if current[field] in (None, "unknownitem"):
                                current[field] = "UNKNOWN"
                        expected, has_expected = "UNKNOWN", True
                    else:
                        expected, has_expected = known, True
                elif field == "hp" and "hp" in fact and not own:
                    expected, has_expected = [fact["hp"], fact.get("max_hp")], "max_hp" in fact
                elif field in ("species", "active", "fainted", "status", "boosts") and "species" in fact:
                    fainted = fact.get("status") == "FNT"
                    values = dict(species=fact["species"], active=fact["active"] and not fainted,
                                  fainted=fainted, status=norm_status(fact.get("status"), fainted),
                                  boosts={k: v for k, v in fact["boosts"].items() if v} if not fainted else {})
                    expected, has_expected = values[field], True
                if field in ("ability", "item") and isinstance(knowledge, str):
                    knowledge = {}
                    for tracker, current in (("poke_env", pn), ("b2", bn), ("official", on)):
                        if has_expected and current[field] == expected:
                            knowledge[tracker] = "confirmed_private_request" if own else "confirmed_protocol"
                        elif current[field] in (None, "unknownitem"):
                            knowledge[tracker] = "unknown"
                        else:
                            knowledge[tracker] = "unconfirmed_or_conflicting"
                    if not own and field == "ability":
                        knowledge["b2_declares_ability_known"] = bm[key].get("ability_known")
                values = {"poke_env": pm[key].get(field), "b2": bm[key].get(field), "official": om[key].get(field)}
                if field == "hp":
                    values = {"poke_env": [pm[key]["hp"], pm[key]["max_hp"]],
                              "b2": bm[key].get("condition") if own else [bm[key]["hp"], bm[key]["max_hp"]],
                              "official": [om[key]["hp"], om[key]["max_hp"]]}
                if own and field in ("status", "fainted"):
                    values["b2"] = bm[key]["condition"]
                emit(f"{collection}.{key}.{field}", values,
                     {"poke_env": pn[field], "b2": bn[field], "official": on[field]},
                     evidence_for(rows, key, field, actor), expected=expected, has_expected=has_expected,
                     knowledge=knowledge, note=("exact_self_request" if own else "public_server_fraction_not_exact_hp") if field == "hp"
                     else "Fainted members have no live slot/stages; retained raw flags/stages are shown as representation differences" if field in ("active", "boosts") else None)

    env_specs = [("weather", parser["weather"], observation.get("weather"), official["weather"], {"-weather"}),
                 ("field", parser["field"], observation.get("field"), official["field"], {"-fieldstart", "-fieldend"})]
    for field, p, b, o, kinds in env_specs:
        cn = {"poke_env": sorted(token(k) for k in p), "b2": sorted(token(k) for k in b or {})}
        cn["official"] = ([token(o)] if o else []) if field == "weather" else sorted(token(v[0]) for v in o)
        emit(field, {"poke_env": p, "b2": b, "official": o}, cn,
             [r for r in rows if r["line"].split("|")[1:2] and r["line"].split("|")[1] in kinds],
             supported=b2 is not None, note="Active effects; parser start turn and client remaining duration are distinct representations")
    for own in (True, False):
        name = "self_side_conditions" if own else "opponent_side_conditions"
        side = next(s for s in official["sides"] if (s["id"] == actor) == own)
        p, b, o = parser[name], observation.get(name), side["side_conditions"]
        convert = lambda values: {token(k): v if token(k) in ("spikes", "toxicspikes") else True
                                  for k, v in values.items() if token(k) not in ("futuresight", "doomdesire")}
        emit(name, {"poke_env": p, "b2": b, "official": o},
             {"poke_env": convert(p), "b2": convert(b or {}), "official": convert({k: v[1] for k, v in o.items()})},
             [r for r in rows if any(r["line"].startswith("|" + k + "|") for k in ("-sidestart", "-sideend", "-swapsideconditions"))],
             supported=b2 is not None, note="Presence and hazard layers only; duration model not equated")
    delayed_ids = ("futuresight", "doomdesire")
    pending = observation.get("protocol_state", {}).get("pending_effects", [])
    delayed_p = sorted({(m["ident"][:2], token(k)) for team in ("self_team", "opponent_team") for m in parser[team]
                        for k in m["effects"] if token(k) in delayed_ids})
    delayed_b = sorted({(e["user"][:2], token(e["effect"])) for e in pending})
    delayed_o = sorted({(s["id"], token(k)) for s in official["sides"] for k in s["side_conditions"] if token(k) in delayed_ids})
    emit("delayed_attacks", {"poke_env": delayed_p, "b2": pending,
                             "official": {s["id"]: {k: v for k, v in s["side_conditions"].items() if token(k) in delayed_ids} for s in official["sides"]}},
         {"poke_env": delayed_p, "b2": delayed_b, "official": delayed_o},
         [r for r in rows if any(name in r["line"] for name in ("Future Sight", "Doom Desire"))],
         note="Caster-side pending attack: Pokemon effect vs B2 target-slot history vs official side condition; exact duration untested")
    actions = b2.get("request", {}).get("legal_actions") if b2 else None
    official_actions = [{k: token(v) if isinstance(v, str) else v for k, v in c["action"].items()} for c in official["candidates"]]
    def action_sort(values):
        return sorted(values, key=lambda v: json.dumps(v, sort_keys=True)) if values is not None else None
    emit("legal_actions", {"poke_env": parser.get("legal_actions"), "b2": actions, "official": official["candidates"]},
         {"poke_env": action_sort(parser.get("legal_actions")), "b2": action_sort(actions), "official": action_sort(official_actions)},
         [r for r in rows if r["line"].startswith("|request|")][-1:], supported=actions is not None,
         note="Singles UI eligibility + official ChoiceBuilder validation; not action selection")
    emit("effect_duration", {"poke_env": parser["field"], "b2": observation.get("protocol_state"), "official": {"weather": official["weather_duration"], "field": official["field"]}},
         {"poke_env": None, "b2": None, "official": None}, [], supported=False,
         note="Start-turn/history versus duration intervals; duration equivalence not implemented")
    return output


def render(rows, output, title):
    def pretty(value):
        return html.escape(json.dumps(value, ensure_ascii=False, indent=2))

    parts = ["<!doctype html><html lang='ko'><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">",
             "<style>body{font:16px system-ui;max-width:1400px;margin:24px auto;padding:0 16px;color:#18222d}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;padding:10px;background:#f1f4f7;margin:6px 0}table{border-collapse:collapse;width:100%;table-layout:fixed}td,th{padding:8px;border:1px solid #bbb;vertical-align:top;overflow-wrap:anywhere}a{color:#246}nav a{display:inline-block;padding:8px}.scroll{overflow-x:auto}h2{margin-top:2em}@media(max-width:700px){table{min-width:850px}}</style>",
             "<title>" + html.escape(title) + "</title><h1>" + html.escape(title) + "</h1>",
             "<p>플레이어별 수신 원문만 재생합니다. 새 Abyssal 경기의 B2는 관측·행동 후보 투영(미전송), EX-044 배틀 B2는 보존 전송값과 대조합니다. 의미 불일치는 파서 단계와 B2 단계의 차이를 모두 포함합니다.</p>",
             "<p><a href='comparisons.jsonl'>전체 비교 JSONL</a> · <a href='received.jsonl'>수신 메시지 JSONL</a> · <a href='summary.json'>집계 JSON</a></p>",
             "<nav>" + " ".join(f"<a href='#d{r['decision_seq']}'>결정{r['decision_seq']} / 턴{r['turn']}</a>" for r in rows) + "</nav>"]
    for row in rows:
        parts.append(f"<section id='d{row['decision_seq']}'><h2>결정 {row['decision_seq']} · 턴 {row['turn']} · {html.escape(row['decision_kind'])} · rqid {row.get('request_id')}</h2>")
        parts.append("<p>" + html.escape(str(row.get("counts", row.get("error")))) + "</p>")
        parts.append("<details><summary>경계·전송 연결</summary><pre>" + pretty({k: row.get(k) for k in ("boundary", "prefix_sha256", "alignment_verified", "delivery_evidence", "error")}) + "</pre></details>")
        for category in ("의미 불일치", "표현 차이", "지원되지 않음", "일치"):
            fields = [f for f in row.get("comparisons", []) if f["classification"] == category]
            parts.append(f"<details{' open' if category == '의미 불일치' else ''}><summary>{category} {len(fields)}개</summary><div class='scroll'><table><tr><th>필드·판정 근거</th><th>poke_env</th><th>B2</th><th>공식 클라이언트</th></tr>")
            for f in fields:
                refs = " ".join(f"<a href='#event{r['event_seq']}'>e{r['event_seq']}:{r['line_index']}</a>" for r in f["evidence"])
                detail = {k: f.get(k) for k in ("knowledge", "expected", "raw_evidence_checked", "note", "first_transition_difference")}
                parts.append("<tr><td>" + html.escape(f["path"]) + "<br>" + refs + "<details><summary>판정·최초 차이</summary><pre>" + pretty(detail) + "</pre></details></td>" +
                             "".join("<td><pre>" + pretty(f["values"].get(k)) + "</pre></td>" for k in ("poke_env", "b2", "official")) + "</tr>")
            parts.append("</table></div></details>")
        projection = row.get("b2_observation_projection") or {}
        for title2, data in (("현재 파서 상태", row.get("poke_env")),
                             ("B2 관측·행동 후보", {k: projection.get(k) for k in ("current_observation", "request")}),
                             ("B2 추론(prior) — 확인 정보와 분리", projection.get("opponent_hypotheses")),
                             ("공식 클라이언트 전체 상태·자기 request", row.get("official"))):
            parts.append("<details><summary>" + title2 + "</summary><pre>" + pretty(data) + "</pre></details>")
        parts.append("</section>")
    received = output.with_name("received.jsonl")
    if received.exists():
        parts.append("<h2>플레이어 수신 원문</h2><p>행 번호는 0부터 시작합니다. request는 이 플레이어 자신의 비공개 정보입니다.</p>")
        for e in read_rows(received):
            parts.append(f"<details id='event{e['event_seq']}'><summary>메시지 e{e['event_seq']}</summary><pre>" + html.escape("\n".join(f"{i}: {line}" for i, line in enumerate(e["protocol"].splitlines()))) + "</pre></details>")
    parts.append("</html>")
    output.write_text("\n".join(parts))


def compare_bundle(bundle, output, client, *, boundaries=None):
    if not verify_bundle(bundle)["valid"]:
        raise ValueError("Invalid source bundle seal")
    events = read_rows(bundle / "events.jsonl")
    manifest = json.loads((bundle / "manifest.json").read_text())
    actor = manifest["metadata"]["actor_id"]
    # Extract only own team. No opponent set is passed across the observation boundary.
    own = next(t["showdown_team"] for t in manifest["teams"] if t["role"] == "player")
    cursors = {r["decision_seq"]: r for r in read_rows(boundaries)} if boundaries else {}
    starts = [e for e in events if e["event_type"] == "decision_start"]
    if boundaries and set(cursors) != {e["decision_seq"] for e in starts}:
        raise ValueError("Cursor/decision coverage mismatch")
    output.mkdir(parents=True, exist_ok=False)
    received = [dict(event_seq=e["event_seq"], protocol=e["protocol"]) for e in events if e["event_type"] == "protocol_in"]
    (output / "received.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in received))
    rows, first = [], {}
    for d in starts:
        row = dict(schema="ep055-observation-v1", source_bundle=str(bundle), actor=actor,
                   decision_seq=d["decision_seq"], decision_event_seq=d["event_seq"],
                   turn=d["showdown_turn"], decision_kind=d["decision_kind"],
                   request_id=d["battle_state"].get("request_id"))
        try:
            prefix, boundary = bounded_prefix(events, d, cursors.get(d["decision_seq"]))
            battle, request = replay_prefix(prefix, actor)
            if d["battle_state"].get("team_preview_policy") == "llm_lead":
                from integration.pokechamp.team_preview import build_input
                original = next(e["original_input"] for e in events if e["event_type"] == "input_snapshot" and e.get("decision_seq") == d["decision_seq"])
                rebuilt = build_input(own, prefix, battle_id=manifest["battle_id"], actor_id=actor, decision_seq=d["decision_seq"])
                if rebuilt != original:
                    raise ValueError("Historical lead input/cutoff replay mismatch")
                boundary["boundary_method"] = "historical_explicit_lead_cutoff_and_full_input_replay"
                row["request_id"] = original["identity"]["request_id"]
                row["historical_lead_input_verified"] = True
            else:
                actual = comparable_snapshot(snapshot_battle(battle))
                expected = comparable_snapshot(d["battle_state"])
                if actual != expected:
                    from integration.pokechamp.diagnostics.input_audit import differences
                    raise ValueError("Live/replay boundary state mismatch: " + json.dumps(differences(expected, actual))[:5000])
            p = parser_snapshot(battle)
            b2, exclusions = None, []
            if request and not request.get("teamPreview") and not request.get("wait"):
                from integration.pokechamp.diagnostics.ex042_input_audit import recent_window
                recent = recent_window(events, prefix, d["event_seq"])
                full, candidates = state.normalize(battle, request, own, recent,
                    battle_id=manifest["battle_id"], actor_id=actor, decision_seq=d["decision_seq"], observed_protocol=prefix)
                # B2's observation/request projection is exactly the production
                # exclusion transform. Calculation encoding affects only the
                # calculation_bundle; it is outside this state-tracker diagnostic.
                b2, exclusions = prune(full)
                p["legal_actions"] = [c.record()["action"] for c in candidates.entries]
                calls = [e for e in events if e["event_type"] == "llm_call" and e.get("decision_seq") == d["decision_seq"]]
                if calls:
                    proofs = []
                    for call in calls:
                        sent = json.loads(call["user_prompt"])
                        for key in ("current_observation", "request", "opponent_hypotheses"):
                            if b2[key] != sent[key]:
                                raise ValueError("Historical B2 wire projection differs: " + key)
                        proofs.append(dict(call_event_seq=call["event_seq"], user_prompt_sha256=hashlib.sha256(call["user_prompt"].encode()).hexdigest()))
                    row["delivery_evidence"] = dict(kind="historical_B2_wire_projection_verified", calls=proofs)
                else:
                    row["delivery_evidence"] = dict(kind="diagnostic_B2_observation_projection_not_sent", calculation_bundle="outside_scope")
            official = client.replay(prefix, actor)
            fields = compare_fields(p, b2, official, prefix, actor, request)
            for field in fields:
                if field["classification"] in ("의미 불일치", "표현 차이"):
                    first.setdefault(field["path"], dict(decision_seq=d["decision_seq"], **boundary))
                    field["first_difference"] = first[field["path"]]
                normalized = field["normalized"]
                for a, b in (("poke_env", "b2"), ("b2", "official")):
                    if a in normalized and b in normalized and normalized[a] != normalized[b]:
                        transition = a + "_to_" + b
                        key = transition + ":" + field["path"]
                        first.setdefault(key, dict(decision_seq=d["decision_seq"], **boundary))
                        field.setdefault("first_transition_difference", {})[transition] = first[key]
            row.update(boundary=boundary, prefix_sha256=digest(prefix), alignment_verified=True,
                       poke_env=p, b2_observation_projection=b2, b2_exclusions=exclusions,
                       official=official, comparisons=fields,
                       counts=dict(Counter(f["classification"] for f in fields)))
        except Exception as error:
            row.update(alignment_verified=False, error=f"{type(error).__name__}: {error}")
        rows.append(row)
    (output / "comparisons.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    render(rows, output / "viewer.html", f"{manifest['battle_id']} · {actor} 관측 비교")
    summary = dict(actor=actor, bundle=str(bundle), decisions=len(rows),
                   aligned=sum(r["alignment_verified"] for r in rows),
                   counts=dict(sum((Counter(r.get("counts", {})) for r in rows), Counter())),
                   errors=[{k: r[k] for k in ("decision_seq", "error")} for r in rows if "error" in r],
                   first_differences=first,
                   protocol_vocabulary=dict(Counter(line.split("|")[1] for e in received for line in e["protocol"].splitlines() if line.startswith("|"))),
                   input_sha256={f: hashlib.sha256((bundle / f).read_bytes()).hexdigest() for f in ("events.jsonl", "manifest.json")})
    write(output / "summary.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--boundaries", type=Path)
    args = p.parse_args()
    install_identity_adapter()
    client = OfficialClient(args.build)
    try:
        summary = compare_bundle(args.bundle.resolve(), args.output.resolve(), client, boundaries=args.boundaries)
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if summary["aligned"] == summary["decisions"] else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
