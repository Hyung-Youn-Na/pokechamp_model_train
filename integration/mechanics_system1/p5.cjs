'use strict';
const assert=require('node:assert/strict');
const {Battle}=require('../../pokemon-showdown/dist/sim');
const profiles=[
 {item:'',ability:'noability',status:'',weather:''},
 {item:'focussash',ability:'noability',status:'',weather:''},
 {item:'',ability:'sturdy',status:'',weather:''},
 {item:'focussash',ability:'noability',status:'psn',weather:''},
 {item:'',ability:'sturdy',status:'brn',weather:''},
 {item:'focussash',ability:'noability',status:'',weather:'sandstorm'},
 {item:'leftovers',ability:'sturdy',status:'psn',weather:''},
 {item:'leftovers',ability:'sturdy',status:'brn',weather:'sandstorm'},
 {item:'leftovers',ability:'noability',status:'psn',weather:'sandstorm'},
 {item:'leftovers',ability:'sturdy',status:'',weather:''},
];
function makeBattle(){
 const b=new Battle({formatid:'gen9customgame',seed:[2026,10,21,201]});
 for(const side of ['p1','p2'])b.setPlayer(side,{name:side,team:[
  {species:'Mew',ability:'No Ability',level:100,moves:['Seismic Toss','Protect','Splash','Earthquake']},
  {species:'Mew',ability:'No Ability',level:100,moves:['Splash']},
 ]});
 return b;
}
function init(p,hp,max,speed,ability='noability',item=''){
 p.types=['Normal'];p.hp=hp;p.maxhp=max;p.baseMaxhp=max;
 p.storedStats.spe=speed;p.baseStoredStats.spe=speed;
 p.ability=ability;p.abilityState={id:ability,target:p};
 p.item=item;p.itemState={id:item,target:p};
}
function predict(c){
 let a=c.ahp,d=c.dhp,item=c.profile.item;
 const afirst=c.trickroom?c.aspeed<150:c.aspeed>150;
 const attackD=()=>{if(a<=0||d<=0||c.defmove==='protect')return;
  if(d===100&&(c.profile.ability==='sturdy'||item==='focussash')){d=1;if(c.profile.ability!=='sturdy')item='';}
  else d=Math.max(0,d-100);
 };
 const attackA=()=>{if(a>0&&d>0&&c.defmove==='seismictoss')a=Math.max(0,a-100);};
 if(afirst){attackD();attackA();}else{attackA();attackD();}
 // Weather precedes item healing, which precedes poison/burn. Dead actives do not heal.
 if(c.profile.weather){a=Math.max(0,a-10);d=Math.max(0,d-6);}
 if(d>0&&item==='leftovers')d=Math.min(100,d+6);
 if(d>0&&c.profile.status)d=Math.max(0,d-(c.profile.status==='psn'?12:6));
 return {a,d,item,first:c.defmove==='protect'?'B':afirst?'A':'B'};
}
function simulate(c){
 const b=makeBattle();try{
  const a=b.p1.active[0],d=b.p2.active[0];init(a,c.ahp,160,c.aspeed);init(d,c.dhp,100,150,c.profile.ability,c.profile.item);
  if(c.profile.status)assert(d.trySetStatus(c.profile.status,d));
  if(c.profile.weather)assert(b.field.setWeather(c.profile.weather,a));
  if(c.trickroom)assert(b.field.addPseudoWeather('trickroom',a));
  const offset=b.log.length;b.makeChoices('move seismictoss',`move ${c.defmove}`);
  const log=b.log.slice(offset);const first=log.find(x=>x.startsWith('|move|'));
  assert(first,'turn must have a move');
  return {a:a.hp,d:d.hp,item:d.item,first:first.startsWith('|move|p1a')?'A':'B',log};
 }finally{b.destroy();}
}
function hpLabel(a,d){return `A: ${a} HP; B: ${d} HP`;}
function rows(){
 const out=[];
 for(const ahp of [80,160])for(const aspeed of [100,200])for(const trickroom of [false,true])for(const dhp of [1,80,100])for(const defmove of ['splash','seismictoss','protect'])for(let pi=0;pi<profiles.length;pi++){
  const c={ahp,aspeed,trickroom,dhp,defmove,profile:profiles[pi]},expected=predict(c),actual=simulate(c);
  const id=`p5-${ahp}-${aspeed}-${trickroom}-${dhp}-${defmove}-${pi}`;
  assert.deepEqual({a:actual.a,d:actual.d,item:actual.item,first:actual.first},expected,id);
  const answer=hpLabel(actual.a,actual.d);
  const options=[...new Set([answer,hpLabel(0,0),hpLabel(ahp,dhp),hpLabel(expected.a,Math.min(100,expected.d+1)),hpLabel(Math.min(160,expected.a+1),expected.d)])].slice(0,4);
  out.push({id,priority:5,rule_id:'turn_order_success_ko_residual',state:{generation:9,battle:'Singles, synthetic controlled state',
   A:{level:100,type:'Normal',hp:ahp,max_hp:160,base_max_hp:160,effective_speed:aspeed,ability:'No Ability',item:'None',status:'None',chosen_move:'Seismic Toss'},
   B:{level:100,type:'Normal',hp:dhp,max_hp:100,base_max_hp:100,effective_speed:150,ability:c.profile.ability,item:c.profile.item||'None',status:c.profile.status||'None',chosen_move:defmove},
   trick_room:trickroom,weather:c.profile.weather||'None',
   assumptions:'Both sides have healthy reserves. No switching this turn, no Tera, hazards, terrain, other effects or speed ties. Moves have PP and ordinary accuracy succeeds; both Seismic Toss moves deal their fixed level damage when they hit. Protect is its first consecutive use and succeeds. All stated abilities/items are active. Weather and Trick Room, if present, last through this turn. B status already exists. Synthetic HP and typing are deliberate, not legal Mew stats.'},
   question:'After both selected actions and this turn\'s residual effects, what are the HP values of the two original active Pokemon?',options,answer,
   evidence:{source:'sim/battle.ts:makeChoices/turn resolution; data/moves.ts:seismictoss/protect; data/items.ts:focussash/leftovers; data/abilities.ts:sturdy; data/conditions.ts',expected,observed:actual,
    oracle:'Full actual one-turn Battle.makeChoices; independent ordered arithmetic, no damage-roll override'}});
 }
 return out;
}
module.exports={rows,makeBattle,init};
if(require.main===module){const r=rows();console.log(JSON.stringify({passed:true,count:r.length,rules:[...new Set(r.map(x=>x.rule_id))]}));}
