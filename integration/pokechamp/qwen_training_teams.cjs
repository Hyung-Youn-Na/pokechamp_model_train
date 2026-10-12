'use strict';
const fs = require('node:fs');
const {Teams} = require('../../pokemon-showdown/dist/sim/teams.js');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = {};
for (const side of ['p1', 'p2']) {
  const packed = input[side].team;
  const team = Teams.unpack(packed);
  const text = Teams.export(team);
  if (JSON.stringify(Teams.unpack(Teams.pack(Teams.import(text)))) !== JSON.stringify(team)) {
    throw new Error('team export changes unpacked sets');
  }
  result[side] = text;
}
process.stdout.write(JSON.stringify(result));
