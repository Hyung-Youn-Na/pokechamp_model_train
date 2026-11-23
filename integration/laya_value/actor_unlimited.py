"""EP-239: `integration.foulplay.actor` with the turn and decision limits lifted (foul-play venv; actor unchanged).

A poke-engine panic inside foul-play's own search (EX-202 fp-b31-s1-a: `generate_instructions.rs:2182` "Taunt
duration cannot be 3 when taunt volatile is active") reaches the actor as a PicklingError of
`pyo3_runtime.PanicException` from the search pool, which the actor records as a phase failure and the executor then
halts every lane. Here such an engine panic ends only that game: it is re-raised as `actor.Limit('engine_panic')`, so
the slot is `incomplete` (failure_scope battle, reason engine_panic) and the other slots go on. Every other error is
unchanged.
"""
from __future__ import annotations

import sys

from integration.foulplay import paths as P

UNLIMITED = 10 ** 6                     # = battle_value.UNLIMITED (this venv does not import the laya side)
P.TURN_LIMIT = UNLIMITED
P.DECISION_LIMIT = UNLIMITED

from integration.foulplay import actor  # noqa: E402  (reads P.* at call time)

_battle_loop = actor.battle_loop


def engine_panic(error):
    text = '%s %s' % (type(error).__name__, error)
    return 'PanicException' in text or 'pyo3_runtime' in text


async def battle_loop(*args, **kwargs):
    try:
        return await _battle_loop(*args, **kwargs)
    except actor.Limit:
        raise
    except Exception as error:
        if engine_panic(error):
            raise actor.Limit('engine_panic') from error
        raise


actor.battle_loop = battle_loop         # looked up as a module global at call time in actor.main's game()

if __name__ == '__main__':
    sys.exit(actor.main())
