"""EX-169 A1: per-decision cause tags, the per-game material timeline, and digests of the lost games.

    python -m integration.laya_v11.analysis.attribution build     # tables/bot-tags.jsonl, bot-games.jsonl, digests/
    python -m integration.laya_v11.analysis.attribution compare   # tag frequency in won vs lost games

Material = (my alive HP% sum - foe alive HP% sum) / 100 from the `board:` line (unknown foe HP counts 100). A swing
is the change of material between two consecutive decisions that have a board line. The tags describe the bot's
choice at a decision from its own input and the log lines that followed; they are rule-based and the lost games are
read one by one on top of them (`digests/`).
"""
from __future__ import annotations
from collections import Counter, defaultdict
import csv
import json
import random
import sys

from .. import paths
from . import features as F
from . import score as S

PIVOT = ('uturn', 'voltswitch', 'flipturn', 'partingshot', 'teleport', 'batonpass', 'chillyreception', 'shedtail')
TAGS = ('dead_pick', 'failed_unmarked', 'protect_blocked', 'sucker_whiff', 'foe_switched_in', 'duel_lose_stay',
        'boosted_foe_stay', 'let_setup', 'repeat_after_fail', 'stalled_repeat', 'protect_again', 'ko_taken',
        'crit_on_me', 'my_miss', 'my_cant', 'tera', 'opp_tera', 'low_conf', 'switch')


def ratings():
    out = {}
    with open(paths.RUN_ANALYSIS / 'source/replays.csv') as f:
        for row in csv.DictReader(f):
            out[row['battle_id']] = row
    return out


def tags(row, facts):
    c = F.chosen(facts, row['choice'])
    a = row['after']
    turn = facts['kind'] == 'turn_action'
    failed = a['my_result'] in ('fail', 'immune', 'absorbed')
    out = dict(
        dead_pick=c['dead'],
        failed_unmarked=failed and not c['dead'] and not a['target_switched'] and c['move'] != 'suckerpunch'
        and not (c['protect'] and c['likely_fail']),
        protect_blocked=a['my_result'] == 'protect',
        sucker_whiff=c['move'] == 'suckerpunch' and a['my_result'] == 'fail',
        foe_switched_in=turn and c['move'] is not None and a['opp_switch'] is not None and c['move'] not in PIVOT,
        duel_lose_stay=turn and facts['duel'] == 'lose' and facts['has_switch'] and not c['switch'],
        boosted_foe_stay=turn and facts['opp_offence'] >= 2 and facts['has_switch'] and not c['switch'],
        let_setup=turn and a['opp_boosts'] >= 2 and not c['switch'],
        repeat_after_fail=turn and c['repeats_last'] and facts['last_fate'] in ('fail', 'immune', 'protect'),
        stalled_repeat=turn and F.loop_class(row['state'], row['choice']) == 'stall_repeat',
        protect_again=c['protect'] and c['likely_fail'],
        ko_taken=a['my_faint'], crit_on_me=a['crit_on_me'], my_miss=a['my_miss'], my_cant=a['my_cant'] is not None,
        tera=c['tera'], opp_tera=a['opp_tera'], low_conf=row['probabilities'].get(row['choice'], 1.0) < 0.4,
        switch=turn and c['switch'])
    return [k for k in TAGS if out[k]]


def material(board):
    return None if board is None else (board[1] - board[3]) / 100.0


