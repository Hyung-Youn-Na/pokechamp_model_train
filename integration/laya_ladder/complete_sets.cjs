'use strict';
// JSONL: each line {candidates:[{species,moves,item,ability,teraType,nature,evs,gender,level}]} (ids or names)
// -> first legal candidate under the pinned local gen9ou validator, converted to display names, or null.
const path = require('node:path');
const server = '/workspace/pokemon-showdown/dist/sim';
const {Dex} = require(path.join(server, 'dex.js'));
const {TeamValidator} = require(path.join(server, 'team-validator.js'));
const validator = new TeamValidator('gen9ou');
const name = (table, v) => { const o = Dex[table].get(v); return o.exists ? o.name : null; };
function build(c) {
  const species = name('species', c.species); if (!species) return null;
  const moves = c.moves.map(m => name('moves', m)); if (moves.some(m => !m)) return null;
  const item = c.item ? name('items', c.item) : ''; if (c.item && !item) return null;
  const ability = name('abilities', c.ability); if (!ability) return null;
  const tera = name('types', c.teraType); if (!tera) return null;
  const set = {name: species, species, item, ability, moves, nature: name('natures', c.nature) || 'Serious',
    evs: c.evs, ivs: {hp:31,atk:31,def:31,spa:31,spd:31,spe:31}, level: c.level || 100, teraType: tera};
  if (c.gender) set.gender = c.gender;
  return set;
}
require('node:readline').createInterface({input: process.stdin}).on('line', line => {
  const req = JSON.parse(line); let out = null, tried = 0, last = null;
  for (const c of req.candidates) {
    const set = build(c); tried++;
    if (!set) continue;
    const copy = JSON.parse(JSON.stringify(set));
    const problems = validator.validateSet(copy, {});
    if (!problems || !problems.length) { delete set.name; out = set; break; }
    last = problems;
  }
  process.stdout.write(JSON.stringify({set: out, tried, last}) + '\n');
});
