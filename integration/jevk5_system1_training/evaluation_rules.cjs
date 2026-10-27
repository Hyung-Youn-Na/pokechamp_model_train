/* EX116 controlled compositional evaluation. Showdown is MIT licensed.
 * Expected rules below do not read engine outputs. Evidence never enters prompts. */
'use strict';
const fs=require('fs'),crypto=require('crypto'),assert=require('node:assert/strict');
const {Battle,Dex}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
const types=['Normal','Fire','Water','Electric','Grass','Ice','Fighting','Poison','Ground','Flying','Psychic','Bug','Rock','Ghost','Dragon','Dark','Steel','Fairy'];
// Independently written attacking-type chart: super-effective, resisted, immune.
const chart={Normal:['','Rock Steel','Ghost'],Fire:['Grass Ice Bug Steel','Fire Water Rock Dragon',''],Water:['Fire Ground Rock','Water Grass Dragon',''],Electric:['Water Flying','Electric Grass Dragon','Ground'],Grass:['Water Ground Rock','Fire Grass Poison Flying Bug Dragon Steel',''],Ice:['Grass Ground Flying Dragon','Fire Water Ice Steel',''],Fighting:['Normal Ice Rock Dark Steel','Poison Flying Psychic Bug Fairy','Ghost'],Poison:['Grass Fairy','Poison Ground Rock Ghost','Steel'],Ground:['Fire Electric Poison Rock Steel','Grass Bug','Flying'],Flying:['Grass Fighting Bug','Electric Rock Steel',''],Psychic:['Fighting Poison','Psychic Steel','Dark'],Bug:['Grass Psychic Dark','Fire Fighting Poison Flying Ghost Steel Fairy',''],Rock:['Fire Ice Flying Bug','Fighting Ground Steel',''],Ghost:['Psychic Ghost','Dark','Normal'],Dragon:['Dragon','Steel','Fairy'],Dark:['Psychic Ghost','Fighting Dark Fairy',''],Steel:['Ice Rock Fairy','Fire Water Electric Steel',''],Fairy:['Fighting Dragon Dark','Fire Poison Steel','']};
function mult(a,d){const [w,r,i]=chart[a].map(v=>v.split(' '));return i.includes(d)?0:w.includes(d)?2:r.includes(d)?.5:1;}
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const frac=(h,d)=>Math.max(1,Math.floor(h/d));
const common='Controlled Generation 9 singles mechanics, not a legal species/set or optimal-action assertion. Listed effects only. All items/abilities are active unless their listed interactions prevent them. No random accuracy or critical hits, no Substitute, no unstated healing or effects.';
function fixture(c={}){
 const b=new Battle({formatid:'gen9customgame',seed:[2026,10,21,116]});
 for(const side of ['p1','p2'])b.setPlayer(side,{name:side,team:[{species:'Mew',level:100,ability:side==='p1'?(c.sourceAbility||'noability'):(c.ability||'noability'),item:side==='p2'?(c.item||''):'',moves:['tackle','splash'],nature:'Hardy'}, {species:'Mew',ability:'No Ability',moves:['splash']}]});
 const a=b.p1.active[0],d=b.p2.active[0];a.types=['Water'];d.types=[c.type||'Normal'];
 d.hp=c.hp??c.maxhp??320;d.maxhp=d.baseMaxhp=c.maxhp??320;a.hp=a.maxhp=a.baseMaxhp=320;
 if(c.tera)d.terastallized=c.tera;
 if(c.status){d.status=c.status;d.statusState={id:c.status,target:d,stage:0};}
 if(c.weather)b.field.setWeather(c.weather,a);
 if(c.terrain)b.field.setTerrain(c.terrain,a);
 b.randomizer=x=>x;return {b,a,d};
}
function attack(ctx,c={}){
 const m=ctx.b.dex.getActiveMove(c.move||'tackle');m.accuracy=true;m.alwaysHit=true;m.willCrit=false;
 if(!ctx.a.moveSlots.some(s=>s.id===m.id))ctx.a.moveSlots.push({move:m.name,id:m.id,pp:32,maxpp:32,target:m.target,disabled:false,used:false});
 if(c.attackType)m.type=c.attackType;
 if(c.damage!==undefined)m.damage=c.damage;
 if(c.hits>1)m.multihit=c.hits;
 ctx.b.actions.runMove(m,ctx.a,1);return m;
}
function residualExpected(h,max,c){
 if(h<=0)return 0;
 if(c.weather==='sandstorm'&&!['Rock','Ground','Steel'].includes(c.type)&&c.ability!=='magicguard')h=Math.max(0,h-frac(max,16));
 if(h>0&&c.item==='leftovers')h=Math.min(max,h+frac(max,16));
 if(h>0&&c.status&&c.ability!=='magicguard')h=Math.max(0,h-frac(max,c.status==='psn'?8:16));
 return h;
}
function koExpected(c,hits){
 let h=c.hp??c.maxhp,item=c.item,a=320;
 for(let i=0;i<hits&&h>0&&a>0;i++){
  if(c.damage>=h&&h===c.maxhp&&(c.ability==='sturdy'||item==='focussash')){h=1;if(c.ability!=='sturdy')item='';}
  else h=Math.max(0,h-c.damage);
  if(h>0&&['sitrusberry','oranberry'].includes(item)&&h<=c.maxhp/2){h=Math.min(c.maxhp,h+(item==='oranberry'?10:frac(c.maxhp,4)));item='';}
  if(c.item==='rockyhelmet')a=Math.max(0,a-frac(320,6));
 }
 h=residualExpected(h,c.maxhp,{...c,item});
 if(c.weather==='sandstorm')a=Math.max(0,a-20);
 return {hp:h,attacker_hp:a};
}
function koObserved(c,hits){const ctx=fixture(c);try{attack(ctx,{damage:c.damage,hits});ctx.b.clearActiveMove();ctx.b.fieldEvent('Residual');return {hp:ctx.d.hp,attacker_hp:ctx.a.hp};}finally{ctx.b.destroy();}}
function grid(values){let out=[{}];for(const [k,vs]of Object.entries(values))out=out.flatMap(o=>vs.map(v=>({...o,[k]:v})));return out;}
const out=[];
function normalizedProfile(name,c){
 const k=JSON.parse(JSON.stringify(c));
 if(name==='ko_prevention_followup'){
  if(!k.weather)k.type='Normal';
  if(k.ability==='sturdy'&&k.damage<160)k.ability='noability';
  if(k.ability==='magicguard'&&!k.status&&(!k.weather||k.type==='Rock'))k.ability='noability';
 }
 if(name==='information_sufficiency'&&!k.weather)k.type='Normal';
 return k;
}

