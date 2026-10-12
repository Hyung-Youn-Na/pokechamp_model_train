'use strict';
// Capability-separated Showdown worker (adapted from fixed_matchup/simulator.cjs).
// role "real": the actual game (init/advance/evidence). role "search": expands public roots only.
const readline = require('node:readline');
const {Battle, extractChannelMessages} = require('../../pokemon-showdown/dist/sim/battle');
const {Teams} = require('../../pokemon-showdown/dist/sim/teams');
const {TeamValidator} = require('../../pokemon-showdown/dist/sim/team-validator');
const {exportPublic, importPublic} = require('./vendor/public_state.cjs');
const {legalActions} = require('./vendor/observation.cjs');
const {renderStatic, renderDynamic, candidateText} = require('./render.cjs');

const role = process.argv[2];
if (!['real', 'search'].includes(role)) throw Error('explicit simulator role required');
let battle;
const copy = value => JSON.parse(JSON.stringify(value));
const noop = () => {};

function seed(value) {
  if (!Array.isArray(value) || value.length !== 4 || value.some(n => !Number.isInteger(n) || n < 0 || n > 65535)) {
    throw Error('four uint16 seed values required');
  }
  return value;
}

function describe(target) {
  // A decision barrier: the validated public root, its rendering and both sides' legal candidates.
  if (target.ended) return {ended: true, winner: target.winner, turn: target.turn};
  const root = exportPublic(target);
  const candidates = {};
  for (const side of target.sides) {
    candidates[side.id] = legalActions(target, side).map(row =>
      ({id: row.id, command: row.command, text: candidateText(root.physical, side.id, row)}));
  }
  return {ended: false, winner: '', turn: target.turn, root, phase: root.physical.requestState,
    dynamic: renderDynamic(root.physical), candidates};
}

function restore(root, value) {
  const restored = Battle.fromJSON(importPublic(root, seed(value)));
  restored.restart(noop);
  for (const side of restored.sides) side.clearChoice();
  return restored;
}

function submit(target, actions) {
  // Validate every acting side before submitting either; no partial joint actions.
  const commands = {};
  for (const side of target.sides) {
    const legal = legalActions(target, side);
    if (!legal.length) continue;
    const row = legal.find(a => a.id === actions?.[side.id]);
    if (!row) throw Error('missing or illegal joint action');
    commands[side.id] = row.command;
  }
  if (Object.keys(commands).sort().join() !== Object.keys(actions || {}).sort().join()) throw Error('extra joint action');
  for (const [side, command] of Object.entries(commands)) {
    if (!target.choose(side, command)) throw Error('Showdown rejected legal action');
  }
  target.sendUpdates();
}

function expand(input) {
  if (role !== 'search') throw Error('only the search role expands');
  const base = importPublic(input.root, [1, 1, 1, 1]);   // validates the public root (checkPhysical)
  const probe = restore(input.root, [1, 1, 1, 1]);
  const rendered = describe(probe);                      // full allowlist export of the restored root
  probe.destroy();
  const children = [];
  for (const child of input.children) {
    const state = structuredClone(base);
    state.prng = state.prngSeed = seed(child.seed).join(',');
    const target = Battle.fromJSON(state);
    target.restart(noop);
    for (const side of target.sides) side.clearChoice();
    try {
      submit(target, child.actions);
      if (target.ended) children.push({key: child.key, ended: true, winner: target.winner, turn: target.turn});
      else {
        const physical = exportPublic(target).physical;   // every child passes the full public allowlist
        children.push({key: child.key, ended: false, turn: target.turn, dynamic: renderDynamic(physical)});
      }
    } finally {
      target.destroy();
    }
  }
  return {root_turn: rendered.turn, root_dynamic: rendered.dynamic, children};
}

let messages = [];
const capture = (type, data) => messages.push({type, data: Array.isArray(data) ? data.join('\n') : String(data)});

function dispatch(input) {
  messages = [];
  switch (input.op) {
  case 'validate': {
    const result = {};
    for (const [name, text] of Object.entries(input.teams)) result[name] = new TeamValidator('gen9ou').validateTeam(Teams.import(text));
    return result;
  }
  case 'init': {
    if (role !== 'real') throw Error('search cannot create an actual game');
    if (battle) battle.destroy();
    battle = new Battle({formatid: 'gen9ou', seed: seed(input.seed).join(','), strictChoices: true, send: capture});
    for (const side of ['p1', 'p2']) {
      const team = Teams.import(input.teams[side]);
      if (!team?.length) throw Error('missing team');
      battle.setPlayer(side, {name: side, avatar: '', team});
    }
    battle.sendUpdates();
    const frame = describe(battle);
    return {...frame, static: renderStatic(frame.root.physical)};
  }
  case 'advance': {
    if (role !== 'real' || !battle) throw Error('advance needs an actual game');
    if (battle.ended) throw Error('cannot advance terminal battle');
    submit(battle, input.actions);
    return describe(battle);
  }
  case 'evidence': {
    if (role !== 'real' || !battle) throw Error('search has no actual evidence capability');
    const logs = extractChannelMessages(battle.log.join('\n'), [0, 1, 2]);
    return copy({messages, public_log: logs[0], actor_logs: {p1: logs[1], p2: logs[2]},
      requests: Object.fromEntries(battle.sides.map(s => [s.id, s.activeRequest])),
      ended: battle.ended, winner: battle.winner, turn: battle.turn, snapshot: battle.toJSON()});
  }
  case 'expand': return expand(input);
  case 'describe': {
    // Audit: re-render a stored public root exactly as the actual game rendered it.
    const target = restore(input.root, [1, 1, 1, 1]);
    try { return describe(target); } finally { target.destroy(); }
  }
  default: throw Error('unknown simulator operation');
  }
}

if (require.main === module) {
  const lines = readline.createInterface({input: process.stdin});
  lines.on('line', line => {
    let input;
    try { input = JSON.parse(line); process.stdout.write(JSON.stringify({id: input.id, ok: true, result: dispatch(input)}) + '\n'); }
    catch (error) { process.stdout.write(JSON.stringify({id: input?.id, ok: false, error: {message: error.message}}) + '\n'); }
  });
  lines.on('close', () => { if (battle) battle.destroy(); });
}
module.exports = {dispatch, describe, expand};
