"""Versioned actor-private official observation boundary (Gen9 OU singles)."""

OFFICIAL = "official-client-v1"
LEGACY = "legacy-poke-env"
BACKENDS = (OFFICIAL, LEGACY)
# EP-056: new preparations only; absent archived fields still mean LEGACY.
PREPARATION_DEFAULT = OFFICIAL


def selected(config):
    value = config.get("observation_backend", LEGACY)
    if value not in BACKENDS:
        raise ValueError("unknown observation_backend")
    return value


def selection(backend=OFFICIAL, *, check_build=True):
    import json
    from pathlib import Path

    from .build import verify

    backend = selected({"observation_backend": backend})
    if backend == LEGACY:
        return {"observation_backend": LEGACY}
    identity = (verify() if check_build else
                json.loads(Path(__file__).with_name("build-identity.json").read_text()))
    return dict(observation_backend=OFFICIAL, observation_identity=identity)


def validate_selection(config, *, check_build=False):
    backend = selected(config)
    if backend == OFFICIAL:
        expected = selection(backend, check_build=check_build)
        if any(config.get(k) != v for k, v in expected.items()):
            raise ValueError("official observation selection/build mismatch")
    elif "observation_identity" in config:
        raise ValueError("legacy observation cannot declare official identity")
    return backend