function domain(name,profiles,make){
 profiles.sort((a,b)=>hash([name,a]).localeCompare(hash([name,b])));
 const seen=new Set();profiles=profiles.filter(c=>{const k=hash(normalizedProfile(name,c));if(seen.has(k))return false;seen.add(k);return true;});assert(profiles.length>=192,`${name} has only ${profiles.length} distinct profiles`);
 const selected=profiles.slice(0,192);
 for(const [i,c]of selected.entries()){
  const group=name+':'+hash(normalizedProfile(name,c)).slice(0,24),pair=make(c);assert.equal(pair.length,2);
  for(const [v,r]of pair.entries()){
   assert.deepEqual(r.observed,r.expected,JSON.stringify({name,c,v,r}));
   assert(r.options.includes(r.expected));assert.equal(new Set(r.options).size,r.options.length);
   out.push({id:group+':'+v,domain:name,group,split:i<64?'validation':'test',state:{generation:9,...r.state,scope:common},question:r.question,options:r.options,answer:r.expected,
    evidence:{expected:r.expected,observed:r.observed,details:r.evidence||{},profile:c,engine:'e64915c0eab066db1d3e732b1280386468dd7415',oracle:r.oracle||'Actual controlled Battle events plus independent rule arithmetic'}});
  }
 }
 console.error(JSON.stringify({event:'rules_domain',domain:name,groups:selected.length,rows:selected.length*2}));
}
const binary=v=>v?'Yes':'No';
function typeDomain(){domain('type_tera_ability',grid({attack:types,tera:types,ability:['levitate','waterabsorb','flashfire','voltabsorb','wonderguard'],item:['','abilityshield']}).filter(c=>c.ability==='wonderguard'||({levitate:'Ground',waterabsorb:'Water',flashfire:'Fire',voltabsorb:'Electric'})[c.ability]===c.attack),c=>[false,true].map(mold=>{
 const k={type:'Normal',tera:c.tera,ability:c.ability,item:c.item,sourceAbility:mold?'moldbreaker':'noability'},ctx=fixture(k);
 try{
  const active=!mold||c.item==='abilityshield',m=mult(c.attack,c.tera);
  const blocked=active&&(c.ability==='levitate'&&c.attack==='Ground'||c.ability==='waterabsorb'&&c.attack==='Water'||c.ability==='flashfire'&&c.attack==='Fire'||c.ability==='voltabsorb'&&c.attack==='Electric'||c.ability==='wonderguard'&&m<=1);
  const before=ctx.d.hp;attack(ctx,{attackType:c.attack});
  return {state:{original_defender_type:'Normal',defender_tera_type:c.tera,defender_ability:c.ability,defender_item:c.item||'None',attacker_ability:k.sourceAbility,attack_type:c.attack,attack:'Ordinary single-hit contact damaging move; no move-specific exceptions; full target HP'},question:'Does the attack deal direct HP damage after current typing and ability interactions?',options:['Yes','No'],expected:binary(m>0&&!blocked),observed:binary(ctx.d.hp<before)};
 }finally{ctx.b.destroy();}
}));}
function statusDomain(){domain('status_immunity_cure',grid({status:['brn','par','psn','tox','slp','frz'],tera:types,ability:['noability','limber','immunity','waterveil','insomnia','magmaarmor'],terrain:['electricterrain','mistyterrain']}).filter(c=>c.ability==='noability'||({brn:'waterveil',par:'limber',psn:'immunity',tox:'immunity',slp:'insomnia',frz:'magmaarmor'})[c.status]===c.ability),c=>['','lumberry'].map(item=>{
 const ctx=fixture({type:'Normal',tera:c.tera,ability:c.ability,item,terrain:c.terrain});try{
  const typeImm=c.status==='brn'&&c.tera==='Fire'||c.status==='par'&&c.tera==='Electric'||['psn','tox'].includes(c.status)&&['Poison','Steel'].includes(c.tera)||c.status==='frz'&&c.tera==='Ice';
  const abilityImm=c.ability==='limber'&&c.status==='par'||c.ability==='immunity'&&['psn','tox'].includes(c.status)||c.ability==='waterveil'&&c.status==='brn'||c.ability==='insomnia'&&c.status==='slp'||c.ability==='magmaarmor'&&c.status==='frz';
  const terrainImm=c.tera!=='Flying'&&(c.terrain==='mistyterrain'||c.terrain==='electricterrain'&&c.status==='slp');
  ctx.d.trySetStatus(c.status,ctx.a);ctx.b.runEvent('Update',ctx.d);
  return {state:{original_defender_type:'Normal',defender_tera_type:c.tera,ability:c.ability,item:item||'None',terrain:c.terrain||'None',attempted_status:c.status,initial_status:'None',event:'Ordinary major-status infliction attempt reaches SetStatus, followed by immediate item Update. This is not a particular status move and bypasses move accuracy/type gates; no weather.'},question:'Is the attempted major status still present after prevention and immediate berry cure?',options:['Yes','No'],expected:binary(!typeImm&&!abilityImm&&!terrainImm&&!item),observed:binary(ctx.d.status===c.status)};
 }finally{ctx.b.destroy();}
}));}
function priorityDomain(){domain('priority_execution',grid({move:['quickattack','aquajet','machpunch','iceshard','shadowsneak'],type:types,ability:['queenlymajesty'],mold:[false,true],protect:[false,true]}),c=>['','psychicterrain'].map(terrain=>{
 const ctx=fixture({type:c.type,ability:c.ability,sourceAbility:c.mold?'moldbreaker':'noability',terrain});try{
  if(c.protect)ctx.d.addVolatile('protect',ctx.d);
  const move=dex.moves.get(c.move);const immune=mult(move.type,c.type)===0;
  const blocked=c.protect||(!c.mold&&c.ability!=='noability')||terrain&&c.type!=='Flying';
  const before=ctx.d.hp;attack(ctx,{move:c.move});
  return {state:{move:move.name,defender_type:c.type,defender_ability:c.ability,attacker_ability:c.mold?'Mold Breaker':'No Ability',terrain:terrain||'None',defender_protect_active:c.protect,defender_grounding:'No item/volatile grounding changes; Flying is airborne',event:'Selected native positive-priority move attempts to execute against the opposing active target; accuracy succeeds and attack is noncritical.'},question:'Does the move deal direct damage after priority-specific protection and execution gates?',options:['Yes','No'],expected:binary(!immune&&!blocked),observed:binary(ctx.d.hp<before)};
 }finally{ctx.b.destroy();}
}));}
const rock={Normal:1,Fire:2,Water:1,Electric:1,Grass:1,Ice:2,Fighting:.5,Poison:1,Ground:.5,Flying:2,Psychic:1,Bug:2,Rock:1,Ghost:1,Dragon:1,Dark:1,Steel:.5,Fairy:1};
function weatherDomain(){domain('weather_entry_residual',grid({tera:types,ability:['noability','levitate','magicguard'],item:['','heavydutyboots','leftovers'],weather:['sandstorm'],spikes:[1,3]}),c=>['','grassyterrain'].map(terrain=>{
 const ctx=fixture({type:'Normal',tera:c.tera,ability:c.ability,item:c.item,weather:c.weather,terrain});try{
  const grounded=c.tera!=='Flying'&&c.ability!=='levitate';let h=320;
  if(c.item!=='heavydutyboots'&&c.ability!=='magicguard'){h-=Math.floor(320*rock[c.tera]/8);if(grounded)h-=c.spikes===3?80:40;}
  if(c.weather&&!['Rock','Ground','Steel'].includes(c.tera)&&c.ability!=='magicguard')h-=20;
  if(terrain&&grounded)h=Math.min(320,h+20);if(c.item==='leftovers')h=Math.min(320,h+20);
  ctx.d.side.addSideCondition('stealthrock',ctx.a);for(let j=0;j<c.spikes;j++)ctx.d.side.addSideCondition('spikes',ctx.a);
  ctx.b.fieldEvent('SwitchIn',[ctx.d]);ctx.b.fieldEvent('Residual');
  return {state:{original_type:'Normal',tera_type:c.tera,ability:c.ability,item:c.item||'None',weather:c.weather||'None',terrain:terrain||'None',current_hp:320,max_hp:320,hazards:['Stealth Rock',`Spikes (${c.spikes} layers)`],event:'One SwitchIn event for the already Terastallized target, then one end-turn Residual event with no intervening attacks or status. Listed field effects last through both events.'},question:'What is the target HP after entry damage and the residual event?',options:[...new Set([String(h),'0','320',String(Math.max(0,h-20)),String(Math.min(320,h+20))])],expected:String(h),observed:String(ctx.d.hp)};
 }finally{ctx.b.destroy();}
}));}
const hpLabel=x=>`Defender ${x.hp} HP; attacker ${x.attacker_hp} HP`;
function koDomain(){domain('ko_prevention_followup',grid({damage:[80,120,160,200],ability:['noability','sturdy','magicguard'],item:['sitrusberry','oranberry','rockyhelmet'],status:['','brn','psn'],weather:['','sandstorm'],type:['Normal','Rock']}),c=>[1,2].map(hits=>{
 const p={...c,maxhp:160,hp:160},expected=hpLabel(koExpected(p,hits)),actual=hpLabel(koObserved(p,hits));
 return {state:{defender:{type:c.type,hp:160,max_hp:160,ability:c.ability,item:c.item||'None',existing_status:c.status||'None'},attacker:{type:'Water',hp:320,max_hp:320,ability:'No Ability',item:'None'},attack:{type:'Normal',contact:true,fixed_direct_damage_per_hit:c.damage,hits},weather:c.weather||'None',event:'One synthetic deterministic contact attack, all stated hits connect unless either participant faints; immediate item effects resolve between hits, then one residual event. Fixed damage bypasses the damage formula; no secondary effects or terrain.'},question:'What are both HP values after the whole attack and follow-up residual effects?',options:[...new Set([expected,'Defender 0 HP; attacker 0 HP','Defender 160 HP; attacker 320 HP','Defender 1 HP; attacker 320 HP'])],expected,observed:actual};
}));}
function classification(values){return values.every(Boolean)?'Guaranteed KO':values.some(Boolean)?'KO depends on hidden conditions':'Guaranteed survival';}
function informationDomain(){domain('information_sufficiency',grid({abilities:[['noability','magicguard'],['noability','sturdy'],['sturdy','magicguard']],items:[['','focussash'],['','leftovers'],['focussash','leftovers']],status:['','brn','psn'],weather:['','sandstorm'],type:['Normal','Rock'],damage:[120,160,200]}).filter(c=>c.status||c.weather),c=>[160,159].map(hp=>{
 const expected=[],observed=[],worlds=[];
 for(const ability of c.abilities)for(const item of c.items){const p={...c,ability,item,maxhp:160,hp};expected.push(koExpected(p,1).hp===0);observed.push(koObserved(p,1).hp===0);worlds.push({ability,item});}
 return {state:{defender_type:c.type,current_hp:hp,max_hp:160,possible_abilities:c.abilities,possible_items:c.items.map(x=>x||'None'),existing_status:c.status||'None',weather:c.weather||'None',fixed_contact_attack_damage:c.damage,event:'One successful deterministic Normal-type hit followed by one residual event. All combinations of the listed hidden abilities and items are possible and exhaust uncertainty. No other hidden variables, item suppression, terrain, or secondary effects.'},question:'Is the target KO after direct damage, immediate item effects and residuals determined by the public conditions?',options:['Guaranteed KO','Guaranteed survival','KO depends on hidden conditions'],expected:classification(expected),observed:classification(observed),evidence:{worlds,expected_world_KO:expected,observed_world_KO:observed}};
}));}
function conditionalDomain(){domain('conditional_ko_boundary',grid({power:[35,55,75,95,115,135],attack:[90,130,170,210],defense:[100,180],ability:['noability','sturdy'],item:['','focussash','leftovers'],weather:['','sandstorm']}).filter(c=>c.ability==='sturdy'||c.item||c.weather),c=>{
 const ctx=fixture({type:'Normal',ability:'noability'}),damages=[];
 try{
  ctx.a.storedStats.atk=c.attack;ctx.d.storedStats.def=c.defense;
  for(let r=85;r<=100;r++){
   ctx.b.randomizer=d=>Math.floor(d*r/100);const m=ctx.b.dex.getActiveMove('tackle');m.basePower=c.power;m.willCrit=false;
   const damage=ctx.b.actions.getDamage(ctx.a,ctx.d,m,true);
   const base=Math.floor(Math.floor((Math.floor(2*100/5)+2)*c.power*c.attack/c.defense)/50)+2;
   assert.equal(damage,Math.floor(base*r/100),'independent non-STAB neutral damage formula');damages.push(damage);
  }
 }finally{ctx.b.destroy();}
 const low=Math.min(...damages),high=Math.max(...damages),maxhp=low+1;
 return [low,low+1].map(hp=>{
  const expected=[],observed=[];
  for(const damage of damages){const p={...c,type:'Normal',maxhp,hp,damage,status:''};expected.push(koExpected(p,1).hp===0);observed.push(koObserved(p,1).hp===0);}
  const classify=v=>v.every(Boolean)?'Guaranteed KO':v.some(Boolean)?'KO on some damage rolls':'KO impossible';
  return {state:{attacker:{type:'Water',level:100,attack_stat:c.attack,ability:'No Ability'},defender:{type:'Normal',defense_stat:c.defense,hp,max_hp:maxhp,ability:c.ability,item:c.item||'None'},attack:{type:'Normal',category:'Physical',base_power:c.power,hits:1,contact:true},verified_prevention_free_direct_damage_range:[low,high],weather:c.weather||'None',event:'One successful noncritical hit with the 16 standard damage factors, then one residual event. The supplied range precedes KO-prevention effects. No status, STAB, terrain, stat changes, other abilities/items, or secondary effects; supplied HP/stats are synthetic controlled values.'},question:'Using the verified damage range and the stated KO-prevention and residual effects, classify target KO at the end of this sequence.',options:['Guaranteed KO','KO on some damage rolls','KO impossible'],expected:classify(expected),observed:classify(observed),evidence:{damage_rolls:damages,expected_KO:expected,observed_KO:observed}};
 });
});}
const functions={typeDomain,statusDomain,priorityDomain,weatherDomain,koDomain,informationDomain,conditionalDomain};

