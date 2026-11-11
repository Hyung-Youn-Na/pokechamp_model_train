"""EX-159 schedule shape: 4 base slots per ring matchup, pairs dealt whole and round-robin to the three shards."""
from integration.laya_imitation import comparison as cmp
from integration.laya_teamset import battle


def teams(n):
    return [dict(team_id='t%d' % i, signature='s%d|x' % i, archetype='balance', team_set='smogon', packed='p%d' % i)
            for i in range(n)]


def test_schedule_and_shards():
    schedule = battle.make_schedule(teams(10))
    assert len(schedule) == 40 and len({r['slot_id'] for r in schedule}) == 40
    shards = battle.deal(schedule)
    assert sorted(len(v) for v in shards.values()) == [12, 14, 14]
    owners = {}
    for name, rows in shards.items():
        for r in rows:
            assert owners.setdefault(r['pair_id'], name) == name
    rows = cmp.make_schedule(shards['g0'], battle.study('g0'))
    assert len(rows) == 3 * len(shards['g0'])
    assert {r['model'] for r in rows} == set(battle.MODELS)
    assert len({r['slot_id'] for r in rows}) == len(rows)
    for r in rows[:6]:
        assert r['base_pair_id'] == rows[0]['base_pair_id']


if __name__ == '__main__':
    test_schedule_and_shards()
    print('ok')
