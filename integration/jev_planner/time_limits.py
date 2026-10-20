"""Nullable elapsed-time limits; infinity stays internal, never in artifacts."""
import time


def remaining_seconds(limit, started):
    return float('inf') if limit is None else limit - (time.monotonic() - started)


def deadline_after(seconds):
    return float('inf') if seconds is None else time.monotonic() + seconds


def battle_window(limit, remaining):
    seconds = min(float('inf') if limit is None else limit, remaining)
    # The opponent receives a JSON-safe null only when both clocks are unbounded.
    return None if seconds == float('inf') else seconds
