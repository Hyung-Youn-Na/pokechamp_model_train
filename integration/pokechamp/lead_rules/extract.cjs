/** Fixed Gen9 OU marginal possibilities, never opponent sets. */
'use strict';
const fs = require('fs'), path = require('path'), cp = require('child_process');
const hash = x => require('crypto').createHash('sha256').update(x).digest('hex');
const root = path.resolve(__dirname, '../../..'), ps = path.join(root, 'pokemon-showdown');
const {Dex} = require(path.join(ps, 'dist/sim/dex'));
const {TeamValidator} = require(path.join(ps, 'dist/sim/team-validator'));
const dex = Dex.mod('gen9'), validator = new TeamValidator('gen9ou');
const pinned = JSON.parse(fs.readFileSync(path.join(__dirname, '../effects/provenance.json')));
const commit = cp.execFileSync('git', ['-C', ps, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim();
if (commit !== pinned.source_commit) throw Error('Dex commit differs from effects pin');
const categories = m => [
  m.weather || ['chillyreception','snowscape','sunnyday','raindance','sandstorm'].includes(m.id) ? 'weather_change' : null,
  ['rapidspin','mortalspin','defog','tidyup','courtchange'].includes(m.id) ? 'hazard_removal_exchange' : null,
  ['taunt','encore'].includes(m.id) ? 'taunt_encore' : null,
  m.selfSwitch ? 'pivot' : null,
  m.category !== 'Status' && (m.priority > 0 || m.onModifyPriority) ? 'priority_attack' : null,
].filter(Boolean);
const moves = {};
for (const m of [...dex.moves.all()].sort((a,b)=>a.id.localeCompare(b.id))) {
  if (!m.exists || m.gen > 9) continue;
  moves[m.id] = {name:m.name, type:m.type, category:m.category, base_power:m.basePower,
    base_accuracy:m.accuracy, priority:m.priority, target:m.target, flags:m.flags,
    related_categories:categories(m)};
}
const related = dex.moves.all().filter(m => categories(m).length && !m.isNonstandard && m.gen <= 9);
const types = dex.types.all().filter(t => t.exists && t.name !== 'Stellar');
const species = {};
const allSpecies = new Map();
for (const s of dex.species.all()) {
  allSpecies.set(s.id, s);
  for (const name of s.cosmeticFormes || []) {
    const form = dex.species.get(name);
    allSpecies.set(form.id, form);
  }
}
for (const s of [...allSpecies.values()].sort((a,b)=>a.id.localeCompare(b.id))) {
  if (!s.exists || s.gen > 9 || s.isNonstandard) continue;
  const abilities = [...new Set(Object.values(s.abilities))];
  const set = (ability, move) => ({name:s.name, species:s.name, ability, moves:[move],
    item:s.requiredItem || s.requiredItems?.[0] || '', nature:'Serious', evs:{hp:1}});
  const legal = (a,m) => !validator.validateSet(set(a,m), {});
  // Single-move validation includes Gen9 origin, learnability and OU bans.
  const possible = related.filter(m => abilities.some(a => legal(a,m.name)));
  const probeMoves = [...new Set(possible.map(m=>m.name).concat(
    dex.species.getFullLearnset(s.id).flatMap(row=>Object.keys(row.learnset))))];
  const possibleAbilities = abilities.filter(a => probeMoves.some(m => legal(a,m)));
  const multipliers = Object.fromEntries(types.map(t => [t.name,
    dex.getImmunity(t.name,s) ? 2 ** dex.getEffectiveness(t.name,s) : 0]));
  const status = ['brn','par','psn','tox','frz'].filter(t => !dex.getImmunity(t === 'tox' ? 'psn' : t,s));
  species[s.id] = {name:s.name, base_species:s.baseSpecies, base_types:s.types,
    non_tera_type_multipliers:multipliers, type_status_immunities:status,
    possible_abilities:possibleAbilities.map(a=>dex.abilities.get(a).id).sort(),
    possible_related_moves:possible.map(m=>m.id).sort()};
}
const content = JSON.stringify({version:'gen9-lead-dex-v2', format:'gen9ou', species, moves}, null, 2)+'\n';
const manifest = {version:'gen9-lead-dex-v2', source_commit:commit,
  source:'https://github.com/smogon/pokemon-showdown', asset_sha256:hash(content),
  extractor_sha256:hash(fs.readFileSync(__filename)), license:'MIT', license_sha256:pinned.license_sha256,
  method:'Dex.mod(gen9) types/immunity/effectiveness and move fields; TeamValidator(gen9ou).validateSet for each single related move and species ability with required form item. Marginal possibilities, no joint set or probability. See extract.cjs category predicates.'};
const dest = path.resolve(process.argv[2] || __dirname); fs.mkdirSync(dest,{recursive:true});
fs.writeFileSync(path.join(dest,'dex-v2.json'),content);
fs.writeFileSync(path.join(dest,'provenance.json'),JSON.stringify(manifest,null,2)+'\n');
fs.copyFileSync(path.join(ps,'LICENSE'),path.join(dest,'LICENSE'));
