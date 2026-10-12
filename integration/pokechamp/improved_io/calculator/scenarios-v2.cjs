'use strict';
const {Field} = require('@smogon/calc');
const {isGrounded, getQPBoostedStat, checkAirLock} = require('@smogon/calc/dist/mechanics/util');
const weatherAbilities = {Drought:'Sun',Drizzle:'Rain','Sand Stream':'Sand','Snow Warning':'Snow'};
const terrainAbilities = {'Electric Surge':'Electric','Grassy Surge':'Grassy','Misty Surge':'Misty','Psychic Surge':'Psychic'};
function clamp(n) {return Math.max(-6, Math.min(6, n));}
function types(p) {return p.teraType && p.teraType !== 'Stellar' ? [p.teraType] : p.types;}
function prepare(gen, scenario, attacker, defender) {
 const raw = structuredClone(scenario.field);
 const field = new Field(raw);
 const projections=[];
 for (const [role,p,spec,side,other] of [
  ['attacker',attacker,scenario.attacker,'attackerSide',defender],
  ['defender',defender,scenario.defender,'defenderSide',attacker],
 ]) {
  p.species.__entryObserved = !spec.projected_entry;
  // Observed rank changes already include Intimidate; a new entrant triggers it.
  if (p.hasAbility('Intimidate')) p.abilityOn = !!spec.projected_entry;
  if (spec.projected_entry) {
   const hpBefore=p.curHP();
   const conditions=raw[side]||{};
   if (field.isMagicRoom || p.hasAbility('Klutz')) p.item='';
   const boots=p.hasItem('Heavy-Duty Boots');
   const grounded=isGrounded(p,field);
   let hazardDamage=0;
   if (!boots && !p.hasAbility('Magic Guard')) {
    if (conditions.isSR) {
     const effectiveness=types(p).reduce((m,t)=>m*gen.types.get('rock').effectiveness[t],1);
     hazardDamage+=Math.max(1,Math.floor(p.maxHP()*effectiveness/8));
    }
    if (grounded && conditions.spikes) hazardDamage+=Math.max(1,Math.floor(p.maxHP()/[0,8,6,4][conditions.spikes]));
   }
   p.originalCurHP=Math.max(0,hpBefore-hazardDamage);
   if (p.originalCurHP > 0 && grounded && !boots) {
    if (conditions.toxicSpikes && !p.status && !types(p).some(t=>['Poison','Steel'].includes(t)) &&
        !p.hasAbility('Immunity','Pastel Veil','Comatose','Purifying Salt') &&
        field.terrain!=='Misty' && !p.hasItem('Air Balloon')) p.status=conditions.toxicSpikes===2?'tox':'psn';
    if (conditions.isStickyWeb && !p.hasAbility('Clear Body','White Smoke','Full Metal Body') && !p.hasItem('Clear Amulet')) {
     const target=p.hasAbility('Mirror Armor') ? other : p;
     const amount=target.hasAbility('Contrary') ? 1 : target.hasAbility('Simple') ? -2 : -1;
     target.boosts.spe=clamp(target.boosts.spe+amount);
     if (amount < 0 && target.hasAbility('Defiant')) target.boosts.atk=clamp(target.boosts.atk+2);
     if (amount < 0 && target.hasAbility('Competitive')) target.boosts.spa=clamp(target.boosts.spa+2);
    }
   }
   if (p.originalCurHP > 0) {
    if (weatherAbilities[p.ability]) field.weather=weatherAbilities[p.ability];
    if (terrainAbilities[p.ability]) field.terrain=terrainAbilities[p.ability];
   }
   projections.push({role,hp_before_entry:hpBefore,hazard_damage:Math.min(hpBefore,hazardDamage),
    hp_after_hazards:p.originalCurHP, status_after_hazards:p.status,
    ability:p.ability||'', entry_boost_already_consumed:!!spec.entry_effects_observed,
    assumptions:'Single selected switch enters under current hazards, before the hypothetical attack; subsequent actions and residual effects are not predicted.'});
  }
 }
 checkAirLock(attacker,field);checkAirLock(defender,field);
 for (const [p,spec] of [[attacker,scenario.attacker],[defender,scenario.defender]]) {
  if (p.item && p.item === `${field.terrain} Seed` && !field.isMagicRoom && !p.hasAbility('Klutz')) {
   const stat=['Electric','Grassy'].includes(field.terrain) ? 'def' : 'spd';
   const amount=p.hasAbility('Contrary') ? -1 : p.hasAbility('Simple') ? 2 : 1;
   p.boosts[stat]=clamp(p.boosts[stat]+amount);
   p.item='';
  }
  if (p.hasAbility('Protosynthesis','Quark Drive')) {
   const environment=p.hasAbility('Protosynthesis') ? ['Sun','Harsh Sunshine'].includes(field.weather) : field.terrain==='Electric';
   if (spec.qp_source==='field' && !environment) p.boostedStat=undefined;
   if (!environment && p.hasItem('Booster Energy') && !field.isMagicRoom) {
    p.boostedStat=getQPBoostedStat(p,gen);
    p.item='';
   } else if (!p.boostedStat) p.boostedStat='auto';
  }
 }
 // Hazards are entry events, not a persistent switch assumption in each damage
 // call (notably Multiscale/Shadow Shield/Tera Shell at current full HP).
 field.attackerSide.isSR=false;field.defenderSide.isSR=false;
 field.attackerSide.spikes=0;field.defenderSide.spikes=0;
 return {field, projections, fainted: projections.some(p=>p.hp_after_hazards===0)};
}
function moveVariants(gen, name, attacker) {
 const data=gen.moves.get(String(name).toLowerCase().replace(/[^a-z0-9]/g,''));
 let counts=[1];
 if (Array.isArray(data.multihit)) {
  const lo=attacker.hasAbility('Skill Link') ? data.multihit[1] : attacker.hasItem('Loaded Dice') && data.multihit[1]===5 ? 4 : data.multihit[0];
  counts=Array.from({length:data.multihit[1]-lo+1},(_,i)=>lo+i);
 } else if (typeof data.multihit==='number') {
  counts=data.multiaccuracy && !attacker.hasAbility('Skill Link') ?
   Array.from({length:data.multihit},(_,i)=>i+1) : [data.multihit];
 }
 return counts.flatMap(hits=>(data.name==='Fickle Beam'?[80,160]:[null]).map(power=>({
  label:`${hits}-hit${power ? '-power-'+power : ''}`,hits,
  options:{hits,ability:attacker.ability,item:attacker.item,...(power ? {overrides:{basePower:power}} : {})},
 })));
}
module.exports={prepare,moveVariants};
