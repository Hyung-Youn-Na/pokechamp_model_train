'use strict';
// Independent pinned simulator oracle. Only test code sees both original teams.
const path = require('node:path');
const readline = require('node:readline');
const root = path.resolve(__dirname, '../../..');
const {Battle, Teams} = require(path.join(root, 'pokemon-showdown/dist/sim'));
let battle;
const input = readline.createInterface({input: process.stdin});
input.on('line', line => {
  const value = JSON.parse(line);
  if (!battle) {
    battle = new Battle({formatid: 'gen9ou', seed: [1, 2, 3, 4]});
    for (const [i, role] of ['p1', 'p2'].entries()) {
      battle.setPlayer(role, {name: role, team: Teams.import(value.teams[i])});
    }
    process.stdout.write(JSON.stringify({public: battle.log.join('\n'),
      requests: [battle.p1.activeRequest, battle.p2.activeRequest]}) + '\n');
  } else {
    for (const [i, role] of ['p1', 'p2'].entries()) {
      if (!/^\/team [1-6]{6}$/.test(value.commands[i])) throw new Error('invalid wire command');
      if (!battle.choose(role, value.commands[i].slice(1))) throw new Error('Showdown rejected team choice');
    }
    process.stdout.write(JSON.stringify({
      first: [battle.p1.active[0].set.species, battle.p2.active[0].set.species],
      switches: battle.log.filter(line => line.startsWith('|switch|')),
      requests: [battle.p1.activeRequest, battle.p2.activeRequest],
    }) + '\n');
    input.close();
  }
});
input.on('close', () => { if (battle) battle.destroy(); });
