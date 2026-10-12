'use strict';
const {Battle} = require('../../../pokemon-showdown/dist/sim');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const battle=new Battle({format:new Format({name:'Double faint fixture',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
const reserve={species:'Pikachu',moves:['Splash'],ability:'Static'};
battle.setPlayer('p1',{name:'one',team:[{species:'Mew',moves:['Explosion'],ability:'Synchronize'},reserve]});
battle.setPlayer('p2',{name:'two',team:[{species:'Slowking',moves:['Splash'],ability:'Regenerator'},reserve]});
battle.p2.active[0].hp=1;
battle.makeChoices('move 1','move 1');
process.stdout.write(JSON.stringify({requestState:battle.requestState,
  fainted:[battle.p1.active[0].fainted,battle.p2.active[0].fainted],protocol:battle.log.join('\n')}));
battle.destroy();
