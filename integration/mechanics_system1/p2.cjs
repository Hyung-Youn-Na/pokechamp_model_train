/* EP201 priority 2: bounded Gen9 controlled entry/residual mechanics.
 * Showdown is MIT licensed. Synthetic configurations are not legal-set claims.
 * Expected arithmetic and rule tables below are independent of engine outputs.
 */
'use strict';
const assert = require('node:assert/strict');
const {Battle} = require('../../pokemon-showdown/dist/sim');
const PIN = 'e64915c0eab066db1d3e732b1280386468dd7415';
const frac = (hp, divisor) => Math.max(1, Math.floor(hp / divisor));
function battle() {
  const b = new Battle({formatid:'gen9customgame', seed:[2026,10,21,201]});
  for (const side of ['p1','p2']) b.setPlayer(side,{name:side,team:[
    {species:'Mew',ability:'No Ability',moves:['splash']},
    {species:'Mew',ability:'No Ability',moves:['splash']},
  ]});
  return b;
}
function configure(p, c) {
  p.types = c.types || ['Normal'];
  p.maxhp = p.baseMaxhp = c.max_hp;
  p.hp = c.current_hp;
  p.ability = c.ability || 'noability';
  p.abilityState = {id:p.ability,target:p};
  p.item = c.item || '';
  p.itemState = {id:p.item,target:p};
  p.status = c.status || '';
  p.statusState = {id:p.status,target:p,stage:c.toxic_stage || 0};
}
function grounded(c) {
  return c.item === 'ironball' || (!c.types.includes('Flying') && c.ability !== 'levitate' && c.item !== 'airballoon');
}
function rows() {
  const out = [];
  function add(id,rule_id,state,question,options,expected,observed,source,extra={}) {
    assert.deepEqual(observed,expected,`${id}: oracle mismatch`);
    assert(options.includes(expected),`${id}: missing answer`);
    assert.equal(new Set(options).size,options.length);
    out.push({id:`p2-${id}`,priority:2,rule_id,state:{generation:9,...state},question,options,answer:expected,
      evidence:{source,expected,observed,showdown_commit:PIN,...extra}});
  }
  function hpRow(id,rule,state,expected,observed,source,extra={}) {
    const candidates = [...new Set([0,state.current_hp,state.max_hp,expected,
      Math.max(0,expected-1),Math.min(state.max_hp,expected+1)].map(String))];
    add(id,rule,state,'What is the resulting current HP? (0 means fainted.)',candidates,String(expected),String(observed),source,extra);
  }
  const common = 'Controlled Gen9 singles state. Listed item and ability are active; no suppression, Tera, other hazards, weather, terrain, status, healing or extra effects unless explicitly listed. This is one actual engine SwitchIn event, not a complete switch action or turn.';
  // Independent Rock chart, intentionally not read from Dex.
  const rock = {Normal:1,Fire:2,Water:1,Electric:1,Grass:1,Ice:2,Fighting:.5,Poison:1,Ground:.5,Flying:2,Psychic:1,Bug:2,Rock:1,Ghost:1,Dragon:1,Dark:1,Steel:.5,Fairy:1};
  const typeCases = Object.keys(rock).map(t=>[t]).concat([['Fire','Flying'],['Bug','Flying'],['Fighting','Steel'],['Ground','Steel'],['Fire','Steel']]);
  for (const types of typeCases) for (const max of [7,101,160,301]) for (const low of [false,true]) for (const guard of ['none','boots','magicguard']) {
    const c={types,max_hp:max,current_hp:low?1:max,item:guard==='boots'?'heavydutyboots':'',ability:guard==='magicguard'?'magicguard':'noability'};
    const mult=types.reduce((v,t)=>v*rock[t],1);
    const lost=guard==='none'?Math.max(1,Math.floor(max*mult/8)):0;
    const expected=Math.max(0,c.current_hp-lost);
    const b=battle();try {
      const p=b.p1.active[0];configure(p,c);p.side.addSideCondition('stealthrock',b.p2.active[0]);
      b.fieldEvent('SwitchIn',[p]);
      hpRow(`sr-${types.join('_')}-${max}-${low}-${guard}`,'stealth_rock_entry_hp',
        {...c,hazards:{stealth_rock:true},scope:common},expected,p.hp,'data/moves.ts:stealthrock.condition; sim/battle.ts:fieldEvent/damage',
        {rock_multiplier:mult,nominal_damage:lost,event:'SwitchIn'});
    } finally {b.destroy();}
  }
  const entryProfiles=[
    {types:['Normal'],ability:'noability',item:''},
    {types:['Flying'],ability:'noability',item:''},
    {types:['Normal'],ability:'levitate',item:''},
    {types:['Normal'],ability:'noability',item:'airballoon'},
    {types:['Flying'],ability:'noability',item:'ironball'},
    {types:['Normal'],ability:'levitate',item:'ironball'},
    {types:['Normal'],ability:'noability',item:'heavydutyboots'},
    {types:['Normal'],ability:'magicguard',item:''},
  ];
  for (const [index,profile] of entryProfiles.entries()) for (const layers of [1,2,3]) for (const max of [7,101,160,301]) for (const low of [false,true]) {
    const c={...profile,max_hp:max,current_hp:low?1:max};
    const divisor={1:8,2:6,3:4}[layers];
    const lost=grounded(c)&&c.item!=='heavydutyboots'&&c.ability!=='magicguard'?frac(max,divisor):0;
    const b=battle();try {
      const p=b.p1.active[0];configure(p,c);
      for(let j=0;j<layers;j++)p.side.addSideCondition('spikes',b.p2.active[0]);
      b.fieldEvent('SwitchIn',[p]);
      hpRow(`spikes-${index}-${layers}-${max}-${low}`,'spikes_entry_hp',{...c,hazards:{spikes_layers:layers},scope:common},Math.max(0,c.current_hp-lost),p.hp,
        'data/moves.ts:spikes.condition; sim/pokemon.ts:isGrounded; sim/battle.ts:fieldEvent/damage',{grounded:!!p.isGrounded(),nominal_damage:lost});
    }finally{b.destroy();}
  }
  const poisonProfiles=entryProfiles.concat([
    {types:['Poison'],ability:'noability',item:''},
    {types:['Poison'],ability:'noability',item:'heavydutyboots'},
    {types:['Poison','Flying'],ability:'noability',item:''},
    {types:['Poison','Flying'],ability:'noability',item:'ironball'},
    {types:['Steel'],ability:'noability',item:''},
    {types:['Normal'],ability:'immunity',item:''},
  ]);
  for (const [index,profile] of poisonProfiles.entries()) for(const layers of [1,2]) for(const existing of ['', 'par']) {
    const c={...profile,max_hp:160,current_hp:160,status:existing};
    const absorb=grounded(c)&&c.types.includes('Poison');
    const poison=grounded(c)&&!absorb&&!c.types.includes('Steel')&&c.item!=='heavydutyboots'&&c.ability!=='immunity'&&!existing;
    const resultStatus=poison?(layers===2?'tox':'psn'):existing;
    const format=(status,remain)=>`${status||'none'}; ${remain?'hazard remains':'hazard removed'}`;
    const b=battle();try {
      const p=b.p1.active[0];configure(p,c);for(let j=0;j<layers;j++)p.side.addSideCondition('toxicspikes',b.p2.active[0]);
      b.fieldEvent('SwitchIn',[p]);
      add(`tspikes-${index}-${layers}-${existing||'none'}`,'toxic_spikes_entry_status',
        {...c,hazards:{toxic_spikes_layers:layers},scope:common},'What are the entrant\'s major status and the Toxic Spikes state immediately after the entry event?',
        ['none; hazard remains','none; hazard removed','psn; hazard remains','tox; hazard remains','par; hazard remains','par; hazard removed'],
        format(resultStatus,!absorb),format(p.status,!!p.side.sideConditions.toxicspikes),
        'data/moves.ts:toxicspikes.condition; sim/pokemon.ts:isGrounded/trySetStatus',{grounded:!!p.isGrounded(),absorbed:absorb});
    }finally{b.destroy();}
  }
  const webProfiles=entryProfiles.concat([
    {types:['Normal'],ability:'contrary',item:''},
    {types:['Normal'],ability:'clearbody',item:''},
    {types:['Normal'],ability:'noability',item:'clearamulet'},
  ]);
  for(const [index,profile] of webProfiles.entries())for(const initial of [-6,0,6]) {
    const c={...profile,max_hp:160,current_hp:160};
    const applies=grounded(c)&&c.item!=='heavydutyboots'&&c.item!=='clearamulet'&&c.ability!=='clearbody';
    const expected=applies?Math.max(-6,Math.min(6,initial+(c.ability==='contrary'?1:-1))):initial;
    const b=battle();try {
      const p=b.p1.active[0];configure(p,c);p.boosts.spe=initial;p.side.addSideCondition('stickyweb',b.p2.active[0]);b.fieldEvent('SwitchIn',[p]);
      add(`web-${index}-${initial}`,'sticky_web_entry_speed_stage',{...c,initial_speed_stage:initial,hazards:{sticky_web:true},scope:common},
        'What is the Speed stat stage after this controlled entry event?',[-6,-5,-1,0,1,5,6].map(String),String(expected),String(p.boosts.spe),
        'data/moves.ts:stickyweb.condition; data/abilities.ts:contrary/clearbody; data/items.ts:clearamulet');
    }finally{b.destroy();}
  }
  // Actual voluntary switching cross-check, using real species types and unmodified HP stats.
  for(const [species,mult] of [['Mew',1],['Charizard',4],['Lucario',.25]])for(const item of ['', 'Heavy-Duty Boots'])for(const spikes of [0,3]) {
    const b=new Battle({formatid:'gen9customgame',seed:[2026,10,21,202]});try {
      b.setPlayer('p1',{team:[{species:'Mew',ability:'No Ability',moves:['splash']},{species,ability:'No Ability',item,moves:['splash']}]});
      b.setPlayer('p2',{team:[{species:'Mew',ability:'No Ability',moves:['splash']}]});
      const p=b.p1.pokemon[1],max=p.maxhp;
      b.p1.addSideCondition('stealthrock',b.p2.active[0]);for(let j=0;j<spikes;j++)b.p1.addSideCondition('spikes',b.p2.active[0]);
      const expected=item?max:max-Math.max(1,Math.floor(max*mult/8))-(spikes&&species!=='Charizard'?frac(max,4):0);
      b.makeChoices('switch 2','move splash');
      hpRow(`real-switch-${species}-${!!item}-${spikes}`,'voluntary_switch_hazards',{species,types:p.getTypes(),max_hp:max,current_hp:max,item:item||'none',ability:'No Ability',hazards:{stealth_rock:true,spikes_layers:spikes},
        scope:'Actual voluntary switch into listed hazards; opposing Pokemon uses Splash. No weather, status, terrain or residual items. No legal-set claim.'},expected,p.hp,
        'sim/battle-actions.ts:switchIn/runSwitch; data/moves.ts:stealthrock/spikes',{actual_switch:true});
    }finally{b.destroy();}
  }
  // The order in which these side conditions were established is explicit.
  // In this bounded dispatch, KO from an earlier hazard stops later callbacks.
  for(const types of [['Normal'],['Poison'],['Flying']])for(const ability of ['noability','magicguard'])for(const item of ['', 'heavydutyboots','ironball'])for(const hp of [1,20,21,40,60,160]) {
    const c={types,ability,item,max_hp:160,current_hp:hp};
    let expectedHp=hp;
    if(item!=='heavydutyboots'&&ability!=='magicguard') {
      expectedHp=Math.max(0,expectedHp-(types.includes('Flying')?40:20));
      if(expectedHp&&grounded(c))expectedHp=Math.max(0,expectedHp-40);
    }
    const absorbed=expectedHp>0&&grounded(c)&&types.includes('Poison');
    const status=expectedHp>0&&grounded(c)&&!absorbed&&item!=='heavydutyboots'?'tox':'';
    const speed=expectedHp>0&&grounded(c)&&item!=='heavydutyboots'?-1:0;
    const encode=(hp,status,absorbed,speed)=>`${hp} HP; ${status||'no status'}; Toxic Spikes ${absorbed?'removed':'remain'}; Speed stage ${speed}`;
    const expected=encode(expectedHp,status,absorbed,speed);
    const b=battle();try {
      const p=b.p1.active[0];configure(p,c);
      for(const [hazard,layers] of [['stealthrock',1],['spikes',3],['toxicspikes',2],['stickyweb',1]])for(let j=0;j<layers;j++)p.side.addSideCondition(hazard,b.p2.active[0]);
      b.fieldEvent('SwitchIn',[p]);
      const observed=encode(p.hp,p.status,!p.side.sideConditions.toxicspikes,p.boosts.spe);
      const options=[...new Set([expected,encode(hp,'',false,0),encode(0,'',false,0),encode(expectedHp,'tox',false,-1),encode(expectedHp,'',true,0)])];
      // All cases retain at least two different possible outcomes.
      if(options.length<2)options.push(encode(160,'',false,0));
      add(`stack-${types.join('_')}-${ability}-${item||'none'}-${hp}`,'stacked_entry_faint_stop',
        {...c,hazards_established_in_order:[{name:'Stealth Rock',layers:1},{name:'Spikes',layers:3},{name:'Toxic Spikes',layers:2},{name:'Sticky Web',layers:1}],scope:common.replace('no suppression, Tera, other hazards','no suppression, Tera, unlisted hazards')},
        'What is the resulting HP, major status, Toxic Spikes state, and Speed stage after this entry event?',options,expected,observed,
        'sim/battle.ts:fieldEvent; data/moves.ts:stealthrock/spikes/toxicspikes/stickyweb',
        {entry_event_only:true,callbacks_stop_at_zero_hp:true});
    }finally{b.destroy();}
  }
  for(const previousStage of [1,5,14,15]) {
    const b=battle();try {
      const p=b.p1.pokemon[1];
      p.status='tox';p.statusState={id:'tox',target:p,stage:previousStage};
      const max=p.maxhp;
      b.makeChoices('switch 2','move splash');
      const expected=max-frac(max,16);
      assert.equal(p.statusState.stage,1);
      hpRow(`toxic-reentry-${previousStage}`,'toxic_reentry_reset',
        {types:['Psychic'],ability:'No Ability',item:'none',status:'tox',max_hp:max,current_hp:max,previous_toxic_stage:previousStage,
          scope:'Actual voluntary switch of an already badly poisoned bench Pokemon, followed by opposing Splash and the normal end-turn residual. No hazards, weather, terrain, items or other effects.'},
        expected,p.hp,'data/conditions.ts:tox.onSwitchIn/onResidual; sim/battle-actions.ts:switchIn/runSwitch',
        {actual_switch:true,toxic_stage_after:p.statusState.stage});
    }finally{b.destroy();}
  }
  const residualProfiles=[
    {types:['Normal'],ability:'noability',item:'',status:''},
    {types:['Rock'],ability:'noability',item:'',status:''},
    {types:['Ground'],ability:'noability',item:'',status:''},
    {types:['Steel'],ability:'noability',item:'',status:''},
    ...['psn','brn','tox'].map(status=>({types:['Normal'],ability:'noability',item:'',status})),
    ...['', 'psn','brn','tox'].map(status=>({types:['Normal'],ability:'noability',item:'leftovers',status})),
    {types:['Poison'],ability:'noability',item:'blacksludge',status:''},
    {types:['Normal'],ability:'noability',item:'blacksludge',status:''},
    {types:['Normal'],ability:'magicguard',item:'blacksludge',status:'tox'},
    {types:['Normal'],ability:'magicguard',item:'leftovers',status:'psn'},
    ...['psn','tox'].flatMap(status=>['','leftovers','blacksludge'].map(item=>({types:['Normal'],ability:'poisonheal',item,status}))),
  ];
  for(const [index,profile] of residualProfiles.entries())for(const max of [7,101,160,301])for(const current of [1,Math.floor(max/2),max])for(const sand of [false,true]) {
    const stages=profile.status==='tox'?[0,1,5,14,15]:[0];
    for(const stage of stages) {
      const c={...profile,max_hp:max,current_hp:current,toxic_stage:stage};let expected=current;
      const trace=[];
      function damage(label,n){if(expected<=0)return;const before=expected;if(c.ability!=='magicguard')expected=Math.max(0,expected-n);trace.push({event:label,before,after:expected});}
      function heal(label,n){if(expected<=0)return;const before=expected;expected=Math.min(max,expected+n);trace.push({event:label,before,after:expected});}
      if(sand&&!c.types.some(t=>['Rock','Ground','Steel'].includes(t)))damage('sandstorm',frac(max,16));
      if(c.item==='leftovers')heal('leftovers',frac(max,16));
      if(c.item==='blacksludge')c.types.includes('Poison')?heal('blacksludge',frac(max,16)):damage('blacksludge',frac(max,8));
      if(c.status==='brn')damage('burn',frac(max,16));
      if(['psn','tox'].includes(c.status)) {
        if(c.ability==='poisonheal')heal('poisonheal',frac(max,8));
        else damage(c.status,c.status==='psn'?frac(max,8):frac(max,16)*Math.min(15,stage+1));
      }
      const b=battle();try {
        const p=b.p1.active[0];configure(p,c);if(sand)b.field.setWeather('sandstorm',b.p2.active[0]);
        b.fieldEvent('Residual');
        hpRow(`residual-${index}-${max}-${current}-${sand}-${stage}`,'ordered_residual_hp',
          {...c,weather:sand?'sandstorm':'none',scope:'One actual engine Residual event; no moves or switching. All listed effects active; no terrain, other effects, suppression or healing prevention. Status already present. toxic_stage is the number of previous active toxic ticks since last entry, capped at 15. No HP revival after reaching 0.'},
          expected,p.hp,'sim/battle.ts:fieldEvent/damage/heal; data/conditions.ts:sandstorm/psn/tox/brn; data/items.ts:leftovers/blacksludge; data/abilities.ts:magicguard/poisonheal',
          {independent_event_trace:trace,toxic_stage_after:p.statusState.stage});
      }finally{b.destroy();}
    }
  }
  assert.equal(new Set(out.map(r=>r.id)).size,out.length);
  return out;
}
module.exports={rows};
if(require.main===module) {const r=rows();console.log(JSON.stringify({passed:true,count:r.length,rules:[...new Set(r.map(x=>x.rule_id))]}));}
