'use strict';
// Independent oracle: only the pinned simulator, never @smogon/calc.
const fs=require('node:fs');
const {Battle}=require('../../../pokemon-showdown/dist/sim');
const {Format}=require('../../../pokemon-showdown/dist/sim/dex-formats');
function run(s,factor) {
 const b=new Battle({format:new Format({name:'Entry ability oracle',mod:'gen9',gameType:'singles',ruleset:[]}),seed:[1,2,3,4]});
 const team=(spec,moves)=>[{species:spec.name,...spec.options,ability:spec.options.ability||'No Ability',moves}];
 b.setPlayer('p1',{name:'attacker',team:team(s.attacker,[s.move])});
 b.setPlayer('p2',{name:'defender',team:team(s.defender,['Close Combat','Splash'])});
 const a=b.p1.active[0],d=b.p2.active[0],initialDefense=d.boosts.def;
 for(let i=0;i<(s.close_combats||0);i++) {
  a.hp=a.maxhp;d.moveThisTurn='';const cc=b.dex.getActiveMove('Close Combat');cc.willCrit=false;b.actions.runMove(cc,d,1);
 }
 const afterCloseCombat=d.boosts.def;
 for(const [p,spec] of [[a,s.attacker],[d,s.defender]]) {
  if(spec.entry_effects_observed) Object.assign(p.boosts,spec.options.boosts);
  p.hp=p.maxhp;
  if(spec.options.status) p.status=spec.options.status;
  if(spec.options.teraType) p.terastallized=spec.options.teraType;
 }
 b.randomizer=n=>Math.floor(n*factor/100);
 const move=b.dex.getActiveMove(s.move);move.willCrit=false;
 const damage=b.actions.getDamage(a,d,move);
 const result={scenario_id:s.scenario_id,factor,damage,attacker_stats:a.storedStats,
  defender_stats:d.storedStats,initial_defense:initialDefense,after_close_combat:afterCloseCombat,
  attack_boosts:{...a.boosts},defense_boosts:{...d.boosts},
  attacker_speed:a.getActionSpeed(),defender_speed:d.getActionSpeed(),protocol:b.log.join('\n')};
 b.destroy();return result;
}
const scenarios=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(scenarios.flatMap(s=>Array.from({length:16},(_,i)=>run(s,i+85)))));
