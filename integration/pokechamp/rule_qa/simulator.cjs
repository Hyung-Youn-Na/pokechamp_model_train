'use strict';
// All interventions and private validation branches remain in evidence.
const {Battle, Teams} = require('../../../pokemon-showdown/dist/sim');
const {extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const fs = require('node:fs');
const copy=x=>JSON.parse(JSON.stringify(x));
const facts = p=>({species:p.species.name,types:p.getTypes(),base_types:p.species.types,hp:p.hp,maxhp:p.maxhp,status:p.status,
 item:p.item,ability:p.ability,grounded:p.isGrounded(),speed:p.getStat('spe'),base_speed:p.storedStats.spe,level:p.level,
 volatiles:Object.keys(p.volatiles),tera:p.terastallized,ignoringAbility:p.ignoringAbility(),attack:p.species.id==='conkeldurr'?p.getStat('atk'):null,stats:copy(p.storedStats)});
const hazards=b=>b.sides.map(s=>Object.fromEntries(Object.entries(s.sideConditions).map(([k,v])=>[k,v.layers||1])));
function clone(b) {const x=Battle.fromJSON(copy(b.toJSON()));x.restart(()=>{});return x;}
function test(b,t) {
 const x=clone(b), a=x.sides[t.side||0].active[0], d=x.sides[1-(t.side||0)].active[0];
 const before=x.log.length, hp=x.sides.map(s=>s.pokemon.map(p=>p.hp)), randomCalls=[];
 const confusionCalls=[],halfModifiers=[],damageCalls=[];
 const getDamage=x.actions.getDamage;
 x.actions.getDamage=function(source,target,move,...rest){
  const value=getDamage.call(this,source,target,move,...rest);
  if(move&&typeof move==='object'&&typeof value==='number')damageCalls.push({move:move.id,value,type_mod:target.getMoveHitData(move).typeMod});
  return value;
 };
 const confusionDamage=x.actions.getConfusionDamage;
 x.actions.getConfusionDamage=function(p,power){confusionCalls.push({base_power:power,attack_stat:'atk',defense_stat:'def'});return confusionDamage.call(this,p,power);};
 const modify=x.modify;
 x.modify=function(value,numerator,denominator){if(numerator===0.5)halfModifiers.push({value,numerator});return modify.call(this,value,numerator,denominator);};
 const orig=x.randomChance;
 x.randomChance=function(n,den) {
  randomCalls.push([n,den]);
  if(t.random && n===t.random[0] && den===t.random[1])return t.random[2];
  return orig.call(this,n,den);
 };
 if(t.roll!==undefined)x.randomizer=n=>Math.floor(n*t.roll/100);
 if(t.add_protect)d.addVolatile('protect');
 if(t.move) {
  const m=x.dex.getActiveMove(t.move);
  if(t.hit){m.accuracy=true;m.alwaysHit=true;}
  m.willCrit=false;
  x.actions.runMove(m,a,m.target==='self'?0:1);
 } else if(t.choices)x.makeChoices(...t.choices);
 else if(t.steps)for(const pair of t.steps)x.makeChoices(...pair);
 else throw Error('unknown oracle test');
 const result={log:x.log.slice(before),hp_before:hp,hp_after:x.sides.map(s=>s.pokemon.map(p=>p.hp)),
  own:facts(x.p1.active[0]),other:facts(x.p2.active[0]),hazards:hazards(x),request:copy(x.p1.activeRequest),random_calls:randomCalls,confusion_calls:confusionCalls,half_modifiers:halfModifiers,damage_calls:damageCalls};
 x.destroy();return result;
}
function run(c) {
 const b=new Battle({formatid:'gen9ou',seed:c.seed||[2026,10,19,1],strictChoices:true});
 const teams=[c.own,c.other];
 for(let i=0;i<2;i++)b.setPlayer('p'+(i+1),{name:'Player'+(i+1),team:teams[i]});
 b.makeChoices('team '+teams[0].map((_,i)=>i+1).join(''),'team '+teams[1].map((_,i)=>i+1).join(''));
 for(const pair of c.steps||[])b.makeChoices(...pair);
 for(const x of c.stage||[]) {
  const side=b.sides[x.side||0],p=side.pokemon[x.slot||0];
  switch(x.kind) {
   case 'pp': {const slot=p.moveSlots.find(m=>m.id===x.move);if(!slot)throw Error('missing PP slot');slot.pp=x.value;break;}
   case 'hp': p.sethp(x.value);b.add('-damage',p,p.getHealth);break;
   case 'status': p.setStatus(x.value);break;
   case 'volatile': p.addVolatile(x.value);break;
   case 'hazard': for(let i=0;i<(x.layers||1);i++)side.addSideCondition(x.value,p);break;
   case 'field': b.field.addPseudoWeather(x.value,p);break;
   case 'tera': b.actions.terastallize(p);break;
   case 'pop_balloon': {if(p.item!=='airballoon')throw Error('no Balloon to pop');b.singleEvent('DamagingHit',p.getItem(),p.itemState,p,b.sides[1-(x.side||0)].active[0],b.dex.getActiveMove('waterpulse'),1);break;}
   case 'remove_item': {const item=p.takeItem();if(item)b.add('-enditem',p,item.name);break;}
   default: throw Error('unknown staging operation '+x.kind);
  }
 }
 if((c.stage||[]).length)b.makeRequest('move');
 for(const pair of c.post_steps||[])b.makeChoices(...pair);
 if(!b.p1.activeRequest||b.p1.activeRequest.wait)throw Error('no actor decision');
 if(b.sides.some(s=>s.choice.actions.length))throw Error('capture after submitted action');
 const actor={protocol:extractChannelMessages(b.log.join('\n'),[1])[1].join('\n'),
  request:{...b.p1.activeRequest,rqid:1},own_team:Teams.export(teams[0]).split('\n').map(line=>line.trimEnd()).join('\n')};
 const oracle={own:facts(b.p1.active[0]),other:facts(b.p2.active[0]),
  teams:b.sides.map(s=>s.pokemon.map(facts)),hazards:hazards(b),moves:{},tests:{},
  public_opponent_moves:[...new Set(b.log.filter(line=>line.startsWith('|move|p2a:')).map(line=>b.toID(line.split('|')[3])))],
  public_opponent_abilities:[...new Set(b.log.flatMap(line=>{
   const p=line.split('|');if(p[1]==='-ability'&&p[2]?.startsWith('p2a:'))return [b.toID(p[3])];
   if(p.some(x=>x.startsWith('[of] p2a:'))){const ref=p.find(x=>x.startsWith('[from] ability: '));if(ref)return [b.toID(ref.slice(16))];}
   return [];
  }))]};
 for(const name of c.query_moves||[]) {
  const m=b.dex.moves.get(name),d=b.sides[c.type_target??1].active[0];
  oracle.moves[m.id]={name:m.name,type:m.type,category:m.category,power:m.basePower,accuracy:m.accuracy,priority:m.priority,
   type_multiplier:b.dex.getImmunity(m.type,d.getTypes())?2**b.dex.getEffectiveness(m.type,d.getTypes()):0,
   effective_type_multiplier:d.runImmunity(b.dex.getActiveMove(name),false)?2**d.runEffectiveness(b.dex.getActiveMove(name)):0};
 }
 if(c.stab_move) {
  const x=clone(b),a=x.p1.active[0],d=x.p2.active[0],move=x.dex.getActiveMove(c.stab_move);
  let stab=1; const original=x.runEvent;
  x.runEvent=function(event,...args){if(event==='ModifySTAB')stab=args[3];return original.call(this,event,...args);};
  move.willCrit=false;x.setActiveMove(move,a,d);x.actions.getDamage(a,d,move);
  oracle.stab=stab;x.destroy();
 }
 for(const [key,t] of Object.entries(c.tests||{}))oracle.tests[key]=test(b,t);
 b.destroy();return {actor,oracle};
}
const input=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(input.map(run)));
