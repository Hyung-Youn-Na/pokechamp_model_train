'use strict';
// CPU rule oracle. All fixture facts are explicitly known; no model/battle server.
const fs = require('node:fs');
const {Battle} = require('../../../pokemon-showdown/dist/sim');
const facts = p => ({species:p.species.name, types:p.getTypes(), hp:p.hp, maxhp:p.maxhp,
  ability:p.ability, suppressed:p.ignoringAbility(), item:p.item, status:p.status,
  volatiles:Object.keys(p.volatiles), tera:p.terastallized || false, teraType:p.teraType});
const results=[];
for (const c of JSON.parse(fs.readFileSync(0,'utf8'))) {
  const b=new Battle({formatid:'gen9customgame',seed:[2026,10,20,1],send(){}});
  b.setPlayer('p1',{name:'Source',team:[{species:c.attacker||'Mew',ability:c.ownAbility||'Synchronize',
    item:c.ownItem||'',moves:[c.move],teraType:c.ownTera||'Fire',level:100}]});
  b.setPlayer('p2',{name:'Target',team:[{species:c.target,ability:c.ability||'Pressure',
    item:c.item||'',moves:['splash'],level:100}]});
  if (b.requestState==='teampreview')b.makeChoices('team 1','team 1');
  const a=b.p1.active[0],d=b.p2.active[0];
  if(c.gravity)b.field.addPseudoWeather('gravity',a);
  if(c.magicRoom)b.field.addPseudoWeather('magicroom',a);
  if(c.weather)b.field.setWeather(c.weather,a);
  if(c.terrain)b.field.setTerrain(c.terrain,a);
  for(const name of c.volatiles||[])d.addVolatile(name,d);
  if(c.status)d.setStatus(c.status,d,null,true);
  if(c.safeguard)d.side.addSideCondition('safeguard',d);
  const before={own:facts(a),target:facts(d)},start=b.log.length;
  if(c.tera)b.actions.terastallize(a);
  const move=b.dex.getActiveMove(c.move);move.accuracy=true;move.alwaysHit=true;move.willCrit=false;
  const damage=[];const getDamage=b.actions.getDamage;
  b.actions.getDamage=function(source,target,m,...rest){
    const value=getDamage.call(this,source,target,m,...rest);
    if(m&&typeof m==='object'&&typeof value==='number')damage.push({type:m.type,type_mod:target.getMoveHitData(m).typeMod,value});
    return value;
  };
  b.actions.runMove(move,a,move.target==='self'?0:1);
  results.push({id:c.id,before,after:{own:facts(a),target:facts(d)},log:b.log.slice(start),damage});
  b.destroy();
}
process.stdout.write(JSON.stringify(results)+'\n');
