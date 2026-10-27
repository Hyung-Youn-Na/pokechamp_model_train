"""EX-120 frozen team rules: archetypes, exclusion-preserving greedy selection, diversity and the 128-slot schedule."""
import itertools

from integration.laya_imitation import teams as t

POOL = ['sp%02d' % i for i in range(60)]


def mon(moves=(), ability='', item=''):
    return dict(moves=list(moves), ability=ability, item=item)


def test_archetype_rules_and_order():
    plain = [mon(['Tackle'])] * 6
    assert t.classify(plain)[0] == 'balance'
    assert t.classify([mon(ability='Drizzle')] + plain[:5])[0] == 'weather'
    assert t.classify([mon(['Snowscape'])] + plain[:5])[0] == 'balance'
    assert t.classify([mon(['Snowscape']), mon(['Chilly Reception'])] + plain[:4])[0] == 'weather'
    assert t.classify([mon(['Swords Dance'])] * 3 + plain[:3])[0] == 'offense'
    assert t.classify([mon(item='Choice Band')] * 4 + [mon(['Roost'])] * 2)[0] == 'balance'
    assert t.classify([mon(item='Choice Band')] * 4 + [mon(['Roost'])] + plain[:1])[0] == 'offense'
    assert t.classify([mon(['Recover'])] * 4 + plain[:2])[0] == 'defense'
    three = [mon(['Recover'])] * 3
    assert t.classify(three + [mon(['Stealth Rock']), mon(['Defog'])] + plain[:1])[0] == 'defense'
    assert t.classify(three + [mon(['Stealth Rock'])] + plain[:2])[0] == 'balance'
    # weather wins over offense when both apply
    assert t.classify([mon(['Dragon Dance'], ability='Drought')] + [mon(['Swords Dance'])] * 3 + plain[:2])[0] == 'weather'


def pool(n=400, seed=0):
    rows = []
    for i in range(n):
        start = (i * 7 + seed) % len(POOL)
        species = sorted({POOL[(start + k * (i % 5 + 1)) % len(POOL)] for k in range(6)})
        if len(species) == 6:
            rows.append(dict(path='team_%d' % i, sha256='x', species=species, signature='|'.join(species)))
    return rows


def checker(kinds=t.ARCHETYPES):
    def check(entry):
        index = int(entry['path'].split('_')[1])
        if index % 11 == 0:
            return dict(path=entry['path'], reason='illegal')
        return dict(team_id='t%04d' % index, signature=entry['signature'], species=entry['species'],
                    archetype=kinds[index % len(kinds)], packed='P%d' % index)
    return check


def test_selection_respects_quota_diversity_and_rejections():
    chosen, rejected, shortfall = t.select(pool(), checker())
    assert len(chosen) == 32 and not shortfall
    assert {k: sum(c['archetype'] == k for c in chosen) for k in t.ARCHETYPES} == {k: 8 for k in t.ARCHETYPES}
    assert all(int(c['team_id'][1:]) % 11 for c in chosen)
    assert all(r['reason'] == 'illegal' for r in rejected)
    assert len({c['signature'] for c in chosen}) == 32
    for a, b in itertools.combinations(chosen, 2):
        assert len(set(a['species']) & set(b['species'])) <= t.MAX_SHARED
    counts = {}
    for c in chosen:
        for s in c['species']:
            counts[s] = counts.get(s, 0) + 1
    assert max(counts.values()) <= t.MAX_SPECIES


def test_shortfall_is_filled_and_recorded():
    chosen, _, shortfall = t.select(pool(), checker(kinds=('offense', 'balance', 'balance')))
    assert len(chosen) == 32
    assert shortfall == {'weather': 8, 'defense': 8}
    assert sum(c['fill'] for c in chosen) == 16


def test_excluded_signatures_never_reach_check():
    rows = pool()
    blocked = {r['signature'] for r in rows[::2]}
    seen = []

    def check(entry):
        seen.append(entry['signature'])
        return checker()(entry)
    t.select([r for r in rows if r['signature'] not in blocked], check)
    assert not blocked & set(seen)


def test_schedule_shape_and_determinism():
    chosen, _, _ = t.select(pool(), checker())
    rows = t.make_schedule(chosen)
    assert rows == t.make_schedule(list(reversed(chosen)))
    assert len(rows) == 128 and len({r['slot_id'] for r in rows}) == 128
    assert len({r['pair_id'] for r in rows}) == 64 and len({r['matchup_id'] for r in rows}) == 32
    appearances = {}
    for m in {r['matchup_id'] for r in rows}:
        ids = {i for r in rows if r['matchup_id'] == m for i in r['team_ids'].values()}
        assert len(ids) == 2
        for i in ids:
            appearances[i] = appearances.get(i, 0) + 1
    assert set(appearances.values()) == {2} and len(appearances) == 32
    for pair in {r['pair_id'] for r in rows}:
        a, b = [r for r in rows if r['pair_id'] == pair]
        assert a['model_side'] == b['model_side'] == ('p1' if a['seed_index'] == 1 else 'p2')
        side = a['model_side']
        assert a['team_ids'][side] == b['team_ids'][[s for s in ('p1', 'p2') if s != side][0]]
        assert b['team_ids'][side] == a['team_ids'][[s for s in ('p1', 'p2') if s != side][0]]
        assert rows.index(b) == rows.index(a) + 1 and a['swap'] == 'a'
        assert a['teams'][side]['packed'] != b['teams'][side]['packed']
    assert [r['submission_order'] for r in rows] == list(range(1, 129))
