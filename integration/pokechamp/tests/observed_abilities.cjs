'use strict';
const {Battle}=require('../../../pokemon-showdown/dist/sim');
const {Format}=require('../../../pokemon-showdown/dist/sim/dex-formats');
const stats=['hp','atk','def','spa','spd','spe'];
function run(kind, enabled, factor) {
 const b=new Battle({format:new Format({name:'Observed ability fixture',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
 const quark=kind==='quark', move=quark?'Moonblast':'Kowtow Cleave';
 const options={level:100,ability:quark?'Quark Drive':'Supreme Overlord',item:quark&&enabled?'Booster Energy':'',nature:quark?'Timid':'Hardy',ivs:Object.fromEntries(stats.map(k=>[k,31])),evs:Object.fromEntries(stats.map(k=>[k,quark&&['spa','spe'].includes(k)?252:0])),boosts:{},status:''};
 const set={species:quark?'Iron Valiant':'Kingambit',...options,moves:[move]};
 const target={species:'Mew',ability:'Synchronize',nature:'Hardy',moves:['Splash']};
 b.setPlayer('p1',{name:'one',team:[set]});b.setPlayer('p2',{name:'two',team:[target]});
 const a=b.p1.active[0],d=b.p2.active[0];
 if(!quark&&enabled){a.side.totalFainted=2;b.singleEvent('Start',a.getAbility(),a.abilityState,a);}
 b.randomizer=n=>Math.floor(n*factor/100);
 const m=b.dex.getActiveMove(move);m.accuracy=true;m.willCrit=false;
 const before=d.hp, speed=a.getActionSpeed();b.actions.runMove(m,a,1);
 const result={kind,enabled,factor,damage:before-d.hp,speed,protocol:b.log.join('\n'),
  scenario:{scenario_id:`${kind}-${enabled}`,attacker:{name:set.species,options:{...options,item:'',curHP:a.maxhp,...(quark&&enabled?{abilityOn:true,boostedStat:'spe'}:{}),...(!quark&&enabled?{alliesFainted:2}:{})}},defender:{name:'Mew',options:{level:100,ability:'Synchronize',item:'',nature:'Hardy',ivs:Object.fromEntries(stats.map(k=>[k,31])),evs:Object.fromEntries(stats.map(k=>[k,0])),boosts:{},status:'',curHP:d.maxhp}},move,field:{}}};
 b.destroy();return result;
}
process.stdout.write(JSON.stringify(['quark','overlord'].flatMap(k=>[false,true].flatMap(e=>Array.from({length:16},(_,i)=>run(k,e,i+85))))));
