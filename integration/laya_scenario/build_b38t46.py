"""Build the battle-gen9ou-38 turn-46 scenario (Gholdengo's Trick in the original game) as a Showdown input log.

Forty-five turns cannot be replayed from one seed, so the input log only starts the battle (same leads: NHJ
Landorus-Therian vs LayaBot Kyurem) and then one `>eval` puts the simulator into the state of the end of turn 45:

- the original turns 1-45 as LayaBot received them are appended to the battle log, with every exact LayaBot HP line
  sent as a `|split|p2` pair (exact for the bot, percent for the person), so both see the original history;
- every Pokemon gets its turn-46 state: LayaBot's exact HP, PP, item and team order from the original turn-46 request;
  NHJ's HP (from the percent the bot saw), status, boosts, items, PP (from the moves in the log), Tera already used,
  Dauntless Shield already used; Stealth Rock on NHJ's side; Zamazenta and Gholdengo active;
- `battle.endTurn()` then starts turn 46 exactly as the simulator does between turns.

Usage: python build_b38t46.py <exported NHJ-20261028 dir> <out dir>   (writes battle38_t46.json, .inputlog.json)
"""
from __future__ import annotations
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOWDOWN = Path('/workspace/pokemon-showdown')
GAME, DECISION, RQID, TURN = 'battle-gen9ou-38', 'LayaBot-121-540', 121, 46
SEED = 'sodium,0000000000000000000000000000b38d'   # any seed: nothing random happens before the eval
HP_FIELD = {'switch': 4, 'drag': 4, 'replace': 4, '-damage': 3, '-heal': 3, '-sethp': 3}
CHAT = {'request', 't:', 'j', 'J', 'l', 'L', 'n', 'N', 'c', 'c:', 'raw', 'html', 'uhtml', 'uhtmlchange', 'inactive',
        'inactiveoff', 'player', 'title', 'init', 'b', 'bigerror', 'error'}


def node(script, stdin=''):
    return subprocess.run(['node', '-e', script], input=stdin, text=True, capture_output=True, check=True,
                          cwd=SHOWDOWN).stdout


def pack(team_text):
    return node("const {Teams}=require('./dist/sim/teams');process.stdout.write(Teams.pack(Teams.import("
                "require('fs').readFileSync(0,'utf8'))))", team_text)


def unpack(packed):
    return json.loads(node("const {Teams}=require('./dist/sim/teams');process.stdout.write(JSON.stringify("
                           "Teams.unpack(require('fs').readFileSync(0,'utf8'))))", packed))


def shared_hp(field):
    """Public form of an exact HP field (sim Pokemon.getHealth, HP Percentage Mod)."""
    hp, _, status = field.partition(' ')
    if hp == '0' or '/' not in hp:
        return field
    now, top = map(int, hp.split('/'))
    pct = math.ceil(now / top * 100)
    pct = 99 if pct == 100 and now < top else pct
    return '%d/100%s' % (pct, ' ' + status if status else '')


def history(events):
    """LayaBot's protocol lines from the first `|turn|1` up to (not including) `|turn|46`."""
    lines = []
    for e in events:
        if e['type'] == 'protocol':
            lines += e['protocol'].split('\n')[1:]
    start = lines.index('|turn|1') + 1
    end = lines.index('|turn|%d' % TURN)
    out = []
    for line in lines[start:end]:
        parts = line.split('|')
        kind = parts[1] if len(parts) > 1 else ''
        if kind in CHAT:
            continue
        index = HP_FIELD.get(kind)
        if index is not None and len(parts) > index and parts[2].startswith('p2') and \
                shared_hp(parts[index]) != parts[index]:
            public = parts[:index] + [shared_hp(parts[index])] + parts[index + 1:]
            out += ['|split|p2', line, '|'.join(public)]
        else:
            out.append(line)
    return out, lines[:start]


