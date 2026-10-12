'use strict';
// fixed-matchup-qwen-text-v1. Every function reads only exportPublic(...).physical (the validated
// public allowlist), never a live Battle object, so the rendered text cannot carry RNG or choices.
const {Dex} = require('../../pokemon-showdown/dist/sim/dex');

const STATS = ['atk', 'def', 'spa', 'spd', 'spe'];
const BOOSTS = [...STATS, 'accuracy', 'evasion'];
const EFFECT_FIELDS = ['layers', 'duration', 'time', 'stage', 'counter', 'turns'];
const CATEGORY = {Physical: 'phys', Special: 'spec', Status: 'status'};
const toID = Dex.toID;

function ref(value, kind) {
  const match = /^\[(\w+):(.*)\]$/.exec(String(value));
  if (!match || match[1] !== kind) throw Error(`expected ${kind} reference`);
  return match[2];
}

function bySlot(side) {
  // State.serializeSide: team[original index] = current position (1-based) of that member.
  const order = side.team.split(side.team.length > 9 ? ',' : '');
  if (order.length !== side.pokemon.length) throw Error('team order mismatch');
  return order.map((position, index) => {
    const mon = side.pokemon[Number(position) - 1];
    if (!mon) throw Error('team order points outside the side');
    return {slot: index + 1, mon};
  });
}

function speciesName(id) {
  const species = Dex.species.get(id);
  if (!species.exists) throw Error(`unknown species ${id}`);
  return species.name;
}

function effect(id, state) {
  const parts = [];
  if (state && typeof state.move === 'string' && state.move) parts.push(`move ${Dex.moves.get(state.move).name}`);
  for (const key of EFFECT_FIELDS) {
    if (state && typeof state[key] === 'number') parts.push(`${key} ${state[key]}`);
  }
  const name = Dex.conditions.get(id).name || id;
  return parts.length ? `${name}(${parts.join(', ')})` : name;
}

function effects(values) {
  return Object.keys(values).sort().map(id => effect(id, values[id]));
}

function moveText(slot) {
  const move = Dex.moves.get(slot.id);
  if (!move.exists) throw Error(`unknown move ${slot.id}`);
  const bits = [move.type, CATEGORY[move.category], move.basePower ? String(move.basePower) : '-',
    move.accuracy === true ? '-' : `${move.accuracy}%`];
  if (move.priority) bits.push(`prio${move.priority > 0 ? '+' : ''}${move.priority}`);
  return `${move.name} (${bits.join(' ')} ${slot.maxpp}pp)`;
}

function renderStatic(physical) {
  const lines = ['Gen 9 OU singles. Both teams and the whole current state are public.'];
  for (const side of physical.sides) {
    lines.push(`[${side.id} team]`);
    for (const {slot, mon} of bySlot(side)) {
      const set = mon.set, species = Dex.species.get(set.species);
      const stats = [`hp ${mon.maxhp}`, ...STATS.map(key => `${key} ${mon.storedStats[key]}`)].join(' ');
      lines.push(`${side.id}.${slot} ${species.name} | ${species.types.join('/')} | tera ${set.teraType || species.types[0]} | ` +
        `${Dex.abilities.get(set.ability).name} | ${Dex.items.get(set.item).name || 'no item'} | ${set.nature || 'Serious'} | ${stats}`);
      lines.push(`  moves: ${mon.moveSlots.map(moveText).join(', ')}`);
    }
  }
  return lines.join('\n');
}

function monLine(sideId, slot, mon) {
  const set = mon.set, parts = [`${sideId}.${slot} ${speciesName(ref(mon.species, 'Species'))}`];
  if (mon.isActive) parts.push('ACTIVE');
  if (mon.fainted) parts.push('fainted');
  parts.push(`hp ${mon.hp}`);
  if (mon.status && mon.status !== 'fnt') parts.push(`status ${effect(mon.status, mon.statusState)}`);
  const boosts = BOOSTS.filter(key => mon.boosts[key]).map(key => `${key}${mon.boosts[key] > 0 ? '+' : ''}${mon.boosts[key]}`);
  if (boosts.length) parts.push(`boosts ${boosts.join(' ')}`);
  if (mon.terastallized) parts.push(`tera ${mon.terastallized}`);
  if (toID(mon.item) !== toID(set.item)) parts.push(`item ${Dex.items.get(mon.item).name || 'none'}`);
  if (toID(mon.ability) !== toID(set.ability)) parts.push(`ability ${Dex.abilities.get(mon.ability).name || mon.ability}`);
  const baseTypes = Dex.species.get(set.species).types.join('/');
  if (!mon.terastallized && mon.types.join('/') !== baseTypes) parts.push(`types ${mon.types.join('/')}`);
  const volatiles = effects(mon.volatiles);
  if (volatiles.length) parts.push(`vol ${volatiles.join(', ')}`);
  // Current PP by move slot in the static move order ('-' = still at the static maximum).
  const pp = mon.moveSlots.map(m => (m.pp < m.maxpp ? String(m.pp) : '-'));
  if (pp.some(value => value !== '-')) parts.push(`pp ${pp.join('/')}`);
  const disabled = mon.moveSlots.filter(m => m.disabled === true).map(m => m.move);
  if (disabled.length) parts.push(`disabled ${disabled.join(', ')}`);
  return parts.join(' ');
}

function fieldEffect(id, state) {
  return id ? effect(id, state) : 'none';
}

function renderDynamic(physical) {
  const field = physical.field;
  const pseudo = effects(field.pseudoWeather);
  const lines = [`phase ${physical.requestState || 'none'} | turn ${physical.turn}`,
    `field weather ${fieldEffect(field.weather, field.weatherState)} | terrain ${fieldEffect(field.terrain, field.terrainState)}` +
    ` | pseudo ${pseudo.length ? pseudo.join(', ') : 'none'}`];
  for (const side of physical.sides) {
    const conditions = effects(side.sideConditions);
    const slots = side.slotConditions.map((values, index) => effects(values).map(text => `${index + 1}:${text}`)).flat();
    const tera = side.pokemon.some(mon => mon.canTerastallize) ? 'available' : 'used';
    lines.push(`${side.id} side: tera ${tera} | conditions ${conditions.length ? conditions.join(', ') : 'none'}` +
      (slots.length ? ` | slot ${slots.join(', ')}` : ''));
    for (const {slot, mon} of bySlot(side)) lines.push(monLine(side.id, slot, mon));
  }
  return lines.join('\n');
}

function slotSpecies(physical, sideId, slot) {
  const side = physical.sides.find(s => s.id === sideId);
  const entry = bySlot(side).find(e => e.slot === slot);
  if (!entry) throw Error('candidate slot outside the team');
  return Dex.species.get(entry.mon.set.species).name;
}

function candidateText(physical, sideId, row) {
  // Ids come from observation.cjs legalActions: lead:<slot>, move:<index>:<id>:<normal|tera>, switch:<slot>.
  const parts = row.id.split(':');
  if (parts[0] === 'lead') return `lead ${slotSpecies(physical, sideId, Number(parts[1]))}`;
  if (parts[0] === 'switch') return `switch ${slotSpecies(physical, sideId, Number(parts[1]))}`;
  if (parts[0] === 'move') return `move ${Dex.moves.get(parts[2]).name}${parts[3] === 'tera' ? ' + terastallize' : ''}`;
  throw Error(`unknown candidate ${row.id}`);
}

module.exports = {renderStatic, renderDynamic, candidateText, bySlot};
