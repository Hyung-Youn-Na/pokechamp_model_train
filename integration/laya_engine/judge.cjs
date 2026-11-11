'use strict';
// EP-224 engine judge: one JSON scenario per stdin line -> one JSON result line, in order.
// A scenario is the decision-time snapshot of a singles battle rebuilt as a 6-vs-6 battle in the pinned Showdown
// engine (`/workspace/pokemon-showdown/dist/sim`, e64915c0e): both teams (species, HP, fainted, status, boosts,
// Tera), side and slot conditions, weather / terrain / pseudo-weather, the actives' volatiles and the history-derived
// state (actions since entry, last moves, Wish / Future Sight pending). For each of my move options every case
// (hidden foe Ability x item, foe action and speed order, asleep or waking) is played for one turn, most favourable
// first, until one works. `fails` / `immune` / `absorbed` / `reflected` only when every informative case does.
// A case whose move does not execute (full paralysis, confusion, flinch, a miss) is retried with other seeds.
const readline = require('node:readline');
const {Battle, Teams, Dex} = require('/workspace/pokemon-showdown/dist/sim');

const dex = Dex.forGen(9);
const toID = v => String(v || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const SEEDS = 6;
const ABSORB = new Set(['voltabsorb', 'lightningrod', 'motordrive', 'waterabsorb', 'stormdrain', 'dryskin', 'flashfire',
                        'wellbakedbody', 'sapsipper', 'eartheater', 'windrider']);
const HIT = /^\|-(damage|crit|supereffective|resisted)\|p2a: /;
const VERSION = 'laya-engine-judge/v1';

function name(table, id) {
  const entry = table.get(id);
  if (!entry || !entry.exists) throw new Error('unknown ' + id);
  return entry.name;
}

function setOf(m) {
  return {species: name(dex.species, m.species), ability: m.ability ? name(dex.abilities, m.ability) : 'No Ability',
          item: m.item ? name(dex.items, m.item) : '', moves: m.moves.map(x => name(dex.moves, x)),
          nature: m.nature || 'Serious', evs: m.evs || {hp: 84, atk: 84, def: 84, spa: 84, spd: 84, spe: 84},
          ivs: m.ivs || {}, level: m.level || 100, gender: m.gender || '',
          teraType: m.tera_type ? name(dex.types, m.tera_type) : dex.species.get(m.species).types[0]};
}

function setStatus(p, m, sleep) {
  p.status = '';
  p.statusState = {id: '', target: p};
  if (!m.status) return;
  p.status = m.status;
  p.statusState = {id: m.status, target: p};
  if (m.status === 'slp') {
    // `sleep` = [startTime, time]; time is what remains before this turn's move attempt.
    const [start, time] = sleep || [4, 4];
    p.statusState.startTime = start;
    p.statusState.time = time;
  }
  if (m.status === 'tox') p.statusState.stage = m.tox_stage || 0;
}

function prepareMon(b, p, m, sleep) {
  if (m.fainted) {
    p.hp = 0;
    p.fainted = true;
    p.status = 'fnt';
    p.side.pokemonLeft--;
    return;
  }
  p.hp = Math.max(1, Math.min(p.maxhp, Math.round(p.maxhp * (m.hp === null || m.hp === undefined ? 100 : m.hp) / 100)));
  setStatus(p, m, sleep);
  p.item = toID(m.item);
  p.itemState = {id: p.item, target: p};
  if (m.pp) {
    for (const slot of p.moveSlots) if (m.pp[slot.id] !== undefined && m.pp[slot.id] !== null) slot.pp = m.pp[slot.id];
  }
}

function prepareActive(b, p, m, foe) {
  for (const [k, v] of Object.entries(m.boosts || {})) if (k in p.boosts) p.boosts[k] = v;
  if (m.terastallized) {
    if (m.tera_type) p.teraType = name(dex.types, m.tera_type);
    b.actions.terastallize(p);
  } else if (m.types && m.types.join('/') !== p.getTypes().map(toID).join('/')) {
    p.setType(m.types.map(t => name(dex.types, t)));
    p.addVolatile('typechange');
  }
  if (m.protean_used) p.abilityState.protean = true;
  const missing = [];
  for (const [id, data] of Object.entries(m.volatiles || {})) {
    if (id === 'encore' || id === 'disable') p.lastMove = data.move ? dex.getActiveMove(data.move) : p.lastMove;
    p.addVolatile(id, foe);
    const v = p.volatiles[id];
    if (!v) {
      missing.push(id);
      continue;
    }
    if (data.duration) v.duration = data.duration;
    if (id === 'confusion') v.time = 1;      // most favourable: it ends on the next move attempt
    if (id === 'substitute') v.hp = 1;       // its HP is hidden: most favourable, any hit breaks it
    if (data.layers) v.layers = data.layers;
  }
  p.activeMoveActions = m.acted ? 1 : 0;
  p.activeTurns = m.acted ? 1 : 0;
  if (m.last_move === '?') p.lastMove = dex.getActiveMove(m.probe_move || 'tackle');
  else if (m.last_move) p.lastMove = dex.getActiveMove(m.last_move);
  else if (m.last_move === null) p.lastMove = null;
  return missing;
}

function build(s, variant, plan, seed) {
  const team = side => {
    const mons = s[side].team.map((m, i) => (side === 'p2' && i === s.p2.active && variant ? Object.assign({}, m, {
      ability: variant.ability, item: variant.item}) : m));
    const order = [s[side].active, ...mons.map((_, i) => i).filter(i => i !== s[side].active)];
    return {mons: order.map(i => mons[i]), order};
  };
  const t1 = team('p1'), t2 = team('p2');
  const b = new Battle({formatid: 'gen9customgame', seed: [seed, 2, 3, 4]});
  b.setPlayer('p1', {name: 'p1', team: Teams.pack(t1.mons.map(setOf))});
  b.setPlayer('p2', {name: 'p2', team: Teams.pack(t2.mons.map(setOf))});
  const me = b.p1.active[0], foe = b.p2.active[0];
  // Switch-in effects (weather / terrain setters, Intimidate, Booster Energy, ...) give way to the snapshot.
  b.field.clearWeather();
  b.field.clearTerrain();
  for (const id of Object.keys(b.field.pseudoWeather)) b.field.removePseudoWeather(id);
  for (const [side, t] of [['p1', t1], ['p2', t2]]) {
    t.mons.forEach((m, i) => prepareMon(b, b[side].pokemon[i], m, side === 'p1' && i === 0 ? plan.sleep : null));
  }
  for (const p of [me, foe]) for (const k of Object.keys(p.boosts)) p.boosts[k] = 0;
  if (s.weather) {
    b.field.setWeather(s.weather.id, foe);
    if (b.field.weatherState) b.field.weatherState.duration = Math.max(2, s.weather.turns || 5);
  }
  if (s.terrain) {
    b.field.setTerrain(s.terrain.id, foe);
    if (b.field.terrainState) b.field.terrainState.duration = Math.max(2, s.terrain.turns || 5);
  }
  for (const [id, turns] of Object.entries(s.pseudo || {})) {
    b.field.addPseudoWeather(id, foe);
    if (b.field.pseudoWeather[id]) b.field.pseudoWeather[id].duration = Math.max(2, turns || 5);
  }
  for (const [side, setter] of [['p1', foe], ['p2', me]]) {
    for (const [id, n] of Object.entries(s[side].conditions || {})) {
      const layers = ['spikes', 'toxicspikes'].includes(id) ? n : 1;
      for (let i = 0; i < layers; i++) b[side].addSideCondition(id, setter);
      const c = b[side].sideConditions[id];
      if (c && c.duration) c.duration = Math.max(2, ['spikes', 'toxicspikes'].includes(id) ? c.duration : n || 5);
    }
    for (const id of s[side].slots || []) {
      const holder = b[side].active[0];
      b[side].addSlotCondition(holder, id, side === 'p1' ? me : foe);
      const c = b[side].slotConditions[holder.position][id];
      if (c) {
        c.duration = 99;     // pending: it does not resolve within the judged turn
        if (id === 'futuremove') Object.assign(c, {move: 'futuresight', source: me, moveData: {id: 'futuresight'}});
      }
    }
    if (!s[side].can_tera) for (const p of b[side].pokemon) p.canTerastallize = null;
  }
  prepareActive(b, me, s.p1.team[s.p1.active], foe);
  const missing = prepareActive(b, foe, Object.assign({}, s.p2.team[s.p2.active], variant || {}), me);
  if (variant) {
    foe.item = toID(variant.item);
    foe.itemState = {id: foe.item, target: foe};
  }
  // A hidden Ability that could not hold the observed status / volatiles (Water Veil and a burn, Own Tempo and
  // confusion, ...) is not a possible case.
  b.eachEvent('Update');
  const foeStatus = s.p2.team[s.p2.active].status || '';
  const consistent = !missing.length && foe.status === foeStatus;
  const fast = plan.order === 'me' ? [me, foe] : [foe, me];
  fast[0].getActionSpeed = () => 400;
  fast[1].getActionSpeed = () => 100;
  return {b, me, foe, consistent};
}

function classify(lines, move) {
  const moveName = dex.moves.get(move).name;
  const i = lines.findIndex(l => l.startsWith('|move|p1a: ') && !l.includes('[from]'));
  if (i < 0) return lines.some(l => l.startsWith('|cant|p1a') || l.startsWith('|faint|p1a')) ? 'cant' : 'error:no-move';
  if (lines[i].split('|')[3] !== moveName) return 'error:other-move ' + lines[i].split('|')[3];
  let j = i + 1;
  while (j < lines.length && !lines[j].startsWith('|move|') && !lines[j].startsWith('|turn|') &&
         !lines[j].startsWith('|upkeep')) j++;
  const window = lines.slice(i + 1, j);
  if (j < lines.length && lines[j].startsWith('|move|p2a: ') && lines[j].includes('[from] ability: Magic Bounce')) {
    return 'reflected';
  }
  if (window.some(l => l.startsWith('|-miss|p1a'))) return 'miss';
  for (const l of window) {
    const m = /ability: ([^|]+)/.exec(l);
    if (m && /^\|-(immune|heal|boost|start)\|p2a/.test(l) && ABSORB.has(toID(m[1]))) return 'absorbed';
    const a = /^\|-ability\|p2a: [^|]*\|([^|]+)\|boost/.exec(l);
    if (a && ABSORB.has(toID(a[1]))) return 'absorbed';
  }
  const failed = window.some(l => l.startsWith('|-fail|') || l.startsWith('|-immune|') || l.startsWith('|-block|'));
  if (!failed) return 'works';
  if (dex.moves.get(move).category !== 'Status' && window.some(l => HIT.test(l) && !l.includes('[from]') ||
      /^\|-activate\|p2a: [^|]*\|(move: )?Substitute\|\[damage\]/.test(l))) {
    return 'side';      // the hit landed; only an added effect was blocked
  }
  return window.some(l => l.startsWith('|-immune|')) ? 'immune' : 'fails';
}

function playCase(s, option, variant, plan, debug) {
  let last = 'error:no-seed';
  for (let k = 0; k < SEEDS; k++) {
    const {b, me, consistent} = build(s, variant, plan, 1 + k);
    if (!consistent) return {label: 'uninformative:inconsistent'};
    const mine = 'move ' + option.move + (option.tera ? ' terastallize' : '');
    if (!b.p1.choose(mine)) return {label: 'error:choice ' + mine};
    const foeMove = dex.moves.get(plan.foe_move);
    if (foeMove.selfSwitch || foeMove.forceSwitch || foeMove.selfdestruct) return {label: 'uninformative:foe-leaves'};
    if (!b.p2.choose('move ' + plan.foe_move)) {
      b.p2.clearChoice();
      if (!b.p2.choose('default')) return {label: 'error:foe-choice'};
    }
    const start = b.log.length;
    b.commitChoices();
    const lines = b.log.slice(start);
    last = classify(lines, option.move);
    if (last !== 'cant' && last !== 'miss') return {label: last, lines: debug ? lines : undefined, seed: 1 + k};
    if (!me.hp && last === 'cant') break;
  }
  return {label: 'uninformative:' + last};
}

const FAILING = new Set(['fails', 'immune', 'absorbed', 'reflected']);

// The foe active's hidden Ability ranges over its species' Abilities, its hidden item over `foe_items`.
function variants(s) {
  const foe = s.p2.team[s.p2.active];
  const species = dex.species.get(foe.species);
  const abilities = foe.ability ? [foe.ability] : [...new Set(Object.values(species.abilities).map(toID))];
  const items = s.foe_items && s.foe_items.length ? s.foe_items : [foe.item || ''];
  const out = [];
  for (const item of items) for (const ability of abilities) out.push({ability, item});
  return out;
}

function judgeOption(s, option) {
  const variants = s.variants;
  const seen = [];
  let cases = 0;
  for (const plan of option.plans) {
    for (const variant of variants) {
      cases++;
      const out = playCase(s, option, variant, plan, s.debug);
      if (out.label === 'works' || out.label === 'side' || out.label.startsWith('error:other-move')) {
        return {label: out.label === 'side' ? 'side' : 'works', cases, case: {plan, variant},
                lines: out.lines};
      }
      if (out.label.startsWith('error:') && !out.label.startsWith('error:choice') &&
          !out.label.startsWith('error:no-move')) {
        return {label: 'unknown', cases, error: out.label, case: {plan, variant}};
      }
      seen.push({label: out.label, plan, variant, lines: out.lines});
    }
  }
  const informative = seen.filter(x => FAILING.has(x.label));
  if (!informative.length) {
    return {label: 'unknown', cases, error: (seen[0] || {}).label};
  }
  // Cases where the move never executes (asleep, flinched, ...) say nothing: the real log would have no `|move|`.
  const kinds = new Set(informative.map(x => x.label));
  return {label: kinds.size === 1 ? [...kinds][0] : 'fails', cases, lines: s.debug ? informative[0].lines : undefined};
}

function run(s) {
  s.variants = variants(s);
  const out = {};
  for (const option of s.options) {
    try {
      out[option.id] = judgeOption(s, option);
    } catch (e) {
      out[option.id] = {label: 'unknown', error: 'error:' + String(e && e.message || e).split('\n')[0]};
    }
  }
  return out;
}

if (require.main === module) {
  process.stdout.write(JSON.stringify({status: 'ready', version: VERSION}) + '\n');
  readline.createInterface({input: process.stdin, crlfDelay: Infinity}).on('line', line => {
    if (!line.trim()) return;
    const s = JSON.parse(line);
    let out;
    try {
      out = {id: s.id, options: run(s)};
    } catch (e) {
      out = {id: s.id, error: String(e && e.message || e).split('\n')[0]};
    }
    process.stdout.write(JSON.stringify(out) + '\n');
  });
}

module.exports = {run, build, classify, VERSION};
