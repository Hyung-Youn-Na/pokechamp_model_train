'use strict';
// Same pinned before/context/after hash contract as patch.cjs. Compile the
// project-owned overlay in memory: the installed v1 module and files stay intact.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Module = require('node:module');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function statePatch() {
 const bytes = fs.readFileSync(path.join(__dirname, 'mechanics-v2.json'));
 const patch = JSON.parse(bytes);
 if (patch.patch_id !== 'mechanics-v2' || patch.version !== '0.11.0' ||
     patch.package !== '@smogon/calc' || patch.mode !== 'verified_in_memory_overlay' || patch.files.length !== 1)
  throw new Error('state patch identity drift');
 const file = patch.files[0];
 if (file.path !== 'dist/mechanics/gen789.js') throw new Error('state patch target drift');
 const target = path.join(__dirname, 'node_modules/@smogon/calc', file.path);
 const raw = fs.readFileSync(target);
 if (sha(raw) !== file.before_sha256) throw new Error('state patch source hash mismatch');
 let output = raw.toString('utf8');
 for (const edit of file.replacements) {
  if (output.split(edit.before).length !== 2) throw new Error('state patch context mismatch');
  output = output.replace(edit.before, edit.after);
 }
 if (sha(output) !== file.after_sha256) throw new Error('state patch output hash mismatch');
 const overlay = new Module(target, module);
 overlay.filename = target;
 overlay.paths = Module._nodeModulePaths(path.dirname(target));
 overlay._compile(output, target);
 if (sha(fs.readFileSync(target)) !== file.before_sha256) throw new Error('state patch modified installation');
 return {identity:{patch_id:patch.patch_id, patch_sha256:sha(bytes), files:{[file.path]:file.after_sha256}},
  calculate:(gen,a,d,m,f)=>overlay.exports.calculateSMSSSV(gen,a.clone(),d.clone(),m.clone(),f.clone())};
}
module.exports = {statePatch};
if (require.main === module) process.stdout.write(JSON.stringify(statePatch().identity)+'\n');
