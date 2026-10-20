"""Explicit shared-integrity versus isolated serving/resource stop scope."""
from .client import LocalRequestError


class SharedFailure(RuntimeError):
    """Both dependent v6 experiments must stop."""


class ModelFailure(RuntimeError):
    """Only this model stops, subject to proven cleanup and no shared defect."""


class RecordedFailure(RuntimeError):
    def __init__(self, record):
        self.record = dict(record)
        super().__init__(record['detail'])


MODEL_TRANSPORT_CATEGORIES = frozenset({
    'timeout', 'transport', 'out_of_memory', 'model_failure', 'resource_limit',
})


def error_record(error):
    if isinstance(error, RecordedFailure):
        return dict(error.record)
    scope = 'shared'
    if isinstance(error, (ModelFailure, MemoryError)) or 'OutOfMemory' in type(error).__name__:
        scope = 'model'
    elif isinstance(error, LocalRequestError) and error.category in MODEL_TRANSPORT_CATEGORIES:
        scope = 'model'
    return dict(type=type(error).__name__, detail=str(error), scope=scope,
                **({'category': error.category} if isinstance(error, LocalRequestError) else {}))


def resource_scope(receipts):
    errors = {name for receipt in receipts for name in receipt.get('errors', [])}
    if not errors:
        return None
    memory_errors = {'host_memory_exceeded'} | {f'gpu{i}_memory_exceeded' for i in range(4)}
    return 'model' if errors <= memory_errors else 'shared'


def may_continue_other_model(completion):
    """A failed 27B run can admit 9B only with an explicit isolated stop and cleanup."""
    if completion.get('closure', {}).get('passed') is not True or completion.get('cleanup_errors'):
        return False
    error = completion.get('error') or (completion.get('result') or {}).get('error')
    if error is None:
        # Isolated unusable choices keep a technically valid completed collection.
        result = completion.get('result') or {}
        return bool(result.get('final_audit_passed') and
                    (completion.get('finalization') or {}).get('passed'))
    return error.get('scope') == 'model' and completion.get('shared_integrity_passed') is True