def nhj_state(events, lines, team):
    """NHJ's side at the end of turn 45: order after the switches, PP spent, and the snapshot the bot decided on."""
    snapshot = next(json.loads(e['body']['state'])['snapshot'] for e in events
                    if e['type'] == 'input' and e['decision'] == DECISION)
    names = [s['species'] for s in team]
    order = list(range(6))          # positions after '/team 123456' (Landorus-Therian leads)
    base = {s['species'].split('-')[0]: i for i, s in enumerate(team)}
    used = {i: {} for i in range(6)}
    active = 0
    for line in lines:
        parts = line.split('|')
        if len(parts) < 4 or not parts[2].startswith('p1a: '):
            continue
        mon = base[parts[2][5:]]
        if parts[1] in ('switch', 'drag'):
            here = order.index(mon)
            order[0], order[here] = order[here], order[0]
            active = mon
        elif parts[1] == 'move' and '[from]' not in line:
            move = parts[3].lower().replace(' ', '').replace('-', '')
            cost = 2 if len(parts) > 4 and parts[4].startswith('p2a: Kyurem') else 1   # LayaBot's Kyurem: Pressure
            used[mon][move] = used[mon].get(move, 0) + cost
    by_species = {p['species']: p for p in snapshot['opponent_team']}
    mons = []
    for i, s in enumerate(team):
        seen = by_species[s['species'].lower().replace('-', '')]
        mons.append(dict(species=s['species'], pct=seen['hp_percent'], status=seen['status'],
                         boosts={k: v for k, v in seen['boosts'].items() if v} if i == active else {},
                         used=used[i], fainted=seen['hp_percent'] == 0))
    assert names[active] == 'Zamazenta', names[active]
    return dict(order=[names[i] for i in order], mons=mons, side_conditions=snapshot['opponent_side_conditions'],
                can_tera=snapshot['opponent_can_tera'])


EVAL = r"""(() => {
const S = %s;
battle.log.pop();   // the '>>> ' echo of this eval
const add = battle.add;
battle.add = function (...args) {   // and its '<<< ' result line
	if (args[0] === '' && String(args[1]).startsWith('<<<')) { battle.add = add; return; }
	return add.apply(this, args);
};
for (const line of S.history) battle.log.push(line);
for (const side of battle.sides) {
	const spec = S[side.id];
	const find = name => side.pokemon.find(p => p.species.name === name);
	side.pokemon = spec.order.map(find);
	side.pokemon.forEach((p, i) => { p.position = i; p.isActive = i === 0; });
	side.active[0] = side.pokemon[0];
	let left = 0;
	for (const m of spec.mons) {
		const p = find(m.species);
		let hp = m.hp;
		if (hp === undefined || hp === null) {   // NHJ: the smallest HP whose public percent is what the bot saw
			hp = Math.max(1, Math.floor(m.pct / 100 * p.maxhp));
			while (Math.ceil(hp / p.maxhp * 100) < m.pct) hp++;
		}
		p.hp = m.fainted ? 0 : (hp === 'max' ? p.maxhp : hp);
		p.fainted = !!m.fainted;
		if (!p.fainted) left++;
		p.status = m.status || '';
		p.statusState = battle.initEffectState({id: p.status, target: p, stage: 0});
		for (const [stat, value] of Object.entries(m.boosts || {})) p.boosts[stat] = value;
		if (m.item !== undefined) p.item = m.item;
		for (const slot of p.moveSlots) {
			if (m.pp && slot.id in m.pp) slot.pp = m.pp[slot.id];
			else if (m.used && slot.id in m.used) slot.pp = Math.max(0, slot.maxpp - m.used[slot.id]);
		}
		if (!spec.canTera) p.canTerastallize = null;
		if (m.shieldBoost) p.shieldBoost = true;
		if (m.lastMove) p.lastMove = battle.dex.getActiveMove(m.lastMove);
		p.activeTurns = p.isActive ? 1 : 0;
	}
	side.pokemonLeft = left;
	side.totalFainted = 6 - left;
	for (const id of spec.sideConditions) {
		side.sideConditions[id] = battle.initEffectState({id, target: side, duration: undefined});
	}
}
battle.turn = S.turn - 1;
battle.endTurn();
return 'ok';
})()"""


