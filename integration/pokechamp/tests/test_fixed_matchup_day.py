"""CPU-only inheritance boundaries; fixtures never run a model or a battle."""
from copy import deepcopy
from pathlib import Path

import pytest

from integration.pokechamp.fixed_matchup import day
from integration.pokechamp.fixed_matchup.schedule import pilot_schedule
from integration.pokechamp.fixed_matchup.storage import atomic, digest, read, sha


def seal(parent):
    names = sorted(str(p.relative_to(parent)) for p in parent.rglob("*")
                   if p.is_file() and p.name not in ("evidence.sha256", "closure.sha256"))
    (parent / "evidence.sha256").write_text("".join(f"{sha(parent / name)}  {name}\n" for name in names))
    (parent / "closure.sha256").write_text(f"{sha(parent / 'evidence.sha256')}  evidence.sha256\n")


@pytest.fixture
def prepared_parent(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    protocol = deepcopy(day.PROTOCOL)
    protocol.update(experiment="EX-077", total_seconds=86400)
    protocol["stage_seconds"]["test"] = 54000
    monkeypatch.setattr(day, "PROTOCOL", protocol)
    old = deepcopy(protocol)
    old.update(experiment="EX-076", total_seconds=43200)
    old["stage_seconds"]["test"] = 10800
    atomic(parent / "catalog.json", {"vocabulary": ["fixture"]})
    atomic(parent / "schedule.json", {"pilot": pilot_schedule()})
    atomic(parent / "source/worker.py", {"frozen": "parent implementation"})
    atomic(parent / "teams/A.txt", {"team": "A"})
    atomic(parent / "models/P0.pt", {"deterministic_initial_weights": 1})
    p0 = sha(parent / "models/P0.pt")
    manifest = dict(protocol=old, sources={"worker.py": sha(parent / "source/worker.py")},
                    teams={"A": dict(file="A.txt", sha256=sha(parent / "teams/A.txt"))},
                    files={n: sha(parent / n) for n in ("catalog.json", "schedule.json")})
    manifest["identity"] = digest(manifest)
    monkeypatch.setattr(day, "PARENT_IDENTITY", manifest["identity"])
    atomic(parent / "manifest.json", manifest)
    atomic(parent / "models/P0.identity.json", dict(identity=manifest["identity"], sha256=p0))
    atomic(parent / "incomplete.json", dict(status="incomplete", gpu_released=True,
          training_games=0, test_games=0, training_updates=0))
    jobs = pilot_schedule()
    failed = [j for j in jobs if j["condition"] == "P0"][:16]
    for job in [j for j in jobs if j["condition"] == "uniform"] + failed:
        slot = job["slot_id"]
        atomic(parent / "claims" / f"{slot}.json", dict(job=job, claimed_at=1))
        atomic(parent / "games" / slot / "payload.json", {"record": "fixture"})
        atomic(parent / "games" / slot / "result.json", dict(job=job,
            status="completed" if job["condition"] == "uniform" else "incomplete",
            reason=None if job["condition"] == "uniform" else "interrupted_reserved_slot",
            model_hashes={"P0": p0}, files={"payload.json": sha(parent / "games" / slot / "payload.json")}))
    for name in ("clock.json", "stages/pilot.json", "stage-spent.json", "benchmarks/results/probe.json"):
        atomic(parent / name, {"historical": True})
    seal(parent)

    def prepare(destination):
        destination.mkdir()
        for name in ("catalog.json", "schedule.json", "teams/A.txt"):
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((parent / name).read_bytes())
        new = dict(protocol=deepcopy(protocol), teams=deepcopy(manifest["teams"]),
                   sources={"new_source": "new_hash"}, files=deepcopy(manifest["files"]))
        new["identity"] = digest(new)
        atomic(destination / "manifest.json", new)
        return new

    monkeypatch.setattr(day, "prepare", prepare)
    return parent, tmp_path / "new"


def test_inherits_only_completed_units_and_links_failed_evidence(prepared_parent):
    parent, destination = prepared_parent
    before = {str(p.relative_to(parent)): sha(p) for p in parent.rglob("*") if p.is_file()}
    result = day.prepare_day(parent, destination)
    assert result["identity"] == digest({k: v for k, v in result.items() if k != "identity"})
    assert result["protocol"]["total_seconds"] == 86400
    inherited = read(destination / "day-inheritance.json")
    assert len(inherited["inherited_games"]) == 32
    assert len(inherited["retry_games"]) == len(inherited["unattempted_games"]) == 16
    assert inherited["retry_limit"] == 1 and inherited["approval"] == "D-122"
    assert len(list((destination / "claims").glob("*.json"))) == 32
    assert all("uniform" in p.name for p in (destination / "games").iterdir())
    for name in ("clock.json", "stages", "stage-spent.json", "benchmarks", "models/P0.identity.json"):
        assert not (destination / name).exists()
    for name, checksum in result["files"].items():
        assert sha(destination / name) == checksum
    assert before == {str(p.relative_to(parent)): sha(p) for p in parent.rglob("*") if p.is_file()}
    for slot in inherited["retry_games"]:
        assert f"games/{slot}/result.json" in inherited["failed_evidence"]
        assert not (destination / "claims" / f"{slot}.json").exists()


@pytest.mark.parametrize("name", ["manifest.json", "source/worker.py", "catalog.json", "teams/A.txt",
                                   "models/P0.pt", "incomplete.json", "clock.json"])
def test_parent_corruption_is_rejected_before_preparation(prepared_parent, name):
    parent, destination = prepared_parent
    path = parent / name
    row = read(path)
    row["corrupt"] = True
    atomic(path, row)
    with pytest.raises(ValueError):
        day.prepare_day(parent, destination)
    assert not destination.exists()


def test_frozen_source_checked_independently_of_resealing(prepared_parent):
    parent, destination = prepared_parent
    atomic(parent / "source/worker.py", {"unexpected": "change"})
    seal(parent)
    with pytest.raises(ValueError, match="source/worker.py"):
        day.prepare_day(parent, destination)


@pytest.mark.parametrize("mutation", ["completed_failed", "missing_failed", "missing_uniform", "wrong_claim",
                                     "wrong_model", "training", "omitted_claim"])
def test_unapproved_inheritance_is_rejected(prepared_parent, mutation):
    parent, destination = prepared_parent
    failed = next((parent / "games").glob("*P0*/result.json"))
    uniform = next((parent / "games").glob("*uniform*/result.json"))
    if mutation == "missing_failed":
        failed.unlink()
    elif mutation == "missing_uniform":
        uniform.unlink()
    elif mutation == "training":
        atomic(parent / "checkpoints/round-000.pt", {})
    elif mutation in ("completed_failed", "wrong_model"):
        path = failed if mutation == "completed_failed" else uniform
        row = read(path)
        row.update(status="completed") if mutation == "completed_failed" else row.update(model_hashes={"P0": "wrong"})
        atomic(path, row)
    elif mutation == "wrong_claim":
        path = parent / "claims" / f"{uniform.parent.name}.json"
        row = read(path)
        row["job"]["block"] = 99
        atomic(path, row)
    seal(parent)
    if mutation == "omitted_claim":
        seal_path = parent / "evidence.sha256"
        seal_path.write_text("\n".join(line for line in seal_path.read_text().splitlines()
                                     if f"claims/{uniform.parent.name}.json" not in line) + "\n")
        (parent / "closure.sha256").write_text(f"{sha(seal_path)}  evidence.sha256\n")
    with pytest.raises(ValueError):
        day.prepare_day(parent, destination)
    assert not destination.exists()


def test_protocol_change_beyond_budget_rejected(prepared_parent, monkeypatch):
    parent, destination = prepared_parent
    monkeypatch.setitem(day.PROTOCOL, "simulations", 128)
    with pytest.raises(ValueError, match="protocol"):
        day.prepare_day(parent, destination)


def test_existing_or_overlapping_destination_is_preserved(prepared_parent):
    parent, destination = prepared_parent
    for target in (parent, parent / "child", parent.parent):
        with pytest.raises(ValueError, match="separate"):
            day.prepare_day(parent, target)
    destination.mkdir()
    with pytest.raises(FileExistsError):
        day.prepare_day(parent, destination)