function refineOptions(r){
 const c=r.evidence.profile;
 if(r.domain==='ko_prevention_followup'){
  const options=new Set();
  for(const ability of new Set([c.ability,'noability']))for(const item of new Set([c.item,'']))for(const residual of [false,true]){
   options.add(hpLabel(koExpected({...c,ability,item,maxhp:160,hp:160,weather:residual?c.weather:'',status:residual?c.status:''},r.state.attack.hits)));
  }
  options.add('Defender 160 HP; attacker 320 HP');r.options=[...options].sort();
 }
 if(r.domain==='weather_entry_residual'){
  let entry=320;
  if(c.item!=='heavydutyboots'&&c.ability!=='magicguard'){
   entry-=40*mult('Rock',c.tera);
   if(c.tera!=='Flying'&&c.ability!=='levitate')entry-=c.spikes===3?80:40;
  }
  r.options=[...new Set([0,320,...[-40,-20,0,20,40].map(d=>Math.max(0,Math.min(320,entry+d)))])].sort((a,b)=>a-b).map(String);
 }
 assert(r.options.includes(r.answer));assert(r.options.length>=2&&r.options.length<=11);
 return r;
}

if(require.main===module){
 const selected=process.argv[2];if(selected){assert(functions[selected]);functions[selected]();}else for(const fn of Object.values(functions))fn();
 for(const row of out)console.log(JSON.stringify(refineOptions(row)));
}
module.exports={functions,koExpected,koObserved,mult,refineOptions};
