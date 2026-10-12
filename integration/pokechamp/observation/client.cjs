/* Official observation v1. Pinned headless client, actor-local incremental state. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const {performance} = require('node:perf_hooks');
const PIN = 'f2faebd6892b314d785a0038f77309afed36970c';
const FILES = ['battle-dex-data', 'battle-dex', 'battle-animations', 'battle-scene-stub',
  'battle-text-parser', 'battle', 'battle-choices'];
const hash = data => crypto.createHash('sha256').update(data).digest('hex');

function build(client, server, output) {
  const revision = cp.execFileSync('git', ['rev-parse', 'HEAD'], {cwd: client, encoding: 'utf8'}).trim();
  if (revision !== PIN) throw new Error('Unexpected client commit');
  if (cp.execFileSync('git', ['diff', '--name-only', 'HEAD'], {cwd: client, encoding: 'utf8'}).trim()) {
    throw new Error('Modified tracked client source');
  }
  fs.mkdirSync(output, {recursive: false});
  const babel = require(path.join(client, 'node_modules/@babel/core'));
  const dependencies = {};
  let compiled = '';
  for (const file of FILES) {
    const filename = path.join(client, 'play.pokemonshowdown.com/src', file + '.ts');
    dependencies[filename] = hash(fs.readFileSync(filename));
    // Modern Node needs only TS erasure and the official browser global linking.
    // No upstream build script (and therefore no server checkout update) runs.
    const result = babel.transformFileSync(filename, {
      babelrc: false, configFile: false, comments: true,
      presets: [[require.resolve(path.join(client, 'node_modules/@babel/preset-typescript')), {allowDeclareFields: true}]],
      plugins: [require.resolve(path.join(client, 'node_modules/babel-plugin-remove-import-export'))],
    });
    compiled += '\n' + result.code + '\n';
  }
  fs.writeFileSync(path.join(output, 'client.js'), compiled);
  const {Dex} = require(path.join(server, 'dist/sim/dex.js'));
  Dex.includeData();
  const data = {};
  for (const [globalName, source] of Object.entries({BattlePokedex: 'Pokedex', BattleMovedex: 'Moves',
    BattleAbilities: 'Abilities', BattleItems: 'Items', BattleTypeChart: 'TypeChart', BattleAliases: 'Aliases'})) {
    data[globalName] = Dex.data[source];
  }
  const serialized = JSON.stringify(data); // public dex only; excludes executable server mechanics
  fs.writeFileSync(path.join(output, 'dex.json'), serialized);
  for (const file of ['package.json', 'package-lock.json']) {
    dependencies[file] = hash(fs.readFileSync(path.join(client, file)));
  }
  const serverRevision = cp.execFileSync('git', ['rev-parse', 'HEAD'], {cwd: server, encoding: 'utf8'}).trim();
  const provenance = {client_commit: revision, server_commit: serverRevision, node: process.version,
    babel: babel.version, dependencies, npm_install: 'npm ci --ignore-scripts --no-audit --no-fund',
    dependency_tree: JSON.parse(cp.execFileSync('npm', ['ls', '--all', '--json'], {cwd: client, encoding: 'utf8', maxBuffer: 20e6})),
    compilation: 'Babel TS erasure + remove-import-export; no upstream build/update scripts',
    data: 'Public Dex.data JSON from existing pinned dist; no battle simulator state',
    data_sha256: hash(serialized), client_js_sha256: hash(compiled),
    licenses: 'battle-*.ts MIT; checkout overall AGPL-3.0; retained upstream headers and checkout LICENSE'};
  fs.writeFileSync(path.join(output, 'provenance.json'), JSON.stringify(provenance, null, 2) + '\n');
  return provenance;
}

function environment(directory) {
  const context = {$: {easing: {}}, console: {log() {}, warn() {}, error(...args) {throw new Error(args.join(' '));}},
    setTimeout, clearTimeout, ...JSON.parse(fs.readFileSync(path.join(directory, 'dex.json')))};
  context.window = context;
  context.global = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(directory, 'client.js'), 'utf8'), context);
  vm.runInContext(`global.createBattle = () => new Battle({debug: true});
    global.fixRequest = (request, battle) => BattleChoiceBuilder.fixRequest(request, battle);
    global.choiceCheck = (request, choice) => new BattleChoiceBuilder(request).addChoice(choice);`, context);
  return context;
}

class Tracker {
  constructor(env, actor) {
    if (!['p1', 'p2'].includes(actor)) throw new Error('Invalid actor');
    this.env = env;
    this.actor = actor;
    this.battle = env.createBattle();
    // The official headless stub uses NaN, unlike BattleScene's counter (1).
    // NaN !== NaN cancels every official timer continuation. No animations or
    // seeking/reset operations exist in this append-only adapter.
    this.battle.scene.interruptionCount = 1;
    this.request = null;
    this.rawRequest = null;
    this.consumed = 0;
  }
  progress(stage) {
    return {stage, consumed: this.consumed, current_step: this.battle.currentStep,
      queue_length: this.battle.stepQueue.length, at_queue_end: this.battle.atQueueEnd};
  }
  async drain(deadline) {
    const complete = () => this.battle.atQueueEnd &&
      this.battle.currentStep === this.battle.stepQueue.length;
    if (performance.now() >= deadline) throw new Error('Official processing deadline exceeded');
    if (complete()) return;
    await new Promise((resolve, reject) => {
      const previous = this.battle.subscription;
      const finish = error => {
        clearTimeout(timer);
        this.battle.subscribe(previous);
        error ? reject(error) : resolve();
      };
      const timer = setTimeout(() => finish(new Error('Official processing deadline exceeded')),
        Math.max(1, deadline - performance.now()));
      this.battle.subscribe(state => {
        try {
          previous?.(state);
          // Resolve only after the official end-of-queue finalization. Promise
          // continuation runs after the callback and nextStep have returned.
          if (state === 'atqueueend' && complete()) finish();
        } catch (error) { finish(error); }
      });
    });
  }
  async append(lines, deadline = performance.now() + 30000) {
    for (const line of lines) {
      if (performance.now() >= deadline) throw new Error('Official processing deadline exceeded');
      if (typeof line !== 'string') throw new Error('Invalid protocol row');
      if (line.startsWith('|request|')) {
        await this.drain(deadline);
        const raw = line.slice(9);
        this.rawRequest = raw ? JSON.parse(raw) : null;
        this.request = this.rawRequest && JSON.parse(raw);
        if (this.request) {
          if (this.request.side && this.request.side.id !== this.actor) throw new Error('Foreign private request');
          if ((this.request.active?.length || 0) > 1 || (this.request.forceSwitch?.length || 0) > 1) throw new Error('Only singles supported');
          this.env.fixRequest(this.request, this.battle);
          if (this.request.side) {
            this.battle.myPokemon = this.request.side.pokemon;
            this.battle.setViewpoint(this.request.side.id);
          }
        }
      } else if (line.startsWith('|')) {
        this.battle.add(line);
        await this.drain(deadline);
      }
      await this.drain(deadline);
      this.consumed++;
    }
    await this.drain(deadline);
  }
  snapshot() {
    const {battle, request, env} = this;
    // Effect arrays may contain Pokemon references (e.g. Transform). Preserve
    // identity rather than traversing the cyclic battle graph or dropping values.
    const serial = value => {
      if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) return value;
      if (value === undefined) return null;
      if (Array.isArray(value)) return value.map(serial);
      if (value.side && typeof value.ident === 'string') return {pokemon_ident: value.ident};
      if (typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k, serial(v)]));
      throw new Error('Unsupported official effect value');
    };
  const mon = p => ({ident: p.ident, species: p.speciesForme, details: p.details,
    active: p.isActive(), fainted: p.fainted, hp: p.hp, max_hp: p.maxhp,
    level: p.level, status: p.status, status_data: p.statusData, boosts: p.boosts, ability: p.ability, baseAbility: p.baseAbility,
    item: p.item, prevItem: p.prevItem, itemEffect: p.itemEffect, prevItemEffect: p.prevItemEffect,
    moves: p.moveTrack, types: p.getTypeList(), battle_types: p.getTypeList(undefined, true), tera_type: p.terastallized,
    volatiles: serial(p.volatiles), turnstatuses: serial(p.turnstatuses), movestatuses: serial(p.movestatuses)});
  const sides = battle.sides.map(s => ({id: 'p' + (s.n + 1), pokemon: s.pokemon.map(mon),
    active: s.active.map(p => p && p.ident), side_conditions: s.sideConditions}));
  // Enumerate UI-eligible singles options and validate through official choice code.
  // ChoiceBuilder alone accepts disabled numeric move slots, so retain UI filtering.
  const candidates = [];
  if (request && request.side && request.requestType !== 'wait') {
    const push = (wire, action) => {
      const error = env.choiceCheck(request, wire);
      if (error) throw new Error('Official candidate rejected: ' + wire + ': ' + error);
      candidates.push({wire, action});
    };
    if (request.requestType === 'team') {
      request.side.pokemon.forEach((p, i) => push('team ' + (i + 1), {team: i + 1}));
    } else {
      const active = request.active?.[0];
      if (request.requestType === 'move' && active) {
        active.moves.forEach((m, i) => {
          if (m.disabled || m.pp === 0) return;
          push('move ' + (i + 1), {move: m.id});
          if (active.canTerastallize) push('move ' + (i + 1) + ' terastallize', {terastallize: m.id});
        });
      }
      if (request.requestType === 'switch' || !active?.trapped) {
        request.side.pokemon.forEach((p, i) => {
          if (!p.active && !p.fainted) push('switch ' + (i + 1), {switch: p.speciesForme});
        });
      }
    }
  }
  return {turn: battle.turn, request: this.rawRequest, choice_request: request, sides, weather: battle.weather,
    weather_duration: [battle.weatherMinTimeLeft, battle.weatherTimeLeft],
    field: battle.pseudoWeather, candidates, consumed: this.consumed,
    official_steps: battle.currentStep, game_type: battle.gameType, gen: battle.gen};
  }
}

async function capture(env, input) {
  const tracker = new Tracker(env, input.actor);
  await tracker.append(input.lines);
  return tracker.snapshot();
}

if (require.main === module) {
  const [command, ...args] = process.argv.slice(2);
  if (command === 'build') {
    const p = build(...args.map(p => path.resolve(p)));
    process.stdout.write(JSON.stringify({client_commit: p.client_commit, data_sha256: p.data_sha256}) + '\n');
  } else if (command === 'serve') {
    const env = environment(path.resolve(args[0]));
    const actor = args[1];
    const trackers = new Map();
    const rl = require('node:readline').createInterface({input: process.stdin});
    let chain = Promise.resolve(), failed = false, active = null;
    const fatal = error => {
      if (failed) return;
      failed = true;
      const diagnostic = {...active?.tracker?.progress(active.stage),
        operation: active?.input?.op, battle_id: active?.input?.battle_id,
        stage: active?.stage || 'command',
        elapsed_ms: active ? performance.now() - active.started : 0};
      trackers.clear();
      rl.close();
      process.stdout.write(JSON.stringify({ok: false, error: error.stack || String(error), diagnostic}) + '\n',
        () => process.exit(1));
    };
    process.on('uncaughtException', fatal);
    process.on('unhandledRejection', fatal);
    rl.on('line', line => {
      chain = chain.then(async () => {
        if (failed) return;
        active = {started: performance.now(), stage: 'command'};
        try {
          const input = JSON.parse(line);
          active.input = input;
          if (input.actor !== actor || typeof input.battle_id !== 'string') throw new Error('Foreign actor/battle');
          const timeout = input.timeout_ms ?? 30000;
          if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 30000) throw new Error('Invalid processing timeout');
          const deadline = active.started + timeout;
          let state;
          if (input.op === 'drop') {
            trackers.delete(input.battle_id);
            state = null;
          } else if (input.op === 'append' || input.op === 'replay') {
            if (input.op === 'append' && !trackers.has(input.battle_id)) trackers.set(input.battle_id, new Tracker(env, actor));
            const tracker = input.op === 'replay' ? new Tracker(env, actor) : trackers.get(input.battle_id);
            active.tracker = tracker;
            if (input.op === 'append' && input.offset !== tracker.consumed) throw new Error('Protocol boundary mismatch');
            active.stage = 'drain';
            await tracker.append(input.lines, deadline);
            active.stage = 'snapshot';
            state = tracker.snapshot();
            if (performance.now() >= deadline) throw new Error('Official processing deadline exceeded');
          } else throw new Error('Unknown operation');
          process.stdout.write(JSON.stringify({ok: true, state, rss_bytes: process.memoryUsage().rss}) + '\n');
          active = null;
        } catch (error) { fatal(error); }
      });
    });
    // EOF is cancellation, including a client closing while a timer is pending.
    rl.on('close', () => { if (!failed) process.exit(0); });
  } else throw new Error('Usage: client.cjs build CLIENT SERVER OUTPUT | serve BUILD ACTOR');
}
module.exports = {build, capture, environment, Tracker};
