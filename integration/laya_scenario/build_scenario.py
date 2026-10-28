"""Build a scenario that starts an NHJ-20261028 game at a fixed turn T, as a Showdown input log.

Many turns cannot be replayed from one seed, so the input log only starts the battle (the original leads) and then one
`>eval` puts the simulator into the state of the end of turn T-1:

- the original turns 1..T-1 as LayaBot received them are appended to the battle log, with every exact LayaBot HP line
  sent as a `|split|p2` pair (exact for the bot, percent for the person), so both see the original history;
- every Pokemon gets its turn-T state: LayaBot's exact HP, PP, item and team order from the original turn-T request,
  its active boosts from the bot's snapshot; NHJ's HP (the smallest value with the percent the bot saw), status,
  active boosts, revealed items, Tera use (snapshot) and PP (moves in the log, LayaBot's Pressure included); last moves
  and once-per-battle Dauntless Shield / Intrepid Sword from the log; side conditions, terrain and weather with the
  turns they have left;
- `battle.endTurn()` then starts turn T exactly as the simulator does between turns.

Volatile effects on the active Pokemon (Substitute, Taunt, Encore, ...) are not rebuilt: a scenario whose snapshot
shows any is refused.

Usage: python build_scenario.py <scenario> <exported NHJ-20261028 dir> <out dir>   (scenario: b38t46, b34t15)
"""
from __future__ import annotations
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHOWDOWN = Path('/workspace/pokemon-showdown')
SCENARIOS = {
    'b38t46': dict(game='battle-gen9ou-38', decision='LayaBot-121-540', team='nhj38_team.txt', stem='battle38_t46',
                   title='battle-gen9ou-38 from turn 46 (Gholdengo Trick)'),
    'b34t15': dict(game='battle-gen9ou-34', decision='LayaBot-35-158', team='nhj34_team.txt', stem='battle34_t15',
                   title='battle-gen9ou-34 from turn 15 (Ting-Lu vs Good as Gold Gholdengo)'),
}
SEED = 'sodium,00000000000000000000000000005eed'   # any seed: nothing random happens before the eval
TERRAINS = {'electric_terrain': 'electricterrain', 'grassy_terrain': 'grassyterrain', 'misty_terrain': 'mistyterrain',
            'psychic_terrain': 'psychicterrain'}
WEATHERS = {'snowscape': 'snow', 'snow': 'snow', 'raindance': 'raindance', 'rain': 'raindance',
            'sunnyday': 'sunnyday', 'sun': 'sunnyday', 'sandstorm': 'sandstorm', 'sand': 'sandstorm'}
SIDE_CONDITIONS = {'stealth_rock': 'stealthrock'}
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
    """Sets, each with `ident`: the name the protocol uses (nickname, else base species)."""
    return json.loads(node("const {Teams}=require('./dist/sim/teams');const {Dex}=require('./dist/sim/dex');"
                           "const t=Teams.unpack(require('fs').readFileSync(0,'utf8'));"
                           "for(const s of t){const sp=Dex.species.get(s.species);"
                           "s.ident=!s.name||Dex.toID(s.name)===sp.id?sp.baseSpecies:s.name;}"
                           "process.stdout.write(JSON.stringify(t))", packed))


def shared_hp(field):
    """Public form of an exact HP field (sim Pokemon.getHealth, HP Percentage Mod)."""
    hp, _, status = field.partition(' ')
    if hp == '0' or '/' not in hp:
        return field
    now, top = map(int, hp.split('/'))
    pct = math.ceil(now / top * 100)
    pct = 99 if pct == 100 and now < top else pct
    return '%d/100%s' % (pct, ' ' + status if status else '')


def history(events, turn):
    """LayaBot's protocol lines from the first `|turn|1` up to (not including) `|turn|<turn>`."""
    lines = []
    for e in events:
        if e['type'] == 'protocol':
            lines += e['protocol'].split('\n')[1:]
    start = lines.index('|turn|1') + 1
    end = lines.index('|turn|%d' % turn)
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


def toid(text):
    return ''.join(c for c in text.lower() if c.isalnum())