def build():
    out = paths.TABLES
    digests = out / 'digests'
    digests.mkdir(parents=True, exist_ok=True)
    rate = ratings()
    by_game = defaultdict(list)
    for row in S.decisions():
        by_game[row['game']].append(row)
    seen = Counter()
    games, tagged = [], []
    for game, rows in sorted(by_game.items()):
        rows.sort(key=lambda r: r['k'])
        info, series = [], []
        for row in rows:
            if row['state'] is None:
                continue
            facts = F.describe(row['state'], row['criteria'])
            found = [] if row['automatic'] else tags(row, facts)
            m = material(facts['board'])
            info.append((row, facts, found, m))
            if m is not None:
                series.append((row['k'], facts['turn'], m, facts['board']))
        swings = sorted(((b[2] - a[2], a[0], a[1]) for a, b in zip(series, series[1:])))[:3]
        worst = {k for _, k, _ in swings}
        first = rows[0]
        battle = (json.loads((paths.GAMES / game / 'result.json').read_text()).get('battle_tag') or '')
        battle = '-'.join(battle.replace('battle-', '').split('-')[:2])
        r = rate.get(battle, {})
        opponent = first['opponent']
        seen[opponent] += 1
        counts = Counter(t for _, _, found, _ in info for t in found)
        near = Counter(t for row, _, found, _ in info for t in found
                       if any(row['k'] in (k, k - 1) for k in worst))
        lead = next((row['choice'] for row, f, _, _ in info if f['kind'] == 'lead'), None)
        games.append(dict(game=game, battle=battle, result=first['result'], opponent=opponent,
                          encounter=seen[opponent], opp_rating=r.get('opponent_rating_before'),
                          rating_before=r.get('rating_before'), rating_change=r.get('rating_change'),
                          turns=first['turns'], policy=first['policy'], ext=first['ext'], fix=first['fix'],
                          opp_team=first['opp_team'], decisions=len(info), lead=lead, tags=dict(counts),
                          tags_near_swings=dict(near), swings=[dict(delta=round(d, 2), k=k, turn=t) for d, k, t in swings],
                          material=[(t, round(m, 2)) for _, t, m, _ in series]))
        lines = ['%s  %s vs %s (%s)  rating %s (opp %s)  turns %s  policy %s  ext=%s fix=%s' % (
            game, first['result'], opponent, 'encounter %d' % seen[opponent], r.get('rating_before'),
            r.get('opponent_rating_before'), first['turns'], first['policy'], first['ext'], first['fix']),
            'opp team: ' + ', '.join(first['opp_team']), '']
        for row, facts, found, m in info:
            probs = sorted(row['probabilities'].items(), key=lambda kv: -kv[1])
            chosen_p = row['probabilities'].get(row['choice'], 1.0)
            others = ', '.join('%s %.2f' % (a, p) for a, p in probs[:4] if a != row['choice'])
            a = row['after']
            mark = row['criteria'][row['choice']] if row['criteria'] else ''
            lines.append('T%-2s %-13s %s%s vs %s%s | board %s | duel %s' % (
                facts['turn'], facts['kind'], facts['me'] or '-', '(%d%%)' % facts['me_hp'] if facts['me_hp'] else '',
                facts['opp'] or '-', ' +%d' % facts['opp_offence'] if facts['opp_offence'] else '',
                '%d/%d%% v %d/%d%%' % facts['board'] if facts['board'] else '-', facts['duel'] or '-'))
            lines.append('    %s %s %.2f [%s]%s   (alt: %s)' % (
                '**' if row['k'] in worst else '  ', row['choice'], chosen_p, mark[:70],
                ' AUTO' if row['automatic'] else '', others))
            lines.append('       -> me %s:%s%s | opp %s%s%s%s%s | tags %s' % (
                a['my_move'], a['my_result'], ' (foe switched)' if a['target_switched'] else '',
                a['opp_move'] or '', ' switch ' + a['opp_switch'] if a['opp_switch'] else '',
                ' +%d' % a['opp_boosts'] if a['opp_boosts'] else '', ' MY FAINT' if a['my_faint'] else '',
                ' OPP FAINT' if a['opp_faint'] else '', ','.join(found) or '-'))
            tagged.append(dict(game=game, k=row['k'], turn=facts['turn'], kind=facts['kind'], choice=row['choice'],
                               tags=found, near_swing=row['k'] in worst, material=m, result=first['result']))
        (digests / (game + '.txt')).write_text('\n'.join(lines) + '\n')
    with open(out / 'bot-games.jsonl', 'w') as f:
        for g in games:
            f.write(json.dumps(g, ensure_ascii=False) + '\n')
    with open(out / 'bot-tags.jsonl', 'w') as f:
        for t in tagged:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')
    print(json.dumps(dict(games=len(games), wins=sum(g['result'] == 'win' for g in games),
                          losses=sum(g['result'] == 'loss' for g in games), decisions=len(tagged))))


