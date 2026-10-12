'use strict';

// This process is a private simulator, never a player-facing source of state.
const path = require('node:path');
const readline = require('node:readline');
const sim = path.resolve(__dirname, '../../../pokemon-showdown/dist/sim');
const {BattleStream} = require(path.join(sim, 'battle-stream.js'));
const {Battle, extractChannelMessages} = require(path.join(sim, 'battle.js'));
const {Teams} = require(path.join(sim, 'teams.js'));
const {PRNG} = require(path.join(sim, 'prng.js'));

const copy = value => JSON.parse(JSON.stringify(value));
const SIDES = ['p1', 'p2'];
let stream = null;
let messages = [];

function seedString(seed) {
  if (!Array.isArray(seed) || seed.length !== 4 ||
      seed.some(n => !Number.isInteger(n) || n < 0 || n > 65535)) {
    throw new Error('seed must contain four uint16 integers');
  }
  return seed.join(',');
}

function capture(type, data) {
  messages.push({type, data: Array.isArray(data) ? data.join('\n') : String(data)});
}

function requireBattle() {
  if (!stream?.battle) throw new Error('simulator is not initialized');
  return stream.battle;
}

function status() {
  const battle = requireBattle();
  const requests = {}, choicesDone = {}, choices = {};
  const needsChoice = [];
  for (const side of battle.sides) {
    requests[side.id] = side.activeRequest;
    choicesDone[side.id] = side.isChoiceDone();
    choices[side.id] = side.getChoice();
    if (!battle.ended && side.activeRequest && !side.activeRequest.wait && !choicesDone[side.id]) {
      needsChoice.push(side.id);
    }
  }
  const logs = extractChannelMessages(battle.log.join('\n'), [0, 1, 2]);
  return copy({
    messages, requests, needs_choice: needsChoice, choices_done: choicesDone, choices,
    ended: battle.ended, winner: battle.winner, turn: battle.turn,
    request_state: battle.requestState, mid_turn: battle.midTurn,
    queue_length: battle.queue.list.length, public_log: logs[0],
    actor_logs: {p1: logs[1], p2: logs[2]},
    errors: messages.filter(m => m.type === 'sideupdate' && m.data.includes('|error|')),
  });
}

function newStream() {
  if (stream?.battle) stream.battle.destroy();
  stream = new BattleStream({noCatch: true, keepAlive: true});
  // Avoid accumulating a second, unread stream buffer; the RPC owns delivery.
  stream.pushMessage = capture;
}

function init(input) {
  const seed = seedString(input.seed);
  if (!input.teams || Object.keys(input.teams).sort().join(',') !== SIDES.join(',')) {
    throw new Error('exactly p1 and p2 teams are required');
  }
  const order = input.player_order || Object.keys(input.teams);
  if (!Array.isArray(order) || [...order].sort().join(',') !== SIDES.join(',')) {
    throw new Error('player_order must contain each side exactly once');
  }
  const players = {};
  for (const side of SIDES) {
    const player = copy(input.teams[side]);
    if (!player || typeof player.name !== 'string' || !player.name || typeof player.team !== 'string') {
      throw new Error('each player requires name and team strings');
    }
    const packed = !/[\r\n]/.test(player.team) && player.team.includes('|');
    const team = packed ? Teams.unpack(player.team) : Teams.import(player.team);
    if (!team?.length) throw new Error('team text/packed input could not be parsed');
    // Preserve the exact archived wire representation and nicknames when the
    // caller has already packed through poke-env's original team builder.
    players[side] = {...player, team: packed ? player.team : Teams.pack(team)};
  }
  newStream();
  stream._writeLine('start', JSON.stringify({
    formatid: input.formatid || 'gen9ou', seed, strictChoices: true,
  }));
  for (const side of order) stream._writeLine('player', `${side} ${JSON.stringify(players[side])}`);
  stream.battle.sendUpdates();
  return status();
}

function step(input) {
  const battle = requireBattle();
  const choices = input.choices;
  if (!choices || typeof choices !== 'object' || Array.isArray(choices) || !Object.keys(choices).length) {
    throw new Error('choices must be a nonempty side-to-command object');
  }
  const eligible = new Set(status().needs_choice);
  for (const [side, command] of Object.entries(choices)) {
    if (!eligible.has(side)) throw new Error(`side ${side} does not need a choice at this barrier`);
    if (typeof command !== 'string' || !command || /[\r\n]/.test(command) ||
        command.startsWith('/') || (command !== 'default' && !/^(?:move|switch|team|pass)\b/.test(command))) {
      throw new Error('expected a single move/switch/team/pass/default command without slash');
    }
  }
  // Validate all participating sides before submitting; a one-sided switch may
  // advance the queue, so newly generated requests must not consume old choices.
  for (const [side, command] of Object.entries(choices)) {
    if (!battle.choose(side, command)) throw new Error(`choice rejected for ${side}`);
  }
  battle.sendUpdates();
  return status();
}

function dispatch(input) {
  messages = [];
  switch (input.op) {
  case 'init': return init(input);
  case 'step': return step(input);
  case 'status': return status();
  case 'snapshot': return copy(requireBattle().toJSON());
  case 'restore': {
    if (!input.snapshot || input.snapshot.strictChoices !== true) {
      throw new Error('restore requires a strict-choice simulator snapshot');
    }
    const battle = Battle.fromJSON(copy(input.snapshot));
    newStream();
    stream.battle = battle;
    battle.restart(capture);
    // Retain requests, submitted choices, queue, sent positions and PRNG.
    return status();
  }
  case 'reseed': {
    const seed = seedString(input.seed);
    const battle = requireBattle();
    // Same PRNG replacement as Battle.resetRNG, without its player-visible
    // administrative message. The seed belongs only in private provenance.
    battle.prng = new PRNG(seed);
    battle.inputLog.push(`>reseed ${battle.prng.getSeed()}`);
    return status();
  }
  case 'close':
    if (stream?.battle) stream.battle.destroy();
    stream = null;
    return {closed: true};
  default: throw new Error(`unknown operation ${input.op}`);
  }
}

const lines = readline.createInterface({input: process.stdin});
lines.on('line', line => {
  let input;
  try {
    input = JSON.parse(line);
    const result = dispatch(input);
    process.stdout.write(JSON.stringify({id: input.id, ok: true, result}) + '\n');
    if (input.op === 'close') lines.close();
  } catch (error) {
    process.stdout.write(JSON.stringify({id: input?.id, ok: false,
      error: {name: error.name, message: error.message}, messages}) + '\n');
  }
});
lines.on('close', () => {
  if (stream?.battle) stream.battle.destroy();
});
