'use strict';
// EX-161 one-time export from the pinned Showdown engine (`pokemon-showdown` e64915c0e, `dist/sim` Dex):
// Gen 9 base PP of every legal move. Writes `pp_gen9.json`; the v10 renderer reads only that file.
// Usage: node integration/laya_v10/pp_export.cjs [output]
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const ENGINE = path.join(__dirname, '../../pokemon-showdown');
const {Dex} = require(path.join(ENGINE, 'dist/sim'));
const dex = Dex.forGen(9);
const commit = execFileSync('git', ['-C', ENGINE, 'rev-parse', '--short=9', 'HEAD'], {encoding: 'utf8'}).trim();
const legal = e => e.exists && !e.isNonstandard && e.num > 0 && e.gen <= 9;

const pp = {};
for (const m of dex.moves.all().filter(legal)) {
  if (m.isMax || m.isZ) continue;
  pp[m.id] = m.pp;
}
const out = {source: {engine: 'pokemon-showdown', commit}, pp: Object.fromEntries(Object.keys(pp).sort().map(k => [k, pp[k]]))};
fs.writeFileSync(process.argv[2] || path.join(__dirname, 'pp_gen9.json'), JSON.stringify(out, null, 1) + '\n');
