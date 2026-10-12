'use strict';
// Pinned simulator drives real entry, switch, suppression, restoration, and damage.
// Private oracle rows are stored separately from the actor-visible input.
const {Battle, Teams} = require('../../../pokemon-showdown/dist/sim');
const {extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const fs = require('node:fs');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = [];
for (const config of cases) {
 const b = new Battle({format:new Format({name:'Input lifecycle',mod:'gen9',gameType:'singles',ruleset:[]}), seed:[1,2,3,4]});
 const own = config.own || [
  {name:'Shield',species:'Zamazenta',ability:'Dauntless Shield',moves:['Splash','Close Combat'],nature:'Hardy'},
  {name:'Bench',species:'Mew',ability:'Synchronize',moves:['Splash']}];
 const other = config.other || [{species:'Mew',ability:'Synchronize',moves:['Splash','Gastro Acid','Roar','Tackle']},
  {species:'Magikarp',ability:'Swift Swim',moves:['Splash']}];
 b.setPlayer('p1',{name:'observer',team:own});
 b.setPlayer('p2',{name:'opponent',team:other});
 const snapshots=[];
 function snap(label) {
  const request = {...b.p1.activeRequest, rqid: snapshots.length+1};
  const protocol = extractChannelMessages(b.log.join('\n'),[1])[1].join('\n');
  const a=b.p2.active[0],d=b.p1.active[0];
  const oracle = b.p1.pokemon.map(p=>({ident:p.fullname, active:p.isActive, hp:p.hp,maxhp:p.maxhp,
   boosts:{...p.boosts},ability:p.ability,ignoringAbility:p.ignoringAbility(),shieldBoost:!!p.shieldBoost,
   swordBoost:!!p.swordBoost,types:p.getTypes(),item:p.item,status:p.status,stats:{...p.storedStats}}));
  const damage=[], outgoingDamage=[];
  if(!a.fainted&&!d.fainted) for(let factor=85;factor<=100;factor++) {
   b.randomizer=n=>Math.floor(n*factor/100);
   const move=b.dex.getActiveMove(config.damage_move||'Tackle');move.willCrit=false;
   damage.push(b.actions.getDamage(a,d,move));
   outgoingDamage.push(b.actions.getDamage(d,a,move));
  }
  snapshots.push({label,actor:{protocol,request,own_team:Teams.export(own)},oracle,damage,outgoingDamage});
 }
 snap('initial');
 for(const step of config.steps||[]) {
  b.makeChoices(step[0],step[1]);snap(step[2]);
 }
 results.push({name:config.name,snapshots});b.destroy();
}
process.stdout.write(JSON.stringify(results));
