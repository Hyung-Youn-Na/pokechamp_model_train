/* EP-195 intrinsic Gen9 mechanics. Pokémon Showdown is MIT licensed.
 * These are direct, controlled hook calls, NOT simulated legal battles. Stubs
 * capture damage/healing/modifiers, disable unrelated effects, and enumerate
 * random branches. All labels are asserted against independently chosen values.
 * Integer HP examples avoid rounding and HP caps. No evidence enters state.
 */
const assert = require('node:assert/strict');
const {Dex} = require('../../pokemon-showdown/dist/sim/dex');
const {Battle} = require('../../pokemon-showdown/dist/sim/battle');
const dex = Dex.forFormat('gen9ou');

function facts() {
  const rows = [];
  const condition = id => dex.conditions.get(id);
  const ability = id => dex.abilities.get(id);
  const item = id => dex.items.get(id);
  const noop = () => {};
  function add(id, rule, state, question, options, answer, source, observed) {
    assert.equal(new Set(options).size, options.length);
    assert(options.includes(answer));
    rows.push({id, rule_id: rule, state: {generation: 9, ...state}, question, options, answer,
      evidence: {source, observed, oracle: 'Direct built Showdown hook; controlled stubs, not a battle'}});
  }
  for (const hp of [160, 320, 480]) {
    for (const status of ['brn', 'psn']) {
      let damage;
      condition(status).onResidual.call({damage: x => {damage = x;}}, {baseMaxhp: hp});
      const expected = hp / (status === 'brn' ? 16 : 8);
      assert.equal(damage, expected);
      add(`${status}_tick_${hp}`, 'residual_damage', {status, base_max_hp: hp, current_hp: hp,
        modifiers: 'No ability, item or other damage modifiers'},
      'How much HP is lost at this status residual?', ['0', String(hp/16), String(hp/8), String(hp/4)],
      String(expected), `data/conditions.ts:${status === 'brn' ? 15 : 133}`, {damage});
    }
    for (const stage of [0, 1, 2, 14, 15]) {
      let damage; const effectState = {stage};
      condition('tox').onResidual.call({effectState, damage: x => {damage=x;},
        clampIntRange: (x, min) => Math.max(min, Math.floor(x))}, {baseMaxhp: hp});
      const next = Math.min(stage+1,15), expected = hp/16*next;
      assert.equal(damage, expected); assert.equal(effectState.stage, next);
      add(`tox_tick_${hp}_${stage}`, 'toxic_damage', {status: 'tox', base_max_hp: hp,
        current_hp: hp, toxic_stage_before_tick: stage, modifiers: 'None'},
      'How much HP is lost at the next bad-poison residual?',
      [...new Set([0,hp/16,expected,hp].map(String))], String(expected), 'data/conditions.ts:154',
      {damage, stage_after:effectState.stage});
    }
  }
  for (const speed of [100, 200, 300]) {
    for (const quickFeet of [false,true]) {
      const statusPokemon = {status:'par',hasAbility: id => id === 'quickfeet' && quickFeet};
      let modifier = 1;
      if (quickFeet) modifier=ability('quickfeet').onModifySpe.call({chainModify:x=>x},speed,statusPokemon);
      const observed=condition('par').onModifySpe.call({finalModify:x=>x},speed*modifier,statusPokemon);
      const expected=speed*(quickFeet?1.5:0.5); assert.equal(observed,expected);
      add(`par_speed_${speed}_${quickFeet}`, 'paralysis_speed', {status:'par',speed_before_ability_and_status:speed,
        ability:quickFeet?'Quick Feet':'None',other_speed_modifiers:'None'}, 'What is the resulting Speed?',
      [speed*0.5,speed,speed*1.5].map(String),String(expected),'data/conditions.ts:30; data/abilities.ts:3683',{speed:observed});
    }
  }
  for (const status of ['brn','psn','tox','par','slp','frz']) {
    const modifier=ability('guts').onModifyAtk.call({chainModify:x=>x},100,{status});
    assert.equal(modifier,1.5);
    add(`guts_${status}`,'guts_attack',{status,ability:'Active Guts',other_attack_modifiers:'None'},
      'What Attack-stat multiplier does Guts apply?', ['0.5','1','1.5','2'],'1.5','data/abilities.ts:1717',{modifier});
  }
  // A minimal custom-game Battle supplies the complete damage event pipeline.
  // Direct status assignment is intentional: this tests damage of existing status,
  // not legal acquisition. Random damage is fixed at its maximum, crits disabled.
  const battle=new Battle({formatid:'gen9customgame'});
  try {
    for(const i of [1,2])battle.setPlayer(`p${i}`,{name:`p${i}`,team:[{species:'Mew',
      ability:'Synchronize',moves:['tackle','facade'],nature:'Serious',evs:{}}]});
    battle.randomizer=x=>x;
    const attacker=battle.p1.active[0],defender=battle.p2.active[0];
    function damage(status,abilityId,moveId,special=false){
      attacker.setAbility(abilityId);attacker.status=status;
      const move=battle.dex.getActiveMove(moveId);move.willCrit=false;
      if(special)move.category='Special';
      return battle.actions.getDamage(attacker,defender,move);
    }
    const normal=damage('','synchronize','tackle'),burned=damage('brn','synchronize','tackle');
    assert.equal(burned,Math.floor(normal/2));assert(burned>0 && burned<normal);
    add('burn_physical_modifier','burn_physical_damage',{status:'brn',ability:'No Guts',
      move:'Ordinary physical move, not Facade',other_damage_modifiers:'None'},
      'What damage modifier does burn apply before integer rounding?',['0.5','1','1.5','2'],'0.5',
      'sim/battle-actions.ts:1814',{oracle:'Actual Battle.actions.getDamage; Mew pair; Tackle; maximum random roll; no crit',normal,burned});
    const gutsBurn=damage('brn','guts','tackle'),gutsPoison=damage('psn','guts','tackle');
    assert.equal(gutsBurn,gutsPoison);assert(gutsBurn>normal);
    add('burn_guts_damage','guts_burn_exception',{status:'brn',ability:'Active Guts',move:'Ordinary physical move'},
      'Does burn still apply its physical-damage halving penalty?',['Yes','No'],'No',
      'sim/battle-actions.ts:1814',{oracle:'Actual getDamage; equal Guts boost for burn/poison',gutsBurn,gutsPoison});
    const facadeBurn=damage('brn','synchronize','facade'),facadePar=damage('par','synchronize','facade');
    const facadeNormal=damage('','synchronize','facade');
    assert.equal(facadeBurn,facadePar);assert(facadeBurn>facadeNormal);
    add('burn_facade','facade_burn_exception',{status:'brn',ability:'No Guts',move:'Facade'},
      'Does burn halve Facade damage in Generation 9?',['Yes','No'],'No',
      'sim/battle-actions.ts:1814; data/moves.ts:5224',
      {oracle:'Actual getDamage; Facade power bonus active for both burn/paralysis',facadeBurn,facadePar,facadeNormal});
    const specialNormal=damage('','synchronize','tackle',true),specialBurn=damage('brn','synchronize','tackle',true);
    assert.equal(specialNormal,specialBurn);
    add('burn_special','burn_special_damage',{status:'brn',ability:'None affecting damage',move_category:'Special'},
      'Does burn apply its physical-damage halving penalty to this special move?',['Yes','No'],'No',
      'sim/battle-actions.ts:1814',{oracle:'Actual getDamage; fixed Normal-type base-power40 move with Special category',specialNormal,specialBurn});
  } finally {battle.destroy();}
  // Enumerate both probability outcomes; capture the probability itself, not a sample frequency.
  for (const [id,num,den,expected] of [['par',1,4,'25%'],['frz',1,5,'20%'],['confusion',33,100,'33%']]) {
    const outcomes=[];
    for (const branch of [false,true]) {
      let probability, cured=false, damagePower=null;
      const pokemon={statusState:{time:3},volatiles:{confusion:{time:3}},
        cureStatus(){cured=true;},removeVolatile:noop};
      const ctx={add:noop,randomChance:(n,d)=>{probability=[n,d];return branch;},
        actions:{getConfusionDamage:(p,power)=>{damagePower=power;return 10;}},damage:noop,toID:x=>x};
      const result=condition(id).onBeforeMove.call(ctx,pokemon,null,{flags:{}});
      assert.deepEqual(probability,[num,den]);
      if(id==='frz'){assert.equal(cured,branch);assert.equal(result,branch?undefined:false);}
      else {assert.equal(result,branch?false:undefined);}
      if(id==='confusion')assert.equal(damagePower,branch?40:null);
      outcomes.push({random_branch:branch,blocked:result===false,cured,damage_power:damagePower});
    }
    add(`${id}_probability`,'status_probability',{status:id,phase:'This status check is reached',
      details:id==='frz'?'Move has no defrost flag':id==='confusion'?'Confusion has not expired':'No other blocking effect'},
      id==='frz'?'What is the natural-thaw probability at this check?':id==='confusion'?
      'What is the exact confusion self-hit probability in this pinned engine?':'What is the full-paralysis probability?',
      ['0%','20%','25%','33%','50%'],expected,`data/conditions.ts:${id==='par'?39:id==='frz'?99:186}`,
      {probability:[num,den],outcomes});
    if(id==='confusion')add('confusion_power','confusion_damage',{status:'confusion',outcome:'Self-hit branch'},
      'What base power is passed to the confusion damage calculator?',['20','40','60','80'],'40',
      'data/conditions.ts:190',{outcomes});
  }
  // Sleep duration is measured in reached BeforeMove checks, not calendar turns.
  const blockedCounts=[];
  for(const initial of [2,3,4]){
    const effectState={};let bounds;
    condition('slp').onStart.call({add:noop,effectState,random:(a,b)=>{bounds=[a,b];return initial;}},
      {removeVolatile:()=>false});
    assert.deepEqual(bounds,[2,5]);assert.equal(effectState.time,initial);
    let cured=false,blocked=0;const p={statusState:effectState,hasAbility:()=>false,cureStatus(){cured=true;}};
    for(let i=0;i<initial;i++)if(condition('slp').onBeforeMove.call({add:noop},p,null,{sleepUsable:false})===false)blocked++;
    assert(cured);assert.equal(blocked,initial-1);blockedCounts.push(blocked);
  }
  add('sleep_duration','sleep_duration',{status:'slp',cause:'Ordinary inflicted sleep, not Rest',ability:'None',
    move:'Not sleepUsable',duration_unit:'Reached sleep BeforeMove checks'},
    'How many ordinary move attempts are blocked before waking?',['1 to 3','Exactly 2','1 to 7','Unlimited'],
    '1 to 3','data/conditions.ts:58',{blocked_counts:blockedCounts});
  for(const usable of [false,true]){
    const result=condition('slp').onBeforeMove.call({add:noop},
      {statusState:{time:3},hasAbility:()=>false,cureStatus:noop},null,{sleepUsable:usable});
    assert.equal(result,usable?undefined:false);
    add(`sleep_usable_${usable}`,'sleep_usable',{status:'slp',still_asleep_at_check:true,move_sleepUsable:usable},
      'Does the sleep condition itself block this move?',['Yes','No'],usable?'No':'Yes','data/conditions.ts:74',{blocked:result===false});
  }
  let reset={stage:12};condition('tox').onSwitchIn.call({effectState:reset});assert.equal(reset.stage,0);
  add('toxic_switch_reset','toxic_switch',{status:'tox',event:'Normal switch out and return without cure',previous_stage:12},
    'What is the toxic stage before the next residual?',['0','1','12','Status cured'],'0','data/conditions.ts:151',{stage:reset.stage});
  for(const status of ['psn','tox']){
    let heal;const result=ability('poisonheal').onDamage.call({heal:x=>{heal=x;}},80,{baseMaxhp:160},null,{id:status});
    assert.equal(heal,20);assert.equal(result,false);
    add(`poisonheal_${status}`,'poison_heal',{status,ability:'Active Poison Heal',base_max_hp:160,current_hp:80,
      healing_restrictions:'None'},'What happens at the poison residual?',
      ['Heal 20 HP; no poison damage','Lose 20 HP','Lose 80 HP','Cure poison'],
      'Heal 20 HP; no poison damage','data/abilities.ts:3258',{healing_requested:heal,damage_blocked:result===false});
  }
  for(const status of ['brn','psn','tox']){
    const result=ability('magicguard').onDamage.call({add:noop},10,{},null,{id:status,effectType:'Status'});
    assert.equal(result,false);
    add(`magicguard_${status}`,'magic_guard_residual',{status,ability:'Active Magic Guard'},
      'Does the status residual deal damage?',['Yes','No'],'No','data/abilities.ts:2417',{damage_blocked:true});
  }
  for(const status of ['brn','par','slp','frz','psn','tox']){
    let cleared=false;ability('naturalcure').onSwitchOut.call({add:noop},
      {status,clearStatus(){cleared=true;}});assert(cleared);
    add(`naturalcure_${status}`,'natural_cure',{status,ability:'Active Natural Cure',event:'Normal switch out'},
      'What happens to the major status?',['Cured','Retained'],'Cured','data/abilities.ts:2816',{cleared});
  }
  let cures=[];
  item('lumberry').onEat.call({}, {cureStatus:()=>cures.push('major_status'),removeVolatile:x=>cures.push(x)});
  assert.deepEqual(cures,['major_status','confusion']);
  add('lum_both','lum_cure',{status:'brn',volatile:'confusion',event:'Lum Berry successfully eaten'},
    'Which conditions does the berry remove?',['Burn only','Confusion only','Both','Neither'],'Both',
    'data/items.ts:3252',{cures});
  for(const status of ['slp','brn']){
    let cured=false;item('chestoberry').onEat.call({}, {status,cureStatus(){cured=true;}});assert.equal(cured,status==='slp');
    add(`chesto_${status}`,'chesto_cure',{status,event:'Chesto Berry successfully eaten'},
      'Does Chesto Berry cure this major status?',['Yes','No'],status==='slp'?'Yes':'No','data/items.ts:847',{cured});
  }
  const shed=[];
  for(const branch of [false,true]){
    let probability,cured=false;
    ability('shedskin').onResidual.call({debug:noop,add:noop,randomChance:(n,d)=>{probability=[n,d];return branch;}},
      {hp:100,status:'brn',cureStatus(){cured=true;}});
    assert.deepEqual(probability,[33,100]);assert.equal(cured,branch);shed.push({branch,cured,probability});
  }
  add('shedskin_probability','shed_skin',{status:'brn',ability:'Active Shed Skin',hp:100,phase:'Residual ability check'},
    'What is the exact cure probability in this pinned engine?',['0%','25%','33%','50%','100%'],'33%',
    'data/abilities.ts:4124',{branches:shed});
  for(const weather of ['raindance','sunnyday','']){
    let cured=false;ability('hydration').onResidual.call({debug:noop,add:noop},
      {status:'brn',effectiveWeather:()=>weather,cureStatus(){cured=true;}});
    assert.equal(cured,weather==='raindance');
    add(`hydration_${weather||'none'}`,'hydration',{status:'brn',ability:'Active Hydration',effective_weather:weather||'None',
      phase:'Residual ability check'},'Is the status cured by Hydration?',['Yes','No'],cured?'Yes':'No',
      'data/abilities.ts:1872',{cured});
  }
  let fireCure=false;condition('frz').onDamagingHit.call({},10,{cureStatus(){fireCure=true;}},null,{type:'Fire',category:'Special'});
  assert(fireCure);
  add('freeze_fire_hit','freeze_fire_cure',{status:'frz',event:'Target takes a damaging Fire-type hit'},
    'Does this hit cure freeze?',['Yes','No'],'Yes','data/conditions.ts:117',{cured:fireCure});
  assert.equal(condition('flinch').duration,1);
  assert.equal(condition('flinch').onBeforeMove.call({add:noop,runEvent:noop},{}),false);
  add('flinch_turn','flinch_duration',{volatile:'flinch',timing:'Inflicted before the target acts this turn'},
    'Which ordinary move is stopped by this flinch?', ['This turn only','Next turn only','This and next turn'],
    'This turn only','data/conditions.ts:198',{duration:1,before_move_result:false});
  const rest=dex.moves.get('rest');
  let healed,restState={},restCure=false;
  rest.onHit.call({heal:x=>{healed=x;}},{maxhp:160,statusState:restState,setStatus:()=>true},{},rest);
  assert.equal(healed,160);assert.equal(restState.time,3);
  let blocked=0;const sleeper={statusState:restState,hasAbility:()=>false,cureStatus(){restCure=true;}};
  for(let i=0;i<3;i++)if(condition('slp').onBeforeMove.call({add:noop},sleeper,null,{})===false)blocked++;
  assert.equal(blocked,2);assert(restCure);
  add('rest_sleep','rest_duration',{event:'Successful Rest',ability:'None',subsequent_cures:'None',
    move:'Ordinary move, not sleepUsable'},'How many subsequent reached move attempts does sleep block?',
    ['1','2','3','Random 1 to 3'],'2','data/moves.ts:15548; data/conditions.ts:66',{blocked,healing_requested:healed});
  const fullResult=rest.onTry.call({add:noop},{status:'brn',hp:160,maxhp:160,hasAbility:()=>false});assert.equal(fullResult,null);
  add('rest_full_hp','rest_failure',{status:'brn',hp:160,max_hp:160,ability:'None'},
    'Does Rest succeed at full HP to remove the burn?',['Yes','No'],'No','data/moves.ts:15534',{onTry:fullResult});
  const rules=dex.formats.getRuleTable(dex.formats.get('gen9ou'));
  assert(rules.has('sleepmovesclause'));assert(!rules.has('sleepclausemod'));
  add('ou_sleep_rule','ou_sleep_clause',{format:'Pinned local gen9ou',topic:'Sleep restriction'},
    'Which sleep rule is active?', ['Sleep Moves Clause','Sleep Clause Mod limiting one foe asleep','Neither'],
    'Sleep Moves Clause','config/formats.ts:49',{sleepmovesclause:true,sleepclausemod:false});
  assert.equal(new Set(rows.map(r=>r.id)).size,rows.length);
  return rows;
}
module.exports={facts};
if(require.main===module){const rows=facts();console.log(JSON.stringify({passed:true,count:rows.length,
  rules:[...new Set(rows.map(r=>r.rule_id))]}));}
