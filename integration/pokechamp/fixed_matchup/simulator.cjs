'use strict';
const readline = require('node:readline');
const {Battle, extractChannelMessages} = require('../../../pokemon-showdown/dist/sim/battle');
const {Teams} = require('../../../pokemon-showdown/dist/sim/teams');
const {TeamValidator} = require('../../../pokemon-showdown/dist/sim/team-validator');
const {PRNG} = require('../../../pokemon-showdown/dist/sim/prng');
const {exportPublic, importPublic} = require('./public_state.cjs');
const {observe, legalActions, vocabulary} = require('./observation.cjs');
const role = process.argv[2];
if (!['real', 'search'].includes(role)) throw Error('explicit simulator role required');
let battle;
let messages = [];
const copy = v => JSON.parse(JSON.stringify(v));
const capture = (type, data) => messages.push({type, data: Array.isArray(data) ? data.join('\n') : String(data)});
function seed(value) {
  if (!Array.isArray(value) || value.length !== 4 || value.some(n => !Number.isInteger(n) || n < 0 || n > 65535)) {
    throw Error('four uint16 seed values required');
  }
  return value;
}
function requireBattle() { if (!battle) throw Error('battle not initialized'); }
function output() {
  requireBattle();
  if (battle.ended) return {ended: true, winner: battle.winner, turn: battle.turn, observations: {}, root: null};
  return {ended: false, winner: '', turn: battle.turn, root: exportPublic(battle),
    observations: {p1: observe(battle, 'p1'), p2: observe(battle, 'p2')}};
}
function dispatch(input) {
  messages = [];
  switch (input.op) {
  case 'catalog': return {vocabulary: vocabulary()};
  case 'validate': {
    const result = {};
    for (const [name, text] of Object.entries(input.teams)) {
      const team = Teams.import(text);
      result[name] = new TeamValidator('gen9ou').validateTeam(team);
    }
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
    return output();
  }
  case 'restore': {
    if (role !== 'search') throw Error('actual game cannot restore a search root');
    const restored = Battle.fromJSON(importPublic(input.root, seed(input.seed)));
    if (battle) battle.destroy();
    battle = restored;
    battle.restart(capture);
    for (const side of battle.sides) side.clearChoice();
    return output();
  }
  case 'advance': {
    requireBattle();
    if (battle.ended) throw Error('cannot advance terminal battle');
    exportPublic(battle);
    const commands = {};
    for (const side of battle.sides) {
      const legal = legalActions(battle, side);
      if (!legal.length) continue;
      const action = legal.find(a => a.id === input.actions?.[side.id]);
      if (!action) throw Error('missing or illegal joint action');
      commands[side.id] = action.command;
    }
    if (Object.keys(commands).sort().join() !== Object.keys(input.actions).sort().join()) throw Error('extra joint action');
    // Validate both sides before submitting either side. No partial-choice RPC exists.
    for (const [side, command] of Object.entries(commands)) if (!battle.choose(side, command)) throw Error('Showdown rejected legal action');
    battle.sendUpdates();
    return output();
  }
  case 'evidence': {
    if (role !== 'real') throw Error('search has no actual evidence capability');
    const logs = extractChannelMessages(battle.log.join('\n'), [0, 1, 2]);
    return copy({messages, public_log: logs[0], actor_logs: {p1: logs[1], p2: logs[2]},
      requests: Object.fromEntries(battle.sides.map(s => [s.id, s.activeRequest])),
      ended: battle.ended, winner: battle.winner, turn: battle.turn, snapshot: battle.toJSON()});
  }
  case 'status': return output();
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
