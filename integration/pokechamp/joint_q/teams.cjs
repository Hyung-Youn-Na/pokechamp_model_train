'use strict';
const fs = require('node:fs');
const crypto = require('node:crypto');
const {Teams} = require('../../../pokemon-showdown/dist/sim/teams.js');
const {Dex} = require('../../../pokemon-showdown/dist/sim/dex.js');
const {TeamValidator} = require('../../../pokemon-showdown/dist/sim/team-validator.js');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = input.map(entry => {
  const sets = entry.packed ? Teams.unpack(entry.text) : Teams.import(entry.text);
  if (!sets || sets.length !== 6) throw Error('expected six sets');
  for (let i = 0; i < sets.length; i++) {
    const s = sets[i], species = Dex.species.get(s.species);
    if (!species.exists) throw Error('unknown species');
    if (!s.gender) {
      const raw = crypto.createHash('sha256').update(`EX065:20260929:${entry.hash}:${i}:gender`).digest();
      s.gender = species.gender || (raw.readUInt32BE(0) / 2**32 < species.genderRatio.M ? 'M' : 'F');
    }
  }
  const before = Teams.pack(sets);
  const problems = new TeamValidator('gen9ou').validateTeam(sets);
  if (problems) throw Error(JSON.stringify(problems));
  const packed = Teams.pack(sets);
  // Explicit normalization is recorded; the fixed own packed wire is kept.
  return {sets, packed, before_validation:before, text:Teams.export(sets),
          species:sets.map(s => Dex.species.get(s.species).id), legal:true};
});
process.stdout.write(JSON.stringify(result));
