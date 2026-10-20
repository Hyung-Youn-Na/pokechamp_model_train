"""Behavior checks for public protocol boundaries and the new portable viewer."""
from __future__ import annotations

import json

import pytest

from integration.jev_eval import turn_logs, viewer
from integration.jev27b.study import seal, write_json


def protocols(user="model"):
    return [dict(type="protocol", username=user, sequence=1, event_seq=1, protocol="\n".join([
        ">battle-gen9ou-fixture", "|init|battle", f"|player|p1|{user}", "|player|p2|other",
        "|poke|p1|Pikachu, L50", "|poke|p2|Mew, L50", "|teampreview",
        '|request|{"teamPreview":true,"secret":"OWN PRIVATE REQUEST"}',
    ])), dict(type="protocol", username=user, sequence=2, event_seq=8, protocol="\n".join([
        ">battle-gen9ou-fixture", "|start", "|switch|p1a: Pikachu|Pikachu|100/100",
        "|switch|p2a: Mew|Mew|100/100", "|turn|1", '|request|{"rqid":2}',
        "|move|p1a: Pikachu|Thunderbolt|p2a: Mew", "|-damage|p2a: Mew|0 fnt",
        "|faint|p2a: Mew", '|request|{"rqid":3,"forceSwitch":[true]}',
        "|switch|p2a: Snorlax|Snorlax|100/100", "|-newmechanic|p2a: Snorlax|public-unknown",
        "|c|other|PRIVATE CHAT", "|debug|SECRET DEBUG", "|sentchoice|PRIVATE CHOICE",
        "|J|joined-user", "|t:|123", "|-hint|public battle hint",
    ])), dict(type="protocol", username=user, sequence=3, event_seq=19, protocol="\n".join([
        "|turn|2", "|-heal|p2a: Snorlax|90/100", "|turn|3", '|request|{"rqid":4}',
        "|move|p1a: Pikachu|Thunderbolt|p2a: Snorlax", f"|win|{user}",
    ]))]


def decisions(user="model"):
    return [dict(id=f"{user}-{n}", turn=turn, technical=dict(input_boundary=dict(
        protocol_event_seq=sequence, line_index=row)))
        for n, (turn, sequence, row) in enumerate(((0, 1, 7), (1, 2, 5), (1, 2, 9), (3, 3, 3)), 1)]


def test_public_rows_preserve_actor_coordinates_and_exclude_private_sources():
    events = protocols()
    events.insert(1, dict(type="protocol", username="other", sequence=1,
        protocol='|request|FOREIGN PRIVATE\n|split|p2\n|-damage|p1a: Pikachu|SECRET HP'))
    events.append(dict(type="protocol", username="model", sequence=4,
                       direction="outbound", protocol="|move|PRIVATE OUTBOUND"))
    events.append(dict(type="server_stdout", username="model", protocol="|move|SERVER SECRET"))
    log = turn_logs.build_turn_log(events, "model", "p1", decisions())
    assert [part["turn"] for part in log["turns"]] == [0, 1, 2, 3]
    assert [part["decision_ids"] for part in log["turns"]] == [["model-1"], ["model-2", "model-3"], [], ["model-4"]]
    rows = [row for part in log["turns"] for row in part["rows"]]
    assert next(row for row in rows if row["protocol"].startswith("|move|"))["line_index"] == 6
    assert next(row for row in rows if row["protocol"].startswith("|-hint|"))["line_index"] == 17
    raw = turn_logs.raw_text(rows)
    assert not any(word in raw for word in ("PRIVATE", "SECRET", "|request|", "|sentchoice|", "|J|", "|t:|"))
    assert "public battle hint" in raw
    assert log["terminal"] == dict(kind="win", turn=3, sequence=3, line_index=5, winner="model")
    assert log["status"] == "completed"


