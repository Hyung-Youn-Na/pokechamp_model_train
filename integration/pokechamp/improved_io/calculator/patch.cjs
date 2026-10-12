'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function patchCalc(apply = false) {
  const bytes = fs.readFileSync(path.join(__dirname, 'ruination-v1.json'));
  const patch = JSON.parse(bytes);
  const root = path.join(__dirname, 'node_modules/@smogon/calc');
  const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'))).version;
  if (patch.patch_id !== 'ruination-v1' || patch.package !== '@smogon/calc' ||
      patch.version !== '0.11.0' || version !== patch.version) throw new Error('calculator version/patch drift');
  // Validate every target before any write, including partially applied installs.
  const targets = patch.files.map(file => {
    const target = path.join(root, file.path);
    const original = fs.readFileSync(target);
    if (sha(original) === file.after_sha256) return {file, target, output: original};
    if (sha(original) !== file.before_sha256) throw new Error(`calculator file hash mismatch: ${file.path}`);
    if (!apply) throw new Error(`calculator patch missing: ${file.path}; run npm run patch:calc`);
    let output = original.toString('utf8');
    for (const edit of file.replacements) {
      if (output.split(edit.before).length !== 2) throw new Error(`patch context mismatch: ${file.path}`);
      output = output.replace(edit.before, edit.after);
    }
    output = Buffer.from(output);
    if (sha(output) !== file.after_sha256) throw new Error(`patch output hash mismatch: ${file.path}`);
    return {file, target, output};
  });
  for (const {file, target, output} of targets) {
    if (apply && sha(fs.readFileSync(target)) !== file.after_sha256) fs.writeFileSync(target, output);
    if (sha(fs.readFileSync(target)) !== file.after_sha256) throw new Error(`patch verification failed: ${file.path}`);
  }
  return {patch_id: patch.patch_id, patch_sha256: sha(bytes),
    files: Object.fromEntries(targets.map(({file}) => [file.path, file.after_sha256]))};
}
module.exports = {patchCalc};
if (require.main === module) {
  try { console.log(JSON.stringify(patchCalc(true))); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
