'use strict';
// Verify the actual simulator player payload against original bytes. Gender omitted
// in the source remains unconstrained; TeamValidator may choose it randomly.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const {Teams} = require(path.join(root, 'pokemon-showdown/dist/sim/teams.js'));
const request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const records = fs.readFileSync(process.argv[3], 'utf8').trim().split('\n').map(JSON.parse);
const norm = x => String(x || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const result = [];
for (const record of records) {
  const split = record.message.indexOf(' ');
  const role = record.message.slice(0, split);
  const payload = JSON.parse(record.message.slice(split + 1));
  const key = request.slot.teams[Number(role.slice(1)) - 1];
  const raw = fs.readFileSync(path.join(request.diagnostic_prepared, 'teams', key + '.txt'), 'utf8');
  const expected = Teams.import(raw);
  const actual = typeof payload.team === 'string' ? Teams.unpack(payload.team) : payload.team;
  const errors = [];
  if (!actual || actual.length !== 6 || payload.name !== request.names[role]) errors.push('identity');
  for (let i = 0; i < 6 && actual; i++) {
    const a = actual[i], e = expected[i];
    for (const field of ['species','item','ability','nature','teraType']) {
      if (norm(a[field]) !== norm(e[field])) errors.push(`${i}:${field}`);
    }
    if (e.gender && a.gender !== e.gender) errors.push(`${i}:gender`);
    if ((a.level || 100) !== (e.level || 100)) errors.push(`${i}:level`);
    if (JSON.stringify(a.moves.map(norm)) !== JSON.stringify(e.moves.map(norm))) errors.push(`${i}:moves`);
    for (const stat of ['hp','atk','def','spa','spd','spe']) {
      if ((a.evs?.[stat] ?? 0) !== (e.evs?.[stat] ?? 0)) errors.push(`${i}:evs:${stat}`);
      if ((a.ivs?.[stat] ?? 31) !== (e.ivs?.[stat] ?? 31)) errors.push(`${i}:ivs:${stat}`);
    }
  }
  result.push({role, key, errors, normalized_team: actual, packed_team: Teams.pack(actual)});
}
const passed = result.length === 2 && new Set(result.map(r => r.role)).size === 2 && result.every(r => !r.errors.length);
process.stdout.write(JSON.stringify({passed, result}));
process.exitCode = passed ? 0 : 1;