def test_cutoff_is_inclusive_mid_frame_and_same_turn_decisions_remain_distinct():
    log = turn_logs.build_turn_log(protocols(), "model", "p1", decisions())
    full = turn_logs.raw_text(turn_logs.rows_for(log, 1))
    before_action = turn_logs.rows_for(log, 1, decision_id="model-2", until_decision=True)
    before_switch = turn_logs.rows_for(log, 1, decision_id="model-3", until_decision=True)
    assert [row["line_index"] for row in before_action] == [4]
    assert [row["line_index"] for row in before_switch] == [4, 6, 7, 8]
    assert "|switch|p2a: Snorlax" in full and "|-newmechanic|" in full
    assert "Thunderbolt" not in turn_logs.raw_text(before_action)
    assert "Thunderbolt" in turn_logs.raw_text(before_switch)
    assert "Snorlax" not in turn_logs.raw_text(before_switch)
    # A decision whose cutoff is itself a public row includes that row exactly.
    ds = decisions()
    ds[1]["technical"]["input_boundary"]["line_index"] = 6
    inclusive = turn_logs.build_turn_log(protocols(), "model", "p1", ds)
    assert turn_logs.rows_for(inclusive, 1, decision_id="model-2", until_decision=True)[-1]["line_index"] == 6


def test_fixed_parser_keeps_readable_moves_and_unsupported_raw_event():
    log = turn_logs.build_turn_log(protocols(), "model", "p1", decisions())
    rows = [row for part in log["turns"] for row in part["rows"]]
    move = next(row for row in rows if row["protocol"].startswith("|move|"))
    assert move["parsed"] and "Pikachu" in move["text"] and "Thunderbolt" in move["text"]
    unknown = next(row for row in rows if row["protocol"].startswith("|-newmechanic|"))
    assert not unknown["parsed"] and unknown["text"] == unknown["protocol"]
    assert turn_logs.parser_identity()["full_log_model_input"] is False


@pytest.mark.parametrize("mutation", ["split", "missing_sequence", "duplicate_sequence", "future_cutoff", "wrong_turn", "bad_cutoff"])
def test_ambiguous_sources_and_cutoffs_are_rejected(mutation):
    events, ds = protocols(), decisions()
    if mutation == "split":
        events[1]["protocol"] += "\n|split|p1\n|-damage|p1a: Pikachu|1/100\n|-damage|p1a: Pikachu|1/300"
    elif mutation == "missing_sequence":
        events[0].pop("sequence")
    elif mutation == "duplicate_sequence":
        events[1]["sequence"] = 1
    elif mutation == "future_cutoff":
        ds[1]["technical"]["input_boundary"]["line_index"] = 200
    elif mutation == "wrong_turn":
        ds[1]["turn"] = 3
    else:
        ds[1]["technical"]["input_boundary"]["line_index"] = True
    with pytest.raises(ValueError):
        turn_logs.build_turn_log(events, "model", "p1", ds)


def test_no_terminal_stays_interrupted_and_tie_belongs_to_final_turn():
    events = protocols()
    events[-1]["protocol"] = events[-1]["protocol"].rsplit("\n", 1)[0]
    log = turn_logs.build_turn_log(events, "model", "p1", decisions())
    assert log["status"] == "interrupted" and log["terminal"] is None
    assert log["terminal_label"] == "진행 중 중단"
    events[-1]["protocol"] += "\n|tie|"
    log = turn_logs.build_turn_log(events, "model", "p1", decisions())
    assert log["terminal"]["kind"] == "tie" and log["terminal"]["turn"] == 3
    assert log["turns"][-1]["rows"][-1]["protocol"] == "|tie|"


