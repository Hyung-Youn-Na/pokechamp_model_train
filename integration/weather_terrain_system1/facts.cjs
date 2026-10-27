/* EP197 controlled Gen9 knowledge facts; direct hooks and synthetic Battle methods.
 * Underlying Pokémon Showdown source is MIT licensed. No legal-set claim.
 * Hook stubs isolate exactly the stated gate; expected values are independent.
 */
const assert=require('node:assert/strict');
const {Dex,Battle}=require('../../pokemon-showdown/dist/sim');
const dex=Dex.forFormat('gen9ou');
function facts(){
 const rows=[],noop=()=>{};
 const weatherIds=['','sunnyday','raindance','sandstorm','snowscape'];
 function add(id,rule_id,state,question,options,answer,source,observed){
  assert(options.includes(answer));assert.equal(new Set(options).size,options.length);
  rows.push({id,rule_id,state:{generation:9,...state},question,options,answer,evidence:{source,observed,
   oracle:'Pinned direct hook or controlled actual Battle; no legal species/set claim'}});
 }
 function field(weather){return {isWeather:query=>Array.isArray(query)?query.includes(weather):query===weather};}
 for(const terrain of ['electricterrain','mistyterrain'])for(const grounded of [false,true])for(const status of ['slp','brn']){
  const result=dex.moves.get(terrain).condition.onSetStatus.call({add:noop},{id:status},
   {isGrounded:()=>grounded,isSemiInvulnerable:()=>false},{},{effectType:'Move'});
  const blocked=result===false;assert.equal(blocked,grounded&&(terrain==='mistyterrain'||status==='slp'));
  add(`status_${terrain}_${grounded}_${status}`,'terrain_status_prevention',{terrain,grounded,new_status:status,
   assumptions:'Target not semi-invulnerable; no existing status, type immunity, item or ability. Isolate terrain gate, not OU move legality'},
   'Does this terrain block the new status?', ['Yes','No'],blocked?'Yes':'No',
   `data/moves.ts:${terrain}.condition.onSetStatus`,{blocked});
 }
 for(const grounded of [false,true]){
  const result=dex.moves.get('mistyterrain').condition.onTryAddVolatile.call({add:noop},{id:'confusion'},
   {isGrounded:()=>grounded,isSemiInvulnerable:()=>false},{},{effectType:'Move',secondaries:[]});
  assert.equal(result===null,grounded);
  add(`confusion_misty_${grounded}`,'terrain_confusion_prevention',{terrain:'Misty Terrain',grounded,new_volatile:'Confusion',
   assumptions:'Not semi-invulnerable; no other prevention'},'Does this terrain block new confusion?', ['Yes','No'],grounded?'Yes':'No',
   'data/moves.ts:mistyterrain.condition.onTryAddVolatile',{blocked:result===null});
 }
 for(const grounded of [false,true])for(const priority of [0,1]){
  const result=dex.moves.get('psychicterrain').condition.onTryHit.call({dex,add:noop,hint:noop},
   {isGrounded:()=>grounded,isSemiInvulnerable:()=>false,isAlly:()=>false},{},
   {id:priority?'quickattack':'tackle',priority,target:'normal'});
  const blocked=result===null;assert.equal(blocked,grounded&&priority>0);
  add(`psychic_priority_${grounded}_${priority}`,'psychic_priority_prevention',{terrain:'Psychic Terrain',target_grounded:grounded,
   integer_move_priority:priority,assumptions:'Opposing targeted move; target not semi-invulnerable. No other blocking effects'},
   'Does this terrain block the move?', ['Yes','No'],blocked?'Yes':'No','data/moves.ts:psychicterrain.condition.onTryHit',{blocked});
 }
 for(const [weather,rock] of [['sunnyday','heatrock'],['raindance','damprock'],['sandstorm','smoothrock'],['snowscape','icyrock']])for(const extended of [false,true]){
  const duration=dex.conditions.get(weather).durationCallback.call({}, {hasItem:id=>extended&&id===rock});
  assert.equal(duration,extended?8:5);
  add(`duration_${weather}_${extended}`,'weather_duration',{weather,setter_item:extended?dex.items.get(rock).name:'None',
   assumptions:'New ordinary weather; item active when set; no subsequent overwrite or suppression'},
   'What is its initial duration, including the turn it is set?',['5 turns','8 turns','Indefinite'],`${duration} turns`,
   `data/conditions.ts:${weather}.durationCallback`,{duration});
 }
 for(const terrain of ['electricterrain','grassyterrain','mistyterrain','psychicterrain'])for(const extended of [false,true]){
  const duration=dex.moves.get(terrain).condition.durationCallback.call({}, {hasItem:id=>extended&&id==='terrainextender'});
  assert.equal(duration,extended?8:5);
  add(`duration_${terrain}_${extended}`,'terrain_duration',{terrain,setter_item:extended?'Active Terrain Extender':'None'},
   'What is its initial duration, including the turn it is set?',['5 turns','8 turns','Indefinite'],`${duration} turns`,
   `data/moves.ts:${terrain}.condition.durationCallback`,{duration});
 }
 for(const [ability,matching] of [['swiftswim','raindance'],['chlorophyll','sunnyday'],['sandrush','sandstorm'],['slushrush','snowscape']])for(const weather of ['',matching,'other']){
  const effective=weather==='other'?(matching==='raindance'?'sunnyday':'raindance'):weather;
  const result=dex.abilities.get(ability).onModifySpe.call({field:field(effective),chainModify:x=>x},100,{effectiveWeather:()=>effective});
  const multiplier=result??1;assert.equal(multiplier,effective===matching?2:1);
  add(`speed_${ability}_${weather||'none'}`,'weather_speed_ability',{ability:dex.abilities.get(ability).name,effective_weather:effective||'None',
   assumptions:'Ability active; no suppression or other speed modifier'},'What Speed multiplier does this ability apply?',
   ['1','1.5','2'],String(multiplier),`data/abilities.ts:${ability}.onModifySpe`,{multiplier});
 }
 for(const attackerUmbrella of [false,true])for(const defenderUmbrella of [false,true]){
  const result=dex.conditions.get('sunnyday').onWeatherModifyDamage.call({debug:noop,chainModify:x=>x},100,
   {hasItem:id=>attackerUmbrella&&id==='utilityumbrella'},{hasItem:id=>defenderUmbrella&&id==='utilityumbrella'},
   {id:'hydrosteam',type:'Water'});
  const multiplier=result??1,expected=!attackerUmbrella?1.5:defenderUmbrella?1:0.5;assert.equal(multiplier,expected);
  add(`hydrosteam_${attackerUmbrella}_${defenderUmbrella}`,'hydro_steam_umbrella',{weather:'Unsuppressed Sunny Day',move:'Hydro Steam',
   attacker_item:attackerUmbrella?'Active Utility Umbrella':'None',defender_item:defenderUmbrella?'Active Utility Umbrella':'None'},
   'What damage multiplier does this weather hook apply?', ['0.5','1','1.5'],String(expected),
   'data/conditions.ts:sunnyday.onWeatherModifyDamage',{multiplier});
 }
 // Actual Pokemon.effectiveWeather supplies Utility Umbrella behavior, rather than copying it into a stub.
 const b=new Battle({formatid:'gen9customgame',seed:[2026,10,21,197]});
 try{
  for(const side of ['p1','p2'])b.setPlayer(side,{name:side,team:[{species:'Mew',ability:'No Ability',moves:['splash']}]});
  const p=b.p1.active[0],q=b.p2.active[0];
  function weatherSet(weather){b.field.clearWeather();if(weather)b.field.setWeather(weather,p);}
  for(const weather of weatherIds)for(const umbrella of [false,true]){
   weatherSet(weather);p.item=umbrella?'utilityumbrella':'';
   const m=dex.getActiveMove('weatherball');m.onModifyType.call(b,m,p);m.onModifyMove.call(b,m,p);
   const suppressed=umbrella&&['sunnyday','raindance'].includes(weather);
   const expectedType=suppressed?'Normal':({'':'Normal',sunnyday:'Fire',raindance:'Water',sandstorm:'Rock',snowscape:'Ice'}[weather]);
   const expectedPower=!weather||suppressed?50:100;assert.equal(m.type,expectedType);assert.equal(m.basePower,expectedPower);
   const answer=`${expectedType}, ${expectedPower}`;
   add(`weatherball_${weather||'none'}_${umbrella}`,'weather_ball',{weather:weather||'None',user_item:umbrella?'Active Utility Umbrella':'None',
    assumptions:'No weather-suppressing ability; no other move transformations'},
    'What are Weather Ball\'s type and base power before damage modifiers?',
    ['Normal, 50','Fire, 100','Water, 100','Rock, 100','Ice, 100'],answer,'data/moves.ts:weatherball; sim/pokemon.ts:effectiveWeather',
    {type:m.type,base_power:m.basePower,effective_weather:p.effectiveWeather()});
  }
  p.item='';
  for(const move of ['thunder','hurricane'])for(const weather of ['','sunnyday','raindance'])for(const umbrella of [false,true]){
   weatherSet(weather);q.item=umbrella?'utilityumbrella':'';
   const m=dex.getActiveMove(move);m.onModifyMove.call(b,m,p,q);
   const expected=umbrella||!weather?70:weather==='raindance'?true:50;assert.equal(m.accuracy,expected);
   add(`accuracy_${move}_${weather||'none'}_${umbrella}`,'weather_accuracy',{move:m.name,weather:weather||'None',
    target_item:umbrella?'Active Utility Umbrella':'None',assumptions:'No weather suppression; isolate move accuracy property, not protection/immunity/target reachability'},
    'What is the move accuracy property after weather adjustment?', ['50','70','Bypasses the ordinary accuracy check'],
    expected===true?'Bypasses the ordinary accuracy check':String(expected),`data/moves.ts:${move}.onModifyMove`,{accuracy:m.accuracy});
  }
  q.item='';
  for(const weather of ['sandstorm','snowscape']){
   weatherSet(weather);p.types=['Normal'];p.hp=p.maxhp;const before=p.hp;
   b.eachEvent('Weather');const damage=before-p.hp;const expected=weather==='sandstorm'?Math.floor(p.baseMaxhp/16):0;
   assert.equal(damage,expected);
   add(`passive_${weather}`,'weather_passive_damage',{weather,type:'Normal',ability:'No Ability',item:'None',hp:'Initially full',
    assumptions:'No other effects; one weather residual, not a full turn'},
    'Does this weather alone cause passive HP damage?', ['Yes, 1/16 base maximum HP with integer rounding','No'],
    weather==='sandstorm'?'Yes, 1/16 base maximum HP with integer rounding':'No','data/conditions.ts:sandstorm/snowscape; Battle.eachEvent Weather',
    {before,after:p.hp,damage,base_max_hp:p.baseMaxhp});
  }
  weatherSet('');
  for(const grounded of [false,true])for(const semi of [false,true])for(const missing of [0,5,40]){
   p.hp=p.maxhp-missing;p.isGrounded=()=>grounded;p.isSemiInvulnerable=()=>semi;
   const before=p.hp;dex.moves.get('grassyterrain').condition.onResidual.call(b,p);
   const healed=p.hp-before,expected=grounded&&!semi?Math.min(missing,Math.floor(p.baseMaxhp/16)):0;assert.equal(healed,expected);
   add(`grassy_heal_${grounded}_${semi}_${missing}`,'grassy_healing',{terrain:'Grassy Terrain',grounded,semi_invulnerable:semi,
    base_max_hp:p.baseMaxhp,max_hp:p.maxhp,current_hp:before,assumptions:'No other effects or healing prevention'},
    'How much HP is actually restored by this terrain residual?', [...new Set([0,5,Math.floor(p.baseMaxhp/16),40].map(String))],
    String(expected),'data/moves.ts:grassyterrain.condition.onResidual; Battle.heal',{healed});
  }
  delete p.isGrounded;delete p.isSemiInvulnerable;p.hp=p.maxhp;
  for(const ability of ['cloudnine','airlock']){
   weatherSet('raindance');p.ability=ability;p.abilityState={id:ability,target:p};
   const stored=b.field.weather,effective=b.field.effectiveWeather();assert.equal(stored,'raindance');assert.equal(effective,'');
   p.ability='noability';assert.equal(b.field.effectiveWeather(),'raindance');
   add(`suppression_${ability}`,'weather_suppression',{weather:'Rain Dance with duration remaining',active_ability:dex.abilities.get(ability).name,
    assumptions:'No competing effect; ability then stops suppressing weather before duration expires'},
    'Which describes the weather state?', ['Deleted permanently','Stored rain is suppressed, then resumes','Terrain is removed'],
    'Stored rain is suppressed, then resumes','sim/field.ts:effectiveWeather/suppressingWeather',{stored,effective,resumed:b.field.effectiveWeather()});
  }
  weatherSet('raindance');b.field.setTerrain('electricterrain',p);
  assert.equal(b.field.weather,'raindance');assert.equal(b.field.terrain,'electricterrain');
  add('coexist','field_coexistence',{first:'Rain Dance established',next:'Electric Terrain successfully established'},
   'What remains active?', ['Rain and Electric Terrain','Only Rain','Only Electric Terrain'], 'Rain and Electric Terrain',
   'sim/field.ts:setWeather/setTerrain',{weather:b.field.weather,terrain:b.field.terrain});
  b.field.setTerrain('grassyterrain',p);assert.equal(b.field.terrain,'grassyterrain');assert.equal(b.field.weather,'raindance');
  add('terrain_overwrite','field_overwrite',{weather:'Rain',terrain:'Electric Terrain',next:'Grassy Terrain successfully established'},
   'What remains active?', ['Rain and Grassy Terrain','Rain and both terrains','Only Grassy Terrain'], 'Rain and Grassy Terrain',
   'sim/field.ts:setTerrain',{weather:b.field.weather,terrain:b.field.terrain});
  b.field.setWeather('sunnyday',p);assert.equal(b.field.weather,'sunnyday');assert.equal(b.field.terrain,'grassyterrain');
  add('weather_overwrite','field_overwrite',{weather:'Rain',terrain:'Grassy Terrain',next:'Sunny Day successfully established'},
   'What remains active?', ['Sun and Grassy Terrain','Rain and Sun and Grassy Terrain','Only Sun'], 'Sun and Grassy Terrain',
   'sim/field.ts:setWeather',{weather:b.field.weather,terrain:b.field.terrain});
 }finally{b.destroy();}
 for(const weather of weatherIds){
  const ctx={field:field(weather),debug:noop,chainModify:x=>x};
  const blizzard=dex.getActiveMove('blizzard');blizzard.onModifyMove.call(ctx,blizzard);
  const accuracy=weather==='snowscape'?true:70;assert.equal(blizzard.accuracy,accuracy);
  add(`blizzard_${weather||'none'}`,'blizzard_accuracy',{weather:weather||'None',move:'Blizzard',assumptions:'Weather is unsuppressed; isolate accuracy property'},
   'What is Blizzard\'s accuracy property?', ['70','Bypasses the ordinary accuracy check'],accuracy===true?'Bypasses the ordinary accuracy check':'70',
   'data/moves.ts:blizzard.onModifyMove',{accuracy});
  const veil=dex.moves.get('auroraveil').onTry.call(ctx);assert.equal(veil,weather==='snowscape');
  add(`veil_${weather||'none'}`,'aurora_veil_weather_gate',{weather:weather||'None',move:'Aurora Veil',assumptions:'Weather unsuppressed; no other failure condition'},
   'Does the weather permit establishing Aurora Veil?', ['Yes','No'],veil?'Yes':'No','data/moves.ts:auroraveil.onTry',{permitted:veil});
  let charged=false;const solar=dex.moves.get('solarbeam');
  const result=solar.onTryMove.call({add:noop,attrLastMove:noop,addMove:noop,runEvent:()=>true},
   {removeVolatile:()=>false,effectiveWeather:()=>weather,addVolatile:()=>{charged=true;}},{},solar);
  assert.equal(charged,weather!=='sunnyday');assert.equal(result,charged?null:undefined);
  add(`solarbeam_${weather||'none'}`,'solar_beam_charge',{weather:weather||'None',move:'Solar Beam',
   assumptions:'First turn; no Power Herb or other charge bypass, no weather suppression or Utility Umbrella'},
   'Does Solar Beam require its charge turn?', ['Yes','No'],charged?'Yes':'No','data/moves.ts:solarbeam.onTryMove',{charged});
 }
 assert.equal(new Set(rows.map(x=>x.id)).size,rows.length);return rows;
}
module.exports={facts};
if(require.main===module){const r=facts();console.log(JSON.stringify({passed:true,count:r.length,rules:[...new Set(r.map(x=>x.rule_id))]}));}
