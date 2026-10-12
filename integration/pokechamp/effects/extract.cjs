/** Reproduce the fixed Gen9 Dex desc asset. Never use shortDesc or rewrite text. */
'use strict';
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const crypto = require('crypto');
const root = path.resolve(__dirname, '../../..');
const showdown = path.join(root, 'pokemon-showdown');
const {Dex} = require(path.join(showdown, 'dist/sim/dex'));
const dex = Dex.mod('gen9');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const asset = {};
const aliases = {};
const missing = {};
for (const kind of ['items', 'abilities', 'moves']) {
  asset[kind] = {};
  aliases[kind] = {};
  missing[kind] = [];
  // Data keys preserve Hidden Power variants; Dex.all() can return duplicate IDs.
  const data = {items: 'Items', abilities: 'Abilities', moves: 'Moves'}[kind];
  for (const key of Object.keys(dex.data[data]).sort()) {
    const entry = dex[kind].get(key);
    const canonical = dex[kind].get(entry.id);
    if (!canonical.exists || !canonical.desc) {
      missing[kind].push(key);
      continue;
    }
    asset[kind][entry.id] = {name: canonical.name, desc: canonical.desc};
    if (key !== entry.id) aliases[kind][key] = entry.id;
  }
  for (const key of [...dex.loadAliases().keys()].sort()) {
    const entry = dex[kind].get(key);
    if (entry.exists && asset[kind][entry.id] && key !== entry.id) {
      aliases[kind][key] = entry.id;
    }
  }
  asset[kind] = Object.fromEntries(Object.entries(asset[kind]).sort());
}
const content = JSON.stringify({version: 'gen9-effects-v1', ...asset, aliases}, null, 2) + '\n';
const manifest = {
  version: 'gen9-effects-v1', generation: 9,
  source: 'https://github.com/smogon/pokemon-showdown',
  source_commit: cp.execFileSync('git', ['-C', showdown, 'rev-parse', 'HEAD'], {encoding:'utf8'}).trim(),
  method: 'node integration/pokechamp/effects/extract.cjs [output-directory]; Dex.mod("gen9")[kind].get(id).desc; canonical IDs; no shortDesc fallback, translation or recursive expansion',
  asset_sha256: hash(content), extractor_sha256: hash(fs.readFileSync(__filename)),
  license: 'MIT', license_sha256: hash(fs.readFileSync(path.join(showdown, 'LICENSE'))),
  counts: Object.fromEntries(Object.entries(asset).map(([k,v])=>[k,Object.keys(v).length])),
  missing_desc: missing,
};
const dest = path.resolve(process.argv[2] || __dirname);
fs.mkdirSync(dest, {recursive: true});
fs.writeFileSync(path.join(dest, 'gen9-effects-v1.json'), content);
fs.writeFileSync(path.join(dest, 'provenance.json'), JSON.stringify(manifest, null, 2) + '\n');
fs.copyFileSync(path.join(showdown, 'LICENSE'), path.join(dest, 'LICENSE'));
