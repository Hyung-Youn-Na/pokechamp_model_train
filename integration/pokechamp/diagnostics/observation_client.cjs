/* EP-055: pinned official client, headless only. No server build/update/network. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const cp = require('node:child_process');
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

function capture(env, input) {
  const battle = env.createBattle();
  let request = null;
  for (const line of input.lines) {
    if (!line.startsWith('|')) continue;
    if (line.startsWith('|request|')) {
      const raw = line.slice(9);
      if (!raw) continue;
      request = JSON.parse(raw);
      if (!request) continue;
      if (request.side && request.side.id !== input.actor) throw new Error('Foreign private request');
      env.fixRequest(request, battle);
      if (request.side) {
        battle.myPokemon = request.side.pokemon;
        battle.setViewpoint(request.side.id);
      }
    } else {
      battle.add(line);
    }
  }
  if (battle.currentStep !== battle.stepQueue.length) throw new Error('Unconsumed official protocol');
  const mon = p => ({ident: p.ident, species: p.speciesForme, details: p.details,
    active: p.isActive(), fainted: p.fainted, hp: p.hp, max_hp: p.maxhp,
    status: p.status, boosts: p.boosts, ability: p.ability, baseAbility: p.baseAbility,
    item: p.item, prevItem: p.prevItem, itemEffect: p.itemEffect,
    moves: p.moveTrack, types: p.getTypeList(), tera_type: p.terastallized,
    volatiles: Object.keys(p.volatiles), turnstatuses: Object.keys(p.turnstatuses)});
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
  return {turn: battle.turn, request, sides, weather: battle.weather,
    weather_duration: [battle.weatherMinTimeLeft, battle.weatherTimeLeft],
    field: battle.pseudoWeather, candidates, consumed: input.lines.length,
    official_steps: battle.currentStep};
}

if (require.main === module) {
  const [command, ...args] = process.argv.slice(2);
  if (command === 'build') {
    const p = build(...args.map(p => path.resolve(p)));
    process.stdout.write(JSON.stringify({client_commit: p.client_commit, data_sha256: p.data_sha256}) + '\n');
  } else if (command === 'replay') {
    const env = environment(path.resolve(args[0]));
    const rl = require('node:readline').createInterface({input: process.stdin});
    rl.on('line', line => {
      try { process.stdout.write(JSON.stringify({ok: true, state: capture(env, JSON.parse(line))}) + '\n'); }
      catch (error) { process.stdout.write(JSON.stringify({ok: false, error: error.stack}) + '\n'); }
    });
  } else throw new Error('Usage: observation_client.cjs build CLIENT SERVER OUTPUT | replay BUILD');
}
module.exports = {build, capture, environment};
