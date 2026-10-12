'use strict';
const readline = require('node:readline');
let enginePatch;
try { enginePatch = require('./patch.cjs').patchCalc(); }
catch (error) {
  process.stdout.write(JSON.stringify({status:'failure', error:error.message})+'\n');
  process.exit(1);
}
const {calculate, Generations, Pokemon, Move, Field} = require('@smogon/calc');
const version = require('@smogon/calc/package.json').version;
if (version !== '0.11.0') throw new Error('calculator version drift');
process.stdout.write(JSON.stringify({status:'ready', engine_patch:enginePatch})+'\n');
const gen = Generations.get(9);
let stateOverlay;
const scenariosV2 = require('./scenarios-v2.cjs');
const id = value => String(value).toLowerCase().replace(/[^a-z0-9]/g, '');
function requireKeys(value, keys, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(label);
  for (const key of Object.keys(value)) if (!keys.includes(key)) throw new Error(`unsupported ${label}.${key}`);
}
function pokemon(spec) {
  requireKeys(spec, ['name', 'options', 'expectedStats', 'entry_effects_observed', 'battle_types', 'projected_entry', 'qp_source', 'tera_projection'], 'pokemon');
  if (!gen.species.get(id(spec.name))) throw new Error('unknown species');
  const options = {...spec.options};
  requireKeys(options, ['level', 'gender', 'ability', 'abilityOn', 'item', 'nature', 'ivs', 'evs',
    'boosts', 'curHP', 'status', 'toxicCounter', 'teraType', 'alliesFainted', 'boostedStat'], 'options');
  for (const key of ['level', 'ability', 'item', 'nature', 'ivs', 'evs', 'boosts', 'curHP', 'status']) {
    if (!(key in options)) throw new Error(`missing explicit ${key}`);
  }
  for (const [key, data] of [['ability',gen.abilities], ['item',gen.items], ['nature',gen.natures]]) {
    if (options[key] && !data.get(id(options[key]))) throw new Error(`unknown ${key}`);
    if (options[key]) options[key] = data.get(id(options[key])).name;
  }
  for (const key of ['ivs','evs']) {
    requireKeys(options[key], ['hp','atk','def','spa','spd','spe'], key);
    for (const stat of ['hp','atk','def','spa','spd','spe']) {
      const n = options[key][stat];
      if (!Number.isInteger(n) || n < 0 || n > (key === 'ivs' ? 31 : 252)) throw new Error(`invalid ${key}`);
    }
  }
  if (Object.values(options.evs).reduce((a,b) => a+b,0) > 510) throw new Error('invalid EV total');
  if (!Number.isInteger(options.level) || options.level < 1 || options.level > 100) throw new Error('invalid level');
  requireKeys(options.boosts, ['atk','def','spa','spd','spe','accuracy','evasion'], 'boosts');
  for (const n of Object.values(options.boosts)) if (!Number.isInteger(n) || Math.abs(n)>6) throw new Error('invalid boost');
  if (!['','brn','par','slp','frz','psn','tox'].includes(options.status)) throw new Error('invalid status');
  if (spec.battle_types) {
    if (!Array.isArray(spec.battle_types) || spec.battle_types.length < 1 || spec.battle_types.length > 2 ||
        spec.battle_types.some(t => !gen.types.get(id(t)))) throw new Error('invalid battle types');
    options.overrides = {types: spec.battle_types};
  }
  const p = new Pokemon(gen, gen.species.get(id(spec.name)).name, options);
  // Calc applies these entry-only boosts unconditionally; the live observation
  // already contains them. Suppress only their trigger, preserving observed boosts.
  if (options.ability === '' || (spec.entry_effects_observed && ['Dauntless Shield', 'Intrepid Sword',
      'Embody Aspect (Teal)', 'Embody Aspect (Hearthflame)',
      'Embody Aspect (Wellspring)', 'Embody Aspect (Cornerstone)'].includes(p.ability))) {
    // clone() reconstructs with options.ability || species.abilities[0].
    // Pokemon owns a deep copy of species; never mutate the generation's data.
    p.ability = '';
    p.species.abilities = {0: ''};
  }
  if (!Number.isInteger(options.curHP) || options.curHP < 1 || options.curHP > p.maxHP()) throw new Error('invalid HP');
  if (spec.expectedStats) {
    for (const [stat, n] of Object.entries(spec.expectedStats)) {
      if (p.rawStats[stat] !== n) throw new Error(`self stat mismatch: ${stat}`);
    }
  }
  return p;
}
function run(req) {
  requireKeys(req, ['identity','scenarios','semantics_version'], 'request');
  if (req.semantics_version && req.semantics_version !== 'calculator-input-v2') throw new Error('unknown calculator semantics');
  const modern = req.semantics_version === 'calculator-input-v2';
  if (modern && !stateOverlay) stateOverlay = require('./state-patch.cjs').statePatch();
  if (!req.identity || !Array.isArray(req.scenarios)) throw new Error('missing identity/scenarios');
  const entries = req.scenarios.map(s => {
    requireKeys(s, ['scenario_id','attacker','defender','move','field'], 'scenario');
    const moveData = gen.moves.get(id(s.move));
    if (!s.scenario_id || !moveData) throw new Error('unknown scenario/move');
    // Move retains its constructor input as originalName. Dynamic type branches
    // compare canonical names, so every calculation must use the resolved name.
    const moveName = moveData.name;
    const attacker = pokemon(s.attacker), defender = pokemon(s.defender);
    requireKeys(s.field, ['weather','terrain','isMagicRoom','isWonderRoom','isGravity','isAuraBreak',
      'isFairyAura','isDarkAura','isBeadsOfRuin','isSwordOfRuin','isTabletsOfRuin','isVesselOfRuin',
      'attackerSide','defenderSide'], 'field');
    for (const side of ['attackerSide','defenderSide']) if (s.field[side]) {
      requireKeys(s.field[side], ['spikes','isSR','isReflect','isLightScreen','isProtected','isSeeded',
        'isSaltCured','isForesight','isTailwind','isHelpingHand','isFlowerGift','isPowerTrick',
        'isFriendGuard','isAuroraVeil','isBattery','isPowerSpot','isSteelySpirit','isSwitching','toxicSpikes','isStickyWeb'], side);
    }
    if (modern) return runModern(s, attacker, defender, moveName);
    const move = new Move(gen, moveName);
    const result = calculate(gen, attacker, defender, move, new Field(s.field));
    const order = {attacker_speed: result.attacker.stats.spe, defender_speed: result.defender.stats.spe,
      move_priority: result.move.priority,
      equal_priority_speed_relation: result.attacker.stats.spe === result.defender.stats.spe ?
        'tie_possible' : result.attacker.stats.spe > result.defender.stats.spe ? 'attacker_first' : 'defender_first',
      conditions: 'conditional on equal move priority; Trick Room reverses unequal speed order; switching and priority/activation uncertainty remain'};
    if (move.category === 'Status') {
      let effect = 'not evaluated; no success or execution claim';
      const types = defender.teraType ? [defender.teraType] : defender.types;
      if (move.name === 'Thunder Wave' && types.some(t => ['Ground','Electric'].includes(t)))
        effect = 'immune: current target typing blocks Thunder Wave';
      return {scenario_id:s.scenario_id, excluded_with_reason:'status move; direct damage not applicable',
        effect_assessment:effect, conditional_order:order};
    }
    const range = result.range();
    if (!range.every(Number.isFinite)) throw new Error('invalid computed range');
    return {scenario_id:s.scenario_id, damage_range_hp:range, damage_rolls:result.damage,
      move:{name:result.move.name, type:result.move.type, category:result.move.category},
      defender_max_hp:defender.maxHP(), conditional_order:order, ko_chance_given_hit:null, survival_given_hit:null};
  });
  return {status:'success', engine:'@smogon/calc', engine_version:version, engine_patch:enginePatch, generation:9,
    identity:req.identity, entries, ...(req.semantics_version ? {semantics_version:req.semantics_version,
      runtime_patch:stateOverlay.identity} : {})};
}
function runModern(s, attacker, defender, moveName) {
  const projected = scenariosV2.prepare(gen,s,attacker,defender);
  const tera=s.attacker.tera_projection || s.defender.tera_projection;
  const state = {phase:projected.projections.length ? 'after_selected_switch_entry' : tera ? 'after_selected_terastallization' : 'current_decision',
    entry:projected.projections, weather:projected.field.weather || null, terrain:projected.field.terrain || null};
  state.items = [{role:'attacker', item:attacker.item || null}, {role:'defender', item:defender.item || null}];
  if (tera) state.terastallization=tera;
  if (projected.fainted) return {scenario_id:s.scenario_id,
    excluded_with_reason:'selected switch faints to current entry hazards before this hypothetical attack', scenario_state:state};
  if (['counter','mirrorcoat','metalburst','comeuppance','bide','lastrespects','ragefist'].includes(id(s.move))) {
    return {scenario_id:s.scenario_id, excluded_with_reason:'damage requires prior hit/turn history not supplied to this scenario; not a computed zero',scenario_state:state};
  }
  const variants = scenariosV2.moveVariants(gen,s.move,attacker);
  const results = variants.map(v=>stateOverlay.calculate(gen,attacker,defender,new Move(gen,moveName,v.options),projected.field));
  const result=results[0], move=result.move;
  // Speeds describe the state before any hit-induced changes within this move.
  const speeds=stateOverlay.calculate(gen,attacker,defender,new Move(gen,'Splash'),projected.field);
  let priority=gen.moves.get(id(s.move)).priority || 0;
  if (attacker.hasAbility('Prankster') && move.category==='Status') priority++;
  if (attacker.hasAbility('Gale Wings') && move.type==='Flying' && attacker.curHP()===attacker.maxHP()) priority++;
  if (attacker.hasAbility('Triage') && (move.drain || gen.moves.get(id(s.move)).flags?.heal)) priority+=3;
  if (id(s.move)==='grassyglide' && projected.field.terrain==='Grassy' &&
      require('@smogon/calc/dist/mechanics/util').isGrounded(attacker,projected.field)) priority++;
  const order={attacker_speed:speeds.attacker.stats.spe,defender_speed:speeds.defender.stats.spe,move_priority:priority,
    equal_priority_speed_relation:speeds.attacker.stats.spe===speeds.defender.stats.spe?'tie_possible':
      speeds.attacker.stats.spe>speeds.defender.stats.spe?'attacker_first':'defender_first',
    conditions:'conditional on equal move priority and the scenario state before the first hit; Trick Room reverses unequal speed order; switching and other priority/activation uncertainty remain'};
  if (move.category==='Status') {
    let effect='not evaluated; no success or execution claim';
    const types=defender.teraType && defender.teraType!=='Stellar'?[defender.teraType]:defender.types;
    if (move.name==='Thunder Wave' && types.some(t=>['Ground','Electric'].includes(t))) effect='immune: current target typing blocks Thunder Wave';
    return {scenario_id:s.scenario_id,excluded_with_reason:'status move; direct damage not applicable',
      effect_assessment:effect,conditional_order:order,scenario_state:state};
  }
  const damageVariants=results.map((r,i)=>({label:variants[i].label,hits:variants[i].hits,
    damage_range_hp:r.range(),damage_rolls:r.damage}));
  const range=[Math.min(...damageVariants.map(v=>v.damage_range_hp[0])),Math.max(...damageVariants.map(v=>v.damage_range_hp[1]))];
  if (!range.every(Number.isFinite)) throw new Error('invalid computed range');
  return {scenario_id:s.scenario_id,damage_range_hp:range,
    ...(damageVariants.length===1?{damage_rolls:result.damage}:{}),damage_variants:damageVariants,
    move:{name:move.name,type:move.type,category:move.category},defender_max_hp:defender.maxHP(),
    conditional_order:order,scenario_state:state,ko_chance_given_hit:null,survival_given_hit:null};
}
readline.createInterface({input:process.stdin, crlfDelay:Infinity}).on('line', line => {
  let req;
  try { req=JSON.parse(line); process.stdout.write(JSON.stringify(run(req))+'\n'); }
  catch (error) { process.stdout.write(JSON.stringify({status:'failure',identity:req?.identity,error:String(error.message)})+'\n'); }
});