def _boot(a, b, draws=10000, seed=paths.SEED):
    """Difference of means b - a with a bootstrap interval over games."""
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        x = [a[rng.randrange(len(a))] for _ in a]
        y = [b[rng.randrange(len(b))] for _ in b]
        out.append(sum(y) / len(y) - sum(x) / len(x))
    out.sort()
    return sum(b) / len(b) - sum(a) / len(a), out[int(0.025 * draws)], out[int(0.975 * draws) - 1]


def compare():
    games = [json.loads(line) for line in open(paths.TABLES / 'bot-games.jsonl')]
    won = [g for g in games if g['result'] == 'win']
    lost = [g for g in games if g['result'] == 'loss']
    rows = []
    for tag in TAGS:
        per = lambda group, key='tags': [g[key].get(tag, 0) / max(1, g['decisions']) * 100 for g in group]
        any_ = lambda group: sum(g['tags'].get(tag, 0) > 0 for g in group) / len(group)
        d = _boot(per(won), per(lost))
        rows.append(dict(tag=tag, per100_win=sum(per(won)) / len(won), per100_loss=sum(per(lost)) / len(lost),
                         diff=d, any_win=any_(won), any_loss=any_(lost),
                         near_swing_loss=sum(g['tags_near_swings'].get(tag, 0) > 0 for g in lost) / len(lost),
                         near_swing_win=sum(g['tags_near_swings'].get(tag, 0) > 0 for g in won) / len(won)))
    (paths.TABLES / 'a1-tags-win-loss.json').write_text(json.dumps(rows, indent=1))
    print('games: %d won, %d lost' % (len(won), len(lost)))
    print('%-18s | per 100 decisions: win  loss  (loss-win 95%%)         | games with any: win  loss | near worst swings: win  loss'
          % 'tag')
    for r in rows:
        print('%-18s | %5.2f %5.2f  %+5.2f [%+5.2f, %+5.2f] | %4.0f%% %4.0f%% | %4.0f%% %4.0f%%' % (
            r['tag'], r['per100_win'], r['per100_loss'], r['diff'][0], r['diff'][1], r['diff'][2],
            100 * r['any_win'], 100 * r['any_loss'], 100 * r['near_swing_win'], 100 * r['near_swing_loss']))
    return rows


