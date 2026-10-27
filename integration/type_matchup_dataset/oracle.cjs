/* Gen9 type-only oracle. Pokemon Showdown events are explicitly neutralized:
 * no ability/item/move-specific alterations are part of this dataset. */
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const {Dex} = require(path.join(root, 'pokemon-showdown/dist/sim/dex'));
const {Pokemon} = require(path.join(root, 'pokemon-showdown/dist/sim/pokemon'));
const dex = Dex.forFormat('gen9ou');
if (dex.gen !== 9) throw new Error('Expected Gen9');
const types = dex.types.all().map(t => t.name).filter(t => t !== 'Stellar').sort();
if (types.length !== 18) throw new Error('Expected 18 ordinary types');
if (process.argv[2] === 'chart') {
  console.log(JSON.stringify({generation: 9, format: 'gen9ou', types,
    damage_taken: Object.fromEntries(types.map(t => [t, dex.types.get(t).damageTaken]))}));
} else if (process.argv[2] === 'validate') {
  const rows = fs.readFileSync(process.argv[3], 'utf8').trim().split('\n').map(JSON.parse);
  let count = 0;
  const pokemon = {
    species: {name: 'Mew'}, types: [], addedType: '', terastallized: '',
    getTypes: Pokemon.prototype.getTypes,
    battle: {
      gen: 9, dex,
      runEvent(event, target, source, effect, relay) {
        if (!['Type', 'Effectiveness'].includes(event)) throw new Error(event);
        return relay;
      },
      singleEvent(event, move, state, target, type, effect, relay) {
        if (event !== 'Effectiveness') throw new Error(event);
        return relay;
      },
    },
  };
  for (const row of rows) {
    pokemon.types = row.defender_types.slice();
    pokemon.terastallized = row.defender_tera_type || '';
    const effective = pokemon.getTypes();
    const move = {type: row.attack_type, category: 'Special'};
    const exponent = Pokemon.prototype.runEffectiveness.call(pokemon, move);
    const multiplier = dex.getImmunity(move, effective) ? 2 ** exponent : 0;
    if (multiplier !== row.multiplier || JSON.stringify(effective) !== JSON.stringify(row.effective_defender_types)) {
      throw new Error(JSON.stringify({id: row.id, multiplier, effective, expected: row.multiplier}));
    }
    // Dual order invariance independently exercised through engine methods.
    pokemon.types.reverse();
    const reversed = dex.getImmunity(move, pokemon.getTypes()) ?
      2 ** Pokemon.prototype.runEffectiveness.call(pokemon, move) : 0;
    if (reversed !== multiplier) throw new Error('Order dependence: '+row.id);
    count++;
  }
  console.log(JSON.stringify({passed: true, checked: count, reverse_order_checked: count,
    oracle: 'Gen9 Dex.getImmunity + Pokemon.getTypes/runEffectiveness',
    scope: 'Type-only; passthrough Type/Effectiveness events; synthetic types, not legal species claims'}));
} else throw new Error('Expected chart or validate');
