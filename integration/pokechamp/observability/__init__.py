"""Opt-in full-fidelity PokéChamp research battle observability."""

from .recorder import (
    BattleBundleConfig,
    BattleRecorder,
    BundleCollisionError,
    DataRootError,
    verify_bundle,
)
from .render import rebuild_battle, rebuild_experiment

__all__ = [
    "BattleBundleConfig",
    "BattleRecorder",
    "BundleCollisionError",
    "DataRootError",
    "rebuild_battle",
    "rebuild_experiment",
    "verify_bundle",
]

