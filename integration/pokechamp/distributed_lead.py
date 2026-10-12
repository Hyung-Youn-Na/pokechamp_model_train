"""EX-042 immutable provider allocation and per-worker projection."""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from pathlib import Path

from . import benchmark as b
from . import team_preview_study as study
from .providers import provider_config, sealed_provider

PROVIDERS = ("ollama", "zai")
PROTOCOL = dict(
    study.EXECUTION_PROTOCOL,
    experiment="EX-042",
    decision="D-059",
    first_429_halt=True,
    gate="first_two_provider_pairs_technical_v1",
    call_limit=None,
    stop_new_work_seconds=20100,
    cleanup_seconds=21600,
    provider_retries=2,
    provider_concurrency={"ollama": 4, "zai": 4},
)
STUDY_LINK = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead/ex042-study-link.json"
VERSION = "distributed-effects-v1"


def is_distributed(value):
    return value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046")


def protocol(experiment_id):
    if experiment_id == "EX-042":
        return dict(PROTOCOL)
    if experiment_id not in ("EX-043", "EX-044", "EX-045", "EX-046"):
        raise ValueError("unknown distributed experiment")
    value = dict(PROTOCOL, experiment=experiment_id, decision={"EX-043": "D-064", "EX-044": "D-065", "EX-045": "D-067", "EX-046": "D-069"}[experiment_id], provider_retries=3,
                 input_audit="official-cutoff-v1" if experiment_id in ("EX-045", "EX-046") else "public-cutoff-v1")
    if experiment_id == "EX-044":
        value["preflight_status"] = "skipped_by_user"
    return value


def lead_identity(experiment_id):
    if experiment_id == "EX-042":
        return study.prompt_identity("v1.1.0")
    from .lead_rules import prompt_identity
    return prompt_identity("matchup-v2", "dex-v2")


def execution(experiment_id, transport, concurrency, provider="ollama"):
    value = study.execution(transport, concurrency, provider=provider, enriched=True,
                            observation_backend="official-client-v1" if experiment_id in ("EX-045", "EX-046") else "legacy-poke-env")
    value["evidence"]["team_preview_prompt_identity"] = lead_identity(experiment_id)
    return value


def prompt_assets(experiment_id):
    from .effects.delivery import asset, prompt_identity
    from .lead_rules import system_prompt
    official = experiment_id in ("EX-045", "EX-046")
    if official:
        from .observation.delivery import asset, prompt_identity
    return dict(
        battle_system=asset("b2-prompt.txt"),
        lead_system=(asset("lead-prompt.txt") if experiment_id == "EX-042" else
                     system_prompt("matchup-v2", "dex-v2")),
        battle_prompt_identity=study.battle_prompts.identity("v1.4.0" if official else "v1.3.0"),
        delivery_prompt_identity=prompt_identity("b2"),
        team_preview_prompt_identity=lead_identity(experiment_id),
    )


def schedule(experiment_id="EX-042"):
    rows = study.schedule() if experiment_id == "EX-042" else study.schedule("20260916:EX043")
    namespace = "20260915:EX042" if experiment_id == "EX-042" else "20260916:EX043"
    selected = set()
    for block in ("b01", "b02", "b03", "b04"):
        pairs = {r["paired_slot_id"] for r in rows if r["block_id"] == block}
        selected.update(
            sorted(
                pairs,
                key=lambda p: hashlib.sha256(
                    f"{namespace}:provider:{p}".encode()
                ).digest(),
            )[:2]
        )
    return [
        dict(r, provider_id="ollama" if r["paired_slot_id"] in selected else "zai")
        for r in rows
    ]


def selected(value, slot):
    if not is_distributed(value):
        return value
    provider = slot["provider_id"]
    return dict(
        value,
        provider_config=value["provider_configs"][provider],
        model=value["models"][provider],
        execution=value["provider_executions"][provider],
    )


def for_actor(value, actor):
    matches = [
        r
        for r in value["schedule"]
        if any(
            actor == "/".join((value["experiment_id"], r["slot_id"] + "-a1", role))
            for role in ("p1", "p2")
        )
    ]
    if len(matches) != 1:
        raise ValueError("unregistered distributed actor")
    return selected(value, matches[0])


