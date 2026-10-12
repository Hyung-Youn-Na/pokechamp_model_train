"""EX-043 sealed treatment, allocation and audit-before-admission boundaries."""

import hashlib
from collections import Counter
from contextlib import ExitStack

import pytest

from integration.pokechamp import benchmark as b
from integration.pokechamp import distributed_lead as d
from integration.pokechamp import team_preview_run as runner
from integration.pokechamp import team_preview_study as study
from integration.pokechamp.diagnostics import corrected_lead as auditor


def test_ex043_seal_and_independent_allocation(tmp_path):
    root = tmp_path / "prepared"
    v = study.prepare(root, experiment_id="EX-043")
    assert study.verify_prepared(root) == v
    assert (v["lead_strategy"], v["lead_rules"]) == ("matchup-v2", "dex-v2")
    assert v["execution_protocol"]["provider_retries"] == 3
    assert v["execution_protocol"]["call_limit"] is None
    assert v["execution_protocol"]["stop_new_work_seconds"] == 20100
    assert study.study_link(v) != d.STUDY_LINK
    old = study.schedule()
    assert {r["battle_seed"] for r in v["schedule"]}.isdisjoint(r["battle_seed"] for r in old)
    assert Counter(r["provider_id"] for r in v["schedule"]) == {"ollama": 16, "zai": 16}
    for block in ("b01", "b02", "b03", "b04"):
        rows = [r for r in v["schedule"] if r["block_id"] == block]
        pairs = sorted({r["paired_slot_id"] for r in rows}, key=lambda p:
                       hashlib.sha256(f"20260916:EX043:provider:{p}".encode()).digest())
        for pair in pairs:
            a, z = [r for r in rows if r["paired_slot_id"] == pair]
            assert a["battle_seed"] == z["battle_seed"]
            assert a["actor_seeds"] == z["actor_seeds"]
            assert a["teams"] == z["teams"]
            assert a["actor_settings"] == z["actor_settings"][::-1]
            assert a["provider_id"] == ("ollama" if pair in pairs[:2] else "zai")
    first, rest = runner.staged_schedule(v["schedule"])
    assert len(first) == 4 and len(rest) == 28
    for provider in d.PROVIDERS:
        expected = next(r["paired_slot_id"] for r in v["schedule"] if r["provider_id"] == provider)
        assert {r["paired_slot_id"] for r in first if r["provider_id"] == provider} == {expected}
        assert v["provider_configs"][provider]["transport_policy_version"] == "provider-retry-v2"
        assert v["provider_executions"][provider]["evidence"]["team_preview_prompt_identity"] == v["team_preview_prompt_identity"]
    v["lead_rules"] = "effects-v1"
    (root / "plan.json").unlink()
    b.seal_json(root / "plan.json", v)
    with pytest.raises(ValueError, match="lead configuration drift"):
        study.verify_prepared(root)


@pytest.mark.parametrize("audit_passed, expected", [(True, 32), (False, 4)])
def test_audit_barrier_before_slot_reuse(tmp_path, monkeypatch, audit_passed, expected):
    root = tmp_path / "prepared"
    v = study.prepare(root, experiment_id="EX-043")
    first, _ = runner.staged_schedule(v["schedule"])
    inspected, dispatched = set(), []
    ports = {}
    monkeypatch.setattr(study, "verify_prepared", lambda _: v)
    monkeypatch.setattr(study, "collection_deadline", lambda _: None)

    def worker(data, directory, value, slot, number, **kw):
        previous = ports.get(kw["port"])
        assert previous is None or previous in inspected
        assert slot in first or len(inspected) >= 4
        ports[kw["port"]] = slot["slot_id"]
        dispatched.append(slot["slot_id"])
        return dict(slot=slot, slot_id=slot["slot_id"], attempt_id=slot["slot_id"] + "-a1",
                    eligible=True, category=None)

    def inspect(directory, result):
        inspected.add(result["slot_id"])
        return dict(passed=audit_passed)

    monkeypatch.setattr(auditor, "before_reuse", inspect)
    with ExitStack() as stack:
        brokers = d.Brokers(stack, tmp_path, v)
        runner.execute_schedule(root, tmp_path / "data", v, brokers, worker=worker,
                                gate_check=lambda *args: dict(passed=True))
    assert len(dispatched) == expected
    assert len(dispatched) == len(set(dispatched))
    if not audit_passed:
        assert b.read_sealed(root / "halt.json")["category"] == "input_contract"


def test_ex043_completed_counts_require_all_input_receipts(tmp_path):
    from integration.pokechamp.distributed_lead_report import completion_controls

    root = tmp_path / "prepared"
    study.prepare(root, experiment_id="EX-043")
    assert completion_controls(root)["input_audits"] is False


@pytest.mark.parametrize("boundary", [
    "test_provider_projection_rejects_wrong_actor_and_settings",
])
def test_ex043_existing_admission_boundaries(tmp_path, monkeypatch, boundary):
    from integration.pokechamp.tests import test_distributed_lead as legacy

    monkeypatch.setattr(legacy, "prepare", lambda path: (
        path / "prepared", study.prepare(path / "prepared", experiment_id="EX-043")))
    getattr(legacy, boundary)(tmp_path)


