'use strict';
const {Battle} = require('../../../pokemon-showdown/dist/sim');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const battle = new Battle({format:new Format({name:'Public fixture', mod:'gen9',
  gameType:'singles', ruleset:[]}), seed:[1,2,3,4]});
battle.setPlayer('p1', {name:'observer',team:[{species:'Mew',moves:['Splash'],ability:'Synchronize',item:'Leftovers'}]});
battle.setPlayer('p2', {name:'revealed',team:[{species:'Gliscor',moves:['Knock Off'],ability:'Poison Heal',item:'Toxic Orb'}]});
battle.p2.active[0].hp = 150;
battle.p2.active[0].setStatus('tox');
battle.makeChoices('move 1','move 1');
process.stdout.write(JSON.stringify({protocol:battle.log.join('\n')}));
battle.destroy();
