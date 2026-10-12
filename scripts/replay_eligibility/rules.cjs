'use strict';
// 현재 로컬 런타임의 공개 규칙을 읽는다. 서버/빌드/설정 변경은 수행하지 않는다.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const server = path.join(root, 'pokemon-showdown');
const {TeamValidator} = require(path.join(server, 'dist/sim/team-validator.js'));
const v = new TeamValidator('gen9ou');
const dex = v.dex;
dex.includeData();
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const catalog = {species: {}, moves: {}, abilities: {}, items: {}};
const alias = Object.fromEntries(dex.loadAliases());
function speciesRow(name) {
  const s = dex.species.get(name);
  const set = {name: s.name, species: s.name};
  return {id: s.id, name: s.name, base_species: s.baseSpecies,
    tier: s.tier, battle_only: s.battleOnly || null, changes_from: s.changesFrom || null,
    required_items: s.requiredItems || (s.requiredItem ? [s.requiredItem] : []),
    other_formes: s.otherFormes || [], cosmetic_formes: s.cosmeticFormes || [],
    abilities: Object.values(s.abilities),
    problems: s.exists ? [v.checkSpecies(set, s, s, {})].filter(Boolean) : ['알 수 없는 종']};
}
for (const s of dex.species.all()) {
  catalog.species[s.id] = speciesRow(s.name);
  for (const name of s.cosmeticFormes || []) {
    const row = speciesRow(name);
    catalog.species[row.id] = row;
  }
}
// checkMove에는 onValidateSet의 sleep/ohko 조건이 포함되지 않으므로 실제 hook도 호출한다.
const moveHooks = ['sleepmovesclause', 'ohkoclause'].filter(id => v.ruleTable.has(id));
for (const m of dex.moves.all()) {
  const set = {name: '관측', moves: [m.name]};
  const problems = [v.checkMove(set, m, {})].filter(Boolean);
  for (const id of moveHooks) {
    const hook = dex.formats.get(id).onValidateSet;
    if (typeof hook !== 'function') throw new Error('누락된 기술 검증 hook: ' + id);
    problems.push(...(hook.call(v, set, v.format, {}, {}) || []));
  }
  catalog.moves[m.id] = {id: m.id, name: m.name, problems: [...new Set(problems)]};
}
for (const [kind, method] of [['abilities', 'checkAbility'], ['items', 'checkItem']]) {
  for (const obj of dex[kind].all()) {
    catalog[kind][obj.id] = {id: obj.id, name: obj.name,
      problems: [v[method]({name: '관측'}, obj, {})].filter(Boolean)};
  }
}
const loaded = Object.keys(require.cache).filter(p => p.startsWith(path.join(server, 'dist') + '/')).sort();
const sourceFiles = ['config/formats.ts', 'data/rulesets.ts', 'data/formats-data.ts',
  'sim/team-validator.ts', 'sim/dex-formats.ts'];
const files = [...new Set([...loaded, ...sourceFiles.map(p => path.join(server, p))])].sort();
const hashes = Object.fromEntries(files.map(p => [path.relative(root, p), sha(fs.readFileSync(p))]));
process.stdout.write(JSON.stringify({schema_version: 'gen9ou-local-rules/v1',
  server_commit: cp.execFileSync('git', ['rev-parse', 'HEAD'], {cwd: server, encoding: 'utf8'}).trim(),
  tracked_changes: cp.execFileSync('git', ['diff', 'HEAD', '--name-only'], {cwd: server, encoding: 'utf8'}).trim(),
  node_version: process.version, format: {id: v.format.id, name: v.format.name,
    ruleset: v.format.ruleset, banlist: v.format.banlist},
  rule_table: [...v.ruleTable.entries()], complex_bans: v.ruleTable.complexBans,
  complex_team_bans: v.ruleTable.complexTeamBans, move_hooks: moveHooks,
  limits: {min_team_size: v.ruleTable.minTeamSize, max_team_size: v.ruleTable.maxTeamSize},
  file_sha256: hashes, aliases: alias, catalog}));
