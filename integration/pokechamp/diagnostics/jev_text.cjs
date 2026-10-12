/* Offline BattleTextParser adapter. Uses pinned official client MIT code and
 * pinned Showdown text tables; no network, simulator, or generated prose. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {environment} = require('../observation/client.cjs');
const root = path.resolve(__dirname, '../../..');
const env = environment(path.join(root, '.artifacts/official-observation/v1'));
const textRoot = path.join(root, 'pokemon-showdown/dist/data/text');
env.BattleText = {en: {}};
for (const [file, key, exported] of [['default','Default','DefaultText'], ['moves','Moves','MovesText'],
  ['abilities','Abilities','AbilitiesText'], ['items','Items','ItemsText']]) {
  // Pinned server uses [TOKEN], pinned client render() expects {TOKEN}.
  // Only placeholder syntax is adapted; official text and parser stay intact.
  const raw = JSON.stringify(require(path.join(textRoot, file + '.js'))[exported]);
  env.BattleText.en[key] = JSON.parse(raw.replace(/\[([A-Z][A-Z0-9]*)\]/g, '{$1}'));
}
// Stat tables moved out of Default in the newer pinned client API.
for (const [target, field] of [['StatNames','statName'],['StatShortNames','statShortName'],['StatMediumNames','statName']]) {
  env.BattleText.en[target] = Object.fromEntries(Object.entries(env.BattleText.en.Default)
    .filter(([,value]) => value[field]).map(([key,value]) => [key,value[field]]));
}
require('node:vm').runInContext('global.TextParser = BattleTextParser;', env);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if (!['p1','p2'].includes(input.actor)) throw new Error('invalid actor');
const parser = new env.TextParser(input.actor, 'en');
parser.p1 = input.actor === 'p1' ? 'You' : 'Opponent';
parser.p2 = input.actor === 'p2' ? 'You' : 'Opponent';
const output = input.events.map(event => {
  const {args, kwArgs} = env.TextParser.parseBattleLine(event.protocol);
  let text = '', error = null;
  try { text = parser.parseArgs(args, kwArgs).trim(); }
  catch (e) { error = e.message; }
  return {text, error};
});
process.stdout.write(JSON.stringify(output));
