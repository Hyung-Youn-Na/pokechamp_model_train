"""Pinned Metamon CPU adapter and shared offline/live public-state projection.

The upstream source is immutable. We use its event parser, adding original-slot
identities and explicit decision cutoffs. Its approximate universal action mask
and backward opponent filling are deliberately not used.
"""
from __future__ import annotations

from collections import defaultdict
import copy
from datetime import datetime, timezone
from enum import Enum
import re

from .impute import (FORME_CHANGED_ABILITIES, SetCorpus, extract_teams, ident, lines_of,
                     revealed_original_sets, species_ident, switch_original_species)

METAMON_REVISION = "0a00a759c9a4382a2877088d828302ec294a05a5"
PUBLIC_EVENTS = {"switch", "drag", "move", "cant", "faint", "turn", "upkeep",
                 "-damage", "-heal", "-status", "-curestatus", "-cureteam", "-boost", "-unboost",
                 "-setboost", "-clearboost", "-clearallboost", "-clearnegativeboost", "-clearpositiveboost",
                 "-copyboost", "-swapboost", "-invertboost", "-restoreboost", "-item", "-enditem",
                 "-ability", "-endability", "-start", "-end", "-singleturn", "-singlemove", "-activate",
                 "-sidestart", "-sideend", "-swapsideconditions", "-weather", "-fieldstart", "-fieldend",
                 "-fieldactivate", "-terastallize", "-immune", "-fail", "-block", "-miss", "-crit",
                 "-supereffective", "-resisted", "-notarget", "-prepare", "-mustrecharge", "-sethp",
                 "detailschange", "-formechange"}
CALLED = {"sleeptalk", "assist", "copycat", "mefirst", "metronome", "mirrormove", "naturepower",
          "snatch", "magiccoat", "magicbounce", "dancer", "instruct"}
CONSECUTIVE = {"outrage", "thrash", "petaldance", "rollout", "iceball", "uproar"}
CHOICE_ITEMS = {"choiceband", "choicespecs", "choicescarf"}
# State is still serialized for audit; such menus have no training label because
# the replay cannot prove an exact request mask with this first adapter.
UNSUPPORTED_MENU_EFFECTS = {"encore", "disable", "torment", "imprison", "taunt", "healblock",
    "throatchop", "attract", "ingrain", "octolock", "partiallytrapped", "trapped", "meanlook",
    "block", "spiderweb", "skydrop", "bide", "recharge", "mustrecharge"}
UNSUPPORTED_MOVES = {"teleport", "transform", "mimic", "sketch", "instruct", "skillswap",
                     "roleplay", "entrainment", "simplebeam", "worryseed", "gastroacid"}


def _clean(value):
    if value is None:
        return None
    if isinstance(value, Enum):
        if value.name.startswith("NO_"):
            return None
        if value.name == "FORCE_UNKNOWN":
            return None
        return value.name.lower()
    return value


def _mapping(mapping):
    return {str(_clean(k)): v for k, v in sorted(mapping.items(), key=lambda p: str(p[0]))}


def _original_set(pokemon):
    """Explicit allowlist: no nickname, team source, frequency or audit fields."""
    result = {k: copy.deepcopy(pokemon[k]) for k in
              ("species", "item", "ability", "moves", "nature", "evs", "ivs", "level", "gender", "teraType")
              if k in pokemon}
    for field in ("species", "item", "ability", "nature", "teraType"):
        if field in result:
            result[field] = ident(result[field])
    result["moves"] = [ident(m) for m in result["moves"]]
    result.setdefault("level", 100)
    return result


