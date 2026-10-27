'use strict';
// EX-121 damage worker: one JSON request per line -> one JSON result line, in order.
// Uses the pinned @smogon/calc 0.11.0 + ruination-v1 patch of integration/pokechamp/improved_io/calculator
// read-only (patchCalc(false) only verifies). Percentages are of the defender's max HP.
const path = require('node:path');
const readline = require('node:readline');
const ROOT = path.join(__dirname, '../pokechamp/improved_io/calculator');
const patch = require(path.join(ROOT, 'patch.cjs')).patchCalc(false);
const calcRoot = path.join(ROOT, 'node_modules/@smogon/calc');
const {calculate, Generations, Pokemon, Move, Field} = require(calcRoot);
const version = require(path.join(calcRoot, 'package.json')).version;
if (version !== '0.11.0') throw new Error('calculator version drift');
const gen = Generations.get(9);
const id = v => String(v || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];

function named(table, value) {
  const entry = value ? table.get(id(value)) : undefined;
  return entry ? entry.name : undefined;
}

function mon(spec, unresolved) {
  const species = gen.species.get(id(spec.species));
  if (!species) throw new Error('unknown species ' + spec.species);
  const fill = (v, d) => Object.fromEntries(STATS.map(s => [s, v && Number.isInteger(v[s]) ? v[s] : d]));
  const options = {
    level: spec.level || 100, nature: named(gen.natures, spec.nature) || 'Serious',
    ability: named(gen.abilities, spec.ability), item: named(gen.items, spec.item),
    evs: fill(spec.evs, 0), ivs: fill(spec.ivs, 31), boosts: spec.boosts || {},
    status: ['brn', 'par', 'slp', 'frz', 'psn', 'tox'].includes(spec.status) ? spec.status : '',
  };
  if (spec.tera) options.teraType = named(gen.types, spec.tera);
  for (const [key, table] of [['ability', gen.abilities], ['item', gen.items], ['nature', gen.natures]]) {
    if (spec[key] && !named(table, spec[key])) unresolved.push(key + ':' + spec[key]);
  }
  if (spec.tera && !options.teraType) unresolved.push('tera:' + spec.tera);
  const p = new Pokemon(gen, species.name, options);
  if (spec.hp_percent !== null && spec.hp_percent !== undefined) {
    p.originalCurHP = Math.max(1, Math.round(p.maxHP() * spec.hp_percent / 100));
  }
  return p;
}

const WEATHER = {sunnyday: 'Sun', desolateland: 'Harsh Sunshine', raindance: 'Rain', primordialsea: 'Heavy Rain',
  sandstorm: 'Sand', snow: 'Snow', snowscape: 'Snow', hail: 'Hail', deltastream: 'Strong Winds'};
const TERRAIN = {electric_terrain: 'Electric', grassy_terrain: 'Grassy', psychic_terrain: 'Psychic',
  misty_terrain: 'Misty'};

function side(values) {
  values = values || {};
  return {isReflect: !!values.reflect, isLightScreen: !!values.light_screen, isAuroraVeil: !!values.aurora_veil};
}

function field(spec) {
  const terrain = Object.keys(spec.field || {}).map(k => TERRAIN[k]).find(Boolean);
  return new Field({weather: WEATHER[spec.weather] || undefined, terrain,
    attackerSide: side(spec.attacker_side), defenderSide: side(spec.defender_side)});
}

function one(request) {
  const unresolved = [];
  const attacker = mon(request.attacker, unresolved);
  const defender = mon(request.defender, unresolved);
  const moveName = named(gen.moves, request.move);
  if (!moveName) throw new Error('unknown move ' + request.move);
  const move = new Move(gen, moveName);
  const result = calculate(gen, attacker, defender, move, field(request));
  let [lo, hi] = result.range();
  const max = defender.maxHP();
  const out = {min: Math.round(1000 * lo / max) / 10, max: Math.round(1000 * hi / max) / 10};
  if (unresolved.length) out.unresolved = unresolved;
  return out;
}

process.stdout.write(JSON.stringify({status: 'ready', calc: version, patch}) + '\n');
readline.createInterface({input: process.stdin, crlfDelay: Infinity}).on('line', line => {
  const requests = JSON.parse(line);
  const out = requests.map(r => { try { return one(r); } catch (e) { return {error: String(e.message || e)}; } });
  process.stdout.write(JSON.stringify(out) + '\n');
});
