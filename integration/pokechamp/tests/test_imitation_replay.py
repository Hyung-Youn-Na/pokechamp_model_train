"""Public-cutoff, label provenance and unmerged CPU parser boundary regressions."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from integration.pokechamp.imitation.impute import (
    SetCorpus, extract_teams, revealed_original_sets, switch_original_species,
)
from integration.pokechamp.imitation.metamon_bridge import BridgeClient


P1 = ["Dragapult", "Zapdos", "Blissey", "Corviknight", "Rillaboom", "Kingambit"]
P2 = ["Iron Hands", "Iron Crown", "Dragonite", "Hatterene", "Iron Moth", "Samurott-Hisui"]
FORMES = [
    ("Ogerpon", "Ogerpon-Teal-Tera", "Grass", "Defiant", "Embody Aspect (Teal)"),
    ("Ogerpon-Wellspring", "Ogerpon-Wellspring-Tera", "Water", "Water Absorb", "Embody Aspect (Wellspring)"),
    ("Ogerpon-Hearthflame", "Ogerpon-Hearthflame-Tera", "Fire", "Mold Breaker", "Embody Aspect (Hearthflame)"),
    ("Ogerpon-Cornerstone", "Ogerpon-Cornerstone-Tera", "Rock", "Sturdy", "Embody Aspect (Cornerstone)"),
    ("Mimikyu", "Mimikyu-Busted", None, "Disguise", "Disguise"),
]


def sets(roster):
    return [dict(species=s, item="Leftovers", ability="Pressure", teraType="Ghost",
                 moves=["U-turn", "Shadow Ball", "Sleep Talk", "Rest"],
                 nature="Timid", evs=dict(hp=4, spa=252, spe=252), ivs=dict(atk=0)) for s in roster]


def fixture(events=""):
    pre = ["|gen|9", "|gametype|singles", "|player|p1|Alice|1|1500", "|player|p2|Bob|1|1700",
           "|teamsize|p1|6", "|teamsize|p2|6", "|rule|Species Clause: Limit one of each Pokémon"]
    pre += [f"|poke|{side}|{name}|" for side, roster in (("p1", P1), ("p2", P2)) for name in roster]
    pre += ["|teampreview", "|start", "|switch|p1a: Clever Nick|Dragapult|100/100",
            "|switch|p2a: Secret Nick|Iron Hands|100/100", "|turn|1"]
    return dict(log="\n".join(pre) + "\n" + events, players=["Alice", "Bob"], rating=1600,
                formatid="gen9ou", uploadtime=1, winner="Alice")


def corpus():
    return [dict(set=s, count=1, sources=["semantic-fixture"]) for s in sets(P1) + sets(P2)]


def forme_fixture(case, *, reveal_original_ability=True):
    original, form, tera, original_ability, form_ability = case
    own = sets([original] + P1[1:])
    own[0].update(ability=original_ability, teraType=tera or "Ghost")
    events = []
    if reveal_original_ability:
        events.append(f"|-ability|p1a: Clever Nick|{original_ability}")
    if tera:
        events.append(f"|-terastallize|p1a: Clever Nick|{tera}")
    events += [f"|detailschange|p1a: Clever Nick|{form}",
               f"|-ability|p1a: Clever Nick|{form_ability}",
               "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick", "|upkeep", "|turn|2",
               "|switch|p1a: Zapdos Nick|Zapdos|100/100", "|upkeep", "|turn|3",
               f"|switch|p1a: Clever Nick|{form}|100/100",
               f"|-ability|p1a: Clever Nick|{form_ability}", "|upkeep", "|turn|4",
               "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick",
               "|move|p2a: Secret Nick|Rest|p2a: Secret Nick"]
    raw = fixture("\n".join(events) + "\n")
    raw["log"] = raw["log"].replace("|Dragapult|", f"|{original}|")
    source = [dict(set=s, count=1, sources=["semantic-fixture"]) for s in own + sets(P2)]
    return raw, own, source


class OriginalSetTests(unittest.TestCase):
    def test_battle_only_mapping_preserves_exact_original_mask_and_other_forms(self):
        for original, form, *_ in FORMES:
            with self.subTest(form=form):
                self.assertEqual(switch_original_species(form), switch_original_species(original))
        self.assertNotEqual(switch_original_species("Ogerpon-Teal-Tera"), "ogerponwellspring")
        self.assertEqual(switch_original_species("Keldeo-Resolute"), "keldeoresolute")
        self.assertEqual(switch_original_species("Greninja-Ash"), "greninjaash")
        self.assertEqual(switch_original_species("Zamazenta-Crowned"), "zamazentacrowned")

    def test_forme_ability_never_becomes_original_ability_after_reentry(self):
        for case in FORMES:
            with self.subTest(form=case[1]):
                raw, _, _ = forme_fixture(case)
                revealed, reasons = revealed_original_sets(raw)
                self.assertFalse(reasons)
                self.assertEqual(revealed["p1"][0]["species"], case[0])
                self.assertEqual(revealed["p1"][0]["ability"], case[3])
                if case[2]:
                    raw, _, _ = forme_fixture(case, reveal_original_ability=False)
                    revealed, reasons = revealed_original_sets(raw)
                    self.assertFalse(reasons)
                    self.assertIsNone(revealed["p1"][0]["ability"])

    def test_identity_changes_still_quarantine_and_wrong_mask_is_not_an_alias(self):
        for event in ("|replace|p1a: Clever Nick|Zoroark|100/100\n",
                      "|-transform|p1a: Clever Nick|p2a: Secret Nick\n"):
            _, reasons = revealed_original_sets(fixture(event))
            self.assertEqual(reasons, [("p1", "unsupported_identity_change"),
                                       ("p2", "unsupported_identity_change")])
        raw, _, _ = forme_fixture(FORMES[1])
        raw["log"] = raw["log"].replace("|Ogerpon-Wellspring-Tera|100/100", "|Ogerpon-Teal-Tera|100/100")
        _, reasons = revealed_original_sets(raw)
        self.assertIn(("p1", "unresolved_switch_species"), reasons)

    def test_sleep_talk_reveals_called_owned_move_but_metronome_does_not(self):
        raw = fixture("|move|p1a: Clever Nick|Sleep Talk|p1a: Clever Nick\n"
                      "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick|[from] move: Sleep Talk\n"
                      "|move|p2a: Secret Nick|Metronome|p2a: Secret Nick\n"
                      "|move|p2a: Secret Nick|Sacred Fire|p1a: Clever Nick|[from] move: Metronome\n")
        revealed, reasons = revealed_original_sets(raw)
        self.assertEqual(revealed["p1"][0]["moves"], ["Sleep Talk", "Shadow Ball"])
        self.assertEqual(revealed["p2"][0]["moves"], ["Metronome"])
        self.assertFalse(reasons)

    def test_trick_received_item_belongs_to_original_donor(self):
        raw = fixture("|move|p1a: Clever Nick|Trick|p2a: Secret Nick\n"
                      "|-activate|p1a: Clever Nick|move: Trick|[of] p2a: Secret Nick\n"
                      "|-item|p1a: Clever Nick|Assault Vest|[from] move: Trick\n"
                      "|-item|p2a: Secret Nick|Choice Scarf|[from] move: Trick\n"
                      "|-enditem|p1a: Clever Nick|Assault Vest|[from] move: Knock Off\n")
        revealed, reasons = revealed_original_sets(raw)
        self.assertFalse(reasons)
        self.assertEqual(revealed["p1"][0]["item"], "Choice Scarf")
        self.assertEqual(revealed["p2"][0]["item"], "Assault Vest")

    def test_weighted_imputation_is_deterministic_and_mismatch_excludes(self):
        rows = corpus()
        alternate = copy.deepcopy(rows[0])
        alternate["set"]["item"] = "Choice Specs"
        alternate["count"] = 9
        rows.append(alternate)
        observed, _ = revealed_original_sets(fixture())
        a = SetCorpus(rows).impute(observed["p1"], "same", "p1")
        b = SetCorpus(list(reversed(rows))).impute(observed["p1"], "same", "p1")
        self.assertEqual(a, b)
        observed["p1"][0]["moves"] = ["Sacred Fire"]
        chosen, audit = SetCorpus(rows).impute(observed["p1"], "same", "p1")
        self.assertIsNone(chosen)
        self.assertEqual(audit["reason"], "no_matching_legal_set")

    def test_public_gender_mismatch_is_not_silently_filled(self):
        observed, _ = revealed_original_sets(fixture().get("log").replace("|Dragapult|", "|Dragapult, F|", 1))
        rows = corpus()
        rows[0]["set"]["gender"] = "M"
        chosen, _ = SetCorpus(rows).impute(observed["p1"], "gender", "p1")
        self.assertIsNone(chosen)

    def test_internal_battle_bond_alias_matches_public_greninja(self):
        row = dict(set=dict(species="Greninja-Bond", moves=["Surf"], item="Choice Specs",
                            ability="Battle Bond", teraType="Water"), count=1)
        observed = [dict(species="Greninja", moves=["Surf"], item=None, ability="Battle Bond",
                         teraType=None, gender=None, level=100)]
        chosen, _ = SetCorpus([row]).impute(observed, "bond", "p1")
        self.assertEqual(chosen[0]["species"], "Greninja-Bond")

    def test_trace_attributes_original_ability_to_correct_side(self):
        raw = fixture("|-ability|p1a: Clever Nick|Quark Drive|[from] ability: Trace|[of] p2a: Secret Nick\n")
        revealed, reasons = revealed_original_sets(raw)
        self.assertFalse(reasons)
        self.assertEqual(revealed["p1"][0]["ability"], "Trace")
        self.assertEqual(revealed["p2"][0]["ability"], "Quark Drive")

    def test_multiple_original_item_moves_excludes_choice_set(self):
        raw = fixture("|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n|turn|2\n"
                      "|move|p1a: Clever Nick|U-turn|p2a: Secret Nick\n")
        observed, _ = revealed_original_sets(raw)
        rows = corpus()
        rows[0]["set"]["item"] = "Choice Specs"
        chosen, audit = SetCorpus(rows).impute(observed["p1"], "choice", "p1")
        self.assertIsNone(chosen)
        self.assertEqual(audit["reason"], "no_matching_legal_set")


class ReplayBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = BridgeClient(corpus())

    @classmethod
    def tearDownClass(cls):
        cls.bridge.close()

    def recover(self, raw):
        result = self.bridge.recover(raw, "semantic-fixture", corpus())
        self.assertFalse(result["exclusions"])
        return result["records"]

    def test_pinned_cpu_identity(self):
        hello = self.bridge.request(dict(op="hello"))
        self.assertEqual(hello["revision"], "0a00a759c9a4382a2877088d828302ec294a05a5")
        self.assertEqual(hello["poke_env"], "0.8.3.3")
        self.assertFalse(hello["gpu"])

    def test_known_battle_only_forms_reenter_original_slots_offline_and_live(self):
        for case in FORMES:
            with self.subTest(form=case[1]):
                raw, own, source = forme_fixture(case)
                result = self.bridge.recover(raw, "form-reentry", source)
                self.assertFalse(result["exclusions"])
                rows = [r for r in result["records"] if r["perspective"] == "p1"]
                prior = next(r for r in rows if r["decision_kind"] == "turn_action" and r["turn"] == 1)
                bench = next(r for r in rows if r["turn"] == 3)
                after = next(r for r in rows if r["turn"] == 4)
                self.assertEqual(prior["snapshot"]["own_team"][0]["species"], switch_original_species(case[0]))
                self.assertEqual(bench["snapshot"]["own_active_slot"], 2)
                self.assertEqual(after["snapshot"]["own_active_slot"], 1)
                expected_ability = case[4].lower().replace(" ", "").replace("(", "").replace(")", "")
                self.assertEqual(bench["snapshot"]["own_team"][0]["ability"], expected_ability)
                self.assertEqual(after["snapshot"]["own_team"][0]["ability"], expected_ability)
                if case[2]:
                    self.assertFalse(after["snapshot"]["can_tera"])
                    self.assertEqual(after["snapshot"]["own_team"][0]["types"], [case[2].lower()])
                for row in result["records"]:
                    original = result["original_sets"][row["perspective"]]
                    live = self.bridge.snapshot(raw["log"].splitlines()[:row["cutoff_line"]],
                                                original, row["perspective"], row["decision_kind"])
                    self.assertEqual(live, row["snapshot"])
                    self.assertTrue(row["label"] is None or row["label"] in {a["id"] for a in row["actions"]})
                changed = copy.deepcopy(raw)
                changed["log"] = changed["log"].replace("|Rest|p2a: Secret Nick", "|Sleep Talk|p2a: Secret Nick")
                changed["log"] = changed["log"].replace("Clever Nick", "New Own Name").replace("Secret Nick", "New Opponent Name")
                changed["winner"], changed["rating"] = "Bob", 9999
                updated = self.bridge.recover(changed, "form-reentry", source)
                self.assertFalse(updated["exclusions"])
                for row in rows:
                    if row["turn"] in {1, 2}:
                        other = next(r for r in updated["records"] if r["perspective"] == "p1" and
                                     r["turn"] == row["turn"] and r["decision_kind"] == row["decision_kind"])
                        self.assertEqual(row["snapshot"], other["snapshot"])
                        self.assertEqual(row["actions"], other["actions"])

    def test_explicit_current_ability_changes_and_suppression_survive_form_projection(self):
        raw, own, _ = forme_fixture(FORMES[1])
        prefix = raw["log"].split("|upkeep", 1)[0]
        changed = self.bridge.snapshot(prefix + "|-ability|p1a: Clever Nick|Insomnia\n",
                                       own, "p1", "turn_action")
        self.assertEqual(changed["own_team"][0]["ability"], "insomnia")
        suppressed = self.bridge.snapshot(prefix + "|-endability|p1a: Clever Nick\n",
                                          own, "p1", "turn_action")
        self.assertIsNone(suppressed["own_team"][0]["ability"])
        self.assertEqual(suppressed["own_team"][0]["original_set"]["ability"], "waterabsorb")

    def test_wrong_mask_switch_is_rejected_by_shared_snapshot(self):
        raw, own, _ = forme_fixture(FORMES[1])
        raw["log"] = raw["log"].replace("|Ogerpon-Wellspring-Tera|100/100", "|Ogerpon-Teal-Tera|100/100")
        with self.assertRaisesRegex(RuntimeError, "unsupported original-slot species or forme"):
            self.bridge.snapshot(raw["log"], own, "p1", "turn_action")

    def test_life_orb_recoil_reveals_item_beyond_history_window(self):
        prefix = fixture()["log"]
        before = self.bridge.snapshot(prefix, sets(P1), "p1", "turn_action")
        self.assertIsNone(before["opponent_team"][0]["item"])
        plain_damage = prefix + "|-damage|p2a: Secret Nick|90/100\n"
        hidden = self.bridge.snapshot(plain_damage, sets(P1), "p1", "turn_action")
        self.assertIsNone(hidden["opponent_team"][0]["item"])
        revealed = prefix + "|-damage|p2a: Secret Nick|90/100|[from] item: Life Orb\n"
        after = self.bridge.snapshot(revealed, sets(P1), "p1", "turn_action")
        self.assertEqual(after["opponent_team"][0]["item"], "lifeorb")
        later = revealed + "".join(f"|upkeep|\n|turn|{turn}\n" for turn in range(2, 8))
        state = self.bridge.snapshot(later, sets(P1), "p1", "turn_action")
        self.assertNotIn("Life Orb", json.dumps(state["history"]))
        self.assertEqual(state["opponent_team"][0]["item"], "lifeorb")
        self.assertTrue(all(m["item"] is None for m in state["opponent_team"][1:]))
        # Visibility persists, but the current item remains parser-owned.
        removed = later + "|-enditem|p2a: Secret Nick|Life Orb|[from] move: Knock Off\n"
        state = self.bridge.snapshot(removed, sets(P1), "p1", "turn_action")
        self.assertIsNone(state["opponent_team"][0]["item"])
        changed = removed + "|-item|p2a: Secret Nick|Choice Scarf\n"
        state = self.bridge.snapshot(changed, sets(P1), "p1", "turn_action")
        self.assertEqual(state["opponent_team"][0]["item"], "choicescarf")

    def test_future_opponent_move_tera_winner_and_names_do_not_change_past_input(self):
        prefix = fixture()["log"]
        initial = self.bridge.snapshot(prefix, sets(P1), "p1", "turn_action")
        changed = prefix.replace("Alice", "Other Alice").replace("Bob", "Other Bob")
        changed = changed.replace("Clever Nick", "A Completely Different Nick").replace("Secret Nick", "Another Nick")
        actual = self.bridge.snapshot(changed, sets(P1), "p1", "turn_action")
        self.assertEqual(initial, actual)
        encoded = json.dumps(initial)
        self.assertNotIn("Nick", encoded)
        self.assertNotIn("Alice", encoded)
        self.assertNotIn("Bob", encoded)
        self.assertFalse(initial["opponent_team"][0]["moves"])
        self.assertIsNone(initial["opponent_team"][0]["tera_type"])
        self.assertIsNone(initial["opponent_team"][0]["ability"])
        first = fixture("|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n"
                        "|move|p2a: Secret Nick|U-turn|p1a: Clever Nick\n|win|Alice\n")
        second = copy.deepcopy(first)
        second["log"] = second["log"].replace("|U-turn|p1", "|Rest|p1").replace("|win|Alice", "|win|Bob")
        second["rating"] = 9999
        r1, r2 = self.recover(first), self.recover(second)
        a = next(r for r in r1 if r["perspective"] == "p1" and r["turn"] == 1)
        b = next(r for r in r2 if r["perspective"] == "p1" and r["turn"] == 1)
        self.assertEqual(a["snapshot"], b["snapshot"])
        self.assertEqual(a["actions"], b["actions"])

    def test_lead_and_pivot_cutoffs_and_live_projection_match(self):
        raw = fixture("|move|p1a: Clever Nick|U-turn|p2a: Secret Nick\n"
            "|-damage|p2a: Secret Nick|80/100\n|\n|t:|123\n"
            "|switch|p1a: Zapdos Nick|Zapdos|100/100\n"
            "|move|p2a: Secret Nick|Shadow Ball|p1a: Zapdos Nick\n"
            "|-damage|p1a: Zapdos Nick|50/100\n|upkeep\n|turn|2\n")
        rows = self.recover(raw)
        leads = [r for r in rows if r["decision_kind"] == "lead"]
        self.assertEqual([r["label"] for r in leads], ["lead:1", "lead:1"])
        self.assertTrue(all(r["snapshot"]["opponent_active_slot"] is None for r in leads))
        pivot = next(r for r in rows if r["decision_kind"] == "pivot_switch")
        self.assertEqual(pivot["label"], "switch:2")
        self.assertEqual(pivot["snapshot"]["opponent_team"][0]["hp_percent"], 80)
        self.assertFalse(pivot["snapshot"]["opponent_team"][0]["moves"])
        for row in rows:
            prefix = raw["log"].splitlines()[:row["cutoff_line"]]
            original = [m["original_set"] for m in row["snapshot"]["own_team"]]
            live = self.bridge.snapshot(prefix, original, row["perspective"], row["decision_kind"])
            self.assertEqual(live, row["snapshot"])

    def test_simultaneous_faint_replacements_do_not_observe_other_choice(self):
        raw = fixture("|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n"
            "|-damage|p2a: Secret Nick|0 fnt\n|faint|p2a: Secret Nick\n"
            "|-damage|p1a: Clever Nick|0 fnt\n|faint|p1a: Clever Nick\n|upkeep\n|\n"
            "|switch|p1a: Zapdos Nick|Zapdos|100/100\n"
            "|switch|p2a: Crown Nick|Iron Crown|100/100\n|turn|2\n")
        rows = [r for r in self.recover(raw) if r["decision_kind"] == "forced_switch"]
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["label"] for r in rows}, {"switch:2"})
        self.assertEqual(len({r["cutoff_line"] for r in rows}), 1)
        self.assertTrue(all(r["snapshot"]["opponent_active_slot"] == 1 for r in rows))
        self.assertTrue(all(r["snapshot"]["own_team"][0]["status"] == "fnt" for r in rows))

    def test_switch_out_cleanup_is_after_pivot_choice_even_without_blank(self):
        raw = fixture("|move|p1a: Clever Nick|U-turn|p2a: Secret Nick\n"
                      "|-damage|p2a: Secret Nick|80/100\n"
                      "|-end|p1a: Clever Nick|Quark Drive|[silent]\n"
                      "|switch|p1a: Zapdos Nick|Zapdos|100/100\n")
        row = next(r for r in self.recover(raw) if r["decision_kind"] == "pivot_switch")
        self.assertEqual(raw["log"].splitlines()[row["cutoff_line"]].split("|")[1], "-end")
        self.assertFalse(any(h["event"] == "-end" for h in row["snapshot"]["history"]))

    def test_tera_consumption_and_type_persist_across_switch_out(self):
        raw = fixture("|-terastallize|p1a: Clever Nick|Ghost\n"
            "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n|upkeep\n|turn|2\n"
            "|switch|p1a: Zapdos Nick|Zapdos|100/100\n|upkeep\n|turn|3\n"
            "|switch|p1a: Clever Nick|Dragapult|100/100\n|upkeep\n|turn|4\n")
        rows = [r for r in self.recover(raw) if r["perspective"] == "p1"]
        first = next(r for r in rows if r["turn"] == 1)
        last = next(r for r in rows if r["turn"] == 4)
        self.assertEqual(first["label"], "move:shadowball:tera")
        self.assertTrue(first["snapshot"]["can_tera"])
        self.assertFalse(last["snapshot"]["can_tera"])
        self.assertEqual(last["snapshot"]["own_team"][0]["types"], ["ghost"])
        self.assertFalse(any(a.get("tera") for a in last["actions"]))

    def test_sleep_talk_labels_primary_choice_and_unknown_selection_is_masked(self):
        raw = fixture("|-status|p1a: Clever Nick|slp\n"
            "|move|p1a: Clever Nick|Sleep Talk|p1a: Clever Nick\n"
            "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick|[from] move: Sleep Talk\n"
            "|cant|p2a: Secret Nick|par\n|upkeep\n|turn|2\n")
        rows = self.recover(raw)
        first = next(r for r in rows if r["turn"] == 1 and r["perspective"] == "p1")
        other = next(r for r in rows if r["turn"] == 1 and r["perspective"] == "p2")
        self.assertEqual(first["label"], "move:sleeptalk:normal")
        self.assertIsNone(other["label"])
        self.assertEqual(other["audit"]["mask_reason"], "unobserved_choice")
        second = next(r for r in rows if r["turn"] == 2 and r["perspective"] == "p1")
        move_pp = {m["id"]:m["pp"] for m in second["snapshot"]["own_team"][0]["moves"]}
        self.assertEqual(move_pp["sleeptalk"], 15)
        self.assertEqual(move_pp["shadowball"], 24)

    def test_taunt_is_quarantined_instead_of_emitting_superset_menu(self):
        raw = fixture("|-start|p1a: Clever Nick|move: Taunt\n|upkeep\n|turn|2\n"
                      "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n")
        row = next(r for r in self.recover(raw) if r["turn"] == 2 and r["perspective"] == "p1")
        self.assertEqual(row["audit"]["mask_reason"], "unsupported_legal_mask:taunt")
        self.assertIsNone(row["label"])
        self.assertFalse(row["actions"])

    def test_private_hp_fraction_is_projected_to_public_percentage(self):
        public = fixture("|-damage|p1a: Clever Nick|50/100\n")["log"]
        private = public.replace("|50/100", "|150/300")
        self.assertEqual(self.bridge.snapshot(public, sets(P1), "p1", "turn_action"),
                         self.bridge.snapshot(private, sets(P1), "p1", "turn_action"))

    def test_pressure_uses_two_pp_for_targeted_primary_move(self):
        raw = fixture("|-ability|p2a: Secret Nick|Pressure\n"
                      "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n|upkeep\n|turn|2\n")
        row = next(r for r in self.recover(raw) if r["turn"] == 2 and r["perspective"] == "p1")
        pp = {m["id"]:m["pp"] for m in row["snapshot"]["own_team"][0]["moves"]}
        self.assertEqual(pp["shadowball"], 22)

    def test_pain_split_updates_both_hp_values(self):
        raw = fixture("|-sethp|p1a: Clever Nick|50/100|p2a: Secret Nick|75/100\n")
        snapshot = self.bridge.snapshot(raw["log"], sets(P1), "p1", "turn_action")
        self.assertEqual(snapshot["own_team"][0]["hp_percent"], 50)
        self.assertEqual(snapshot["opponent_team"][0]["hp_percent"], 75)

    def test_automatic_outrage_is_not_a_new_choice(self):
        raw = fixture("|move|p1a: Clever Nick|Outrage|p2a: Secret Nick\n|upkeep\n|turn|2\n"
                      "|move|p1a: Clever Nick|Outrage|p2a: Secret Nick\n")
        source = corpus()
        source[0]["set"]["moves"][0] = "Outrage"
        result = self.bridge.recover(raw, "automatic", source)
        self.assertFalse(result["exclusions"])
        rows = [r for r in result["records"] if r["perspective"] == "p1" and r["decision_kind"] == "turn_action"]
        self.assertEqual(rows[0]["label"], "move:outrage:normal")
        self.assertIsNone(rows[1]["label"])
        self.assertEqual(rows[1]["audit"]["mask_reason"], "automatic_continuation:outrage")

    def test_unobserved_first_choice_lock_stays_quarantined_until_switch(self):
        raw = fixture("|cant|p1a: Clever Nick|par\n|upkeep\n|turn|2\n"
                      "|move|p1a: Clever Nick|Shadow Ball|p2a: Secret Nick\n|upkeep\n|turn|3\n")
        source = corpus()
        source[0]["set"]["item"] = "Choice Specs"
        result = self.bridge.recover(raw, "unknown_choice", source)
        self.assertFalse(result["exclusions"])
        rows = [r for r in result["records"] if r["perspective"] == "p1" and r["turn"] in {2, 3}]
        self.assertTrue(all(r["audit"]["mask_reason"] == "unsupported_legal_mask:unobserved_choice_lock" for r in rows))


class OptionalPublicStateTests(unittest.TestCase):
    """D-195 optional fields: item held/removed, sleep/toxic counters, weather start turn."""

    @classmethod
    def setUpClass(cls):
        cls.bridge = BridgeClient(corpus())

    @classmethod
    def tearDownClass(cls):
        cls.bridge.close()

    def state(self, events):
        return self.bridge.snapshot(fixture()["log"] + events, sets(P1), "p1", "turn_action")

    def item(self, events, slot=1):
        return self.state(events)["opponent_team"][slot - 1]["item_state"]

    def test_item_state_separates_unknown_held_and_removal_causes(self):
        self.assertEqual(self.item(""), dict(state="unknown", item=None, cause=None))
        healed = "|-heal|p2a: Secret Nick|94/100|[from] item: Leftovers\n"
        state = self.state(healed)
        # The legacy item field keeps its reveal rule; only item_state learns effect reveals.
        self.assertIsNone(state["opponent_team"][0]["item"])
        self.assertEqual(state["opponent_team"][0]["item_state"], dict(state="held", item="leftovers", cause=None))
        later = healed + "".join(f"|upkeep|\n|turn|{turn}\n" for turn in range(2, 8))
        self.assertEqual(self.item(later)["item"], "leftovers")
        knocked = later + "|-enditem|p2a: Secret Nick|Leftovers|[from] move: Knock Off|[of] p1a: Clever Nick\n"
        self.assertEqual(self.item(knocked), dict(state="removed", item="leftovers", cause="knockoff"))
        balloon = "|-item|p2a: Secret Nick|Air Balloon\n"
        self.assertEqual(self.item(balloon), dict(state="held", item="airballoon", cause=None))
        self.assertEqual(self.item(balloon + "|-enditem|p2a: Secret Nick|Air Balloon\n"),
                         dict(state="removed", item="airballoon", cause="popped"))
        self.assertEqual(self.item("|-enditem|p2a: Secret Nick|Sitrus Berry|[eat]\n"),
                         dict(state="removed", item="sitrusberry", cause="consumed"))
        self.assertEqual(self.item("|-enditem|p2a: Secret Nick|Booster Energy\n")["cause"], "consumed")
        self.assertEqual(self.item("|-enditem|p2a: Secret Nick|Leftovers|[silent]|[from] move: Thief|"
                                   "[of] p1a: Clever Nick\n")["cause"], "other")
        helmet = "|-damage|p1a: Clever Nick|80/100|[from] item: Rocky Helmet|[of] p2a: Secret Nick\n"
        self.assertEqual(self.item(helmet)["item"], "rockyhelmet")
        regained = knocked + "|-item|p2a: Secret Nick|Choice Scarf\n"
        self.assertEqual(self.item(regained), dict(state="held", item="choicescarf", cause=None))
        self.assertNotIn("item_state", self.state(healed)["own_team"][0])

    def test_sleep_and_toxic_counters_follow_public_attempts_and_switches(self):
        rest = "|move|p2a: Secret Nick|Rest|p2a: Secret Nick\n|-status|p2a: Secret Nick|slp|[from] move: Rest\n"
        mon = self.state(rest)["opponent_team"][0]
        self.assertEqual((mon["status"], mon["status_counter"], mon["status_source"]), ("slp", 0, "rest"))
        # Showdown prints `cant|slp` before Sleep Talk too: one attempt, one count.
        attempts = rest + "|upkeep|\n|turn|2\n|cant|p2a: Secret Nick|slp\n" \
            "|move|p2a: Secret Nick|Sleep Talk|p2a: Secret Nick\n" \
            "|move|p2a: Secret Nick|Rest||[from] move: Sleep Talk|[still]\n|upkeep|\n|turn|3\n"
        self.assertEqual(self.state(attempts)["opponent_team"][0]["status_counter"], 1)
        woke = attempts + "|-curestatus|p2a: Secret Nick|slp|[msg]\n"
        mon = self.state(woke)["opponent_team"][0]
        self.assertEqual((mon["status"], mon["status_counter"], mon["status_source"]), (None, None, None))
        tox = "|-status|p2a: Secret Nick|tox\n|upkeep|\n|turn|2\n|-damage|p2a: Secret Nick|94/100 tox|[from] psn\n" \
            "|upkeep|\n|turn|3\n|-damage|p2a: Secret Nick|81/100 tox|[from] psn\n"
        self.assertEqual(self.state(tox)["opponent_team"][0]["status_counter"], 2)
        back = tox + "|switch|p2a: Crown|Iron Crown|100/100\n|switch|p2a: Secret Nick|Iron Hands|81/100 tox\n"
        self.assertEqual(self.state(back)["opponent_team"][0]["status_counter"], 0)
        own = "|-status|p1a: Clever Nick|slp\n|upkeep|\n|turn|2\n|cant|p1a: Clever Nick|slp\n"
        mon = self.state(own)["own_team"][0]
        self.assertEqual((mon["status_counter"], mon["status_source"]), (1, None))
        burned = self.state("|-status|p2a: Secret Nick|brn\n")["opponent_team"][0]
        self.assertEqual((burned["status"], burned["status_counter"]), ("brn", None))

    def test_weather_turn_is_start_turn_until_weather_ends(self):
        self.assertIsNone(self.state("")["weather_turn"])
        rain = "|-weather|RainDance|[from] ability: Drizzle|[of] p2a: Secret Nick\n|upkeep|\n|turn|2\n"
        self.assertEqual(self.state(rain)["weather_turn"], 1)
        kept = rain + "|-weather|RainDance|[upkeep]\n|upkeep|\n|turn|3\n"
        self.assertEqual(self.state(kept)["weather_turn"], 1)
        self.assertIsNone(self.state(kept + "|-weather|none\n")["weather_turn"])


if __name__ == "__main__":
    unittest.main()
