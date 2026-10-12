'use strict';
// Private simulator state is emitted only as a test oracle, never as B input.
const {Battle, extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
function run(mode, seed = [1, 2, 3, 4]) {
 const b = new Battle({format: new Format({name:'Protect lifecycle', mod:'gen9', gameType:'singles', ruleset:[]}), seed});
 b.setPlayer('p1', {name:'shield', team:[
  {species:'Mew', name:'Shield', moves:['Protect','Splash'], ability:'Synchronize'},
  {species:'Chansey', name:'Bench', moves:['Splash'], ability:'Natural Cure'}]});
 b.setPlayer('p2', {name:'attack', team:[
  {species:'Mew', name:'Attack', moves:['Tackle','Chilly Reception','Feint','Splash'], ability:'Synchronize'},
  {species:'Chansey', name:'Other', moves:['Splash'], ability:'Natural Cure'}]});
 const rows=[];
 function snap(phase) {
  rows.push({phase, public_protocol:extractChannelMessages(b.log.join('\n'), [1])[1].join('\n'),
   oracle:b.sides.flatMap(side=>side.pokemon.map(p=>({ident:side.id+': '+p.name,
    protect:!!p.volatiles.protect, hp:p.hp, active:p.isActive, fainted:p.fainted}))),
   request_state:b.requestState});
 }
 const original=b.runAction;
 b.runAction=function(action) {const result=original.call(this, action); snap(action.choice); return result;};
 if (mode==='consecutive') {
  for(let i=0;i<7;i++) b.makeChoices('move 1','move 1');
 } else if(mode==='no_block') {
  b.makeChoices('move 1','move 4');
 } else if(mode==='feint') {
  b.makeChoices('move 1','move 3');
 } else if(['pivot','switch','faint'].includes(mode)) {
  b.makeChoices('move 1','move 2'); snap('midturn_request');
  if(mode==='switch') {b.actions.switchIn(b.p1.pokemon[1], 0);snap('forced_switch');}
  if(mode==='faint') {b.p1.active[0].faint();b.faintMessages();snap('faint');}
  if(mode==='pivot') {b.makeChoices('', 'switch 2');snap('after_pivot');}
 } else {
  b.makeChoices('move 1','move 1');snap('next_turn');
  b.makeChoices('move 2','move 1');snap('unprotected_attack');
 }
 b.destroy(); return {mode, seed, rows};
}
process.stdout.write(JSON.stringify(['success','no_block','consecutive','feint','pivot','switch','faint'].map(x=>run(x))));
