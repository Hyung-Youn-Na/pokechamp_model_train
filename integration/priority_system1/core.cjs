'use strict';
const assert=require('node:assert/strict');
const {Dex,Battle,Pokemon}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
const moves=dex.moves.all().filter(m=>m.exists&&m.gen<=9&&!m.isNonstandard&&!m.isZ&&!m.isMax).sort((a,b)=>a.id.localeCompare(b.id));
const brackets=[...new Set(moves.map(m=>m.priority))].sort((a,b)=>a-b);
assert.equal(moves.length,685);assert.deepEqual(brackets,[-7,-6,-5,-4,-3,0,1,2,3,4,5]);
const speeds=[50,100,200,400];
const choices=['A acts first','B acts first','Speed tie: either may act first'];
function actionSpeed(speed,trick){
 return Pokemon.prototype.getActionSpeed.call({getStat:()=>speed,
  battle:{ruleTable:{has:()=>false},field:{getPseudoWeather:()=>trick},trunc:(v,n)=>Math.trunc(v)%(2**n)}});
}
function compare(pa,pb,sa,sb,trick,fa=0,fb=0){
 const a={priority:pa+fa,speed:actionSpeed(sa,trick)},b={priority:pb+fb,speed:actionSpeed(sb,trick)};
 const cmp=Battle.prototype.comparePriority(a,b);
 const reverse=Battle.prototype.comparePriority(b,a);assert.equal(Math.sign(cmp),-Math.sign(reverse)||0);
 return {answer:cmp<0?choices[0]:cmp>0?choices[1]:choices[2],engine_actions:{a,b},comparator:cmp};
}
function expected(pa,pb,sa,sb,trick,fa=0,fb=0){
 if(pa!==pb)return pa>pb?choices[0]:choices[1];
 if(fa!==fb)return fa>fb?choices[0]:choices[1];
 if(sa===sb)return choices[2];
 return (trick?sa<sb:sa>sb)?choices[0]:choices[1];
}
function core(){
 const rows=[];
 function add(id,rule,state,question,options,answer,evidence){
  assert(options.includes(answer));assert.equal(new Set(options).size,options.length);
  rows.push({id,rule_id:rule,state,question,options,answer,evidence});
 }
 const anchors={protect:4,trickroom:-7,extremespeed:2,quickattack:1,fakeout:3,helpinghand:5,
   dragontail:-6,counter:-5,avalanche:-4,focuspunch:-3,tackle:0};
 for(const [id,p] of Object.entries(anchors))assert.equal(dex.moves.get(id).priority,p,id);
 for(const move of moves){
  add('base-'+move.id,'move_base_priority',{generation:9,move:move.name,
    assumptions:'Base move priority only; no ability, terrain or other priority changes. This is a Gen9 standard-move reference, not a claim about species learnsets or OU legality.'},
    'What is this move\'s base integer priority?',brackets.map(String),String(move.priority),
    {source:'data/moves.ts:'+move.id+'.priority (default 0)',observed:move.priority,oracle:'Pinned Gen9 Dex move record'});
  for(const [ability,full] of [['prankster',true],['galewings',true],['galewings',false],['triage',true]]){
   const m=dex.getActiveMove(move.id);const p={hp:full?100:50,maxhp:100};
   const result=dex.abilities.get(ability).onModifyPriority.call({},move.priority,p,null,m);
   const observed=result===undefined?move.priority:result;
   const delta=ability==='prankster'&&move.category==='Status'?1:
     ability==='galewings'&&full&&move.type==='Flying'?1:ability==='triage'&&move.flags.heal?3:0;
   assert.equal(observed,move.priority+delta);
   const options=[...new Set([move.priority-1,move.priority,move.priority+1,move.priority+3].map(String))];
   add(`ability-${ability}-${full}-${move.id}`,'ability_integer_priority',
    {move:move.name,base_priority:move.priority,move_type_at_priority_check:move.type,category:move.category,
     healing_flag:!!move.flags.heal,ability:dex.abilities.get(ability).name,current_hp:p.hp,max_hp:p.maxhp,
     assumptions:'Ability active; isolate its integer-priority effect. No terrain or other modifier. Synthetic ability/move pairing; not a learnset claim.'},
    'What is the integer priority after this ability is applied?',options,String(observed),
    {source:'data/abilities.ts:'+ability+'.onModifyPriority',expected:move.priority+delta,observed});
  }
 }
 for(const pa of brackets)for(const pb of brackets)for(const sa of speeds)for(const sb of speeds)for(const trick of [false,true]){
  const result=compare(pa,pb,sa,sb,trick);assert.equal(result.answer,expected(pa,pb,sa,sb,trick));
  add(`pair-${pa}-${pb}-${sa}-${sb}-${trick}`,'priority_speed_trickroom',
   {A:{integer_priority:pa,effective_speed:sa},B:{integer_priority:pb,effective_speed:sb},trick_room_active:trick,
    assumptions:'Two pending move actions in the same action phase. No first/last activation or queue rearrangement. Effective Speed already includes all stat modifiers. Both actions can execute; this asks order, not accuracy or damage.'},
   'Which action is ordered first?',choices,result.answer,{source:'sim/battle.ts:comparePriority; sim/pokemon.ts:getActionSpeed',...result});
 }
 // Only within-bracket effects: integer priorities are intentionally equal here.
 const ranks=[-0.1,0,0.1],labels={'-0.1':'Move-late effect active (e.g. Stall)','0':'No first/last effect','0.1':'Move-first activation active (e.g. Quick Claw)'};
 for(const p of brackets)for(const sa of speeds)for(const sb of speeds)for(const trick of [false,true])for(const fa of ranks)for(const fb of ranks){
  if(fa===0&&fb===0)continue;
  const result=compare(p,p,sa,sb,trick,fa,fb);assert.equal(result.answer,expected(p,p,sa,sb,trick,fa,fb));
  add(`within-${p}-${sa}-${sb}-${trick}-${fa}-${fb}`,'within_priority_first_last',
    {A:{integer_priority:p,effective_speed:sa,order_effect:labels[fa]},B:{integer_priority:p,effective_speed:sb,order_effect:labels[fb]},
     trick_room_active:trick,assumptions:'Isolated move actions; the stated first/last effects already apply. No other priority or queue changes. Effects alter order within the integer bracket, not the integer move priority.'},
    'Which action is ordered first?',choices,result.answer,{source:'sim/battle.ts:comparePriority; sim/pokemon.ts:getActionSpeed',...result});
 }
 assert.equal(rows.filter(r=>r.rule_id==='priority_speed_trickroom').length,3872);
 assert.equal(rows.filter(r=>r.rule_id==='within_priority_first_last').length,2816);
 return rows;
}
module.exports={core};
if(require.main===module)console.log(JSON.stringify({count:core().length,brackets,moves:moves.length}));
