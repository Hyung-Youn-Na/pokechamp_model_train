'use strict';

const path = require('node:path');

const showdownRoot = process.env.POKECHAMP_SHOWDOWN_ROOT;
const sealedSeed = '100,100,100,100';
if (!showdownRoot || !path.isAbsolute(showdownRoot)) {
  throw new Error('POKECHAMP_SHOWDOWN_ROOT must be an absolute path');
}
if (process.env.POKECHAMP_SHOWDOWN_SEED !== sealedSeed) {
  throw new Error(`POKECHAMP_SHOWDOWN_SEED must be ${sealedSeed}`);
}

// NODE_OPTIONS preloads this module in the main server and every worker process.
const {PRNG} = require(path.join(showdownRoot, 'dist', 'sim', 'prng.js'));
const rootPrng = new PRNG(sealedSeed);
PRNG.generateSeed = () => [
  rootPrng.random(2 ** 16),
  rootPrng.random(2 ** 16),
  rootPrng.random(2 ** 16),
  rootPrng.random(2 ** 16),
].join(',');

// Benchmark-only: inject the declared battle seed at the simulator start boundary.
// Qualification still uses its sealed root PRNG above.
if (process.env.POKECHAMP_BENCHMARK_SEED) {
  const fs = require('node:fs');
  const seed = process.env.POKECHAMP_BENCHMARK_SEED;
  const evidence = process.env.POKECHAMP_BENCHMARK_SEED_RECORD;
  if (!/^\d+,\d+,\d+,\d+$/.test(seed) || seed.split(',').some(x => +x >= 65536) || !path.isAbsolute(evidence || '')) {
    throw new Error('Invalid benchmark seed/evidence');
  }
  const {BattleStream} = require(path.join(showdownRoot, 'dist', 'sim', 'battle-stream.js'));
  const original = BattleStream.prototype._writeLine;
  BattleStream.prototype._writeLine = function(type, message) {
    if (type === 'start') {
      const options = JSON.parse(message);
      options.seed = seed;
      message = JSON.stringify(options);
    }
    if (type === 'player' && process.env.POKECHAMP_A_DIAGNOSTIC_TEAM_RECORD) {
      fs.appendFileSync(process.env.POKECHAMP_A_DIAGNOSTIC_TEAM_RECORD,
        JSON.stringify({type, message}) + '\n', {mode: 0o600});
    }
    const result = original.call(this, type, message);
    if (type === 'start') {
      fs.appendFileSync(evidence, JSON.stringify({seed: this.battle.prngSeed, format: this.battle.format.id}) + '\n', {mode: 0o600});
    }
    return result;
  };
}
