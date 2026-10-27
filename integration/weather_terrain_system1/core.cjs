'use strict';
const assert=require('node:assert/strict');
const {Dex,Pokemon}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
const types=dex.types.all().map(t=>t.name).filter(t=>t!=='Stellar').sort();
const defs=types.map(t=>[t]);for(let i=0;i<18;i++)for(let j=i+1;j<18;j++)defs.push([types[i],types[j]]);
const weather=['none','sunnyday','raindance','sandstorm','snowscape'];
const terrain=['none','electricterrain','grassyterrain','mistyterrain','psychicterrain'];
const powerLabels=['0.5x','1x','approximately 1.3x','1.5x'];
function label(v){if(Array.isArray(v)){assert.deepEqual(v,[5325,4096]);return 'approximately 1.3x';}return `${v??1}x`;}
function core(){
 const rows=[];
 function add(id,rule,state,question,options,expected,observed,source,evidence={}){
  assert.deepEqual(observed,expected,id);assert(options.includes(observed));assert.equal(new Set(options).size,options.length);
  rows.push({id,rule_id:rule,state,question,options,answer:observed,evidence:{source,expected,observed,...evidence}});
 }
 const p={types:[],terastallized:'',addedType:'',getTypes:Pokemon.prototype.getTypes,
  hasType(t){return this.getTypes().includes(t);},battle:{gen:9,runEvent:(_e,_t,_s,_f,x)=>x}};
 for(const original of defs)for(const tera of [null,...types,'Stellar']){
  p.types=original;p.terastallized=tera||'';const effective=tera&&tera!=='Stellar'?[tera]:original;
  const shared={generation:9,original_types:original,tera_type:tera,
    assumptions:'Weather active and unsuppressed. No abilities/items or other stat/damage effects. Test current defensive typing only; synthetic type/Tera combination.'};
  for(const [w,stat,boostType] of [['sandstorm','SpD','Rock'],['snowscape','Def','Ice']]){
   const result=dex.conditions.get(w)['onModify'+stat].call({field:{isWeather:x=>x===w},modify:(x,n)=>x*n},200,p);
   const observed=(result??200)/200;const expected=effective.includes(boostType)?1.5:1;
   add(`stat-${w}-${original.join('-')}-${tera||'none'}`,'weather_defensive_stat',
    {...shared,weather:w,stat,stat_before_weather:200},`What multiplier does this weather apply to ${stat}?`,
    ['0.5x','1x','1.5x','2x'],label(expected),label(observed),`data/conditions.ts:${w}.onModify${stat}; sim/pokemon.ts:getTypes`);
  }
  const expected=!effective.some(t=>['Rock','Ground','Steel'].includes(t));
  const observed=dex.getImmunity('sandstorm',p);
  add(`sand-typing-${original.join('-')}-${tera||'none'}`,'sand_type_immunity',
   {...shared,weather:'Sandstorm'},'Does this typing permit sandstorm residual damage (no intrinsic immunity)?',
   ['Yes','No'],expected?'Yes':'No',observed?'Yes':'No','sim/dex.ts:getImmunity; data/typechart.ts:sandstorm');
 }
 for(const w of weather)for(const type of types)for(const attackUmbrella of [false,true])for(const defendUmbrella of [false,true]){
  const a={hasItem:x=>attackUmbrella&&x==='utilityumbrella'},d={hasItem:x=>defendUmbrella&&x==='utilityumbrella'};
  const result=w==='none'?undefined:dex.conditions.get(w).onWeatherModifyDamage?.call({debug(){},chainModify:x=>x},100,a,d,{id:'genericattack',type});
  let expected=1;
  if(!defendUmbrella){if(w==='sunnyday')expected=type==='Fire'?1.5:type==='Water'?0.5:1;
   if(w==='raindance')expected=type==='Water'?1.5:type==='Fire'?0.5:1;}
  add(`damage-${w}-${type}-${attackUmbrella}-${defendUmbrella}`,'weather_damage_modifier',
   {weather:w,attack_type:type,attacker_item:attackUmbrella?'Utility Umbrella':'None',defender_item:defendUmbrella?'Utility Umbrella':'None',
    assumptions:'Final move type is stated. Ordinary damaging move, not Hydro Steam or another special-case move. Weather unsuppressed; items active. Exclude type effectiveness, STAB, abilities and all other damage effects.'},
   'What damage multiplier does this weather/item combination apply?', ['0.5x','1x','1.5x','2x'],label(expected),label(result),
   'data/conditions.ts:'+w+'.onWeatherModifyDamage');
 }
 for(const t of terrain)for(const type of types)for(const ga of [false,true])for(const gd of [false,true])for(const sa of [false,true])for(const sd of [false,true]){
  const a={isGrounded:()=>ga,isSemiInvulnerable:()=>sa},d={isGrounded:()=>gd,isSemiInvulnerable:()=>sd};
  const result=t==='none'?undefined:dex.moves.get(t).condition.onBasePower?.call({debug(){},chainModify:x=>x},100,a,d,{id:'genericattack',type});
  let expected='1x';
  if(t==='electricterrain'&&type==='Electric'&&ga&&!sa)expected='approximately 1.3x';
  if(t==='psychicterrain'&&type==='Psychic'&&ga&&!sa)expected='approximately 1.3x';
  if(t==='grassyterrain'&&type==='Grass'&&ga)expected='approximately 1.3x';
  if(t==='mistyterrain'&&type==='Dragon'&&gd&&!sd)expected='0.5x';
  add(`terrain-${t}-${type}-${ga}-${gd}-${sa}-${sd}`,'terrain_base_power',
   {terrain:t,final_move_type:type,attacker_grounded:ga,defender_grounded:gd,attacker_semi_invulnerable:sa,defender_semi_invulnerable:sd,
    assumptions:'Generic damaging move; no move-specific terrain exceptions, abilities/items or other modifiers. Inspect only this terrain base-power gate, not whether the move can execute or hit a semi-invulnerable Pokemon.'},
   'What base-power modifier does this terrain apply?',powerLabels,expected,label(result),`data/moves.ts:${t}.condition.onBasePower`,{raw_modifier:result??1});
 }
 for(const move of ['earthquake','bulldoze','magnitude','earthpower'])for(const ground of [false,true])for(const semi of [false,true]){
  const result=dex.moves.get('grassyterrain').condition.onBasePower.call({debug(){},chainModify:x=>x},100,
   {isGrounded:()=>true},{isGrounded:()=>ground,isSemiInvulnerable:()=>semi},{id:move,type:'Ground'});
  const expected=move!=='earthpower'&&ground&&!semi?0.5:1;
  add(`grassy-ground-${move}-${ground}-${semi}`,'grassy_ground_move_exception',
   {terrain:'Grassy Terrain',move:dex.moves.get(move).name,defender_grounded:ground,defender_semi_invulnerable:semi,
    assumptions:'Only terrain base-power gate; no other effects. Does not imply Ground moves can hit ungrounded or semi-invulnerable targets.'},
   'What base-power modifier does Grassy Terrain apply to this move?',powerLabels,label(expected),label(result),
   'data/moves.ts:grassyterrain.condition.onBasePower');
 }
 assert.equal(rows.length,12076);
 return rows;
}
module.exports={core};
if(require.main===module)console.log(JSON.stringify({passed:true,count:core().length}));
