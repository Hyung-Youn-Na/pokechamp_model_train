/* EP201 priority 1. Synthetic Gen9 singles controlled engine scenarios.
 * Pokémon Showdown underlying source is MIT licensed. Abilities/items are
 * supplied conditions; these combinations are not claims of OU legal sets.
 */
'use strict';
const assert=require('node:assert/strict');
const {Battle,Dex}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
const SOURCE_MODES=['noability','moldbreaker','neutralizinggas'];
function fixture({sourceAbility='noability',targetAbility='noability',item='',types=['Normal'],chipped=false,magicRoom=false}={}){
 const b=new Battle({formatid:'gen9customgame',seed:[2026,10,21,201]});
 for(const side of ['p1','p2'])b.setPlayer(side,{name:side,team:[{species:'Mew',level:100,nature:'Hardy',
  ability:side==='p1'?sourceAbility:targetAbility,item:side==='p2'?item:'',
  evs:{hp:0,atk:0,def:0,spa:0,spd:0,spe:0},ivs:{hp:31,atk:31,def:31,spa:31,spd:31,spe:31},
  moves:['tackle','gastroacid']}]});
 const source=b.p1.active[0],target=b.p2.active[0];target.types=types.slice();
 if(chipped)target.hp-=100;
 if(magicRoom)b.field.addPseudoWeather('magicroom',source);
 b.randomizer=x=>x;
 return {b,source,target};
}
function attack(ctx,{type='Rock',damage=null,hits=1}={}){
 const {b,source}=ctx;const move=b.dex.getActiveMove('tackle');
 move.type=type;move.category='Special';move.basePower=60;move.accuracy=true;move.alwaysHit=true;move.willCrit=false;
 if(damage!==null)move.damage=damage;
 if(hits>1)move.multihit=hits;
 b.actions.runMove(move,source,1);
 return move;
}
function rows(){
 const result=[];
 function add(id,rule_id,state,question,options,expected,observed,source,evidence={}){
  assert.deepEqual(observed,expected,id);assert(options.includes(expected));assert.equal(new Set(options).size,options.length);
  result.push({id:'p1-'+id,priority:1,rule_id,state:{generation:9,scenario:'Controlled synthetic singles; not a legal species/set assertion',...state},
   question,options,answer:expected,evidence:{source,expected,observed,...evidence}});
 }
 const items=[{id:'none',item:'',magicRoom:false},{id:'shield',item:'abilityshield',magicRoom:false},
  {id:'shield_magicroom',item:'abilityshield',magicRoom:true}];
 const blocks={levitate:'Ground',waterabsorb:'Water',dryskin:'Water',stormdrain:'Water',voltabsorb:'Electric',
  lightningrod:'Electric',motordrive:'Electric',sapsipper:'Grass',flashfire:'Fire',eartheater:'Ground',wellbakedbody:'Fire'};
 for(const [ability,blockedType]of Object.entries(blocks))for(const type of [blockedType,'Rock'])
 for(const sourceAbility of SOURCE_MODES)for(const item of items)for(const chipped of [false,true]){
  const ctx=fixture({sourceAbility,targetAbility:ability,...item,chipped});
  try{
   const before=ctx.target.hp;attack(ctx,{type});const after=ctx.target.hp;
   const shieldActive=item.id==='shield';
   const abilityWorks=sourceAbility==='noability'||shieldActive;
   const expected=type===blockedType&&abilityWorks?'No':'Yes';
   const observed=after<before?'Yes':'No';
   add(`immunity-${ability}-${type}-${sourceAbility}-${item.id}-${chipped}`,'p1_attack_immunity',
    {attacker_ability:dex.abilities.get(sourceAbility).name,defender_ability:dex.abilities.get(ability).name,
     defender_types:['Normal'],defender_item:item.item?dex.items.get(item.item).name:'None',magic_room:item.magicRoom,
     defender_hp_before:before,defender_max_hp:ctx.target.maxhp,attack:{type,category:'Special',base_power:60,hits:1},
     assumptions:'Attack reaches the target; accuracy succeeds; noncritical. No Protect/Substitute/status/Tera/weather/terrain or other effects. No type immunity for these Normal targets. Magic Room, when stated, suppresses held-item effects.'},
    'Does this attack deal direct HP damage to the defender?', ['Yes','No'],expected,observed,
    'data/abilities.ts:immunity/absorber hooks and Mold Breaker/Neutralizing Gas; sim/pokemon.ts:runImmunity/ignoringAbility; sim/battle.ts:suppressingAbility; data/items.ts:abilityshield',
    {oracle:'Actual Battle.actions.runMove; deterministic noncritical roll',hp_before:before,hp_after:after,
     defender_boosts:{...ctx.target.boosts},public_events:ctx.b.log.filter(l=>/^\|-(damage|heal|immune|boost|activate|block)\|/.test(l))});
  }finally{ctx.b.destroy();}
 }
 // Wonder Guard must still respect intrinsic typing when bypassed.
 for(const type of ['Fire','Water','Normal'])for(const sourceAbility of SOURCE_MODES)for(const item of items){
  const ctx=fixture({sourceAbility,targetAbility:'wonderguard',types:['Bug','Ghost'],...item});
  try{
   const before=ctx.target.hp;attack(ctx,{type});
   const active=sourceAbility==='noability'||item.id==='shield';
   const expected=type!=='Normal'&&(!active||type==='Fire')?'Yes':'No';
   add(`wonderguard-${type}-${sourceAbility}-${item.id}`,'p1_wonder_guard',
    {attacker_ability:dex.abilities.get(sourceAbility).name,defender_ability:'Wonder Guard',defender_types:['Bug','Ghost'],
     defender_item:item.item?'Ability Shield':'None',magic_room:item.magicRoom,attack_type:type,
     assumptions:'Synthetic target has full HP. Direct single-hit special attack with base power60, successful accuracy and no critical hit. No other effects.'},
    'Does this attack deal direct HP damage?', ['Yes','No'],expected,ctx.target.hp<before?'Yes':'No',
    'data/abilities.ts:wonderguard; sim/pokemon.ts:runImmunity; sim/battle.ts:suppressingAbility',
    {hp_before:before,hp_after:ctx.target.hp,oracle:'Actual runMove including type immunity and Wonder Guard'});
  }finally{ctx.b.destroy();}
 }
 const protection=[['noability',''],['noability','focussash'],['sturdy',''],['sturdy','focussash'],['sturdy','abilityshield']];
 for(const [ability,item]of protection)for(const sourceAbility of SOURCE_MODES)for(const full of [false,true])for(const hits of [1,2]){
  const ctx=fixture({sourceAbility,targetAbility:ability,item});
  try{
   if(!full)ctx.target.hp--;
   const before=ctx.target.hp;attack(ctx,{type:'Rock',damage:500,hits});
   const sturdyActive=ability==='sturdy'&&(sourceAbility==='noability'||item==='abilityshield');
   const survives=full&&hits===1&&(item==='focussash'||sturdyActive);
   add(`survival-${ability}-${item||'none'}-${sourceAbility}-${full}-${hits}`,'p1_ko_prevention',
    {attacker_ability:dex.abilities.get(sourceAbility).name,defender_ability:dex.abilities.get(ability).name,
     defender_item:item?dex.items.get(item).name:'None',defender_types:['Normal'],defender_hp_before:before,
     defender_max_hp:ctx.target.maxhp,attack:{type:'Rock',hits,unmodified_direct_damage_per_hit:500},
     assumptions:'A synthetic deterministic move deals the stated fixed direct damage per hit before KO-prevention effects. All stated hits connect unless the target faints; no crit, immunity, recovery, other effects, or item suppression. Multi-hit is one move, not separate turns.'},
    'Does the defender survive the entire attack?', ['Yes','No'],survives?'Yes':'No',ctx.target.hp>0?'Yes':'No',
    'data/abilities.ts:sturdy.onDamage; data/items.ts:focussash.onDamage; sim/battle-actions.ts:runMove/multihit',
    {hp_after:ctx.target.hp,item_after:ctx.target.item,oracle:'Actual runMove; fixed pre-prevention500 damage per hit',
     damage_lines:ctx.b.log.filter(l=>l.startsWith('|-damage|p2'))});
  }finally{ctx.b.destroy();}
 }
 // Gastro Acid is applied through a real move; do not pre-inject its volatile.
 for(const ability of ['levitate','waterabsorb','sturdy','neutralizinggas','comatose'])
 for(const mode of ['gas','gastroacid'])for(const item of items){
  const ctx=fixture({sourceAbility:mode==='gas'?'neutralizinggas':'noability',targetAbility:ability,...item});
  try{
   if(mode==='gastroacid'){
    const move=ctx.b.dex.getActiveMove('gastroacid');move.accuracy=true;move.alwaysHit=true;
    ctx.b.actions.runMove(move,ctx.source,1);
   }
   const unsuppressible=ability==='comatose'||mode==='gas'&&ability==='neutralizinggas';
   const expected=!unsuppressible&&item.id!=='shield';
   const observed=ctx.target.ignoringAbility();
   add(`suppression-${ability}-${mode}-${item.id}`,'p1_ability_suppression',
    {defender_ability:dex.abilities.get(ability).name,defender_item:item.item?'Ability Shield':'None',magic_room:item.magicRoom,
     action:mode==='gas'?'Opponent has active Neutralizing Gas':'Opponent uses Gastro Acid',
     assumptions:'Active target in singles, no transformation or other suppression. Gastro Acid accuracy succeeds and no protection blocks it. Magic Room, if stated, suppresses held items. Test suppression, not ability replacement.'},
    'Is the defender\'s ability suppressed now?', ['Yes','No'],expected?'Yes':'No',observed?'Yes':'No',
    'sim/pokemon.ts:ignoringAbility; data/moves.ts:gastroacid; data/abilities.ts:neutralizinggas; data/items.ts:abilityshield',
    {oracle:'Actual Pokemon.ignoringAbility after live field or runMove',gastroacid_present:!!ctx.target.volatiles.gastroacid,
     current_ability:ctx.target.ability});
  }finally{ctx.b.destroy();}
 }
 // Prevention is not retroactive cure: a newly held Shield stops Gas, but
 // does not remove an already-established Gastro Acid volatile.
 for(const mode of ['gas','gastroacid']){
  const ctx=fixture({sourceAbility:mode==='gas'?'neutralizinggas':'noability',targetAbility:'levitate'});
  try{
   if(mode==='gastroacid'){
    const move=ctx.b.dex.getActiveMove('gastroacid');move.accuracy=true;
    ctx.b.actions.runMove(move,ctx.source,1);
   }
   assert.equal(ctx.target.ignoringAbility(),true);
   assert(ctx.target.setItem('abilityshield'));
   const stillSuppressed=ctx.target.ignoringAbility();assert.equal(stillSuppressed,mode==='gastroacid');
   add(`shield_acquired_after-${mode}`,'p1_shield_prevention_vs_cure',
    {defender_ability:'Levitate',initial_item:'None',initial_suppression:mode==='gas'?'Active opposing Neutralizing Gas':'Gastro Acid successfully applied',
     later_event:'Defender successfully acquires an active Ability Shield',assumptions:'Same active target; Gastro Acid has not been removed. No Magic Room or other effect. The item transfer itself succeeds.'},
    'Is Levitate still suppressed after acquiring Ability Shield?', ['Yes','No'],mode==='gastroacid'?'Yes':'No',stillSuppressed?'Yes':'No',
    'sim/pokemon.ts:ignoringAbility ordering and setItem; data/moves.ts:gastroacid',
    {oracle:'Actual suppression then Pokemon.setItem and ignoringAbility',gastroacid_present:!!ctx.target.volatiles.gastroacid});
  }finally{ctx.b.destroy();}
 }
 // Mold Breaker ignores a breakable ability for its move, rather than erasing it.
 for(const shield of [false,true]){
  const ctx=fixture({sourceAbility:'moldbreaker',targetAbility:'levitate',item:shield?'abilityshield':''});
  try{
   attack(ctx,{type:'Ground'});ctx.b.clearActiveMove();
   assert.equal(ctx.target.ability,'levitate');assert.equal(ctx.target.ignoringAbility(),false);
   add(`mold_persistence-${shield}`,'p1_mold_breaker_persistence',
    {attacker_ability:'Mold Breaker',defender_ability:'Levitate',defender_item:shield?'Ability Shield':'None',
     event:'After the attacker completes a Ground-type move',assumptions:'Defender survives the move and remains active. No Neutralizing Gas, Gastro Acid, or other ability-changing effect.'},
    'Is Levitate still present and usable against a later ordinary attacker?', ['Yes','No'],'Yes','Yes',
    'sim/battle.ts:suppressingAbility/clearActiveMove; sim/pokemon.ts:ignoringAbility',
    {ability:ctx.target.ability,globally_suppressed:ctx.target.ignoringAbility()});
  }finally{ctx.b.destroy();}
 }
 assert.equal(new Set(result.map(r=>r.id)).size,result.length);return result;
}
module.exports={rows,fixture,attack};
if(require.main===module){const r=rows();console.log(JSON.stringify({passed:true,count:r.length,rules:[...new Set(r.map(x=>x.rule_id))]}));}