def walk(lines, side, team, pressure=()):
    """One side through the log: team order after the switches, active Pokemon, PP spent (Pressure targets cost 2),
    last move since the active Pokemon's switch-in, and who has ever been in (once-per-battle abilities)."""
    base = {s['ident']: i for i, s in enumerate(team)}
    order, used, active, last, seen = list(range(6)), {i: {} for i in range(6)}, 0, None, set()
    for line in lines:
        parts = line.split('|')
        if len(parts) < 4 or not parts[2].startswith(side + 'a: '):
            continue
        mon = base[parts[2][5:]]
        if parts[1] in ('switch', 'drag'):
            here = order.index(mon)
            order[0], order[here] = order[here], order[0]
            active, last = mon, None
            seen.add(mon)
        elif parts[1] == 'move' and '[from]' not in line:
            move = toid(parts[3])
            cost = 2 if len(parts) > 4 and parts[4][5:] in pressure and parts[4][:3] != side else 1
            used[mon][move] = used[mon].get(move, 0) + cost
            last = move
    return dict(order=order, used=used, active=active, last=last, seen=seen)


def snapshot_of(events, decision):
    return next(json.loads(e['body']['state'])['snapshot'] for e in events
                if e['type'] == 'input' and e['decision'] == decision)


def conditions(raw):
    unknown = set(raw) - set(SIDE_CONDITIONS)
    if unknown:
        raise NotImplementedError('side conditions not rebuilt yet: %s' % sorted(unknown))
    return [SIDE_CONDITIONS[k] for k in raw]


