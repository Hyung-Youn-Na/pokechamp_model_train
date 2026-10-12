'use strict';

const path = require('node:path');

const showdownRoot = process.env.POKECHAMP_SHOWDOWN_ROOT;
if (!showdownRoot || !path.isAbsolute(showdownRoot)) {
  throw new Error('POKECHAMP_SHOWDOWN_ROOT must be an absolute path');
}
for (const requiredFlag of ['--no-security', '--ai-tournament']) {
  if (!process.argv.includes(requiredFlag)) {
    throw new Error(`Missing required server flag: ${requiredFlag}`);
  }
}

const sealedSeed = '100,100,100,100';
if (process.env.POKECHAMP_SHOWDOWN_SEED !== sealedSeed) {
  throw new Error(`POKECHAMP_SHOWDOWN_SEED must be ${sealedSeed}`);
}

// The pinned fork sets forcetimer=true. Repository-managed experiments are
// untimed unless a player explicitly sends /timer on for a declared condition.
const configLoader = require(path.join(showdownRoot, 'dist', 'server', 'config-loader.js'));
configLoader.Config.forcetimer = false;

// Supplying the port disables the fork's host-specific SSL configuration.
// Supplying the address prevents the tracked 0.0.0.0 default from being used.
const server = require(path.join(showdownRoot, 'dist', 'server', 'index.js'));
const port = Number(process.env.POKECHAMP_BENCHMARK_PORT || 8000);
if (port !== 8000 && (!Number.isInteger(port) || port < 8100 || port > 8109)) {
  throw new Error('Invalid benchmark port');
}
server.listen(port, '127.0.0.1', 1);
