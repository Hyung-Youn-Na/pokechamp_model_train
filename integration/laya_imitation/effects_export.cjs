'use strict';
// EX-126 one-time export from the pinned Showdown engine (`pokemon-showdown` e64915c0e, `dist/sim` Dex):
// Gen 9 move / item / ability effect text and flags, and the legal species' types and possible abilities.
// Writes `dex_gen9_effects.json`; generators read only that file.
// Usage: node integration/laya_imitation/effects_export.cjs [output]
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const ENGINE = path.join(__dirname, '../../pokemon-showdown');
const {Dex} = require(path.join(ENGINE, 'dist/sim'));
const dex = Dex.forGen(9);
const commit = execFileSync('git', ['-C', ENGINE, 'rev-parse', '--short=9', 'HEAD'], {encoding: 'utf8'}).trim();
const legal = e => e.exists && !e.isNonstandard && e.num > 0 && e.gen <= 9;
const sorted = obj => Object.fromEntries(Object.keys(obj).sort().map(k => [k, obj[k]]));

const moves = {};
for (const m of dex.moves.all().filter(legal)) {
  if (m.isMax || m.isZ) continue;
  moves[m.id] = {
    name: m.name, type: m.type.toLowerCase(), category: m.category.toLowerCase(), power: m.basePower,
    priority: m.priority, target: m.target, flags: Object.keys(m.flags).sort(), shortDesc: m.shortDesc,
    desc: m.desc || m.shortDesc,
  };
}
const items = {};
for (const i of dex.items.all().filter(legal)) {
  if (i.megaStone || i.zMove || i.isPokeball) continue;
  items[i.id] = {name: i.name, shortDesc: i.shortDesc, desc: i.desc || i.shortDesc};
}
const abilities = {};
for (const a of dex.abilities.all().filter(legal)) {
  abilities[a.id] = {name: a.name, shortDesc: a.shortDesc, desc: a.desc || a.shortDesc};
}
const species = {};
for (const s of dex.species.all().filter(legal)) {
  // Forms that need a specific item / Ability / move revert in battle, so a card could not state their typing.
  if (s.battleOnly || s.isMega || s.isPrimal || s.isTotem || s.requiredItem || s.requiredItems || s.requiredAbility ||
      s.requiredMove) continue;
  species[s.id] = {types: s.types.map(t => t.toLowerCase()),
                   abilities: [...new Set(Object.values(s.abilities).map(a => dex.abilities.get(a).id))].sort()};
}
const value = {engine: {repository: 'pokemon-showdown', commit}, gen: 9,
               moves: sorted(moves), items: sorted(items), abilities: sorted(abilities), species: sorted(species)};
const out = process.argv[2] || path.join(__dirname, 'dex_gen9_effects.json');
fs.writeFileSync(out, JSON.stringify(value, null, 0) + '\n');
console.log(JSON.stringify({out, commit, moves: Object.keys(moves).length, items: Object.keys(items).length,
                            abilities: Object.keys(abilities).length,
                            species: Object.keys(species).length}));
