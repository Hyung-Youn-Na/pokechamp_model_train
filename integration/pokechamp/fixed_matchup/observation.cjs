'use strict';
const {Dex} = require('../../../pokemon-showdown/dist/sim/dex');
const {exportPublic} = require('./public_state.cjs');

const TYPES = ['global', 'pokemon', 'move', 'effect', 'candidate', 'own', 'opponent',
  'lead', 'switch', 'attack', 'tera', 'wait', 'movephase', 'switchphase', 'teampreview',
  'status:brn', 'status:par', 'status:psn', 'status:tox', 'status:slp', 'status:frz', 'none'];
const NUMERIC_EFFECTS = ['duration', 'time', 'startTime', 'stage', 'layers', 'counter', 'damage',
  'thisTurn', 'effectOrder', 'sourceSlot', 'sourcePosition', 'targetSlot', 'slot', 'position',
  'numConsecutive', 'totalDamage', 'hits', 'hitCount', 'multiplier', 'turns', 'initial',
  'maxDuration', 'minDuration', 'ended', 'isSlotCondition', 'abilityOrder'];
const STATS = ['atk', 'def', 'spa', 'spd', 'spe'];
const BOOSTS = [...STATS, 'accuracy', 'evasion'];
function vocabulary() {
  const labels = new Set(TYPES);
  for (const [prefix, values] of [
    ['species', Dex.species.all()], ['move', Dex.moves.all()], ['item', Dex.items.all()],
    ['ability', Dex.abilities.all()], ['type', Dex.types.all()], ['nature', Dex.natures.all()],
  ]) for (const row of values) labels.add(`${prefix}:${row.id}`);
  // Conditions include move/item/ability-backed volatile conditions.
  for (const id of new Set([...Object.keys(Dex.data.Conditions), ...Object.keys(Dex.data.Moves),
    ...Object.keys(Dex.data.Items), ...Object.keys(Dex.data.Abilities)])) labels.add(`effect:${id}`);
  for (const name of ['Physical', 'Special', 'Status']) labels.add(`category:${name}`);
  return [...labels].sort();
}
function token(categories, numbers = []) {
  if (numbers.length > 32 || numbers.some(n => !Number.isFinite(n))) throw Error('invalid numeric features');
  return {categories: categories.filter(Boolean), numbers: [...numbers, ...Array(32 - numbers.length).fill(0)]};
}
function fixedSlot(side, pokemon) {
  // set references are rebound by State.deserializePokemon; compare stable full set data.
  const signature = JSON.stringify(pokemon.set);
  const found = side.team.map((s, i) => JSON.stringify(s) === signature ? i + 1 : 0).filter(Boolean);
  if (found.length !== 1) throw Error('ambiguous original team slot');
  return found[0];
}
function legalActions(battle, side) {
  const r = side.activeRequest;
  if (battle.ended || !r || r.wait) return [];
  const rows = [];
  if (r.teamPreview) {
    for (let i = 1; i <= side.pokemon.length; i++) {
      const p = side.pokemon[i - 1]; const slot = fixedSlot(side, p);
      rows.push({id: `lead:${slot}`, command: `team ${[i, ...side.pokemon.map((_, j) => j + 1).filter(j => j !== i)].join('')}`,
        token: token(['candidate', 'lead', `species:${p.species.id}`], [slot / 6])});
    }
    return rows.sort((a, b) => a.id.localeCompare(b.id));
  }
  const active = r.active?.[0];
  if (active) for (const [i, move] of active.moves.entries()) {
    if (move.disabled || (move.pp !== undefined && move.pp <= 0)) continue;
    const info = Dex.moves.get(move.id || move.move);
    for (const tera of [false, ...(active.canTerastallize ? [true] : [])]) {
      rows.push({id: `move:${i + 1}:${info.id}:${tera ? 'tera' : 'normal'}`,
        command: `move ${i + 1}${tera ? ' terastallize' : ''}`,
        token: token(['candidate', 'attack', `move:${info.id}`, `type:${Dex.toID(info.type)}`,
          tera ? 'tera' : 'none'], [(i + 1) / 4, info.basePower / 250,
          info.accuracy === true ? 1 : info.accuracy / 100, info.priority / 7, Number(tera)])});
    }
  }
  if (r.forceSwitch?.[0] || (active && !active.trapped)) {
    for (const [i, p] of side.pokemon.entries()) {
      if (p.fainted || side.active.includes(p)) continue;
      const slot = fixedSlot(side, p);
      rows.push({id: `switch:${slot}`, command: `switch ${i + 1}`,
        token: token(['candidate', 'switch', `species:${p.species.id}`], [slot / 6, p.hp / p.maxhp])});
    }
  }
  if (!rows.length) throw Error('non-wait request has no legal action');
  return rows;
}