class Timeline:
    def __init__(self, raw, own_sets=None, *, replay_id="prefix"):
        from metamon.backend.replay_parser.forward import SimProtocol
        from metamon.backend.replay_parser.replay_state import ParsedReplay
        self.lines = lines_of(raw)
        self.teams = extract_teams(raw)
        self.originals = own_sets or {}
        self.replay = ParsedReplay(gameid=replay_id, format="gen9ou",
                                   time_played=datetime(2000, 1, 1, tzinfo=timezone.utc))
        self.sim = SimProtocol(self.replay)
        self.history = []
        self.nick = {}
        self.active = {}
        self.public_ability = set()
        self.public_item = set()
        self.public_tera = set()
        self.tera_slots = set()
        self.tera_types = {}
        self.aux = defaultdict(lambda: dict(last_move=None, last_move_turn=None,
            choice_changed=False, automatic=None, unknown_first_choice=False, unsupported=set()))
        self.records = []
        self.pending = {}
        self.forced = {}
        self.force_blank = {}
        self.capture = False
        self.line_number = 0

    @property
    def turn(self):
        return self.sim.curr_turn.turn_number

    def key(self, token):
        token = token.removeprefix("[of] ")
        return self.nick.get(token) or self.active.get(token[:2])

    def slot(self, side, species):
        original_species = switch_original_species(species)
        candidates = [i + 1 for i, name in enumerate(self.teams[side]) if ident(name) == original_species]
        if len(candidates) != 1:
            raise ValueError("unsupported original-slot species or forme: " + species)
        return candidates[0]

    def normalized_history(self, perspective):
        result = []
        for row in self.history:
            if row["turn"] < self.turn - 4:
                continue
            result.append(dict(turn=row["turn"], event=row["event"],
                args=[a.replace("@p1", "self" if perspective == "p1" else "opponent")
                       .replace("@p2", "self" if perspective == "p2" else "opponent") for a in row["args"]]))
        return result

    def _history_arg(self, arg):
        # Side names and Pokémon nicknames are never copied into model history.
        arg = re.sub(r"p[12][a-d]?: [^|]+?(?=$|\]|\[)", lambda m: self._replace_ident(m.group(0)), arg)
        if re.search(r"p[12][a-d]?:", arg):
            arg = self._replace_ident(arg)
        return arg

    def _replace_ident(self, arg):
        match = re.search(r"p([12])([a-d])?:", arg)
        if not match:
            return arg
        side = "p" + match.group(1)
        prefix = arg[:match.start()]
        if match.group(2):
            key = self.key(arg[match.start():])
            if key is None:
                return prefix + "@" + side + ":active"
            return prefix + "@" + side + ":slot" + str(key[1])
        return prefix + "@" + side

    def _pokemon(self, pokemon, side, slot, own):
        from metamon.backend.replay_parser.replay_state import Move
        original = self.originals.get(side, [])[slot - 1] if own else None
        key = (side, slot)
        species = ident(self.teams[side][slot - 1])
        if pokemon is None:
            raise ValueError("preview pokemon missing from pinned parser")
        hp = pokemon.current_hp
        max_hp = pokemon.max_hp
        hp_percent = round(100 * hp / max_hp, 1) if hp is not None and max_hp else None
        if hp_percent is None and (own or self.turn == 0):
            hp_percent = 100.0
        status = _clean(pokemon.status)
        if status == "fnt":
            hp_percent = 0.0
        item = _clean(pokemon.active_item)
        ability = _clean(pokemon.active_ability)
        moves = []
        if own:
            if pokemon.active_item is None:
                item = original.get("item")
            if pokemon.active_ability is None:
                ability = original.get("ability")
            known = {ident(m.name): m for m in pokemon.had_moves.values()}
            for name in original["moves"]:
                move = known.get(ident(name)) or Move(name, 9)
                moves.append(dict(id=ident(name), pp=move.pp, max_pp=move.maximum_pp))
        else:
            item = item if key in self.public_item else None
            ability = ability if key in self.public_ability else None
            moves = [dict(id=ident(m.name), pp=None, max_pp=m.maximum_pp) for m in pokemon.moves.values()]
        row = dict(slot=slot, species=ident(pokemon.name) or species, hp_percent=hp_percent,
                   status=status, boosts=pokemon.boosts.to_dict(), item=ident(item) if item else None,
                   ability=ident(ability) if ability else None, moves=moves,
                   types=([self.tera_types[key]] if key in self.tera_types and self.tera_types[key] != "stellar"
                          else [ident(t) for t in pokemon.type]),
                   tera_type=(ident(original.get("teraType", "")) if own else
                              ident(pokemon.tera_type) if key in self.public_tera else None),
                   terastallized=key in self.tera_slots, effects=_mapping(pokemon.effects))
        if own:
            row["original_set"] = _original_set(original)
        # Opponent list order is public preview order; own list order is frozen
        # original team order. These orders are identical during offline parsing.
        return row

    def snapshot(self, perspective, decision_kind):
        if perspective not in self.originals or len(self.originals[perspective]) != 6:
            raise ValueError("snapshot requires six own original sets")
        other = "p2" if perspective == "p1" else "p1"
        state = self.sim.curr_turn
        rows = {}
        for side in (perspective, other):
            mons = state.pokemon_1 if side == "p1" else state.pokemon_2
            by_slot = {}
            for mon in mons:
                if mon is not None:
                    # Name may change after Tera (e.g. Ogerpon) without creating a
                    # new original slot. Preview-order identity is retained.
                    matched = next((i + 1 for i, p in enumerate(mons) if p is mon), None)
                    by_slot[matched] = mon
            rows[side] = [self._pokemon(by_slot.get(slot), side, slot, side == perspective)
                          for slot in range(1, 7)]
        own_slot = self.active.get(perspective, (None, None))[1]
        opp_slot = self.active.get(other, (None, None))[1]
        return dict(turn=self.turn, decision_kind=decision_kind, own_team=rows[perspective],
                    opponent_team=rows[other], own_active_slot=own_slot, opponent_active_slot=opp_slot,
                    can_tera=state.can_tera_1 if perspective == "p1" else state.can_tera_2,
                    opponent_can_tera=state.can_tera_2 if perspective == "p1" else state.can_tera_1,
                    weather=_clean(state.weather), field=_mapping(state.battle_field),
                    own_side_conditions=_mapping(state.conditions_1 if perspective == "p1" else state.conditions_2),
                    opponent_side_conditions=_mapping(state.conditions_2 if perspective == "p1" else state.conditions_1),
                    history=self.normalized_history(perspective))

    def candidates(self, snapshot, perspective):
        kind = snapshot["decision_kind"]
        own = snapshot["own_team"]
        if kind == "lead":
            return [dict(id=f"lead:{m['slot']}", kind="lead", slot=m["slot"],
                         description=f"Lead with slot {m['slot']}: {m['species']}") for m in own], None
        slot = snapshot["own_active_slot"]
        if slot is None:
            return [], "missing_active_pokemon"
        active = own[slot - 1]
        switches = [dict(id=f"switch:{m['slot']}", kind="switch", slot=m["slot"],
                         description=f"Switch to slot {m['slot']}: {m['species']}")
                    for m in own if m["slot"] != slot and m["status"] != "fnt"]
        if kind in {"forced_switch", "pivot_switch"}:
            return switches, None
        aux = self.aux[(perspective, slot)]
        if aux["automatic"]:
            return [], "automatic_continuation:" + aux["automatic"]
        if active["status"] == "fnt":
            return [], "fainted_before_request"
        effects = set(map(ident, active["effects"]))
        unsupported = (effects & UNSUPPORTED_MENU_EFFECTS) | aux["unsupported"]
        if unsupported:
            return [], "unsupported_legal_mask:" + ",".join(sorted(unsupported))
        opponent_slot = snapshot["opponent_active_slot"]
        opponent = snapshot["opponent_team"][opponent_slot - 1] if opponent_slot else None
        if opponent and "imprison" in set(map(ident, opponent["effects"])):
            return [], "unsupported_legal_mask:opponent_imprison"
        # All ordinary trapping abilities are banned or publicly announced except
        # Magnet Pull. Unknown possible Magnet Pull is not assumed absent.
        if opponent and opponent["species"] in {"magnezone", "magneton", "magnemite", "probopass"} and "steel" in active["types"]:
            if opponent["ability"] is None:
                return [], "unrevealed_possible_magnet_pull"
        if opponent and opponent["ability"] in {"magnetpull", "arenatrap", "shadowtag"}:
            return [], "unsupported_legal_mask:trapping_ability"
        item = active["item"]
        if active["ability"] == "klutz" or "magicroom" in set(map(ident, snapshot["field"])) or "embargo" in effects:
            item = None
        if item in CHOICE_ITEMS and aux["choice_changed"]:
            return [], "unsupported_legal_mask:changed_choice_item"
        if item in CHOICE_ITEMS and aux["unknown_first_choice"]:
            return [], "unsupported_legal_mask:unobserved_choice_lock"
        from metamon.backend.replay_parser.replay_state import Move
        available = []
        for move in active["moves"]:
            name = move["id"]
            if name in {"belch", "stuffcheeks"}:
                return [], "unsupported_legal_mask:" + name
            if move["pp"] <= 0:
                continue
            if item in CHOICE_ITEMS and aux["last_move"] and name != aux["last_move"]:
                continue
            definition = Move(name, 9)
            if item == "assaultvest" and str(definition.category).lower().endswith("status"):
                continue
            if name in {"gigatonhammer", "bloodmoon"} and aux["last_move"] == name:
                continue
            available.append(name)
        if not available:
            available = ["struggle"]
        actions = []
        for name in available:
            for tera in ([False, True] if snapshot["can_tera"] else [False]):
                actions.append(dict(id=f"move:{name}:{'tera' if tera else 'normal'}", kind="move",
                    move_id=name, tera=tera,
                    description=f"Use {name}" + (f"; Terastallize into {active['tera_type']}" if tera else "")))
        return actions + switches, None

    def new_record(self, perspective, kind, *, snapshot=None, cutoff=None):
        snapshot = snapshot or self.snapshot(perspective, kind)
        actions, reason = self.candidates(snapshot, perspective)
        row = dict(perspective=perspective, decision_kind=kind, cutoff_line=self.line_number if cutoff is None else cutoff,
                   turn=snapshot["turn"], label=None, label_kind=None, actions=actions, snapshot=snapshot,
                   audit=dict(mask_reason=reason, parser_revision=METAMON_REVISION))
        self.records.append(row)
        return row

    def _set_label(self, row, value, label_kind):
        if row is None or row["audit"]["mask_reason"]:
            return
        if row["label"] is not None and row["label"] != value:
            row["label"] = None
            row["audit"]["mask_reason"] = "ambiguous_multiple_choices"
            return
        row["label"] = value
        row["label_kind"] = label_kind

    def _is_outgoing_cleanup(self, index, side):
        """Recognize switch-out cleanup when the log omits request separators.

        Effects such as Quark Drive can end *after* the replacement was chosen
        but before its switch row. Those rows cannot enter that choice's input.
        Only contiguous same-side cleanup followed by a switch qualifies.
        """
        for line in self.lines[index + 1:]:
            parts = line.split("|")
            if len(parts) < 2 or parts[1] in {"", "t:", "inactive", "inactiveoff"}:
                continue
            if parts[1] in {"-end", "-endability"} and len(parts) > 2 and parts[2].startswith(side):
                continue
            return parts[1] == "switch" and len(parts) > 2 and parts[2].startswith(side)
        return False

    def consume(self, *, capture=False):
        self.capture = capture
        for index, line in enumerate(self.lines):
            self.line_number = index
            parts = [p.strip() for p in line.split("|")[1:]]
            if not parts or not parts[0]:
                if capture:
                    for sub in self.sim.curr_turn.subturns:
                        side = "p" + str(sub.team)
                        if sub.unfilled and side in self.originals:
                            active = self.sim.curr_turn.get_active_pokemon(side == "p1")[0]
                            kind = "forced_switch" if active and _clean(active.status) == "fnt" else "pivot_switch"
                            self.force_blank[side] = (self.snapshot(side, kind), index + 1)
                continue
            event, *args = parts
            if (capture and event in {"-end", "-endability"} and args and
                    self._is_outgoing_cleanup(index, args[0][:2])):
                for sub in self.sim.curr_turn.subturns:
                    side = "p" + str(sub.team)
                    if sub.unfilled and side in self.originals and side not in self.force_blank:
                        active = self.sim.curr_turn.get_active_pokemon(side == "p1")[0]
                        kind = "forced_switch" if active and _clean(active.status) == "fnt" else "pivot_switch"
                        self.force_blank[side] = (self.snapshot(side, kind), index)
            if event == "start" and capture:
                for side in self.originals:
                    self.pending[side] = self.new_record(side, "lead")
            if event in {"switch", "drag"} and len(args) >= 2:
                side = args[0][:2]
                target_slot = self.slot(side, args[1].split(",")[0])
                # All unfilled simultaneous requests are frozen BEFORE either
                # player's replacement is publicly revealed.
                if capture:
                    for sub in self.sim.curr_turn.subturns:
                        requested = "p" + str(sub.team)
                        if sub.unfilled and requested in self.originals and requested not in self.forced:
                            active = self.sim.curr_turn.get_active_pokemon(requested == "p1")[0]
                            kind = "forced_switch" if active and _clean(active.status) == "fnt" else "pivot_switch"
                            prior = self.force_blank.get(requested)
                            self.forced[requested] = self.new_record(requested, kind,
                                snapshot=prior[0] if prior else None, cutoff=prior[1] if prior else None)
                    if event == "switch" and side in self.originals:
                        row = self.forced.pop(side, None)
                        if row is not None:
                            self._set_label(row, f"switch:{target_slot}", row["decision_kind"])
                        else:
                            row = self.pending.get(side)
                            lead = row and row["decision_kind"] == "lead"
                            self._set_label(row, f"{'lead' if lead else 'switch'}:{target_slot}",
                                            "lead" if lead else "voluntary_switch")
                        self.force_blank.pop(side, None)
                self.nick[args[0]] = (side, target_slot)
                self.active[side] = (side, target_slot)
                self.aux[(side, target_slot)] = dict(last_move=None, last_move_turn=None,
                    choice_changed=False, automatic=None, unknown_first_choice=False, unsupported=set())
            if event == "move" and len(args) >= 2:
                side = args[0][:2]
                key = self.key(args[0])
                move = ident(args[1])
                source = [ident(a.split(":", 1)[-1].replace("[from] ", "")) for a in args[3:] if a.startswith("[from]")]
                called = any(s in CALLED for s in source)
                repeated = "lockedmove" in source or (key and self.aux[key]["automatic"] is not None)
                if capture and not called and not repeated and side in self.originals:
                    row = self.pending.get(side)
                    tera = bool(row and row["audit"].get("selected_tera"))
                    self._set_label(row, f"move:{move}:{'tera' if tera else 'normal'}", "move")
                if key and not called:
                    aux = self.aux[key]
                    aux["last_move"] = move
                    aux["last_move_turn"] = self.turn
                    if move in UNSUPPORTED_MOVES:
                        aux["unsupported"].add(move)
                    if move in CONSECUTIVE:
                        aux["automatic"] = move
                    elif "[still]" in args:
                        from metamon.backend.replay_parser.replay_state import Move
                        aux["automatic"] = move if Move(move, 9).charge_move else None
                    else:
                        aux["automatic"] = None
            if event == "-terastallize" and args:
                key = self.key(args[0])
                if key:
                    self.tera_slots.add(key)
                    self.tera_types[key] = ident(args[1])
                    self.public_tera.add(key)
                    if capture and key[0] in self.pending:
                        self.pending[key[0]]["audit"]["selected_tera"] = True
            if event in {"-item", "-enditem"} and args:
                key = self.key(args[0])
                if key:
                    self.public_item.add(key)
                    if event == "-item" and any(x in " ".join(args[2:]).lower() for x in ("trick", "switcheroo", "thief", "covet")):
                        self.aux[key]["choice_changed"] = True
            if event == "-damage" and "[from] item: Life Orb" in args:
                # Recoil publicly reveals the item without a separate -item.
                # Keep the parser authoritative for its current value/removal.
                holder = next((a for a in args if a.startswith("[of] ")), args[0])
                key = self.key(holder)
                if key:
                    self.public_item.add(key)
            if event in {"-ability", "-endability"} and args:
                key = self.key(args[0])
                if key:
                    self.public_ability.add(key)
            if args:
                if any(a.startswith("[from] ability:") for a in args) or (len(args) > 1 and args[1].startswith("ability:")):
                    token = next((a for a in args if a.startswith("[of] ")), args[0])
                    key = self.key(token)
                    if key:
                        self.public_ability.add(key)
                key = self.key(args[0])
                if key and event == "-mustrecharge":
                    self.aux[key]["automatic"] = "recharge"
                if key and event == "cant" and len(args) > 1 and args[1] == "recharge":
                    self.aux[key]["automatic"] = None
                if key and event == "cant" and self.aux[key]["last_move"] is None:
                    self.aux[key]["unknown_first_choice"] = True
                if key and event == "-start" and len(args) > 1 and ident(args[1]) == "confusion":
                    self.aux[key]["automatic"] = None
                if key and event == "-end" and len(args) > 1 and ident(args[1]) in CONSECUTIVE | {"lockedmove"}:
                    self.aux[key]["automatic"] = None
            # No retrospective winner/name/rating dependency. Unknown metadata is
            # discarded; unsupported battle mechanics still raise in Metamon.
            if event not in {"win", "tie", "player", "choice", "sentchoice", "request"}:
                if event == "-sethp" and len(args) >= 4 and args[2].startswith(("p1", "p2")):
                    # Pain Split may place both HP assignments on a single
                    # protocol row; pinned Metamon otherwise consumes only one.
                    for offset in range(0, len(args) - 1, 2):
                        if args[offset].startswith(("p1", "p2")):
                            self.sim.interpret_message([event, args[offset], args[offset + 1]])
                else:
                    self.sim.interpret_message(parts)
            if (event in {"detailschange", "-formechange"} and len(args) >= 2 and
                    ident(args[1].split(",")[0]) in FORME_CHANGED_ABILITIES):
                # Showdown's permanent Ogerpon Tera forme change updates
                # baseAbility. Metamon restores had_ability on switch-out, so
                # preserve the publicly determined form ability for that reset.
                # Do not overwrite active_ability: later explicit changes or
                # suppression still belong to the pinned event parser.
                pokemon = self.sim.curr_turn.get_pokemon_from_str(args[0])
                abilities = pokemon._lookup_pokedex_info(pokemon.name, 9)["abilities"]
                if len(abilities) != 1:
                    raise ValueError("known Tera form must have one public ability")
                pokemon.had_ability = next(iter(abilities.values()))
            if event in PUBLIC_EVENTS:
                clean_args = list(args)
                if event in {"switch", "drag"} and len(clean_args) > 2:
                    clean_args[2] = _percent_condition(clean_args[2])
                elif event in {"-damage", "-heal", "-sethp"} and len(clean_args) > 1:
                    clean_args[1] = _percent_condition(clean_args[1])
                    if event == "-sethp":
                        for offset in range(3, len(clean_args), 2):
                            clean_args[offset] = _percent_condition(clean_args[offset])
                self.history.append(dict(turn=self.turn, event=event,
                                         args=[self._history_arg(a) for a in clean_args]))
            if event == "turn" and capture:
                self.force_blank.clear()
                for side in self.originals:
                    self.pending[side] = self.new_record(side, "turn_action", cutoff=index + 1)
        self.line_number = len(self.lines)
        return self


