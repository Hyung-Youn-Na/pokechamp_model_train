'use strict';
const {Battle, extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
function run(mode) {
 const b = new Battle({format:new Format({name:'State lifecycle',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
 b.setPlayer('p1',{name:'caster',team:[
  {species:'Slowking-Galar',moves:['Future Sight','Splash'],ability:'Regenerator'},
  {species:'Mew',moves:['Splash'],ability:'Synchronize'}]});
 b.setPlayer('p2',{name:'target',team:[
  {species:'Mew',moves:['Splash'],ability:'Synchronize'},
  {species:mode==='immune'?'Ting-Lu':'Chansey',moves:['Splash'],ability:mode==='immune'?'Vessel of Ruin':'Natural Cure'}]});
 const rows=[];
 function snap() {rows.push({turn:b.turn,protocol:extractChannelMessages(b.log.join('\n'),[1])[1].join('\n'),
   pending:Object.keys(b.p2.slotConditions[0]),target:b.p2.active[0].species.name,hp:b.p2.active[0].hp});}
 b.makeChoices('move 1','move 1');snap();
 if(mode==='failed_recast') b.makeChoices('move 1','move 1');
 else b.makeChoices('switch 2','switch 2');
 snap();
 if(mode==='silent_expiry') {b.p2.active[0].faint();b.faintMessages();}
 if(mode==='silent_expiry') {b.fieldEvent('Residual');b.turn++;b.add('turn',b.turn);}
 else b.makeChoices(mode==='failed_recast'?'move 2':'move 1','move 1');
 snap();
 b.destroy();return {mode,rows};
}
process.stdout.write(JSON.stringify(['switch','immune','failed_recast','silent_expiry'].map(run)));
