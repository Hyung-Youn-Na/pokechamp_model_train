/* Offline test preload only. Never modifies the official clock or build. */
'use strict';
const vm = require('node:vm');
const original = vm.runInContext;
const fs = require('node:fs');
function install(env, mode = 'delay') {
  const create = env.createBattle;
  env.createBattle = () => {
    const battle = create();
    const run = battle.run;
    let remaining = mode === 'repeat' ? 3 : 1;
    battle.run = function(line, ...args) {
      if (remaining && (line === '|turn|2' || mode === 'repeat' && line.startsWith('|turn|'))) {
        remaining--;
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 320);
      }
      return run.call(this, line, ...args);
    };
    return battle;
  };
  const timer = env.setTimeout;
  env.setTimeout = (callback, delay, ...args) => {
    if (process.env.EP058_DELAY_LOG) fs.appendFileSync(process.env.EP058_DELAY_LOG,
      JSON.stringify({pid:process.pid, mode, delay, at:Date.now()}) + '\n');
    if (mode === 'hang') return timer(() => {}, delay);
    return timer(() => {
      if (mode === 'throw') throw new Error('EP058 controlled timer callback exception');
      callback(...args);
    }, delay);
  };
}
if (process.env.EP058_DELAY_MODE) vm.runInContext = function(code, context, ...args) {
  const result = original.call(this, code, context, ...args);
  if (typeof code === 'string' && code.includes('global.createBattle =')) {
    install(context, process.env.EP058_DELAY_MODE || 'delay');
  }
  return result;
};
module.exports = {install};
