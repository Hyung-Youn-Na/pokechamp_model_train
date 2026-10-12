// 고정된 로컬 Showdown Gen9 효과를 재현 가능한 검토용 JSON으로 추출한다.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const cp = require('child_process');
const root = path.resolve(__dirname, '../..');
const {Dex} = require(path.join(root, 'pokemon-showdown/dist/sim/dex'));
const d = Dex.mod('gen9');
const target = process.argv[2] || path.join(root, 'project_context/exec-plans/evidence/ep091/mechanics.json');
const moves = {};
for (const x of d.moves.all()) {
  if (!x.exists) continue;
  moves[x.id] = {id:x.id,name:x.name,type:x.type.toLowerCase(),category:x.category,power:x.basePower,priority:x.priority,
    target:x.target,boosts:x.boosts||null,self:x.self||null,secondaries:x.secondaries||[],status:x.status||null,
    volatileStatus:x.volatileStatus||null,sideCondition:x.sideCondition||null,weather:x.weather||null,
    pseudoWeather:x.pseudoWeather||null,terrain:x.terrain||null,selfSwitch:x.selfSwitch||null,forceSwitch:x.forceSwitch||false,
    heal:x.heal||null,drain:x.drain||null,isNonstandard:x.isNonstandard||null,flags:x.flags||{},desc:x.desc,shortDesc:x.shortDesc,
    fixedDamage:!!(x.damage||x.damageCallback),ohko:!!x.ohko,multihit:x.multihit||null};
}
const species = {};
for (const x of d.species.all()) if (x.exists) species[x.id] = {id:x.id,name:x.name,types:x.types.map(t=>t.toLowerCase()),
  baseStats:x.baseStats,abilities:x.abilities,baseSpecies:x.baseSpecies,tier:x.tier};
const abilities = {};
for (const x of d.abilities.all()) if (x.exists) abilities[x.id] = {id:x.id,name:x.name,desc:x.desc,shortDesc:x.shortDesc};
const items = {};
for (const x of d.items.all()) if (x.exists) items[x.id] = {id:x.id,name:x.name,desc:x.desc,shortDesc:x.shortDesc};
fs.writeFileSync(target, JSON.stringify({gen:9,species,moves,abilities,items},null,2)+'\n');
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const files = Object.keys(require.cache).filter(p=>p.startsWith(path.join(root,'pokemon-showdown'))).sort();
const provenance = {gen:9,repository:'https://github.com/smogon/pokemon-showdown',
  revision:cp.execFileSync('git',['-C',path.join(root,'pokemon-showdown'),'rev-parse','HEAD'],{encoding:'utf8'}).trim(),
  snapshot_sha256:sha(target),exporter_sha256:sha(__filename),
  loaded_files:files.map(p=>({path:path.relative(root,p),sha256:sha(p)}))};
fs.writeFileSync(target.replace(/\.json$/,'.provenance.json'),JSON.stringify(provenance,null,2)+'\n');
