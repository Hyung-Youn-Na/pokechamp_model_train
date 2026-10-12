'use strict';
const fs = require('node:fs');
const {performance} = require('node:perf_hooks');
const current = require('../observation/client.cjs');
const {install} = require('./official_async_delay.cjs');
const build = '/workspace/.artifacts/official-observation/v1';
async function run(input, oldPath) {
  const old = require(oldPath);
  const records = [];
  for (const test of input) {
    for (const mode of ['old_delayed', 'normal', 'delayed', 'replay_delayed']) {
      const lib = mode === 'old_delayed' ? old : current;
      const env = lib.environment(build);
      if (mode !== 'normal') install(env, 'repeat');
      const tracker = new lib.Tracker(env, 'p1');
      let offset = 0;
      const results = [];
      for (const decision of test.decisions) {
        const t = mode === 'replay_delayed' ? new lib.Tracker(env, 'p1') : tracker;
        const started = performance.now();
        try {
          await t.append(decision.lines.slice(mode === 'replay_delayed' ? 0 : offset));
          results.push({decision:decision.decision, state:JSON.parse(JSON.stringify(t.snapshot())), elapsed_ms:performance.now()-started});
          offset = decision.lines.length;
        } catch(error) {
          results.push({decision:decision.decision, error:String(error), elapsed_ms:performance.now()-started,
            current_step:t.battle.currentStep, queue_length:t.battle.stepQueue.length, consumed:t.consumed});
          break;
        }
      }
      records.push({battle:test.battle, mode, results, rss_bytes:process.memoryUsage().rss});
    }
  }
  return records;
}
run(JSON.parse(fs.readFileSync(process.argv[2])), process.argv[3]).then(r => {
  fs.writeFileSync(process.argv[4],JSON.stringify(r,null,2)+'\n');
  process.exit(0);
}).catch(e=>{console.error(e);process.exit(1);});
