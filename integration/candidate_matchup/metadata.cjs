'use strict';
// Read public, pinned game rules only. No Battle, model, network, or state writes.
const path = require('node:path');
const {Dex} = require(path.resolve(__dirname, '../../pokemon-showdown/dist/sim'));
const dex = Dex.mod('gen9');
const hooks = obj => Object.keys(obj).filter(k => typeof obj[k] === 'function').sort();
const moves = Object.fromEntries(dex.moves.all().map(m => [m.id, {
  id:m.id, name:m.name, type:m.type, category:m.category, target:m.target,
  flags:m.flags || {}, status:m.status || null, ignoreImmunity:m.ignoreImmunity ?? null,
  secondaryStatuses:(m.secondaries || (m.secondary ? [m.secondary] : [])).filter(s => s.status).map(s => s.status),
  ignoreAbility:!!m.ignoreAbility, breaksProtect:!!m.breaksProtect,
  damage:typeof m.damage === 'number' || typeof m.damage === 'string' ? m.damage : null,
  hooks:hooks(m),
}]));
const abilities = Object.fromEntries(dex.abilities.all().map(a => [a.id, {
  id:a.id, flags:a.flags || {}, hooks:hooks(a),
}]));
const types = dex.types.all().map(t => t.name).filter(t => t !== 'Stellar');
const typeChart = Object.fromEntries(types.map(a => [a, Object.fromEntries(types.map(d =>
  [d, dex.getImmunity(a,d) ? 2 ** dex.getEffectiveness(a,d) : 0]))]));
process.stdout.write(JSON.stringify({generation:9, moves, abilities, type_chart:typeChart})+'\n');