def environment(settings, *, require_key=False, environ=None):
    from .dotenv import load_workspace_credential

    env = dict(os.environ if environ is None else environ)
    load_workspace_credential(environ=env)
    env["POKECHAMP_PROVIDER"] = settings["provider"]
    env["POKECHAMP_TRANSPORT_POLICY"] = settings["transport_policy_version"]
    # Endpoint still compared against resolved settings; do not silently accept drift.
    if provider_config(env, require_key=require_key) != settings:
        raise ValueError("distributed provider settings drift")
    other = "ZAI_API_KEY" if settings["provider"] == "ollama" else "OLLAMA_API_KEY"
    env[other] = ""  # Prevent child dotenv reload from reintroducing the other key.
    return env


def prepare(directory, *, transport, concurrency, experiment_id="EX-042", local_identity=None):
    if local_identity is not None and (local_identity != "ep058-local-eight" or transport != "fake" or experiment_id != "EX-045"):
        raise ValueError("local identity requires EX-045 fake transport")
    selected_protocol = protocol(experiment_id)
    modern = experiment_id in ("EX-043", "EX-044", "EX-045", "EX-046")
    if transport not in ("fake", "cloud") or concurrency not in (None, 8):
        raise ValueError("EX-042 requires total concurrency 8 (4+4)")
    from .dotenv import load_workspace_credential

    env = dict(os.environ)
    if transport == "cloud":
        load_workspace_credential(environ=env)
    else:
        env = dict(ZAI_BASE_URL="https://zai.example.test/v4")
    settings = {p: provider_config(dict(env, POKECHAMP_PROVIDER=p,
                POKECHAMP_TRANSPORT_POLICY="provider-retry-v2" if modern else "connect-retry-v1")) for p in PROVIDERS}
    directory = Path(directory).resolve()
    b.cli._assert_submodule_pins(require_clean=True)
    directory.mkdir(parents=True, exist_ok=False)
    origin = b.WORKSPACE_ROOT / ".pokechamp-data/b2-lead/ex039/plan.json"
    frozen = b.read_sealed(origin)
    if frozen["schedule"] != study.schedule():
        raise ValueError("EX-039 schedule drift")
    sources = study.shared.source_identity()
    for relative in sources:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(b.WORKSPACE_ROOT / relative, target)
    for key, record in frozen["teams"].items():
        source = b.cli._team_path(int(key))
        if b.digest(source) != record["sha256"]:
            raise ValueError("EX-039 team drift")
        target = directory / "teams" / f"{key}.txt"
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
    executions = {
        p: execution(experiment_id, transport, 4, provider=p) for p in PROVIDERS
    }
    models = {
        p: dict(study.MODEL, **v, seed=100 if p == "ollama" else None)
        for p, v in settings.items()
    }
    from .effects.delivery import prompt_identity

    prompts = prompt_assets(experiment_id)
    b.seal_json(directory / "prompts.json", prompts)
    value = dict(
        **study.policy_selection(),
        preparation_version="distributed-official-v1" if experiment_id in ("EX-045", "EX-046") else "distributed-corrected-v1" if modern else VERSION,
        registered_experiment=experiment_id,
        experiment_id=experiment_id.lower().replace("-", "") + "-" + transport,
        provider_configs=settings,
        provider_executions=executions,
        models=models,
        config=dict(study.CONFIG, battle_watchdog_seconds=None),
        execution=execution(experiment_id, transport, 8),
        model=dict(model=study.MODEL["model"]),
        source=b.cli._research_source_snapshot(),
        parent_files=sources,
        teams=frozen["teams"],
        schedule=schedule(experiment_id),
        schedule_origin=dict(path=str(origin), sha256=b.digest(origin)),
        transport=transport,
        execution_authorized=transport == "fake",
        efficacy_evidence=False,
        team_preview_prompt_identity=lead_identity(experiment_id),
        delivery_prompt_identity=prompts["delivery_prompt_identity"],
        prompts_sha256=b.digest(directory / "prompts.json"),
        execution_protocol=selected_protocol,
    )
    if experiment_id in ("EX-045", "EX-046"):
        from .observation import selection
        value.update(selection())
    if local_identity is not None:
        value.update(local_identity=local_identity, experiment_id=local_identity)
    if modern:
        value.update(lead_strategy="matchup-v2", lead_rules="dex-v2")
    b.seal_json(directory / "plan.json", value)
    (directory / "requests").mkdir()
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute(
            "CREATE TABLE reservations (number INTEGER PRIMARY KEY, actor TEXT, reserved_at REAL, payload TEXT)"
        )
    return value


