'use strict';
const {Battle} = require('../../../pokemon-showdown/dist/sim');
const {Format} = require('../../../pokemon-showdown/dist/sim/dex-formats');
const results = [];
for (const [item, species, ability] of [
  ['Toxic Orb', 'Gliscor', 'Poison Heal'],
  ['Flame Orb', 'Ursaring', 'Guts'],
  ['', 'Gliscor', 'Poison Heal'],
]) {
  const battle = new Battle({format: new Format({name: 'Public item fixture', mod: 'gen9',
    gameType: 'singles', ruleset: []}), seed: [1, 2, 3, 4]});
  battle.setPlayer('p1', {name: 'observer', team: [
    {species: 'Mew', moves: ['Splash', 'Knock Off', 'Toxic'], ability: 'Synchronize'},
  ]});
  battle.setPlayer('p2', {name: 'revealed', team: [
    {species, moves: ['Splash'], ability, item},
    {species: 'Magikarp', moves: ['Splash'], ability: 'Swift Swim'},
  ]});
  battle.makeChoices(item ? 'move 1' : 'move 3', 'move 1');
  const activated = battle.log.join('\n');
  const itemAfterActivation = battle.p2.active[0].item;
  battle.makeChoices('move 2', 'move 1');
  battle.makeChoices('move 1', 'switch 2');
  // Showdown swaps the active Pokemon into team position one on every switch.
  battle.makeChoices('move 1', 'switch 2');
  results.push({item, species, activated, afterRemovalAndSwitch: battle.log.join('\n'),
    itemAfterActivation, itemAfterRemoval: battle.p2.active[0].item});
  battle.destroy();
}
process.stdout.write(JSON.stringify(results));
