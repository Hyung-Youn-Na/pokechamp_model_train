'use strict';
// EX-126 engine oracle: one JSON scenario per stdin line -> one JSON result line, in order.
// Each scenario is a 1-vs-1 battle in the pinned Showdown engine (`dist/sim`, e64915c0e) set up directly
// (weather, terrain, status, HP, volatiles, side conditions, speed order), then `turns` of choices.
// kind 'outcome': what happened to p1's `move` on the last turn (works / fails / immune / absorbed / reflected).
// kind 'select': whether p1 may choose `move` after the turns (yes / no).
const path = require('node:path');
const readline = require('node:readline');
const {Battle, Teams, Dex} = require(path.join(__dirname, '../../pokemon-showdown/dist/sim'));

const dex = Dex.forGen(9);
const WEATHER = {snow: 'snowscape', snowscape: 'snowscape', sunnyday: 'sunnyday', raindance: 'raindance',
                 sandstorm: 'sandstorm'};
const TERRAIN = {misty_terrain: 'mistyterrain', electric_terrain: 'electricterrain', psychic_terrain: 'psychicterrain',
                 grassy_terrain: 'grassyterrain'};
const SIDE = {spikes: 'spikes', toxic_spikes: 'toxicspikes', stealth_rock: 'stealthrock', sticky_web: 'stickyweb',
              aurora_veil: 'auroraveil', reflect: 'reflect', light_screen: 'lightscreen'};
const ABSORB = new Set(['voltabsorb', 'lightningrod', 'motordrive', 'waterabsorb', 'stormdrain', 'dryskin', 'flashfire',
                        'wellbakedbody', 'sapsipper', 'eartheater', 'windrider']);
const toID = v => String(v || '').toLowerCase().replace(/[^a-z0-9]/g, '');

function set(spec) {
  return {species: dex.species.get(spec.species).name, ability: spec.ability ? dex.abilities.get(spec.ability).name
    : 'No Ability', item: spec.item ? dex.items.get(spec.item).name : '', moves: spec.moves.map(m => dex.moves.get(m).name),
          nature: 'Serious', evs: {hp: 4}, ivs: {}, level: spec.level || 100, teraType: 'Normal'};
}

function prepare(b, s, side) {
  const p = b[side].active[0];
  if (s[side + '_hp'] !== undefined && s[side + '_hp'] !== null) p.sethp(Math.max(1, Math.round(p.maxhp * s[side + '_hp'] / 100)));
  const status = s[side + '_status'];
  if (status) {
    p.setStatus(status, null, null, true);
    if (status === 'slp') { p.statusState.time = 4; p.statusState.startTime = 4; }
  }
  for (const v of s[side + '_volatiles'] || []) p.addVolatile(v);
  for (const [key, n] of Object.entries(s[side + '_side'] || {})) {
    for (let i = 0; i < n; i++) b[side].addSideCondition(SIDE[key] || key, p);
  }
  p.storedStats.spe = s.first === side ? 400 : 100;
}

function classify(lines, s) {
  const name = dex.moves.get(s.move).name;
  if (lines.some(l => /^\|cant\|p2a: [^|]*\|ability: (Dazzling|Queenly Majesty|Armor Tail)\|/.test(l))) return 'fails';
  const i = lines.findIndex(l => l.startsWith('|move|p1a: ') && l.split('|')[3] === name && !l.includes('[from]'));
  if (i < 0) return 'error:no-move ' + lines.filter(l => l.startsWith('|cant|') || l.startsWith('|faint|')).join(' ');
  let j = i + 1;
  while (j < lines.length && !/^\|(move|upkeep|turn|faint)\|/.test(lines[j]) && lines[j] !== '|upkeep') j++;
  if (j < lines.length && lines[j].startsWith('|move|p2a: ') && lines[j].includes('[from] ability: Magic Bounce')) {
    return 'reflected';
  }
  const window = lines.slice(i + 1, j);
  for (const l of window) {
    const m = /ability: ([^|]+)/.exec(l);
    if (m && /^\|-(immune|heal|boost|start)\|p2a/.test(l) && ABSORB.has(toID(m[1]))) return 'absorbed';
    const a = /^\|-ability\|p2a: [^|]*\|([^|]+)\|boost/.exec(l);
    if (a && ABSORB.has(toID(a[1]))) return 'absorbed';
  }
  if (window.some(l => l.startsWith('|-immune|') || l.startsWith('|-block|p2a') ||
                      /^\|-activate\|p2a: [^|]*\|item: Safety Goggles/.test(l))) {
    return 'immune';
  }
  if (window.some(l => l.startsWith('|-fail|') || /^\|-activate\|p2a: [^|]*\|move: (Psychic|Misty|Electric) Terrain/.test(l))) {
    return 'fails';
  }
  return 'works';
}

function run(s) {
  const b = new Battle({formatid: 'gen9customgame', seed: s.seed || [1, 2, 3, 4]});
  b.setPlayer('p1', {name: 'p1', team: Teams.pack([set(s.p1)])});
  b.setPlayer('p2', {name: 'p2', team: Teams.pack([set(s.p2)])});
  // Switch-in abilities (Snow Warning, surges) may have set the field already; the scenario's field wins.
  b.field.clearWeather();
  b.field.clearTerrain();
  if (s.weather) b.field.setWeather(WEATHER[s.weather] || s.weather, b.p2.active[0]);
  if (s.terrain) b.field.setTerrain(TERRAIN[s.terrain] || s.terrain, b.p2.active[0]);
  prepare(b, s, 'p1');
  prepare(b, s, 'p2');
  let start = b.log.length;
  for (const [c1, c2] of s.turns) {
    if (b.ended) return {label: 'error:battle ended early', missed: false};
    start = b.log.length;
    b.makeChoices(c1, c2);
  }
  if (s.kind === 'select' && b.ended) return {label: 'error:battle ended early', missed: false};
  if (s.kind === 'select') {
    // Recompute this turn's disabled moves the way `nextTurn` does after the setup changes.
    const p = b.p1.active[0];
    for (const slot of p.moveSlots) { slot.disabled = false; slot.disabledSource = ''; }
    b.runEvent('DisableMove', p);
    const moves = p.getMoveRequestData().moves;
    const entry = moves.find(m => m.id === s.move);
    return {label: entry && !entry.disabled ? 'yes' : 'no', missed: false};
  }
  const lines = b.log.slice(start);
  return {label: classify(lines, s), lines: s.debug ? lines : undefined, missed: lines.some(l => l.startsWith('|-miss|p1a'))};
}

// A miss hides whether the move would have failed; retry with other seeds (fixed sequence) until it connects.
function settle(s) {
  let out = run(s);
  for (let k = 1; out.missed && k <= 20; k++) out = run(Object.assign({}, s, {seed: [1 + k, 2, 3, 4]}));
  if (out.missed) out.label = 'error:always-missed';
  delete out.missed;
  return out;
}

const rl = readline.createInterface({input: process.stdin, terminal: false});
rl.on('line', line => {
  if (!line.trim()) return;
  const s = JSON.parse(line);
  let out;
  try {
    out = Object.assign({id: s.id}, s.kind === 'select' ? run(s) : settle(s));
  } catch (e) {
    out = {id: s.id, label: 'error:' + String(e && e.message || e).split('\n')[0]};
  }
  process.stdout.write(JSON.stringify(out) + '\n');
});