def patterns():
    """Per-game indicators of how a game went, and one rule-based category per lost game (first rule that holds):
    `setup_sweep` (two or more of my Pokemon fainted to a foe at +2 Atk / SpA or more), `lead_lost_early` (my first
    faint by turn 3 before any foe fainted), `long_game` (45 turns or more), `misses` (two or more of my moves
    missed), else `traded_down`. The categories describe; they do not prove a cause."""
    from . import games as G
    by_game = defaultdict(list)
    for row in S.decisions():
        by_game[row['game']].append(row)
    info = {json.loads(line)['game']: json.loads(line) for line in open(paths.TABLES / 'bot-games.jsonl')}
    out = []
    for game, rows in sorted(by_game.items()):
        rows.sort(key=lambda r: r['k'])
        d = dict(game=game, result=info[game]['result'], opponent=info[game]['opponent'],
                 encounter=info[game]['encounter'], turns=info[game]['turns'], policy=info[game]['policy'], faints=0,
                 faints_to_boosted=0, setup_turns=0, setup_passive=0, setup_attack=0, setup_switch=0, sucker=0,
                 sucker_fail=0, misses=0, crits_on_me=0, protect_fail=0, dead_picks=0, first_faint=None,
                 first_own_faint_turn=None)
        for row in rows:
            if row['state'] is None:
                continue
            facts = F.describe(row['state'], row['criteria'])
            a, c = row['after'], F.chosen(facts, row['choice'])
            turn = facts['kind'] == 'turn_action'
            if a['my_faint']:
                d['faints'] += 1
                if d['first_own_faint_turn'] is None:
                    d['first_own_faint_turn'] = facts['turn']
                if facts['opp_offence'] >= 2 or (turn and a['opp_boosts'] >= 2):
                    d['faints_to_boosted'] += 1
            if d['first_faint'] is None and (a['my_faint'] or a['opp_faint']):
                d['first_faint'] = 'both' if a['my_faint'] and a['opp_faint'] else 'mine' if a['my_faint'] else 'foe'
            if not turn or row['automatic']:
                continue
            if a['opp_boosts'] >= 2 and a['opp_move'] in G.SETUP:
                d['setup_turns'] += 1
                d['setup_switch' if c['switch'] else 'setup_passive' if (c['status'] or c['dead']) else 'setup_attack'] += 1
            if c['move'] == 'suckerpunch':
                d['sucker'] += 1
                d['sucker_fail'] += a['my_result'] == 'fail'
            d['misses'] += a['my_miss']
            d['crits_on_me'] += a['crit_on_me']
            d['dead_picks'] += c['dead']
            d['protect_fail'] += c['protect'] and a['my_result'] == 'fail'
        if d['result'] == 'loss':
            early = d['first_faint'] == 'mine' and d['first_own_faint_turn'] is not None and d['first_own_faint_turn'] <= 3
            d['category'] = 'setup_sweep' if d['faints_to_boosted'] >= 2 else 'lead_lost_early' if early else \
                'long_game' if (d['turns'] or 0) >= 45 else 'misses' if d['misses'] >= 2 else 'traded_down'
        out.append(d)
    won = [d for d in out if d['result'] == 'win']
    lost = [d for d in out if d['result'] == 'loss']
    mean = lambda xs: sum(xs) / len(xs)
    keys = ('faints', 'faints_to_boosted', 'setup_turns', 'setup_passive', 'setup_attack', 'setup_switch', 'sucker',
            'sucker_fail', 'misses', 'crits_on_me', 'protect_fail', 'dead_picks')
    summary = dict(games=dict(won=len(won), lost=len(lost)),
                   per_game={k: dict(win=mean([d[k] for d in won]), loss=mean([d[k] for d in lost]),
                                     any_win=mean([d[k] >= 1 for d in won]), any_loss=mean([d[k] >= 1 for d in lost]),
                                     two_win=mean([d[k] >= 2 for d in won]), two_loss=mean([d[k] >= 2 for d in lost]))
                             for k in keys},
                   totals={k: sum(d[k] for d in out) for k in keys},
                   first_faint={'%s:%s' % k: v for k, v in Counter((d['result'], d['first_faint']) for d in out).items()},
                   loss_categories=dict(Counter(d['category'] for d in lost)),
                   repeat_opponents={'%s:%s' % k: v for k, v in
                                     Counter(('first' if d['encounter'] == 1 else 'again', d['result']) for d in out).items()},
                   leads={'%s:%s' % k: v for k, v in Counter((info[d['game']]['lead'], d['policy']) for d in out).items()})
    atomic_path = paths.TABLES / 'a1-game-patterns.json'
    atomic_path.write_text(json.dumps(dict(summary=summary, games=out), indent=1))
    print(json.dumps(summary, indent=1))
    for d in lost:
        print(d['game'][9:15], '%-16s' % d['opponent'][:16], 'enc%d' % d['encounter'], 'T%-3s' % d['turns'],
              '%-16s' % d['category'], 'boosted-faints %d  setup turns %d (passive %d)  misses %d  first own faint T%s'
              % (d['faints_to_boosted'], d['setup_turns'], d['setup_passive'], d['misses'], d['first_own_faint_turn']))
    return summary


if __name__ == '__main__':
    dict(build=build, compare=compare, patterns=patterns)[sys.argv[1]]()
