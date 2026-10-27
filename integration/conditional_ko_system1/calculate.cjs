/* EP199 controlled damage profiles. Underlying Pokémon Showdown is MIT licensed.
 * No replay outcomes, hidden sets, public percentages, or original HP are read.
 * Direct getDamage omits hit accuracy and secondary/after-hit effects by design.
 */
'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const {Dex,Battle}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
const STAT_KEYS=['hp','atk','def','spa','spd','spe'];
function callbacks(value,path='',seen=new Set()){
 if(!value||typeof value!=='object'||seen.has(value))return [];
 seen.add(value);const result=[];
 for(const [k,v]of Object.entries(value)){
  const name=path?`${path}.${k}`:k;
  if(typeof v==='function')result.push(name);
  else if(v&&typeof v==='object')result.push(...callbacks(v,name,seen));
 }
 return result;
}
function eligibility(input){
 const attacker=dex.species.get(input.attacker),defender=dex.species.get(input.defender),move=dex.moves.get(input.move);
 for(const [role,s]of [['attacker',attacker],['defender',defender]]){
  if(!s.exists||s.gen>9||s.isNonstandard)return {reason:`${role}_unknown_or_nonstandard`};
  if(s.battleOnly||s.requiredItem||s.requiredItems||s.requiredAbility)return {reason:`${role}_conditional_form`};
 }
 if(!move.exists||move.gen>9||move.isNonstandard||move.isZ||move.isMax)return {reason:'move_unknown_or_nonstandard'};
 if(!['Physical','Special'].includes(move.category)||!Number.isInteger(move.basePower)||move.basePower<=0)return {reason:'not_fixed_positive_power_damage'};
 if(!['normal','any','allAdjacent','allAdjacentFoes'].includes(move.target))return {reason:'unsupported_move_target'};
 const hooks=callbacks(move);if(hooks.length)return {reason:'move_callback',details:hooks};
 for(const flag of ['damage','multihit','ohko','willCrit','critModifier','overrideOffensiveStat','overrideOffensivePokemon',
  'overrideDefensiveStat','overrideDefensivePokemon','ignoreNegativeOffensive','ignorePositiveDefensive','ignoreOffensive',
  'ignoreDefensive','ignoreAbility','forceSTAB','selfdestruct','recoil','struggleRecoil','mindBlownRecoil']){
  if(move[flag])return {reason:'unsupported_move_property',details:flag};
 }
 if(move.flags.charge||move.flags.futuremove)return {reason:'charge_or_future_move'};
 return {attacker,defender,move};
}
function calculate(inputs){
 assert(Array.isArray(inputs));const profiles=[],exclusions=[],seen=new Set();
 for(const input of inputs){
  assert(input&&typeof input.key==='string'&&typeof input.attacker==='string'&&typeof input.defender==='string'&&typeof input.move==='string');
  assert(!seen.has(input.key),'duplicate profile key');seen.add(input.key);
  const check=eligibility(input);
  if(check.reason){exclusions.push({key:input.key,source_profile:input,...check});continue;}
  const {attacker,defender,move}=check;
  const battle=new Battle({formatid:'gen9customgame',seed:[2026,10,21,199]});
  try{
   const set=s=>({species:s.name,name:s.name,level:100,ability:'No Ability',item:'',nature:'Hardy',
    ivs:Object.fromEntries(STAT_KEYS.map(k=>[k,31])),evs:Object.fromEntries(STAT_KEYS.map(k=>[k,0])),moves:[move.id]});
   battle.setPlayer('p1',{name:'Attacker',team:[set(attacker)]});
   battle.setPlayer('p2',{name:'Defender',team:[set(defender)]});
   const a=battle.p1.active[0],d=battle.p2.active[0];
   if(!a||!d||a.species.id!==attacker.id||d.species.id!==defender.id){
    exclusions.push({key:input.key,source_profile:input,reason:'runtime_form_changed',
     actual_attacker:a?.species.name,actual_defender:d?.species.name});continue;
   }
   for(const p of [a,d]){
    assert.equal(p.level,100);assert.equal(p.ability,'noability');assert.equal(p.item,'');assert.equal(p.status,'');
    assert(!p.terastallized);assert.deepEqual(Object.keys(p.volatiles),[]);
    assert(Object.values(p.boosts).every(x=>x===0));
    assert.equal(p.set.nature,'Hardy');
    for(const k of STAT_KEYS){assert.equal(p.set.ivs[k],31);assert.equal(p.set.evs[k],0);}
   }
   assert.equal(battle.field.weather,'');assert.equal(battle.field.terrain,'');
   assert.deepEqual(Object.keys(battle.field.pseudoWeather),[]);
   assert.deepEqual(Object.keys(a.side.sideConditions),[]);assert.deepEqual(Object.keys(d.side.sideConditions),[]);
   const rolls=[];let nativeRandomizerChecks=0;
   for(let roll=85;roll<=100;roll++){
    battle.randomizer=baseDamage=>{
     const expected=Math.floor(baseDamage*roll/100);
     const originalRandom=battle.random;
     battle.random=n=>{assert.equal(n,16);return 100-roll;};
     let native;try{native=Battle.prototype.randomizer.call(battle,baseDamage);}finally{battle.random=originalRandom;}
     assert.equal(native,expected,'randomizer arithmetic mismatch');nativeRandomizerChecks++;
     return expected;
    };
    const active=battle.dex.getActiveMove(move.id);active.willCrit=false;
    const raw=battle.actions.getDamage(a,d,active,true);
    const damage=raw===false?0:raw;
    assert(Number.isInteger(damage)&&Number.isFinite(damage)&&damage>=0,'invalid getDamage result');
    assert.equal(active.willCrit,false);
    if(raw!==false)assert.equal(d.getMoveHitData(active).crit,false,'unexpected critical hit');
    else assert.equal(d.runImmunity(active,false),false,'false result not explained by type immunity');
    if(rolls.length)assert(damage>=rolls[rolls.length-1].damage,'nonmonotone damage rolls');
    rolls.push({roll,damage});
   }
   assert.equal(rolls.length,16);
   const min=rolls[0].damage,max=rolls[15].damage;
   // Independent engine HP application at every admissible class boundary.
   // Reset only HP/faint bookkeeping; no full turn or secondary effect is simulated.
   const boundaryHP=[...new Set([1,d.maxhp,min,min+1,max,max+1].filter(h=>Number.isInteger(h)&&h>=1&&h<=d.maxhp))].sort((x,y)=>x-y);
   const boundaryChecks=[];
   for(const hp of boundaryHP){
    const koRolls=[];
    for(const {roll,damage}of rolls){
     d.hp=hp;d.fainted=false;d.faintQueued=false;battle.faintQueue=[];
     const applied=d.damage(damage,a,battle.dex.getActiveMove(move.id));
     assert.equal(applied,Math.min(damage,hp));assert.equal(d.hp,Math.max(0,hp-damage));
     assert.equal(d.faintQueued,damage>=hp);if(d.hp===0)koRolls.push(roll);
    }
    assert.equal(koRolls.length,rolls.filter(r=>r.damage>=hp).length);
    boundaryChecks.push({target_hp:hp,ko_rolls:koRolls,ko_roll_count:koRolls.length});
   }
   const record=p=>({species:p.species.name,species_id:p.species.id,types:p.getTypes(),level:p.level,max_hp:p.maxhp,
    stats:Object.fromEntries(['atk','def','spa','spd','spe'].map(k=>[k,p.getStat(k,false,false)])),
    nature:p.set.nature,ivs:p.set.ivs,evs:p.set.evs,ability:p.ability,item:p.item});
   profiles.push({key:input.key,source_profile:{...input},attacker:record(a),defender:record(d),
    move:{id:move.id,name:move.name,type:move.type,category:move.category,base_power:move.basePower,target:move.target},
    conditions:{generation:9,format:'gen9customgame',level:100,ivs:31,evs:0,nature:'Hardy',ability:'No Ability',item:'None',
     status:'None',boosts:'All zero',weather:'None',terrain:'None',screens:'None',volatiles:'None',tera:false,
     accuracy:'Condition on successful accuracy check; type immunity still applies',critical_hit:false,hits:1,
     damage_scope:'Direct hit only; no secondary effects, recoil, healing or later-turn outcomes'},
    rolls,min_damage:min,max_damage:max,target_max_hp:d.maxhp,
    validation:{passed:true,roll_count:16,noncritical_verified:true,monotone:true,
     native_randomizer_checks:nativeRandomizerChecks,hp_application_boundary_checks:boundaryChecks}});
  }finally{battle.destroy();}
 }
 return {profiles,exclusions};
}
module.exports={calculate,eligibility};
if(require.main===module){assert(process.argv[2],'Usage: node calculate.cjs inputs.json');
 const inputs=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify(calculate(inputs)));}