def field_of(snapshot, turn):
    """Terrain and weather with the turns left at the start of `turn` (5-turn effects, set at the recorded turn)."""
    field = {}
    terrains = {k: v for k, v in snapshot['field'].items() if k in TERRAINS}
    if set(snapshot['field']) - set(terrains):
        raise NotImplementedError('field effects not rebuilt yet: %s' % sorted(set(snapshot['field']) - set(terrains)))
    for key, start in terrains.items():
        field['terrain'] = dict(id=TERRAINS[key], duration=5 - (turn - start))
    if snapshot['weather']:
        field['weather'] = dict(id=WEATHERS[snapshot['weather']], duration=5 - (turn - snapshot['weather_turn']))
    return field


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
		if (m.swordBoost) p.swordBoost = true;
		if (m.lastMove) p.lastMove = battle.dex.getActiveMove(m.lastMove);
		p.activeTurns = p.isActive ? 1 : 0;
	}
	side.pokemonLeft = left;
	side.totalFainted = 6 - left;
	for (const id of spec.sideConditions) {
		side.sideConditions[id] = battle.initEffectState({id, target: side, duration: undefined});
	}
}
if (S.field.terrain) {
	battle.field.terrain = S.field.terrain.id;
	battle.field.terrainState = battle.initEffectState({id: S.field.terrain.id, duration: S.field.terrain.duration});
}
if (S.field.weather) {
	battle.field.weather = S.field.weather.id;
	battle.field.weatherState = battle.initEffectState({id: S.field.weather.id, duration: S.field.weather.duration});
}
battle.turn = S.turn - 1;
battle.endTurn();
return 'ok';
})()"""


def main(name, source, out):
    cfg = SCENARIOS[name]
    source, out = Path(source), Path(out)
    events = [json.loads(line) for line in (source / cfg['game'] / 'events.jsonl').open()]
    rqid = int(cfg['decision'].split('-')[1])
    snapshot = snapshot_of(events, cfg['decision'])
    turn = snapshot['turn']
    bot_team = next(e['packed_team'] for e in events if e['type'] == 'team_submission')
    bot_lead = next(e['command'] for e in events if e['type'] == 'selection' and e['choice'].startswith('lead:'))
    lines, opening = history(events, turn)
    plain = [ln for ln in lines if not ln.startswith('|split|')]
    requests = [json.loads(e['protocol'].split('|request|', 1)[1].split('\n')[0]) for e in events
                if e['type'] == 'protocol' and '|request|{' in e['protocol']]
    request = next(r for r in requests if r.get('rqid') == rqid)
    preview = next(r for r in requests if r.get('teamPreview'))
    bot_sets = unpack(bot_team)
    pressure = {s['ident'] for s in bot_sets if toid(s['ability']) == 'pressure'}

    nhj_team = pack((HERE / cfg['team']).read_text())
    nhj_sets = unpack(nhj_team)
    nhj = walk(plain, 'p1', nhj_sets, pressure)
    by_species = {p['species']: p for p in snapshot['opponent_team']}
    active_seen = next(p for p in snapshot['opponent_team'] if p['slot'] == snapshot['opponent_active_slot'])
    if toid(nhj_sets[nhj['active']]['species']) != active_seen['species'] or active_seen['effects']:
        raise ValueError('NHJ active Pokemon or its volatile effects do not match the snapshot')
    p1_mons = []
    for i, set_ in enumerate(nhj_sets):
        seen = by_species[toid(set_['species'])]
        fainted = seen['hp_percent'] == 0
        entry = dict(species=set_['species'], fainted=fainted, status='' if fainted else seen['status'] or '',
                     boosts={k: v for k, v in seen['boosts'].items() if v} if i == nhj['active'] else {},
                     used=nhj['used'][i], pct=None if fainted else seen['hp_percent'])
        if seen['hp_percent'] in (100, None):   # None: never sent out, so untouched
            entry['hp'] = 'max'
        state = seen['item_state']
        if state['state'] == 'held':
            entry['item'] = state['item']
        elif state['state'] == 'removed':
            entry['item'] = ''
        if i == nhj['active'] and nhj['last']:
            entry['lastMove'] = nhj['last']
        if i in nhj['seen'] and toid(set_['species']) == 'zamazenta':
            entry['shieldBoost'] = True
        if i in nhj['seen'] and toid(set_['species']) == 'zacian':
            entry['swordBoost'] = True
        p1_mons.append(entry)

    bot = walk(plain, 'p2', bot_sets)
    own_active = next(p for p in snapshot['own_team'] if p['slot'] == snapshot['own_active_slot'])
    if own_active['effects']:
        raise ValueError('LayaBot active volatile effects are not rebuilt: %s' % own_active['effects'])
    p2_mons, p2_order = [], []
    for mon in request['side']['pokemon']:
        species = mon['details'].split(',')[0]
        p2_order.append(species)
        hp, _, status = mon['condition'].partition(' ')
        fainted = status == 'fnt'
        moves = request['active'][0]['moves'] if mon['active'] else None
        entry = dict(species=species, fainted=fainted, hp=int(hp.split('/')[0]) if not fainted else 0,
                     status='' if fainted else status, item=mon['item'],
                     pp={x['id']: x['pp'] for x in moves} if moves else None)
        if mon['active']:
            entry['boosts'] = {k: v for k, v in own_active['boosts'].items() if v}
            if bot['last']:
                entry['lastMove'] = bot['last']
        p2_mons.append(entry)

    state = dict(turn=turn, history=lines, field=field_of(snapshot, turn),
                 p1=dict(order=[nhj_sets[i]['species'] for i in nhj['order']], mons=p1_mons,
                         canTera=snapshot['opponent_can_tera'],
                         sideConditions=conditions(snapshot['opponent_side_conditions'])),
                 p2=dict(order=p2_order, mons=p2_mons, canTera=snapshot['can_tera'],
                         sideConditions=conditions(snapshot['own_side_conditions'])))
    spec = dict(format='gen9ou', title=cfg['title'],
                players=dict(p1=dict(name='NHJ', team=nhj_team), p2=dict(name='LayaBot', team=bot_team)),
                choices=[['p1', 'team 123456'], ['p2', bot_lead.removeprefix('/')]],
                p2_slots={m['ident']: i for i, m in enumerate(preview['side']['pokemon'], 1)},
                opening=opening, request=request, state=state)
    (out / (cfg['stem'] + '.json')).write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    inputs = ['>start ' + json.dumps(dict(formatid='gen9ou', seed=SEED))]
    inputs += ['>player %s %s' % (side, json.dumps(dict(name=p['name'], team=p['team'])))
               for side, p in spec['players'].items()]
    inputs += ['>%s %s' % (side, choice) for side, choice in spec['choices']]
    code = EVAL % json.dumps(state, ensure_ascii=False)
    inputs.append('>eval ' + code.replace('\n', '\f'))   # one input line; the simulator turns \f back into \n
    (out / (cfg['stem'] + '.inputlog.json')).write_text(json.dumps(dict(seed=SEED, title=cfg['title'],
                                                                        inputlog='\n'.join(inputs))))
    print(json.dumps(dict(scenario=name, turn=turn, history_lines=len(lines), field=state['field'],
                          p1=state['p1']['order'], p2=p2_order), ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:4])
