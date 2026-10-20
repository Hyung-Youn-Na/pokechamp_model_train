"""Explicit EX-085 wrappers around the shared GPU ownership and budget monitor."""
from pathlib import Path

from integration.jev27b import resource as shared
from .config import ROOT, runtime_profile

SHARED_ENVIRONMENT_ROOTS = (ROOT / 'pokechamp/.venv', Path('/tmp/ep037/tools'),
                            Path('/root/.cache/ms-playwright'))

canonical_gpu_uuid = shared.canonical_gpu_uuid
gpu_facts = shared.gpu_facts
gpu_compute_processes = shared.gpu_compute_processes


def disk_roots(*, profile='ex085', budget_root=None, extra_roots=()):
    runtime_profile(profile)
    return shared.disk_roots(profile=profile, budget_root=budget_root,
                             extra_roots=(*SHARED_ENVIRONMENT_ROOTS, *extra_roots))


def disk_bytes(*, profile='ex085', budget_root=None, extra_roots=()):
    runtime_profile(profile)
    return shared.disk_bytes(profile=profile, budget_root=budget_root,
                             extra_roots=(*SHARED_ENVIRONMENT_ROOTS, *extra_roots))


def limit_errors(sample, *, profile='ex085'):
    runtime_profile(profile)
    return shared.limit_errors(sample, profile=profile)


def own_gpus(directory, *, profile='ex085', budget_root=None, extra_roots=()):
    runtime_profile(profile)
    return shared.own_gpus(directory, profile=profile, budget_root=budget_root,
                           extra_roots=(*SHARED_ENVIRONMENT_ROOTS, *extra_roots))


def wait_owned_gpu_release(directory, previous_pid, *, profile='ex085'):
    runtime_profile(profile)
    return shared.wait_owned_gpu_release(directory, previous_pid, profile=profile)


class ResourceMonitor(shared.ResourceMonitor):
    def __init__(self, directory, *, profile='ex085', budget_root=None, extra_roots=(),
                 expected_uuids=None):
        runtime_profile(profile)
        super().__init__(directory, profile=profile, budget_root=budget_root,
                         extra_roots=(*SHARED_ENVIRONMENT_ROOTS, *extra_roots),
                         expected_uuids=expected_uuids)
