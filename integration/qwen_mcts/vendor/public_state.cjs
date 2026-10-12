'use strict';

// The serializer is pinned and fails closed when upstream adds an unclassified field.
// RNG, current choices and transport/log metadata never cross this boundary.
const {Dex} = require('../../../pokemon-showdown/dist/sim/dex');
const set = text => new Set(text.split(/\s+/).filter(Boolean));
const BATTLE = set(`strictChoices formatData gameType activePerHalf rated reportExactHP
 reportPercentages requestState turn midTurn started ended effectOrder speedOrder field sides
 queue formatid winner lastMove lastSuccessfulMoveThisTurn lastDamage`);
const PRIVATE = set(`sentRequests debugMode forceRandomChance prngSeed supportCancel faintQueue
 inputLog messageLog sentLogPos sentEnd effect effectState event events eventDepth activeMove
 activePokemon activeTarget lastMoveLine quickClawRoll prng hints log rewardConfig`);
const SIDE = set(`foe allySide lastSelectedMove id n name avatar pokemonLeft active faintedLastTurn
 faintedThisTurn totalFainted zMoveUsed dynamaxUsed sideConditions slotConditions lastMove pokemon
 team choice activeRequest`);
const MON = set(`m baseSpecies species speciesState gender dynamaxLevel gigantamax moveSlots
 position details status statusState volatiles hpType hpPower baseHpType baseHpPower baseStoredStats
 storedStats boosts baseAbility ability abilityState item itemState lastItem usedItemThisTurn
 ateBerry trapped maybeTrapped maybeDisabled maybeLocked illusion transformed fainted faintQueued
 subFainted formeRegression types baseTypes addedType knownType apparentType teraType terastallized
 switchFlag forceSwitchFlag skipBeforeSwitchOutEventFlag draggedIn newlySwitched beingCalledBack
 lastMove lastMoveUsed moveThisTurn statsRaisedThisTurn statsLoweredThisTurn hurtThisTurn lastDamage
 attackedBy timesAttacked isActive activeTurns activeMoveActions previouslySwitchedIn truantTurn
 bondTriggered swordBoost shieldBoost syrupTriggered stellarBoostedTypes isStarted duringMove
 weighthg speed canMegaEvo canUltraBurst canGigantamax canTerastallize maxhp baseMaxhp hp set
 baseMoveSlots showCure disabledMoves moveLastTurnResult moveThisTurnResult lastMoveTargetLoc`);
const DATA = set(`id name species item ability moves nature gender evs ivs level shiny happiness
 pokeball hpType dynamaxLevel gigantamax teraType move pp maxpp target disabled disabledSource used
 virtual hp atk def spa spd spe accuracy evasion critRatio effectOrder duration time startTime stage
 source sourceSlot sourceEffect targetSlot slot layers counter move damage thisTurn isSlotCondition
 sourcePosition target position numConsecutive durationCallback ended lastMove totalDamage hits
 hitCount multiplier type moveSlot turns abilityOrder initial maxDuration minDuration damageValue
 hit moveHitData hitTargets crit typeMod zBrokeProtect p1a p2a spreadHit spreadDamage totalDamage
 recoil drain causedCrashDamage hasSheerForce isExternal isZOrMaxPowered isFutureMove
 pranksterBoosted priority accuracy basePower category flags contact protect mirror sound heal
 ignoreAbility ignoreDefensive ignoreEvasion ignoreImmunity willCrit infiltrates selfSwitch
 forceSwitch negatesProtect secondaries chance boosts status volatileStatus self onHit
 ignoreNegativeOffensive ignorePositiveDefensive multihit multihitType selfDropped`);
const copy = value => JSON.parse(JSON.stringify(value));

function keys(value, allowed, where) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error(`expected object: ${where}`);
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw Error(`unclassified ${where}.${key}`);
}

function data(value, where) {
  if (value === null || ['string', 'boolean'].includes(typeof value)) return;
  if (typeof value === 'number' && Number.isFinite(value)) return;
  if (Array.isArray(value)) return value.forEach((v, i) => data(v, `${where}.${i}`));
  keys(value, DATA, where);
  for (const [key, child] of Object.entries(value)) data(child, `${where}.${key}`);
}

function conditions(value, where) {
  for (const [id, state] of Object.entries(value)) {
    if (!Dex.conditions.get(id).exists) throw Error(`unknown condition ${where}.${id}`);
    data(state, `${where}.${id}`);
  }
}

