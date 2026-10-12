'use strict';
const {Battle} = require('../../../pokemon-showdown/dist/sim');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const battle = new Battle({format: new Format({name: 'Public weather source', mod: 'gen9', gameType: 'singles', ruleset: []}), seed: [1,2,3,4]});
battle.setPlayer('p1', {name: 'observer', team: [{species: 'Mew', ability: 'Synchronize', moves: ['Splash']}]});
battle.setPlayer('p2', {name: 'opponent', team: [{name: 'Sun Fox', species: 'Ninetales', ability: 'Drought', moves: ['Splash']}]});
process.stdout.write(JSON.stringify({event_seq: 1, protocol: battle.log.join('\n')}));
battle.destroy();
