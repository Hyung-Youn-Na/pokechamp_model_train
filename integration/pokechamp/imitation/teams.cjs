'use strict';
// Local pinned simulator validation. Never change upstream data or simulator config.
const fs = require('node:fs');
const crypto = require('node:crypto');
const {Teams} = require('../../../pokemon-showdown/dist/sim/teams.js');
const {Dex} = require('../../../pokemon-showdown/dist/sim/dex.js');
const {TeamValidator} = require('../../../pokemon-showdown/dist/sim/team-validator.js');
const validator = new TeamValidator('gen9ou');
function normalizeEntries(input) { return input.map(entry => {
  const sets = entry.sets ? JSON.parse(JSON.stringify(entry.sets)) :
    entry.packed ? Teams.unpack(entry.text) : Teams.import(entry.text);
  if (!sets || sets.length !== 6) return {error:'expected_six_sets'};
  for (let slot = 0; slot < sets.length; slot++) {
    const set = sets[slot];
    const species = Dex.species.get(set.species);
    if (!species.exists) return {error:'unknown_species'};
    set.name = species.name;
    if (!set.gender) {
      const bytes = crypto.createHash('sha256').update(`EX071:20261001:${entry.sha256}:${slot}:gender`).digest();
      set.gender = species.gender || (bytes.readUInt32BE(0) / 2**32 < species.genderRatio.M ? 'M' : 'F');
    }
  }
  if (entry.parse_only) return {sets, species:sets.map(s => Dex.species.get(s.species).id)};
  const individual = sets.map(s => {
    const copy = JSON.parse(JSON.stringify(s));
    const problems = validator.validateSet(copy, {}) || [];
    return {set:copy, problems};
  });
  const before = Teams.pack(sets);
  const problems = validator.validateTeam(sets) || [];
  return {sets, individual, species:sets.map(s => Dex.species.get(s.species).id),
          problems, legal:problems.length === 0, before_validation:before,
          packed:Teams.pack(sets), text:Teams.export(sets)};
}); }
if (process.argv.includes('--jsonl')) {
  const readline = require('node:readline');
  readline.createInterface({input:process.stdin, crlfDelay:Infinity}).on('line', line => {
    try { process.stdout.write(JSON.stringify({ok:true,results:normalizeEntries(JSON.parse(line))})+'\n'); }
    catch(error) { process.stdout.write(JSON.stringify({ok:false,error:String(error)})+'\n'); }
  });
} else {
  process.stdout.write(JSON.stringify(normalizeEntries(JSON.parse(fs.readFileSync(0,'utf8')))));
}