def payload(turn, kind, automatic=False, *, version="jev-choice-v6"):
    return dict(state=dict(version=version, turn=turn, decision_kind=kind,
        self_team=[dict(slot=1, species="Pikachu", active=True, condition="100/100",
            ability=dict(name="Static"), item=dict(name="Light Ball"),
            current_move_slots=[dict(slot=1, id="thunderbolt", name="Thunderbolt")])],
        opponent_team=[
            dict(species="Mew", active=False, hp_percent=0, hp_precision="rounded",
                moves=[dict(id="psychic", name="Psychic")], item=dict(knowledge="confirmed_absent"),
                ability=dict(knowledge="suppressed", suppressed=True,
                             underlying_ability=dict(id="synchronize", name="Synchronize")),
                baseAbility=dict(id="synchronize", name="Synchronize")),
            dict(species="Snorlax", active=True, hp_percent=37.125, hp_precision="rounded",
                moves=[dict(id="bodyslam", name="Body Slam")], item=dict(id="leftovers", name="Leftovers"),
                ability=dict(id="immunity", name="Immunity", suppressed="unknown"), baseAbility=dict(knowledge="unknown")),
            dict(species="Zapdos", active=False, hp_percent="unknown", hp_precision="unknown",
                moves="unknown", item=dict(knowledge="unknown"), ability=dict(knowledge="unknown"), baseAbility=dict(knowledge="unknown")),
        ]), questions=dict(action=dict(type="choice", instructions="Choose one. 原文 </script>",
            criteria={"move:1": dict(kind="move", slot=1)} if automatic else
            {"move:2": dict(kind="move", slot=2, move=dict(name="Volt Switch")),
             "move:1": dict(kind="move", slot=1)})))


