'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..', 'pokemon-showdown');
const {Teams} = require(path.join(root, 'dist/sim/teams.js'));
const {TeamValidator} = require(path.join(root, 'dist/sim/team-validator.js'));
const teams = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = Object.entries(teams).map(([key, value]) => ({
  key, errors: new TeamValidator('gen9ou').validateTeam(Teams.import(value.showdown_team)) || [],
}));
const passed = results.length === 2 && results.every(row => row.errors.length === 0);
process.stdout.write(JSON.stringify({passed, format: 'gen9ou', results}));
process.exitCode = passed ? 0 : 1;
