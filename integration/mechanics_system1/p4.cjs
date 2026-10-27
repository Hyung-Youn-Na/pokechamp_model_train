'use strict';
const assert=require('node:assert/strict');
const {Battle,Dex}=require('../../pokemon-showdown/dist/sim');
const {makeBattle,init}=require('./p5.cjs');
const dex=Dex.forFormat('gen9ou');
const OPTIONS=['Certain: event occurs','Certain: event does not occur','Chance-dependent under every allowed hidden condition','Insufficient information: allowed hidden conditions give different certainty classes'];
const BASE='Synthetic Gen9 singles. The listed possible values exhaust all uncertainty for this exercise; no other unknown mechanics, Tera, effects or unlisted alternatives. A singleton is publicly known. Do not guess the actual hidden value. Determine certainty class, not probability or the sampled future outcome.';
function classify(outcomes){const s=new Set(outcomes);return s.size===2?2:s.has(true)?0:1;}
function rows(){
 const out=[];
 function add(id,rule,state,event,worlds){
  assert(worlds.length);for(const w of worlds)assert.deepEqual(w.observed,w.expected,id);
  const classes=worlds.map(w=>classify(w.observed));const target=new Set(classes).size===1?classes[0]:3;
  out.push({id:'p4-'+id,priority:4,rule_id:rule,state:{generation:9,...state,assumptions:BASE+' '+state.assumptions},
   question:`Using only the given public constraints, classify this event: ${event}`,options:OPTIONS,answer:OPTIONS[target],
   evidence:{source:'Pinned actual Battle/actions/Pokemon methods; complete Cartesian enumeration of the stated hidden domains',worlds,certainty_classes:classes,expected:target,observed:target}});
 }
 let n=0;
 for(const abilities of [['noability'],['levitate'],['noability','levitate']])for(const items of [[''],['airballoon'],['','airballoon']])for(const mold of [false,true])for(const gravity of [false,true]){
  const worlds=[];
  for(const ability of abilities)for(const item of items){
   const b=makeBattle();try{
    const a=b.p1.active[0],d=b.p2.active[0];init(a,160,160,200,mold?'moldbreaker':'noability');init(d,160,160,100,ability,item);
    if(gravity)assert(b.field.addPseudoWeather('gravity',a));
    const before=d.hp;b.actions.runMove('earthquake',a,1);
    const observed=d.hp<before,expected=gravity||((ability!=='levitate'||mold)&&item!=='airballoon');
    worlds.push({hidden:{ability,item},expected:[expected],observed:[observed],before,after:d.hp});
   }finally{b.destroy();}
  }
  add('ground-'+n++,'information_ground_immunity',{target_type:'Normal',target_possible_abilities:abilities,target_possible_items:items.map(x=>x||'None'),
   attacker_ability:mold?'Mold Breaker':'No Ability',move:'Earthquake',gravity,assumptions:'Accuracy succeeds. No Protect/Substitute; target has positive HP. Items and abilities active except the stated interactions.'},
   'Earthquake directly reduces the target\'s HP',worlds);
 }
 for(const abilities of [['noability'],['sturdy'],['noability','sturdy']])for(const items of [[''],['focussash'],['','focussash']])for(const max of [100,160])for(const hp of [1,80,99,100])for(const type of ['Normal','Ghost'])for(const mold of [false,true]){
  const worlds=[];
  for(const ability of abilities)for(const item of items){
   const b=makeBattle();try{
    const a=b.p1.active[0],d=b.p2.active[0];init(a,160,160,200,mold?'moldbreaker':'noability');init(d,hp,max,100,ability,item);d.types=[type];
    b.actions.runMove('seismictoss',a,1);
    const prevented=hp===max&&((ability==='sturdy'&&!mold)||item==='focussash');
    const expected=type!=='Ghost'&&hp<=100&&!prevented;
    worlds.push({hidden:{ability,item},expected:[expected],observed:[d.hp===0],after_hp:d.hp});
   }finally{b.destroy();}
  }
  add('ko-'+n++,'information_ko_prevention',{target_type:type,target_hp:hp,target_max_hp:max,target_possible_abilities:abilities,target_possible_items:items.map(x=>x||'None'),
   attacker_level:100,attacker_ability:mold?'Mold Breaker':'No Ability',move:'Seismic Toss',assumptions:'Accuracy succeeds. One direct hit, no Protect/Substitute, no residual or healing; items active. Question ends immediately after the attack.'},
   'the target is knocked out directly by this attack',worlds);
 }
 for(const speeds of [[100],[150],[200],[100,200],[100,150],[150,200]])for(const trick of [false,true])for(const pa of [0,1])for(const pb of [0,1]){
  const worlds=[];
  for(const speed of speeds){const b=makeBattle();try{
   const a=b.p1.active[0],d=b.p2.active[0];init(a,160,160,150);init(d,160,160,speed);
   if(trick)b.field.addPseudoWeather('trickroom',a);
   const cmp=Battle.prototype.comparePriority({priority:pa,speed:a.getActionSpeed()},{priority:pb,speed:d.getActionSpeed()});
   const observed=cmp===0?[false,true]:[cmp<0];
   const expected=pa!==pb?[pa>pb]:speed===150?[false,true]:[trick?150<speed:150>speed];
   worlds.push({hidden:{speed},expected,observed,comparator:cmp});
  }finally{b.destroy();}}
  add('speed-'+n++,'information_action_order',{A_effective_speed:150,B_possible_effective_speeds:speeds,A_move_priority:pa,B_move_priority:pb,trick_room:trick,
   assumptions:'Both actions are selected ordinary moves. No forced order, fractional priority, Quick Claw or action interruption. Tied effective speeds at equal priority use the ordinary random tie break.'},
   'A\'s move is ordered before B\'s move',worlds);
 }
 // Unknown attack stat versus known stochastic roll: every ordinary damage roll is enumerated.
 for(const attacks of [[100],[200],[100,200]])for(const hp of [1,29,30,35,36,58,59,69,70]){
  const worlds=[];
  for(const atk of attacks){const b=makeBattle();try{
   const a=b.p1.active[0],d=b.p2.active[0];init(a,160,160,200);init(d,hp,160,100);a.types=['Water'];d.types=['Normal'];a.storedStats.atk=atk;d.storedStats.def=100;
   const damages=[];const expectedDamages=[];
   for(let roll=85;roll<=100;roll++){
    b.randomizer=base=>{const old=b.random;b.random=()=>100-roll;try{return Battle.prototype.randomizer.call(b,base);}finally{b.random=old;}};
    const move=dex.getActiveMove('tackle');move.willCrit=false;
    const damage=b.actions.getDamage(a,d,move,true);assert.equal(d.getMoveHitData(move).crit,false);
    const expected=Math.floor((Math.floor(Math.floor(42*40*atk/100)/50)+2)*roll/100);
    assert.equal(damage,expected,`damage ${atk}/${roll}`);damages.push(damage);expectedDamages.push(expected);
   }
   worlds.push({hidden:{attack_stat:atk},expected:expectedDamages.map(x=>x>=hp),observed:damages.map(x=>x>=hp),damage_rolls:damages});
  }finally{b.destroy();}}
  add('stats-'+n++,'information_stats_and_randomness',{attacker_level:100,attacker_type:'Water',attacker_possible_unboosted_attack_stats:attacks,
   target_type:'Normal',target_hp:hp,target_max_hp:160,target_defense_stat:100,move:'Tackle',
   assumptions:'No abilities/items/status/stat stages. Ordinary 40-power physical Tackle; successful accuracy, no critical hit, one hit. All 16 standard damage rolls are possible. No STAB, resistance, weakness, protection, substitute, weather, terrain or other modifiers. The attack stat is the only possibly hidden fixed value.'},
   'this attack directly knocks out the target',worlds);
 }
 return out;
}
module.exports={rows};
if(require.main===module){const r=rows();console.log(JSON.stringify({passed:true,count:r.length,rules:[...new Set(r.map(x=>x.rule_id))],answers:Object.fromEntries(OPTIONS.map(x=>[x,r.filter(y=>y.answer===x).length]))}));}
