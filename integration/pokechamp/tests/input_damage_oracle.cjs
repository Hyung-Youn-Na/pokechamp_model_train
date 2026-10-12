'use strict';
// Independent damage/roll oracle: pinned simulator only, never calc.
const fs=require('node:fs');
const {Battle}=require('../../../pokemon-showdown/dist/sim');
const {Format}=require('../../../pokemon-showdown/dist/sim/dex-formats');
const {extractChannelMessages}=require('../../../pokemon-showdown/dist/sim/battle');
const rows=[];
for(const s of JSON.parse(fs.readFileSync(0,'utf8'))) for(let factor=85;factor<=100;factor++) {
 const b=new Battle({format:new Format({name:'Independent damage',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
 const set=(p,moves)=>({species:p.name,...p.options,ability:p.options.ability||'No Ability',moves});
 b.setPlayer('p1',{name:'attacker',team:[set(s.attacker,[s.move,'Splash'])]});
 b.setPlayer('p2',{name:'defender',team:[set(s.defender,['Splash'])]});
 const a=b.p1.active[0],d=b.p2.active[0];
 for(const [p,spec] of [[a,s.attacker],[d,s.defender]]) {
  p.hp=spec.options.curHP;
  if(spec.options.boosts) Object.assign(p.boosts,spec.options.boosts);
  if(spec.options.status) p.setStatus(spec.options.status);
  if(spec.options.teraType) p.terastallized=spec.options.teraType;
 }
 const field=s.field||{};
 if(field.weather) b.field.setWeather({Sun:'sunnyday',Rain:'raindance',Snow:'snowscape',Sand:'sandstorm'}[field.weather],a);
 if(field.terrain) b.field.setTerrain(field.terrain.toLowerCase()+'terrain',a);
 // Authored current snapshots place the terrain before entry. Restore the item
 // consumed during this harness's initial no-terrain setPlayer sequence.
 for(const [p,spec] of [[a,s.attacker],[d,s.defender]]) {
  if(spec.options.item==='Booster Energy' &&
     ((p.hasAbility('quarkdrive') && field.terrain==='Electric') ||
      (p.hasAbility('protosynthesis') && field.weather==='Sun'))) p.setItem('Booster Energy');
 }
 for(const [role,p] of [['attackerSide',a],['defenderSide',d]]) {
  const side=field[role]||{};
  for(const [k,name] of Object.entries({isReflect:'reflect',isLightScreen:'lightscreen',isAuroraVeil:'auroraveil',isTailwind:'tailwind'}))
   if(side[k])p.side.addSideCondition(name,p);
 }
 const before={attacker_hp:a.hp,defender_hp:d.hp,attacker_speed:a.getActionSpeed(),defender_speed:d.getActionSpeed(),
  attacker_boosts:{...a.boosts},defender_boosts:{...d.boosts},weather:b.field.weather,terrain:b.field.terrain};
 const hits=[];const damage=d.damage;
 d.damage=function(n,source,effect) {const result=damage.call(this,n,source,effect);if(source===a&&effect?.id===s.move.toLowerCase().replace(/[^a-z0-9]/g,''))hits.push(n);return result;};
 b.randomizer=n=>Math.floor(n*factor/100);
 if(s.fickle_all_out!==undefined) {
  const original=b.randomChance;
  b.randomChance=function(n,d){return n===3&&d===10?s.fickle_all_out:original.call(this,n,d);};
 }
 const move=b.dex.getActiveMove(s.move);move.accuracy=true;move.alwaysHit=true;move.willCrit=!!move.willCrit;
 if(s.hits)move.multihit=s.hits;
 b.actions.runMove(move,a,1);
 rows.push({scenario_id:s.scenario_id,factor,before,hits,total:hits.reduce((a,n)=>a+n,0),
  after:{attacker_hp:a.hp,defender_hp:d.hp},protocol:extractChannelMessages(b.log.join('\n'),[1])[1].join('\n')});
 b.destroy();
}
process.stdout.write(JSON.stringify(rows));