function checkMon(mon) {
  keys(mon, MON, 'pokemon');
  if (Object.keys(mon.m).length || mon.illusion || mon.transformed) throw Error('unsupported custom/hidden state');
  for (const [key, value] of Object.entries(mon)) {
    if (key === 'volatiles') conditions(value, 'volatiles');
    else if (key === 'disabledMoves') {
      for (const [id, entry] of Object.entries(value)) {
        if (!Dex.moves.get(id).exists) throw Error('unknown disabled move');
        data(entry, key);
      }
    } else data(value, key);
  }
}

function checkPhysical(state) {
  keys(state, BATTLE, 'public battle');
  if (state.formatid !== 'gen9ou' || state.gameType !== 'singles' || !state.strictChoices) {
    throw Error('only strict gen9ou singles supported');
  }
  if (state.sides.length !== 2) throw Error('two sides required');
  for (const action of state.queue) {
    // The only pending operation exported is the public preview start operation.
    if (state.requestState !== 'teampreview' || action.choice !== 'start' ||
        Object.keys(action).some(k => !['choice', 'order', 'speed'].includes(k))) {
      throw Error('hidden pending action at decision barrier');
    }
  }
  keys(state.field, set('weather weatherState terrain terrainState pseudoWeather'), 'field');
  data(state.field.weatherState, 'weather'); data(state.field.terrainState, 'terrain');
  conditions(state.field.pseudoWeather, 'field');
  for (const side of state.sides) {
    keys(side, SIDE, 'side');
    if ('choice' in side || 'activeRequest' in side) throw Error('private choice/request in public root');
    if (side.name !== side.id || side.avatar !== '') throw Error('noncanonical identity');
    // Gen 1 Counter uses this historical intent field; Gen 9 does not. A move
    // prevented by paralysis may never have been publicly revealed.
    if (side.lastSelectedMove !== '') throw Error('unrevealed historical choice in public root');
    side.pokemon.forEach(checkMon);
    conditions(side.sideConditions, 'side');
    side.slotConditions.forEach(c => conditions(c, 'slot'));
    for (const [key, value] of Object.entries(side)) {
      if (!['pokemon', 'sideConditions', 'slotConditions'].includes(key)) data(value, `side.${key}`);
    }
  }
  for (const [key, value] of Object.entries(state)) {
    if (!['sides', 'field', 'queue'].includes(key)) data(value, key);
  }
}

function exportPublic(battle) {
  const raw = battle.toJSON();
  keys(raw, new Set([...BATTLE, ...PRIVATE]), 'battle');
  if (raw.faintQueue.length || Object.keys(raw.events || {}).length || raw.eventDepth) {
    throw Error('not a quiescent decision barrier');
  }
  for (const side of raw.sides) {
    keys(side, SIDE, 'side');
    if (side.choice.actions.length) throw Error('submitted action cannot enter search');
  }
  const physical = {};
  for (const key of BATTLE) if (key in raw) physical[key] = copy(raw[key]);
  for (const side of physical.sides) {
    delete side.choice; delete side.activeRequest;
    side.name = side.id; side.avatar = '';
    side.lastSelectedMove = '';
  }
  checkPhysical(physical);
  return {schema: 'fixed-matchup-root-v1', physical};
}

function importPublic(root, seed) {
  keys(root, set('schema physical'), 'root');
  if (root.schema !== 'fixed-matchup-root-v1') throw Error('wrong public root schema');
  checkPhysical(root.physical);
  const state = copy(root.physical);
  Object.assign(state, {prng: seed.join(','), prngSeed: seed.join(','), log: [], inputLog: [],
    messageLog: [], sentLogPos: 0, sentEnd: false, sentRequests: true, debugMode: false,
    forceRandomChance: null, supportCancel: false, faintQueue: [], hints: [],
    effect: {id: ''}, effectState: {id: ''}, event: {id: ''}, events: {}, eventDepth: 0,
    activeMove: null, activePokemon: null, activeTarget: null, lastMoveLine: -1, quickClawRoll: false});
  for (const side of state.sides) side.choice = {cantUndo: false, error: '', actions: [],
    forcedSwitchesLeft: 0, forcedPassesLeft: 0, switchIns: [], zMove: false, mega: false,
    ultra: false, dynamax: false, terastallize: false};
  return state;
}

module.exports = {exportPublic, importPublic, checkPhysical};