def viewer_collection(directory, *, before_input_failure=False, experiment="EX-086"):
    directory.mkdir()
    user = "model"
    version = "jev-choice-v6-no-damage" if experiment == "EX-090" else "jev-choice-v6"
    ds, frames, events = decisions(user), protocols(user), []
    if before_input_failure:
        ds, frames = [], frames[:1]
    for frame in frames:
        events.append(frame)
        for n, decision in enumerate(ds):
            if decision["technical"]["input_boundary"]["protocol_event_seq"] != frame["sequence"]:
                continue
            kind = ("lead", "turn_action", "forced_switch", "turn_action")[n]
            automatic = kind == "forced_switch"
            body = payload(decision["turn"], kind, automatic, version=version)
            if experiment == "EX-090":
                body["state"]["speed_comparison"] = dict(status="available", self_speed=[200, 200],
                    opponent_speed=[100, 180], speed_certainty="recommended_sets_only")
            events.append(dict(type="input", decision=decision["id"], payload=body,
                commands={key: "/choose move 1" for key in body["questions"]["action"]["criteria"]},
                boundary=decision["technical"]["input_boundary"], observation_identity={}))
            if not automatic:
                request = dict(model="fixture/JEV", **body)
                response = dict(model="fixture/JEV", answers=dict(action=dict(choice="move:1",
                    probabilities={key: .5 for key in body["questions"]["action"]["criteria"]})),
                    usage=dict(input_tokens=123, output_tokens=0))
                events.extend([dict(type="http_request", decision=decision["id"], body=request,
                                    raw_body=json.dumps(request)),
                    dict(type="response", decision=decision["id"], body=response, elapsed_seconds=.2)])
            events.extend([dict(type="selection", decision=decision["id"], automatic=automatic,
                                choice="move:1", command="/choose move 1"),
                           dict(type="wire", decision=decision["id"], command="/choose move 1")])
    events.append(dict(type="protocol", username="other", sequence=1, protocol="|request|FOREIGN PRIVATE\n|split|p2"))
    for n, event in enumerate(events, 1):
        event["event_seq"] = n
    row = dict(slot_id="fixture-p1", paired_slot_id="fixture", jev_actor="p1")
    outcome = dict(row, slot=1, username=user, completed=not before_input_failure, audit_passed=True,
                   outcome="output_failure" if before_input_failure else "player_won")
    result = dict(planned=32, completed=int(not before_input_failure), completed_pairs=0,
        failed=int(before_input_failure), invalid=0, unattempted=31, decisions=len(ds),
        outcomes=[outcome], overall=dict(wins=int(not before_input_failure), draws=0, losses=0),
        final_audit_passed=True)
    (directory / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    write_json(directory / "manifest.json", dict(experiment_id=experiment, schema_version=version,
        schedule=[row], source=viewer.source_identity()))
    write_json(directory / "result.json", result)
    attempt = directory / "battle-1"
    attempt.mkdir()
    write_json(attempt / "request.json", dict(slot=row, names={"p1": user, "p2": "other"}))
    write_json(attempt / "outcome.json", outcome)
    seal(directory)
    return directory


@pytest.mark.parametrize("experiment", ["EX-086", "EX-088", "EX-089", "EX-090"])
def test_portable_export_preserves_raw_decisions_order_and_actor_only_turns(tmp_path, experiment):
    source = viewer_collection(tmp_path / "source", experiment=experiment)
    output = tmp_path / "export"
    checked = viewer.export(source, output, compared={})
    assert checked["passed"] and checked["games"] == 1 and checked["decisions"] == 4
    assert checked["all_public_rows_and_cutoffs_compared"]
    assert (source / "events.jsonl").read_bytes() == (output / "raw/events.jsonl").read_bytes()
    data = json.loads((output / "battle-1/decisions.json").read_text())
    assert data["experiment"] == experiment
    assert experiment in (output / "index.html").read_text()
    assert list(data["decisions"][1]["request"]["questions"]["action"]["criteria"]) == ["move:2", "move:1"]
    assert data["decisions"][2]["request"] is None and data["decisions"][2]["automatic"]
    assert "PRIVATE" not in (output / "battle-1/showdown.log").read_text()
    provenance = json.loads((output / "provenance.json").read_text())
    assert provenance["viewer_source"] == provenance["source_manifest_viewer_files"] == viewer.source_identity()
    if experiment == "EX-090":
        for metadata in (checked, data, provenance):
            assert metadata["input_profile"] == "jev-choice-v6-no-damage"
            assert metadata["treatment"] == dict(damage_predictions_enabled=False, speed_comparison_enabled=True)
        assert "피해 예측 비활성화 · 스피드 비교 유지" in (output / "index.html").read_text()
        assert "EX-089" in (output / "index.html").read_text()
        assert "EX-083" not in (output / "index.html").read_text()
        assert "damage_index" not in data
        assert data["decisions"][1]["request"]["state"]["speed_comparison"]["self_speed"] == [200, 200]
    else:
        assert "treatment" not in data and "input_profile" not in data
    assert "\\u003c/script\\u003e" in (output / "battle-1/index.html").read_text()
    with pytest.raises(FileExistsError):
        viewer.export(source, output)


@pytest.mark.parametrize("change", ["original", "decision", "turn", "embedded"])
def test_export_verification_catches_independent_mutations(tmp_path, change):
    source = viewer_collection(tmp_path / "source")
    output = tmp_path / "export"
    viewer.export(source, output)
    if change == "original":
        (output / "raw/events.jsonl").write_text("changed\n")
    elif change in ("decision", "turn"):
        path = output / "battle-1/decisions.json"
        data = json.loads(path.read_text())
        if change == "decision":
            data["decisions"][1]["request"]["state"]["opponent_team"][0]["hp_percent"] = 100
        else:
            data["turn_log"]["turns"][1]["rows"][0]["line_index"] = 0
        write_json(path, data)
    else:
        path = output / "battle-1/index.html"
        path.write_text(path.read_text().replace('"hp_percent": 0', '"hp_percent": 99'))
    with pytest.raises(ValueError, match="differ"):
        viewer.verify_data(source, output)


def test_failure_before_input_still_exports_preparation_and_interruption(tmp_path):
    source = viewer_collection(tmp_path / "source", before_input_failure=True)
    output = tmp_path / "export"
    checked = viewer.export(source, output)
    assert checked["passed"] and checked["decisions"] == 0
    data = json.loads((output / "battle-1/decisions.json").read_text())
    assert data["turn_log"]["turns"][0]["turn"] == 0
    assert data["turn_log"]["terminal"] is None
    assert "진행 중 중단" in (output / "index.html").read_text()


def test_renderer_assets_must_be_in_the_execution_source(tmp_path):
    source = viewer_collection(tmp_path / "source")
    path = source / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["source"].pop("integration/jev_eval/viewer.js")
    write_json(path, manifest)
    seal(source)
    with pytest.raises(ValueError, match="frozen manifest"):
        viewer.export(source, tmp_path / "export")


@pytest.mark.parametrize("change", ["manifest", "request", "automatic"])
def test_no_damage_export_rejects_a_different_input_profile(tmp_path, change):
    source = viewer_collection(tmp_path / "source", experiment="EX-090")
    if change == "manifest":
        path = source / "manifest.json"
        value = json.loads(path.read_text())
        value["schema_version"] = "jev-choice-v6"
        write_json(path, value)
    else:
        path = source / "events.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if change == "request":
            next(row for row in rows if row["type"] == "http_request")["body"]["state"]["version"] = "jev-choice-v6"
        else:
            next(row for row in rows if row["type"] == "input" and row["decision"] == "model-3")["payload"]["state"]["version"] = "jev-choice-v6"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    seal(source)
    with pytest.raises(ValueError, match="input profile"):
        viewer.export(source, tmp_path / "export")
    assert not (tmp_path / "export").exists()


@pytest.mark.parametrize("change", ["provenance", "notice", "scenario_index"])
def test_no_damage_export_verifies_treatment_metadata_and_notice(tmp_path, change):
    source = viewer_collection(tmp_path / "source", experiment="EX-090")
    output = tmp_path / "export"
    viewer.export(source, output)
    if change == "notice":
        path = output / "index.html"
        path.write_text(path.read_text().replace("피해 예측 비활성화", "피해 예측 활성화"))
    elif change == "provenance":
        path = output / "provenance.json"
        value = json.loads(path.read_text())
        value["treatment"]["damage_predictions_enabled"] = True
        write_json(path, value)
    else:
        path = output / "battle-1/decisions.json"
        value = json.loads(path.read_text())
        value["damage_index"] = {}
        write_json(path, value)
    with pytest.raises(ValueError, match="treatment|disabled damage"):
        viewer.verify_data(source, output)


@pytest.mark.parametrize("experiment", ["EX-086", "EX-090"])
def test_browser_actual_summary_and_navigation(tmp_path, experiment):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    source = viewer_collection(tmp_path / "source", experiment=experiment)
    output = tmp_path / "export"
    viewer.export(source, output)
    checked = viewer.verify_browser(output, resource_check=lambda **kwargs: 0)
    assert checked["passed"] and checked["offline_relocated"]
    assert checked["synthetic_failure_fixture"] and len(checked["representative_screens"]) == 5
    assert checked["treatment_screens_checked"] == (5 if experiment == "EX-090" else 0)
    # One CPU fixture screen checks concrete public summary text independently.
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(offline=True)
        page = context.new_page()
        page.goto((output / "battle-1/index.html").as_uri())
        if experiment == "EX-090":
            assert page.locator("#treatment-note").inner_text() == "피해 예측 비활성화 · 스피드 비교 유지"
            page.click("#damage-tab")
            assert page.locator("#damage-status").get_attribute("data-state") == "disabled"
            assert page.locator("#damage-summary-section").is_hidden()
            assert page.locator("[data-copy=damage]").is_disabled()
        page.select_option("#decision", "1")
        page.click("#state-tab")
        rows = page.locator("[data-opponent-index]").all_text_contents()
        assert "0%" in rows[0] and "Psychic" in rows[0] and "Synchronize" in rows[0]
        assert "확인된 부재" in rows[0] and "억제됨" in rows[0]
        assert "37.13%" in rows[1] and "Body Slam" in rows[1] and "Leftovers" in rows[1]
        assert "Immunity · 억제 여부 미확인" in rows[1]
        assert "미확인" in rows[2] and "%" not in rows[2]
        page.click("#turn-log-tab")
        assert "선택한 결정 이후 결과" in page.locator("#turn-after").inner_text()
        page.check("#until-decision")
        assert "Thunderbolt" not in page.locator("#turn-readable").inner_text()
        page.select_option("#decision", "2")
        assert "Thunderbolt" in page.locator("#turn-readable").inner_text()
        assert "Snorlax" not in page.locator("#turn-readable").inner_text()
        page.select_option("#turn", "2")
        assert page.locator("#decision").input_value() == ""
        assert "이 턴에는 결정" in page.locator("#turn-status").inner_text()
        assert "|-heal|p2a: Snorlax|90/100" in page.locator("#turn-raw").text_content()
        page.select_option("#turn", "1")
        assert page.locator("#decision").input_value() == "1"
        page.click("#next")
        assert page.locator("#decision").input_value() == "2" and page.locator("#turn").input_value() == "1"
        context.close()
        browser.close()
