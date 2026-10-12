'use strict';
// Simulator internals below are test answers only; actor input is a separate object.
const {Battle, Teams} = require('../../../pokemon-showdown/dist/sim');
const {extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const cases = [
 {name:'one_side', sides:[{stealthrock:1},{}]},
 {name:'layers', sides:[{spikes:1,toxicspikes:2},{spikes:3,toxicspikes:1,stickyweb:1}]},
 {name:'screens', sides:[{reflect:1,tailwind:1},{lightscreen:1}]},
 {name:'unsupported', sides:[{safeguard:1,mist:1},{}]},
 {name:'empty', sides:[{},{}]},
 {name:'repeat', sides:[{stealthrock:1,spikes:2},{toxicspikes:2}]},
 {name:'removal', sides:[{stealthrock:1,spikes:2,stickyweb:1},{}]},
];
const out=[];
for(const c of cases) {
 const b=new Battle({format:new Format({name:'Court Change oracle',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
 const teams=[0,1].map(i=>[
  {name:i?'Other':'Court',species:'Mew',ability:'Synchronize',moves:['Court Change','Splash','Rapid Spin','Tackle'],nature:'Hardy'},
  {name:i?'OtherBench':'Bench',species:'Blissey',ability:'Natural Cure',moves:['Splash','Tackle'],nature:'Hardy'},
 ]);
 b.setPlayer('p1',{name:'observer1',team:teams[0]});
 b.setPlayer('p2',{name:'observer2',team:teams[1]});
 // The independent simulator installs the conditions and emits their actual rows.
 for(let i=0;i<2;i++) for(const [id,layers] of Object.entries(c.sides[i])) {
  for(let n=0;n<layers;n++) b.sides[i].addSideCondition(id,b.sides[1-i].active[0],b.dex.moves.get(id));
 }
 const snapshots=[];
 function snap(phase) {
  const sides=b.sides.map(side=>Object.fromEntries(Object.entries(side.sideConditions).map(([id,s])=>[id,{layers:s.layers||1,duration:s.duration??null}])));
  const oracle=b.sides.map(side=>({side:side.id,active:side.active[0].name,hp:side.active[0].hp,maxhp:side.active[0].maxhp,status:side.active[0].status,speed:side.active[0].getActionSpeed(),boosts:{...side.active[0].boosts},volatiles:Object.keys(side.active[0].volatiles)}));
  const damage=b.sides.map(side=>Array.from({length:16},(_,n)=>{
   b.randomizer=v=>Math.floor(v*(85+n)/100);
   const move=b.dex.getActiveMove('Tackle');move.willCrit=false;
   return b.actions.getDamage(side.active[0],side.foe.active[0],move);
  }));
  const actors=b.sides.map((side,i)=>({protocol:extractChannelMessages(b.log.join('\n'),[i+1])[i+1].join('\n'),request:{...side.activeRequest,rqid:snapshots.length+1},own_team:Teams.export(teams[i])}));
  snapshots.push({phase,sides,oracle,damage,actors});
 }
 snap('installed');
 b.makeChoices('move Court Change','move Splash');snap('swapped');
 if(c.name==='repeat') {b.makeChoices('move Court Change','move Splash');snap('swapped_twice');}
 if(c.name==='screens') {
  for(let n=0;n<5;n++) {b.makeChoices('move Splash','move Splash');snap('duration_'+n);}
 } else if(c.name==='removal') {
  b.makeChoices('move Splash','move Rapid Spin');snap('removed');
 } else {
  // Capture entry before residual poison damage so the calculator's boundary matches.
  const run=b.runAction;
  b.runAction=function(action) {const r=run.call(this,action);if(action.choice==='runSwitch') {for(const side of b.sides) if(side.active[0].name.endsWith('Bench') && !snapshots.some(s=>s.phase==='entry_'+side.id)) snap('entry_'+side.id);}return r;};
  b.makeChoices('switch 2','switch 2');snap('after_switch_turn');
 }
 out.push({name:c.name,snapshots});b.destroy();
}
process.stdout.write(JSON.stringify(out));
