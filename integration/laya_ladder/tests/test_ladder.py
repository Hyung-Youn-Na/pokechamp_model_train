"""Assert-based checks for EP-230 helpers: `python -m integration.laya_ladder.tests.test_ladder` (CPU, laya env)."""
import tempfile
from pathlib import Path

from integration.laya_ladder import abilities, train_ddp

LOG = '\n'.join([
    '|poke|p1|Clodsire, M|', '|poke|p2|Walking Wake|', '|start',
    '|switch|p1a: Clodsire|Clodsire, M|100/100', '|switch|p2a: Wake|Walking Wake|100/100',
    '|move|p2a: Wake|Hydro Steam|p1a: Clodsire',
    '|-heal|p1a: Clodsire|100/100|[from] ability: Water Absorb|[of] p2a: Wake',
    '|move|p1a: Clodsire|Skill Swap|p2a: Wake',
    '|-activate|p1a: Clodsire|Skill Swap|Protosynthesis|Water Absorb|[of] p2a: Wake',
    '|-ability|p2a: Wake|Water Absorb',
    '|-damage|p2a: Wake|90/100|[from] ability: Rough Skin|[of] p1a: Clodsire',
    '|switch|p2a: Other|Gholdengo|100/100',
    '|-ability|p2a: Other|Good as Gold',
])


def test_rewrite():
    out = abilities.rewrite(LOG)
    assert len(out) == len(LOG.splitlines())
    heal = out[6]
    assert '[of]' not in heal and '[from] ability: Water Absorb' in heal       # the subject holds it
    assert out[9].endswith('|[from] move: Skill Swap')                         # swapped, not original
    assert '[from] swapped: Rough Skin' in out[10]                             # credited to a swapped holder
    assert out[12] == '|-ability|p2a: Other|Good as Gold'                      # the switch-in is not swapped
    assert out[:6] == LOG.splitlines()[:6]


def test_plan():
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / 'a.jsonl', Path(d) / 'b.jsonl'
        a.write_text(''.join('{}\n' for _ in range(1003)))
        b.write_text(''.join('{}\n' for _ in range(57)))
        keys, calib = train_ddp.plan([str(a), str(b)], 4, 0, 400, 0.1, 20260922)
        assert len(keys) % 4 == 0 and len(set(keys)) == len(keys)
        assert len(calib) == 100 and not {(0, i) for i in calib} & set(keys)  # calibration never trains
        shards = [keys[r::4] for r in range(4)]
        assert len({len(s) for s in shards}) == 1 and sum(map(len, shards)) == len(keys)
        assert keys == train_ddp.plan([str(a), str(b)], 4, 0, 400, 0.1, 20260922)[0]   # same on every rank


if __name__ == '__main__':
    test_rewrite()
    test_plan()
    print('ok')