function observe(battle, perspective) {
  // Validate before reading any state, even for policy-only decisions.
  exportPublic(battle);
  const own = battle.sides.find(s => s.id === perspective);
  if (!own) throw Error('invalid perspective');
  const tokens = [token(['global', battle.requestState === 'move' ? 'movephase' :
    battle.requestState === 'switch' ? 'switchphase' : battle.requestState || 'wait'], [battle.turn / 300])];
  function effects(values, role, slot, scope) {
    for (const [id, state] of Object.entries(values)) {
      const nums = [slot / 6, scope, ...NUMERIC_EFFECTS.map(k => typeof state[k] === 'number' ? state[k] / 300 :
        typeof state[k] === 'boolean' ? Number(state[k]) : 0)];
      // Reference ownership is current public state, never an address or private log.
      if (state.source?.side) nums.push(state.source.side === own ? 1 : -1,
        fixedSlot(state.source.side, state.source) / 6);
      const move = typeof state.move === 'string' ? Dex.moves.get(state.move) : null;
      tokens.push(token(['effect', role, `effect:${id}`, move?.exists ? `move:${move.id}` : null], nums));
    }
  }
  for (const side of [own, own.foe]) {
    const role = side === own ? 'own' : 'opponent';
    for (const p of [...side.pokemon].sort((a, b) => fixedSlot(side, a) - fixedSlot(side, b))) {
      const slot = fixedSlot(side, p);
      // Showdown's terminal marker is not a major status or an effect. Fainting
      // is represented by the explicit numeric flag below; keep its HP/slot.
      const majorStatus = p.status === 'fnt' ? '' : p.status;
      tokens.push(token(['pokemon', role, `species:${p.species.id}`, `item:${p.item || ''}`,
        `ability:${p.ability}`, ...p.getTypes().map(t => `type:${Dex.toID(t)}`),
        `type:${Dex.toID(p.teraType)}`, majorStatus ? `status:${majorStatus}` : 'none'],
      [slot / 6, p.hp / p.maxhp, p.maxhp / 1000, p.level / 100, ...STATS.map(k => p.storedStats[k] / 1000),
        ...BOOSTS.map(k => p.boosts[k] / 6), Number(p.isActive), Number(p.fainted), Number(!!p.terastallized),
        Number(!!p.canTerastallize), p.speed / 1000, p.activeTurns / 300,
        p.timesAttacked / 300, side.totalFainted / 6, Number(p.trapped), Number(p.usedItemThisTurn)]));
      for (const [i, m] of p.moveSlots.entries()) {
        const info = Dex.moves.get(m.id);
        tokens.push(token(['move', role, `move:${m.id}`, `type:${Dex.toID(info.type)}`,
          `category:${info.category}`], [slot / 6, (i + 1) / 4, m.pp / 64, m.maxpp / 64,
          Number(m.disabled), Number(m.used), info.basePower / 250,
          info.accuracy === true ? 1 : info.accuracy / 100, info.priority / 7]));
      }
      effects(p.volatiles, role, slot, 0);
      if (majorStatus) effects({[majorStatus]: p.statusState}, role, slot, 1);
      if (p.item) effects({[p.item]: p.itemState}, role, slot, 2);
      effects({[p.ability]: p.abilityState}, role, slot, 3);
    }
    effects(side.sideConditions, role, 0, 4);
    side.slotConditions.forEach((v, i) => effects(v, role, i + 1, 5));
  }
  if (battle.field.weather) effects({[battle.field.weather]: battle.field.weatherState}, 'own', 0, 6);
  if (battle.field.terrain) effects({[battle.field.terrain]: battle.field.terrainState}, 'own', 0, 7);
  effects(battle.field.pseudoWeather, 'own', 0, 8);
  // Empty-item is a legitimate category; unknown arbitrary strings are not.
  for (const row of tokens) row.categories = row.categories.map(c => c === 'item:' ? 'none' : c);
  if (tokens.length > 256) throw Error('public observation exceeds 256 tokens; no truncation');
  return {schema: 'fixed-matchup-public-v1', tokens, actions: legalActions(battle, own)};
}
module.exports = {observe, legalActions, vocabulary};
