"""Unchanged Abyssal actor with an isolated EX114 server port."""
import argparse
import asyncio
from integration.jev27b import battle
from .core import PORT

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    battle.PORT = PORT  # Process-local binding only; no shared source modification.
    asyncio.run(battle.bot_worker(args.output))
