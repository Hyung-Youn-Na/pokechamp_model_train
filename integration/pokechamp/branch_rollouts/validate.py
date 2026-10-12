"""Replay every immutable root through its archived suffix before collection."""

from __future__ import annotations

import copy
import time
import traceback
from pathlib import Path

from .common import (
    Budget, code_identity, digest, file_hash, gameplay_lines, gzread,
    normalize_request, read, rows, verify_source, write,
)
from .runner import _decode_actors, expected_prefix, feed_response
from .simulator import Simulator


def _require_equal(actual, expected, label):
    if actual != expected:
        raise ValueError(f"Root validation mismatch: {label}")


def _expected_winner(manifest):
    outcome = manifest["original_outcome"]["outcome"]
    if outcome == "player_lost":
        return manifest["teams"]["p1"]["name"]
    if outcome == "player_won":
        return manifest["teams"]["p2"]["name"]
    if outcome == "tied":
        return ""
    raise ValueError("Unrecognized archived terminal outcome")


def _replay_root(root, anchors, events, manifest, expected_public, deadline):
    """One validation attempt: round-trip and original suffix, without reseeding."""
    index = root["original_index"]
    original_index = index
    inputs = [event for event in events if event["type"] == "input"]
    actors = _decode_actors(root["actors"])
    histories, cursors = copy.deepcopy(root["histories"]), dict(root["cursors"])
    original_hash = digest(root)
    checked = 0
    started = time.monotonic()
    with Simulator() as sim:
        response = sim.restore(root["simulator"])
        # Restore must neither regenerate requests nor discard pending midturn
        # actions. Full serialized equality detects more than visible-state checks.
        _require_equal(sim.snapshot(), root["simulator"], "snapshot round-trip")
        _require_equal(response["needs_choice"], root["needs_choice"], "root request barrier")
        _require_equal({side: digest(log) for side, log in response["actor_logs"].items()},
                       root["actor_logs_sha256"], "root actor log hashes")
        while not response["ended"]:
            if time.time() >= deadline or time.monotonic() - started >= 120:
                raise TimeoutError("Root suffix validation reached its time limit")
            needs = response["needs_choice"]
            if not needs:
                raise ValueError("Nonterminal root suffix has no requested action")
            if "p2" in needs:
                if index >= len(inputs) or index >= len(anchors):
                    raise ValueError("Root suffix has an extra archived-side decision")
                current, anchor = inputs[index], anchors[index]
                _require_equal(normalize_request(response["requests"]["p2"]),
                               normalize_request(current["official"]["request"]),
                               anchor["anchor_id"] + ":request")
                _require_equal(gameplay_lines(response["actor_logs"]["p2"]),
                               expected_prefix(events, current),
                               anchor["anchor_id"] + ":protocol")
                checked += 1
            choices = {}
            for side in needs:
                if side == "p2":
                    anchor = anchors[index]
                    matches = [action["command"] for action in anchor["actions"]
                               if action["action_id"] == anchor["original_action_id"]]
                    if len(matches) != 1:
                        raise ValueError("Archived root action is not unique")
                    choices[side] = matches[0]
                    index += 1
                else:
                    choices[side] = actors[side].choose()
            response = sim.step(choices)
            feed_response(response, actors, histories, cursors)
        _require_equal(index, len(anchors), "terminal decision count")
        _require_equal(response["turn"], manifest["original_outcome"]["turns"], "terminal turn")
        _require_equal(response["winner"], _expected_winner(manifest), "terminal winner")
        archived = [line for event in events if event["type"] == "protocol"
                    for line in event["protocol"].splitlines()]
        _require_equal(gameplay_lines(response["actor_logs"]["p2"]),
                       gameplay_lines(archived), "terminal actor gameplay")
        _require_equal(gameplay_lines(response["public_log"]),
                       gameplay_lines(expected_public), "terminal spectator gameplay")
    _require_equal(digest(root), original_hash, "in-memory root preservation")
    return dict(
        anchor_id=root["anchor_id"], passed=True, original_index=original_index,
        snapshot_round_trip=True, request_barrier_matched=True,
        suffix_decisions_checked=checked, turns=response["turn"], winner=response["winner"],
        actor_gameplay_sha256=digest(gameplay_lines(response["actor_logs"]["p2"])),
        public_gameplay_sha256=digest(gameplay_lines(response["public_log"])),
        original_rng_preserved=True, root_preserved=True,
        elapsed_seconds=time.monotonic() - started,
    )


def validate(directory):
    """Validate all 22 roots; reserve each suffix against the cumulative budget."""
    directory = Path(directory)
    target = directory / "validation.json"
    if target.exists():
        raise FileExistsError("Validation receipt already exists; no automatic rerun")
    manifest = read(directory / "manifest.json")
    reconstruction = read(directory / "reconstruction.json")
    if not reconstruction.get("passed"):
        raise ValueError("Reconstruction must pass before root validation")
    verify_source(manifest["source_hashes"])
    anchors = rows(directory / "anchors.jsonl")
    roots = reconstruction["anchors"]
    if len(anchors) != 22 or len(roots) != 22:
        raise ValueError("Validation requires all 22 registered roots")
    if [root["anchor_id"] for root in roots] != [anchor["anchor_id"] for anchor in anchors]:
        raise ValueError("Root and anchor order/identity mismatch")
    identity = code_identity()
    before_hashes = {root["root_path"]: file_hash(directory / root["root_path"]) for root in roots}
    for root in roots:
        if before_hashes[root["root_path"]] != root["root_sha256"]:
            raise ValueError("Root changed after reconstruction: " + root["anchor_id"])
    events = gzread(directory / "source/selected-events.json.gz")
    trace = gzread(directory / "reconstruction-trace.json.gz")
    budget = Budget(directory)
    started = time.monotonic()
    receipt = dict(passed=False, validation_version="original-suffix-v1", planned_roots=22,
                   completed_roots=0, source_identity=identity,
                   reconstruction_sha256=file_hash(directory / "reconstruction.json"), roots=[])
    active = None
    try:
        for index, (info, anchor) in enumerate(zip(roots, anchors)):
            active = info["anchor_id"]
            attempt = budget.reserve("validation", active)
            root = gzread(directory / info["root_path"])
            _require_equal(root["anchor_id"], active, "stored root identity")
            _require_equal(root["original_index"], index, "stored root decision index")
            result = _replay_root(root, anchors, events, manifest, trace["public_log"],
                                  budget.value["admission_deadline"])
            _require_equal(file_hash(directory / info["root_path"]), info["root_sha256"],
                           "root artifact preservation")
            result.update(attempt_id=attempt, phase=anchor["phase"], root_path=info["root_path"],
                          root_sha256=info["root_sha256"])
            receipt["roots"].append(result)
            receipt["completed_roots"] += 1
        _require_equal(code_identity(), identity, "source identity during validation")
        _require_equal({name: file_hash(directory / name) for name in before_hashes},
                       before_hashes, "all root artifact hashes")
        verify_source(manifest["source_hashes"])
        receipt.update(passed=True, original_source_preserved=True, root_files_preserved=True,
                       phase_coverage=sorted({record["phase"] for record in receipt["roots"]}),
                       completed_roots=22)
    except Exception as error:
        receipt.update(failed_anchor=active, error=dict(type=type(error).__name__, message=str(error)),
                       traceback=traceback.format_exc())
        raise
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        write(target, receipt)
    return {key: value for key, value in receipt.items() if key not in ("roots", "source_identity")}