@pytest.mark.parametrize("boundary", [
    "test_unlimited_8001_deadline_halt_and_clock_reset",
    "test_time_expiry_prevents_both_provider_http",
    "test_first_failed_gate_game_stops_peer_requests_before_other_games_finish",
])
def test_ex043_shared_boundaries(tmp_path, monkeypatch, boundary):
    from integration.pokechamp.tests import test_distributed_lead as legacy

    monkeypatch.setattr(legacy, "prepare", lambda path: (
        path / "prepared", study.prepare(path / "prepared", experiment_id="EX-043")))
    if boundary == "test_first_failed_gate_game_stops_peer_requests_before_other_games_finish":
        monkeypatch.setattr(auditor, "before_reuse", lambda *args: dict(passed=True))
    getattr(legacy, boundary)(tmp_path, monkeypatch)


@pytest.mark.parametrize("provider", d.PROVIDERS)
def test_final_429_only_halts_after_three_retries(tmp_path, provider):
    import httpx
    from integration.pokechamp import cloud
    from integration.pokechamp.tests.test_distributed_lead import backend, call

    root = tmp_path / "prepared"
    v = study.prepare(root, experiment_id="EX-043")
    row = next(r for r in v["schedule"] if r["provider_id"] == provider)
    sent = []

    def handler(request):
        assert not (root / "halt.json").exists()
        sent.append(request.content)
        return httpx.Response(429, json={"error": "rate limited"})

    with pytest.raises(cloud.CloudRequestError):
        call(backend(v, root, row, handler))
    assert len(sent) == 4 and len(set(sent)) == 1
    assert b.read_sealed(root / "halt.json")["http_status"] == 429
    for other in d.PROVIDERS:
        next_row = next(r for r in v["schedule"] if r["provider_id"] == other)
        with pytest.raises(cloud.CloudRequestError):
            call(backend(v, root, next_row, handler))
    assert len(sent) == 4


@pytest.mark.parametrize("has_error", [True, False])
def test_missing_snapshot_retains_reason_without_inventing_input(tmp_path, has_error):
    import json
    import sqlite3
    from integration.pokechamp.diagnostics.ex042_input_audit import run

    directory = tmp_path / "study"
    directory.mkdir()
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute("CREATE TABLE reservations(number INTEGER, actor TEXT, reserved_at REAL, payload TEXT)")
    bundle = tmp_path / "match-p1"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps(dict(
        metadata=dict(actor_id="p1", team_preview_policy="llm_lead"),
        teams=[dict(role="player", showdown_team="")], battle_id="match")))
    events = [dict(event_type="decision_start", event_seq=1, decision_seq=1,
                   showdown_turn=0, decision_kind="team_preview")]
    if has_error:
        events.append(dict(event_type="decision_result", event_seq=2, decision_seq=1,
                           error=dict(category="peer_failure", message="cancelled")))
    (bundle / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    result = run(tmp_path, tmp_path / "audit", study_root=directory, bundles=[bundle])
    key = "failed_before_snapshot" if has_error else "unexplained_missing_snapshot"
    assert result["snapshot_absence_reasons"] == {key: 1}
    assert result["totals"].get("status_failure", 0) == (0 if has_error else 1)
    row = json.loads((tmp_path / "audit/match-p1.json").read_text())[0]
    assert "replayed_input_sha256" not in row
    assert row["original_error"] == ([events[-1]["error"]] if has_error else [])



def test_online_audit_timeout_closes_owned_process_group(tmp_path):
    import sys
    import time
    from integration.pokechamp.cloud import CloudRequestError

    pidfile = tmp_path / "child.pid"
    code = ("import subprocess,sys,time,pathlib; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid)); time.sleep(60)")
    started = time.time()
    with pytest.raises(CloudRequestError, match="cleanup deadline"):
        auditor.bounded_process([sys.executable, "-c", code], tmp_path / "audit.log",
                                deadline=started+1)
    assert time.time()-started < 6
    child = int(pidfile.read_text())
    # A terminated grandchild may remain a zombie briefly until init reaps it.
    stat = __import__("pathlib").Path(f"/proc/{child}/stat")
    assert not stat.exists() or stat.read_text().split()[2] == "Z"
    assert not (tmp_path / "input-audit-receipts").exists()


@pytest.mark.parametrize("caller", ["workspace", "temporary"])
def test_audit_child_uses_pinned_cwd_from_any_launcher(tmp_path, monkeypatch, caller):
    import json
    import sys

    monkeypatch.chdir(b.WORKSPACE_ROOT if caller == "workspace" else tmp_path)
    proof = tmp_path / "cwd-proof.json"
    code = (
        "import json,hashlib; from pathlib import Path; "
        "from poke_env.environment.pokemon import Pokemon; "
        "p=Pokemon(gen=9,species='pikachu'); "
        "data=Path('poke_env/data/static/gen9/ou/sets_1500.json').read_bytes(); "
        f"Path({str(proof)!r}).write_text(json.dumps(dict(cwd=str(Path.cwd()), "
        "sha256=hashlib.sha256(data).hexdigest(),sets=len(p._sets))))"
    )
    auditor.bounded_process([sys.executable, "-c", code], tmp_path / "audit.log", deadline=None)
    result = json.loads(proof.read_text())
    assert result["cwd"] == str(b.cli.POKECHAMP_ROOT)
    assert result["sha256"] == b.digest(b.cli.POKECHAMP_ROOT / "poke_env/data/static/gen9/ou/sets_1500.json")
    assert result["sets"] > 0