def verify(directory, value, *, current, provider_id=None):
    if provider_id is not None and provider_id not in PROVIDERS:
        raise ValueError("unknown worker provider")
    directory = Path(directory)
    experiment_id = value["registered_experiment"]
    if "local_identity" in value and (value["local_identity"] != "ep058-local-eight" or value["transport"] != "fake" or experiment_id != "EX-045"):
        raise ValueError("local identity requires EX-045 fake transport")
    modern = experiment_id in ("EX-043", "EX-044", "EX-045", "EX-046")
    if experiment_id in ("EX-045", "EX-046"):
        from .observation import OFFICIAL, validate_selection
        if validate_selection(value, check_build=current) != OFFICIAL:
            raise ValueError("EX-045 requires official observations")
    if (
        value["preparation_version"] != ("distributed-official-v1" if experiment_id in ("EX-045", "EX-046") else "distributed-corrected-v1" if modern else VERSION)
        or value["execution_protocol"] != protocol(experiment_id)
        or value["schedule"] != schedule(experiment_id)
        or value["config"] != dict(study.CONFIG, battle_watchdog_seconds=None)
        or value["execution"] != execution(experiment_id, value["transport"], 8)
        or value["experiment_id"] != (value.get("local_identity") or experiment_id.lower().replace("-", "") + "-" + value["transport"])
        or value["execution_authorized"] is not (value["transport"] == "fake")
        or any(value.get(k) != v for k, v in study.policy_selection().items())
        or set(value["provider_configs"]) != set(PROVIDERS)
        or set(value["provider_executions"]) != set(PROVIDERS)
        or set(value["models"]) != set(PROVIDERS)
        or value["model"] != dict(model=study.MODEL["model"])
    ):
        raise ValueError("EX-042 configuration drift")
    for p in PROVIDERS:
        settings = value["provider_configs"][p]
        sealed_provider(dict(provider_config=settings))
        if (
            settings["provider"] != p
            or settings.get("transport_policy_version") != ("provider-retry-v2" if modern else "connect-retry-v1")
            or value["models"][p]
            != dict(study.MODEL, **settings, seed=100 if p == "ollama" else None)
            or value["provider_executions"][p]
            != execution(experiment_id, value["transport"], 4, provider=p)
        ):
            raise ValueError("EX-042 provider drift")
        if current and value["transport"] == "cloud" and provider_id in (None, p):
            environment(settings, require_key=True)
    origin = value["schedule_origin"]
    frozen = b.read_sealed(origin["path"])
    if (
        b.digest(origin["path"]) != origin["sha256"]
        or frozen["schedule"] != study.schedule()
        or frozen["teams"] != value["teams"]
    ):
        raise ValueError("EX-039 provenance drift")
    expected = prompt_assets(experiment_id)
    if modern and (value.get("lead_strategy"), value.get("lead_rules")) != ("matchup-v2", "dex-v2"):
        raise ValueError("EX-043 lead configuration drift")
    if (
        b.read_sealed(directory / "prompts.json") != expected
        or b.digest(directory / "prompts.json") != value["prompts_sha256"]
        or value["team_preview_prompt_identity"]
        != expected["team_preview_prompt_identity"]
        or value["delivery_prompt_identity"] != expected["delivery_prompt_identity"]
    ):
        raise ValueError("EX-042 prompts drift")
    if current and value["parent_files"] != study.shared.source_identity():
        raise ValueError("lead source drift")
    for relative, checksum in value["parent_files"].items():
        if b.digest(directory / "source" / relative) != checksum:
            raise ValueError("lead archived source drift")
    for key, record in value["teams"].items():
        if b.digest(directory / "teams" / f"{key}.txt") != record["sha256"] or (
            current and b.digest(b.cli._team_path(int(key))) != record["sha256"]
        ):
            raise ValueError("lead team drift")
    return value


class Brokers:
    """Independent account/model brokers with a combined audit snapshot."""

    def __init__(self, stack, directory, value):
        from .permits import PermitBroker
        from .transport_policy import drain_seconds

        self.providers = {
            p: stack.enter_context(
                PermitBroker(
                    Path(directory) / f"{p}.sock",
                    4,
                    {study.MODEL["model"]: 4},
                    timeout=drain_seconds(value["provider_configs"][p]),
                    revoke_on_close=True,
                )
            )
            for p in PROVIDERS
        }

    def stop(self):
        for broker in self.providers.values():
            broker.stop()

    def snapshot(self):
        snapshots = {p: broker.snapshot() for p, broker in self.providers.items()}
        return dict(
            providers=snapshots,
            active_at_close={
                p + ":" + k: v
                for p, s in snapshots.items()
                for k, v in s["active_at_close"].items()
            },
            events=[
                dict(e, provider_id=p)
                for p, s in snapshots.items()
                for e in s["events"]
            ],
        )

    def path_for(self, slot):
        return self.providers[slot["provider_id"]].path
