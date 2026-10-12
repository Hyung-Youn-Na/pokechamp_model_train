'use strict';
// Individual pinned Smogon calls, independent of the diagnostic union/worker.
// Restricted to explicit current-state fixtures; no future action prediction.
const fs = require('node:fs');
const base = '../improved_io/calculator/';
const patch = require(base + 'patch.cjs').patchCalc();
const {calculate, Generations, Pokemon, Move, Field} = require(base + 'node_modules/@smogon/calc');
const gen = Generations.get(9);
const id = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const entries = JSON.parse(fs.readFileSync(0, 'utf8')).map(s => {
  const pokemon = spec => {
    const opts = structuredClone(spec.options);
    if (spec.battle_types) opts.overrides = {types: spec.battle_types};
    if (opts.ability) opts.ability = gen.abilities.get(id(opts.ability)).name;
    if (opts.item) opts.item = gen.items.get(id(opts.item)).name;
    const p = new Pokemon(gen, gen.species.get(id(spec.name)).name, opts);
    if (opts.ability === '' || (spec.entry_effects_observed &&
        ['Dauntless Shield', 'Intrepid Sword', 'Embody Aspect (Teal)',
         'Embody Aspect (Hearthflame)', 'Embody Aspect (Wellspring)', 'Embody Aspect (Cornerstone)'].includes(p.ability))) {
      p.ability = '';
      p.species.abilities = {0: ''};
    }
    if (p.ability === 'Intimidate') p.abilityOn = false;
    return p;
  };
  const a = pokemon(s.attacker), d = pokemon(s.defender);
  const move = new Move(gen, gen.moves.get(id(s.move)).name, s.move_options || {});
  const result = calculate(gen, a, d, move, new Field(s.field));
  return {scenario_id: s.scenario_id, damage_range_hp: result.range(),
          defender_max_hp: d.maxHP(), damage_rolls: result.damage, is_crit: move.isCrit};
});
process.stdout.write(JSON.stringify({version: require(base + 'node_modules/@smogon/calc/package.json').version, patch, entries}));