def main(source, out):
    source, out = Path(source), Path(out)
    events = [json.loads(line) for line in (source / GAME / 'events.jsonl').open()]
    bot_team = next(e['packed_team'] for e in events if e['type'] == 'team_submission')
    lines, opening = history(events)
    requests = [json.loads(e['protocol'].split('|request|', 1)[1].split('\n')[0]) for e in events
                if e['type'] == 'protocol' and '|request|{' in e['protocol']]
    request = next(r for r in requests if r.get('rqid') == RQID)
    preview = next(r for r in requests if r.get('teamPreview'))
    nhj_text = (HERE / 'nhj38_team.txt').read_text()
    nhj_team = pack(nhj_text)
    nhj_sets = unpack(nhj_team)
    nhj = nhj_state(events, [ln for ln in lines if not ln.startswith('|split|')], nhj_sets)
    p1_mons = []
    for set_, m in zip(nhj_sets, nhj['mons']):
        top = None if m['fainted'] else m['pct']
        entry = dict(species=set_['species'], fainted=m['fainted'], status=m['status'] or '', boosts=m['boosts'],
                     used=m['used'], hp='max' if top == 100 else None, pct=top)
        if set_['species'] == 'Zamazenta':
            entry.update(shieldBoost=True, lastMove='irondefense')
        p1_mons.append(entry)
    p2_mons, p2_order = [], []
    for mon in request['side']['pokemon']:
        species = mon['details'].split(',')[0]
        p2_order.append(species)
        hp, _, status = mon['condition'].partition(' ')
        fainted = status == 'fnt'
        moves = request['active'][0]['moves'] if mon['active'] else None
        p2_mons.append(dict(species=species, fainted=fainted, hp=int(hp.split('/')[0]) if not fainted else 0,
                            status='' if fainted else status, item=mon['item'],
                            pp={x['id']: x['pp'] for x in moves} if moves else None))
    state = dict(turn=TURN, history=lines,
                 p1=dict(order=nhj['order'], mons=p1_mons, canTera=nhj['can_tera'],
                         sideConditions=[{'stealth_rock': 'stealthrock'}[k] for k in nhj['side_conditions']]),
                 p2=dict(order=p2_order, mons=p2_mons, canTera=True, sideConditions=[]))
    spec = dict(format='gen9ou', title='battle-gen9ou-38 from turn 46 (Gholdengo Trick)',
                players=dict(p1=dict(name='NHJ', team=nhj_team), p2=dict(name='LayaBot', team=bot_team)),
                choices=[['p1', 'team 123456'], ['p2', 'team 213456']],
                p2_slots={m['ident']: i for i, m in enumerate(preview['side']['pokemon'], 1)},
                opening=opening, request=request, state=state)
    (out / 'battle38_t46.json').write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    inputs = ['>start ' + json.dumps(dict(formatid='gen9ou', seed=SEED))]
    inputs += ['>player %s %s' % (side, json.dumps(dict(name=p['name'], team=p['team'])))
               for side, p in spec['players'].items()]
    inputs += ['>%s %s' % (side, choice) for side, choice in spec['choices']]
    code = EVAL % json.dumps(state, ensure_ascii=False)
    inputs.append('>eval ' + code.replace('\n', '\f'))   # one input line; the simulator turns \f back into \n
    (out / 'battle38_t46.inputlog.json').write_text(json.dumps(dict(seed=SEED, title=spec['title'],
                                                                    inputlog='\n'.join(inputs))))
    print(json.dumps(dict(history_lines=len(lines), p1=nhj['order'], p2=p2_order), ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:3])