def _percent_condition(condition):
    match = re.match(r"(\d+)/(\d+)(.*)", condition)
    if match:
        return f"{round(int(match[1]) * 100 / int(match[2]), 1):g}/100{match[3]}"
    return condition


def serialize_state(prefix, own_sets, perspective, decision_kind):
    """The sole state serializer used by both replay preparation and live play."""
    teams = extract_teams(prefix)
    order = {species_ident(s): i for i, s in enumerate(teams[perspective])}
    if len(own_sets) != 6 or set(order) != {species_ident(s["species"]) for s in own_sets}:
        raise ValueError("submitted own sets do not match public preview")
    # Gen9 live preview is normally submitted team order. Fail closed instead of
    # silently changing original-slot action identities if that invariant differs.
    if any(species_ident(s["species"]) != species_ident(t) for s, t in zip(own_sets, teams[perspective])):
        raise ValueError("public preview and original team slot order differ")
    return Timeline(prefix, {perspective: own_sets}).consume().snapshot(perspective, decision_kind)


def recover(raw_json, replay_id, corpus_sets):
    corpus = corpus_sets if isinstance(corpus_sets, SetCorpus) else SetCorpus(corpus_sets)
    revealed, unsupported = revealed_original_sets(raw_json)
    exclusions, originals, imputation = [], {}, {}
    for side in ("p1", "p2"):
        reasons = [reason for who, reason in unsupported if who == side]
        if reasons:
            exclusions.append(dict(perspective=side, reason="unsupported_original_evidence", details=reasons))
            continue
        selected, audit = corpus.impute(revealed[side], replay_id, side)
        if selected is None:
            exclusions.append(audit)
        else:
            originals[side] = selected
            imputation[side] = audit
    if not originals:
        return dict(records=[], exclusions=exclusions, imputation=imputation, original_sets=originals)
    try:
        timeline = Timeline(raw_json, originals, replay_id=replay_id).consume(capture=True)
    except Exception as exc:
        exclusions.append(dict(reason="parser_reconstruction_failure", error_type=type(exc).__name__, detail=str(exc)))
        return dict(records=[], exclusions=exclusions, imputation=imputation, original_sets=originals)
    records = []
    inconsistent = set()
    for row in timeline.records:
        if row["label"] is not None and row["label"] not in {a["id"] for a in row["actions"]}:
            row["audit"]["mask_reason"] = "chosen_action_not_in_proven_legal_mask"
            row["audit"]["unaccepted_label"] = row["label"]
            row["label"] = None
            inconsistent.add(row["perspective"])
        if row["label"] is None and row["audit"]["mask_reason"] is None:
            row["audit"]["mask_reason"] = "unobserved_choice"
        row["audit"]["singleton"] = len(row["actions"]) == 1
        records.append(row)
    for side in inconsistent:
        exclusions.append(dict(perspective=side, reason="imputed_set_or_label_menu_inconsistent"))
        for row in records:
            if row["perspective"] == side:
                row["audit"]["quarantined_perspective"] = True
                if row["label"] is not None:
                    row["audit"]["unaccepted_label"] = row["label"]
                row["label"] = None
                row["audit"]["mask_reason"] = "quarantined_inconsistent_perspective"
    return dict(records=records, exclusions=exclusions, imputation=imputation, original_sets=originals)
