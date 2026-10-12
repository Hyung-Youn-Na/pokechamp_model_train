'use strict';
const {Battle} = require('../../../pokemon-showdown/dist/sim');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
function run(move) {
 const battle = new Battle({format:new Format({name:'Delayed fixture',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
 battle.setPlayer('p1',{name:'caster',team:[{species:'Slowking-Galar',moves:[move,'Splash'],ability:'Regenerator'}]});
 battle.setPlayer('p2',{name:'target',team:[{species:'Mew',moves:['Splash'],ability:'Synchronize'}]});
 const hp=[battle.p2.active[0].hp];
 battle.makeChoices('move 1','move 1'); hp.push(battle.p2.active[0].hp);
 battle.makeChoices('move 2','move 1'); hp.push(battle.p2.active[0].hp);
 battle.makeChoices('move 2','move 1'); hp.push(battle.p2.active[0].hp);
 const result={move,hp,protocol:battle.log.join('\n')};battle.destroy();return result;
}
process.stdout.write(JSON.stringify([run('Future Sight'),run('Splash')]));
