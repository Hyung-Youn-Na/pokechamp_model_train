'use strict';
const assert=require('node:assert/strict');
const {Dex,Battle,Pokemon}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
const statuses=['brn','par','psn','tox','slp','frz'];
const names={brn:'burn',par:'paralysis',psn:'ordinary poison',tox:'bad poison',slp:'sleep',frz:'freeze'};
const types=dex.types.all().map(t=>t.name).filter(t=>t!=='Stellar').sort();
const defs=types.map(t=>[t]);for(let i=0;i<18;i++)for(let j=i+1;j<18;j++)defs.push([types[i],types[j]]);
const immune={brn:['Fire'],par:['Electric'],psn:['Poison','Steel'],tox:['Poison','Steel'],slp:[],frz:['Ice']};
function core(){
 const out=[];
 function add(rule,id,state,question,expected,observed,source,group){
  assert.equal(observed,expected,id);
  out.push({id,rule_id:rule,state,question,options:['Yes','No'],answer:observed?'Yes':'No',
   semantic_group:group||id,evidence:{source,expected,observed,oracle:'Pinned Showdown direct methods/hooks'}});
 }
 const fake={types:[],terastallized:'',addedType:'',getTypes:Pokemon.prototype.getTypes,
   battle:{gen:9,runEvent:(_e,_p,_s,_f,relay)=>relay}};
 for(const status of statuses)for(const original of defs)for(const tera of [null,...types,'Stellar']){
  fake.types=original;fake.terastallized=tera||'';
  const effective=tera&&tera!=='Stellar'?[tera]:original;
  const expected=!effective.some(t=>immune[status].includes(t));
  const observed=dex.getImmunity(status==='tox'?'psn':status,fake);
  add('type_tera_immunity',`type-${status}-${original.join('-')}-${tera||'none'}`,
   {generation:9,original_types:original,defender_tera_type:tera,attempted_status:names[status],
    assumptions:'No existing major status. Test intrinsic typing only; ignore abilities, items, weather, terrain, move accuracy/immunity and format move bans.'},
   'Does the current typing permit this major status (no intrinsic type immunity)?',expected,observed,
   'sim/dex.ts:getImmunity; sim/pokemon.ts:getTypes; data/typechart.ts',`type-${status}-${effective.join('-')}`);
 }
 const blank={add(){},debug(){}};
 const abilityBlocks={immunity:['psn','tox'],limber:['par'],insomnia:['slp'],vitalspirit:['slp'],
  waterveil:['brn'],waterbubble:['brn'],magmaarmor:['frz'],comatose:statuses,purifyingsalt:statuses,
  leafguard:[],none:[]};
 for(const [ability,blocked] of Object.entries(abilityBlocks))for(const weather of (ability==='leafguard'?['none','sunnyday']:['none']))for(const status of statuses){
  const target={effectiveWeather:()=>weather};const a=dex.abilities.get(ability);
  const setResult=a.onSetStatus?.call(blank,{id:status},target,{},null);
  const immunityResult=a.onImmunity?.call(blank,status==='tox'?'psn':status,target);
  const result=(setResult===false||setResult===null||immunityResult===false||immunityResult===null)?false:undefined;
  add('ability_prevention',`ability-${ability}-${weather}-${status}`,
   {attempted_status:names[status],ability:a.name||'No Ability',weather,assumptions:'Ability active and not bypassed. No existing status or other blocking effects; ignore type immunity. Isolate new major-status application.'},
   'Does this ability permit the new major status?',!(blocked.includes(status)||(ability==='leafguard'&&weather==='sunnyday')),
   result!==false&&result!==null,'data/abilities.ts:'+ability+'.onSetStatus/onImmunity');
 }
 for(const terrain of ['electricterrain','mistyterrain'])for(const grounded of [false,true])for(const semi of [false,true])for(const status of statuses){
  const target={isGrounded:()=>grounded,isSemiInvulnerable:()=>semi};
  const result=dex.moves.get(terrain).condition.onSetStatus.call(blank,{id:status},target,{},{});
  add('terrain_prevention',`terrain-${terrain}-${grounded}-${semi}-${status}`,
   {terrain,grounded,semi_invulnerable:semi,attempted_status:names[status],assumptions:'No existing status or other blocking effects. Isolate the terrain status gate; this is not a claim that a move reaches a semi-invulnerable target.'},
   'Does the terrain gate permit this new major status?',!(grounded&&!semi&&(terrain==='mistyterrain'||status==='slp')),
   result!==false&&result!==null,'data/moves.ts:'+terrain+'.condition.onSetStatus');
 }
 for(const ability of ['owntempo','innerfocus'])for(const volatile of ['confusion','flinch']){
  const result=dex.abilities.get(ability).onTryAddVolatile.call(blank,{id:volatile},{});
  add('volatile_prevention',`volatile-${ability}-${volatile}`,
   {ability:dex.abilities.get(ability).name,new_volatile:volatile,assumptions:'Active unsuppressed ability; no other prevention.'},
   'Does the ability permit this volatile condition?',!(ability==='owntempo'&&volatile==='confusion'||ability==='innerfocus'&&volatile==='flinch'),
   result!==false&&result!==null,'data/abilities.ts:'+ability+'.onTryAddVolatile');
 }
 for(const grounded of [false,true])for(const volatile of ['confusion','flinch']){
  const result=dex.moves.get('mistyterrain').condition.onTryAddVolatile.call(blank,{id:volatile},
    {isGrounded:()=>grounded,isSemiInvulnerable:()=>false},{},{effectType:'Move',secondaries:[]});
  add('volatile_prevention',`volatile-misty-${grounded}-${volatile}`,
   {terrain:'Misty Terrain',grounded,new_volatile:volatile,assumptions:'Not semi-invulnerable; no other prevention.'},
   'Does the terrain permit this new volatile condition?',!(grounded&&volatile==='confusion'),result!==false&&result!==null,
   'data/moves.ts:mistyterrain.condition.onTryAddVolatile');
 }
 for(const umbrella of [false,true])for(const status of statuses){
  const result=dex.conditions.get('sunnyday').onImmunity.call(blank,status==='tox'?'psn':status,{hasItem:x=>umbrella&&x==='utilityumbrella'});
  add('sun_freeze',`sun-${umbrella}-${status}`,
   {weather:'Sunny Day',item:umbrella?'active Utility Umbrella':'none',attempted_status:names[status],assumptions:'No type immunity, ability, terrain, existing status, or other prevention. Isolate the weather gate.'},
   'Does this weather/item combination permit the new major status?',umbrella||status!=='frz',result!==false&&result!==null,
   'data/conditions.ts:sunnyday.onImmunity');
 }
 // Controlled live Pokemon methods: no battle rounds, team legality or sampled outcomes are claimed.
 const b=new Battle({formatid:'gen9customgame',seed:[2026,10,21,195]});
 for(const side of ['p1','p2'])b.setPlayer(side,{name:side,team:[{species:'Mew',ability:'No Ability',moves:['splash']}]});
 const p=b.p1.active[0],source=b.p2.active[0];
 function reset(){p.status='';p.statusState={};p.types=['Normal'];p.terastallized='';p.hp=p.maxhp;p.ability='noability';source.ability='noability';source.types=['Normal'];source.moveThisTurn='';source.moveSlots=['thunderwave','glare','spore','willowisp','toxic'].map(id=>({move:b.dex.moves.get(id).name,id,pp:99,maxpp:99,target:'normal',disabled:false,used:false}));b.log.length=0;}
 for(const old of ['',...statuses])for(const status of statuses){
  reset();p.status=old;p.statusState={id:old};
  const result=!!p.trySetStatus(status,source);
  add('major_status_coexistence',`existing-${old||'none'}-${status}`,
   {existing_major_status:old?names[old]:'none',attempted_status:names[status],assumptions:'Normal-type healthy target except stated major status. No ability/item/terrain/weather effects. Standard status infliction, not Rest or a scripted status replacement.'},
   'Can this attempt newly establish the requested major status?',old==='',result,'sim/pokemon.ts:trySetStatus/setStatus');
 }
 for(const original of defs)for(const status of ['psn','tox'])for(const corrosion of [false,true]){
  reset();p.types=original;source.ability=corrosion?'corrosion':'noability';
  const result=!!p.trySetStatus(status,source);
  add('corrosion',`corrosion-${original.join('-')}-${status}-${corrosion}`,
   {defender_types:original,source_ability:corrosion?'Corrosion':'No Ability',attempted_status:names[status],
    assumptions:'No existing status, other abilities/items/fields. Status-infliction gate reached; not a Poison-type damaging hit and not a move accuracy check.'},
   'Can the source establish this poison status?',corrosion||!original.some(t=>['Poison','Steel'].includes(t)),result,
   'sim/pokemon.ts:setStatus Corrosion branch');
 }
 for(const status of statuses)for(const tera of [...types,'Stellar']){
  reset();p.status=status;p.statusState={id:status};p.teraType=tera;b.actions.terastallize(p);
  add('tera_preservation',`tera-retain-${status}-${tera}`,
   {existing_major_status:names[status],new_tera_type:tera,assumptions:'Successful Terastallization; no ability/item/other status cure.'},
   'Does the existing major status remain after Terastallization?',true,p.status===status,'sim/battle-actions.ts:terastallize');
 }
 // Move gating matters: Ground is not intrinsically paralysis-immune, but Thunder Wave has Electric immunity.
 for(const original of defs)for(const move of ['thunderwave','glare','spore','willowisp','toxic']){
  reset();p.types=original;
  const m=b.dex.getActiveMove(move);m.accuracy=true;m.alwaysHit=true;
  b.actions.runMove(m,source,1);
  const status={thunderwave:'par',glare:'par',spore:'slp',willowisp:'brn',toxic:'tox'}[move];
  const expected=!original.some(t=>immune[status].includes(t))&&!(move==='thunderwave'&&original.includes('Ground'))&&!(move==='spore'&&original.includes('Grass'));
  add('move_specific_infliction',`move-${move}-${original.join('-')}`,
   {defender_types:original,move:dex.moves.get(move).name,assumptions:'Move used by an unmodified opposing Normal-type source; accuracy forced successful; no existing status, ability, item, substitute, terrain, weather, Protect or other effects. Intrinsic Gen9 mechanics; format move bans are NOT applied (Spore is not legal in Gen9OU).'},
   'Does this move establish its major status on the target?',expected,p.status===status,'sim/battle-actions.ts:runMove; data/moves.ts:'+move);
 }
 b.destroy();assert.equal(out.filter(r=>r.rule_id==='type_tera_immunity').length,20520);
 return out;
}
module.exports={core};
if(require.main===module)console.log(JSON.stringify(core()));
