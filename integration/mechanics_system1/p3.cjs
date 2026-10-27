/* EP201 priority 3. Synthetic controlled Gen9 rules, not legal OU sets.
 * Oracle: pinned Pokemon Showdown (MIT); independently specified expectations.
 * Selection requests and execution gates are deliberately different questions.
 */
'use strict';
const assert = require('node:assert/strict');
const {Dex, Battle} = require('../../pokemon-showdown/dist/sim');
const dex = Dex.forFormat('gen9customgame');
const PIN = 'e64915c0eab066db1d3e732b1280386468dd7415';
function scene(ability = 'No Ability', item = '', moves = ['tackle', 'growl']) {
  const b = new Battle({formatid: 'gen9customgame', seed: [2026, 10, 21, 201]});
  b.setPlayer('p1', {name: 'user', team: [{species: 'Mew', ability, item, moves}]});
  b.setPlayer('p2', {name: 'target', team: [{species: 'Mew', ability: 'No Ability', moves: ['splash']}]});
  return b;
}
function selection(b, p) {
  for (const slot of p.moveSlots) { slot.disabled = false; slot.disabledSource = ''; }
  b.runEvent('DisableMove', p);
  return p.getMoveRequestData().moves.filter(m => !m.disabled).map(m => m.id);
}
function rows() {
  const out = [];
  function add(id, rule_id, state, question, options, expected, observed, source, extra = {}) {
    assert.deepEqual(observed, expected, id);
    assert(options.includes(expected), id);
    out.push({id: `p3-${id}`, priority: 3, rule_id,
      state: {generation: 9, format: 'controlled singles; no species/moveset legality claim', ...state},
      question, options, answer: expected,
      evidence: {source, expected, observed, engine_commit: PIN, ...extra}});
  }
  // All independent combinations of known restrictions, excluding impossible active
  // Encore/Disable snapshots whose constrained move already has no PP on application.
  for (const item of ['', 'assaultvest', 'choiceband', 'choicescarf', 'choicespecs'])
  for (const klutz of [false, true]) for (const taunt of [false, true])
  for (const encore of ['', 'tackle', 'growl']) for (const disabled of ['', 'tackle', 'growl'])
  for (const pp of [[0, 0], [0, 3], [3, 0], [3, 3]]) {
    if (encore && pp[encore === 'tackle' ? 0 : 1] === 0) continue;
    if (disabled && pp[disabled === 'tackle' ? 0 : 1] === 0) continue;
    const b = scene(klutz ? 'Klutz' : 'No Ability', item);
    try {
      const p = b.p1.active[0], q = b.p2.active[0];
      p.moveSlots.forEach((s, i) => { s.pp = pp[i]; });
      if (item.startsWith('choice')) {
        b.activeMove = dex.getActiveMove('tackle');
        assert(p.addVolatile('choicelock', p));
      }
      if (encore) { p.lastMove = dex.getActiveMove(encore); assert(p.addVolatile('encore', q)); }
      if (disabled) { p.lastMove = dex.getActiveMove(disabled); assert(p.addVolatile('disable', q)); }
      if (taunt) assert(p.addVolatile('taunt', q));
      const expectedIds = ['tackle', 'growl'].filter((m, i) => pp[i] > 0 &&
        !(m === 'growl' && (taunt || item === 'assaultvest' && !klutz)) &&
        !(item.startsWith('choice') && !klutz && m !== 'tackle') &&
        (!encore || m === encore) && m !== disabled);
      if (!expectedIds.length) expectedIds.push('struggle');
      const names = ids => ids.map(id => dex.moves.get(id).name).join(' + ');
      const observed = selection(b, p);
      add(`selection-${item || 'none'}-${klutz}-${taunt}-${encore || 'none'}-${disabled || 'none'}-${pp.join('-')}`,
        'move_selection_restrictions', {
          phase: 'move selection, before either side acts', ability: klutz ? 'Klutz (active)' : 'No Ability',
          item: item ? dex.items.get(item).name : 'None',
          known_moves: [{name: 'Tackle', pp: pp[0]}, {name: 'Growl', pp: pp[1]}],
          taunt_active: taunt, encore_locked_move: encore ? dex.moves.get(encore).name : 'None',
          disabled_move: disabled ? dex.moves.get(disabled).name : 'None',
          choice_lock_move: item.startsWith('choice') ? 'Tackle' : 'None',
          assumptions: 'Exactly these two known moves. Listed volatiles are currently active. No other restrictions, PP effects, item suppression, transformation, recharge or trapping. Switching is outside this question.'
        }, 'Which moves are selectable now (including mandatory Struggle if no ordinary move is usable)?',
        ['Tackle', 'Growl', 'Tackle + Growl', 'Struggle'], names(expectedIds), names(observed),
        'sim/pokemon.ts:getMoveRequestData/getMoves; Battle.runEvent DisableMove; data/moves.ts:taunt/encore/disable; data/conditions.ts:choicelock; data/items.ts:assaultvest; data/abilities.ts:klutz',
        {request_move_ids: observed});
    } finally { b.destroy(); }
  }
  // A newly applied Taunt can stop an already selected status move; Mental Herb
  // acts during Update before that attempt, unlike request-only legality checks.
  for (const effect of ['taunt', 'disable', 'encore'])
  for (const herb of [false, true]) for (const klutz of [false, true]) {
    const b = scene(klutz ? 'Klutz' : 'No Ability', herb ? 'mentalherb' : '');
    try {
      const p = b.p1.active[0], q = b.p2.active[0];
      p.lastMove = dex.getActiveMove('growl');
      assert(p.addVolatile(effect, q));
      b.runEvent('Update', p);
      const removed = !p.volatiles[effect];
      const expected = herb && !klutz;
      add(`herb-${effect}-${herb}-${klutz}`, 'mental_herb_restriction_cure', {
        phase: 'immediately after successful application and item Update', new_volatile: dex.moves.get(effect).name,
        item: herb ? 'Mental Herb, unconsumed before application' : 'None',
        ability: klutz ? 'Klutz (active)' : 'No Ability', last_move: 'Growl, with PP remaining',
        assumptions: 'Application succeeded. No other volatile or item effect; no Magic Room. Observe only whether this new volatile remains.'
      }, 'Has the newly applied restriction been removed before the next action?', ['Yes', 'No'],
      expected ? 'Yes' : 'No', removed ? 'Yes' : 'No',
      'data/items.ts:mentalherb.onUpdate; actual Pokemon.addVolatile and Battle.runEvent Update',
      {remaining_item: p.item, volatile_remaining: !removed});
    } finally { b.destroy(); }
  }
  for (const move of ['tackle', 'growl', 'recover', 'protect']) for (const taunt of [false, true]) {
    const b = scene('No Ability', '', [move]);
    try {
      const p = b.p1.active[0], q = b.p2.active[0];
      if (taunt) assert(p.addVolatile('taunt', q));
      const allowed = b.runEvent('BeforeMove', p, q, dex.getActiveMove(move)) !== false;
      const expected = !taunt || move === 'tackle';
      add(`taunt-execution-${move}-${taunt}`, 'taunt_execution_gate', {
        phase: 'execution of an already selected move', move: dex.moves.get(move).name, taunt_active_at_execution: taunt,
        assumptions: 'The move was selected before any new Taunt. Isolate the Taunt BeforeMove gate; all other action blockers absent. Passing this gate does not guarantee the move hits or succeeds.'
      }, 'Does the selected move pass the Taunt execution gate?', ['Yes', 'No'],
      expected ? 'Yes' : 'No', allowed ? 'Yes' : 'No', 'data/moves.ts:taunt.condition.onBeforeMove; actual Battle.runEvent BeforeMove');
    } finally { b.destroy(); }
  }
  // Actual move execution: protection success has already been established.
  for (const move of ['tackle', 'swift', 'feint', 'hyperspacefury', 'growl', 'taunt'])
  for (const protectedTarget of [false, true]) for (const unseen of [false, true]) {
    const b = scene(unseen ? 'Unseen Fist' : 'No Ability', '', [move]);
    try {
      const p = b.p1.active[0], q = b.p2.active[0];
      // Hyperspace Fury is species-locked; use the actual permitted species.
      if (move === 'hyperspacefury') {
        p.formeChange('Hoopa-Unbound', null, true);
        p.setAbility(unseen ? 'unseenfist' : 'noability');
      }
      if (protectedTarget) assert(q.addVolatile('protect', q));
      const before = q.hp;
      const activeMove = dex.getActiveMove(move);
      activeMove.accuracy = true; // Explicitly condition on the accuracy gate passing.
      b.actions.useMove(activeMove, p, {target: q});
      const affected = q.hp < before || q.boosts.atk < 0 || !!q.volatiles.taunt;
      const bypass = ['feint', 'hyperspacefury'].includes(move) || unseen && move === 'tackle';
      const expected = !protectedTarget || bypass;
      add(`protect-${move}-${protectedTarget}-${unseen}`, 'protect_execution_bypass', {
        phase: 'execution after move selection', move: dex.moves.get(move).name,
        user_species: move === 'hyperspacefury' ? 'Hoopa-Unbound' : 'Mew',
        user_ability: unseen ? 'Unseen Fist (active)' : 'No Ability', target_species: 'Mew',
        target_protect_already_active: protectedTarget,
        assumptions: 'All accuracy checks succeed (conditioned, not a hit-probability claim). Target is healthy, has no ability/item/substitute/status, neutral stat stages, and no relevant type immunity. No other prevention or field effect; ordinary non-Z/non-Max move. Protect establishment roll is not being tested.'
      }, 'Does this attempted move affect the target through the stated protection state?', ['Yes', 'No'],
      expected ? 'Yes' : 'No', affected ? 'Yes' : 'No', 'data/moves.ts:protect/feint/hyperspacefury; data/abilities.ts:unseenfist; actual Battle.actions.useMove',
      {hp_lost: before - q.hp, attack_stage: q.boosts.atk, taunt: !!q.volatiles.taunt});
    } finally { b.destroy(); }
  }
  for (const move of ['tackle', 'swift', 'hypervoice', 'growl', 'thunderwave', 'taunt'])
  for (const substitute of [false, true]) for (const infiltrator of [false, true]) {
    const b = scene(infiltrator ? 'Infiltrator' : 'No Ability', '', [move]);
    try {
      const p = b.p1.active[0], q = b.p2.active[0];
      if (substitute) assert(q.addVolatile('substitute', q));
      const before = q.hp, beforeSub = q.volatiles.substitute?.hp;
      const activeMove = dex.getActiveMove(move);
      activeMove.accuracy = true; // Includes Thunder Wave's otherwise 90% accuracy.
      b.actions.useMove(activeMove, p, {target: q});
      const affected = q.hp < before || q.boosts.atk < 0 || !!q.status || !!q.volatiles.taunt;
      const bypass = infiltrator || ['hypervoice', 'growl', 'taunt'].includes(move);
      const expected = !substitute || bypass;
      add(`substitute-${move}-${substitute}-${infiltrator}`, 'substitute_target_effect_gate', {
        phase: 'execution after move selection', move: dex.moves.get(move).name,
        user_ability: infiltrator ? 'Infiltrator (active)' : 'No Ability',
        target_species: 'Mew', target_substitute_active: substitute,
        assumptions: 'All accuracy checks succeed (conditioned, not a hit-probability claim). Target is healthy with no ability/item/status, neutral stat stages, and no relevant type immunity. No protection, field effect or other failure condition. Evaluate the Pokemon itself, not damage to its substitute.'
      }, 'Does the move affect the target Pokemon itself, rather than only its substitute or being blocked?', ['Yes', 'No'],
      expected ? 'Yes' : 'No', affected ? 'Yes' : 'No', 'data/moves.ts:substitute; move bypasssub flags; data/abilities.ts:infiltrator; actual Battle.actions.useMove',
      {hp_lost: before - q.hp, before_substitute_hp: beforeSub ?? null,
        after_substitute_hp: q.volatiles.substitute?.hp ?? null, target_status: q.status});
    } finally { b.destroy(); }
  }
  // Isolated exact queue predicate: a passed Sucker Punch gate is not guaranteed damage.
  for (const queued of ['tackle', 'growl', 'suckerpunch', 'none']) for (const recharge of [false, true]) {
    if (recharge && queued !== 'none') continue; // A recharge turn has no pending attacking move.
    const target = {volatiles: recharge ? {mustrecharge: {}} : {}};
    const ctx = {queue: {willMove: () => queued === 'none' ? null : {choice: 'move', move: dex.moves.get(queued)}}};
    const passed = dex.moves.get('suckerpunch').onTry.call(ctx, {}, target) !== false;
    const expected = !recharge && ['tackle', 'suckerpunch'].includes(queued);
    add(`sucker-punch-${queued}-${recharge}`, 'sucker_punch_queue_gate', {
      phase: 'Sucker Punch execution', target_pending_move: queued === 'none' ? 'No remaining move action (already acted or switched)' : dex.moves.get(queued).name,
      target_must_recharge: recharge,
      assumptions: 'Exactly the stated target action remains in the action queue. No other failure/immunity/protection condition is evaluated. Selection of Sucker Punch was legal.'
    }, 'Does Sucker Punch pass its pending-damaging-move condition?', ['Yes', 'No'],
    expected ? 'Yes' : 'No', passed ? 'Yes' : 'No', 'data/moves.ts:suckerpunch.onTry (direct hook with explicit queue)');
  }
  for (const firstAction of [true, false]) {
    const passed = dex.moves.get('fakeout').onTry.call({hint() {}}, {activeMoveActions: firstAction ? 1 : 2}) !== false;
    add(`fake-out-${firstAction}`, 'fake_out_first_action_gate', {
      phase: 'Fake Out execution', first_action_since_switch_in: firstAction,
      assumptions: 'User can act; target exists. Isolate the first-action condition, not accuracy, protection, immunity or flinching.'
    }, 'Does Fake Out pass its first-action condition?', ['Yes', 'No'],
    firstAction ? 'Yes' : 'No', passed ? 'Yes' : 'No', 'data/moves.ts:fakeout.onTry');
  }
  for (const chosen of ['tackle', 'growl']) for (const constrained of ['tackle', 'growl']) {
    const b = scene();
    try {
      const p = b.p1.active[0], q = b.p2.active[0];
      p.lastMove = dex.getActiveMove(constrained);
      assert(p.addVolatile('disable', q));
      const allowed = b.runEvent('BeforeMove', p, q, dex.getActiveMove(chosen)) !== false;
      add(`disable-execution-${chosen}-${constrained}`, 'disable_execution_gate', {
        phase: 'execution after an opponent applied Disable following selection',
        selected_move: dex.moves.get(chosen).name, disabled_move: dex.moves.get(constrained).name,
        assumptions: 'Both moves have PP. Disable application succeeded. No other execution blocker; passing this gate does not imply a hit.'
      }, 'Does the already selected move pass the Disable execution gate?', ['Yes', 'No'],
      chosen !== constrained ? 'Yes' : 'No', allowed ? 'Yes' : 'No',
      'data/moves.ts:disable.condition.onBeforeMove; actual Battle.runEvent BeforeMove');
      p.removeVolatile('disable');
      assert(p.addVolatile('encore', q));
      const override = b.runEvent('OverrideAction', p, q, dex.getActiveMove(chosen));
      const observed = typeof override === 'string' ? override : chosen;
      add(`encore-execution-${chosen}-${constrained}`, 'encore_action_override', {
        phase: 'execution after an opponent applied Encore following selection',
        selected_move: dex.moves.get(chosen).name, encore_locked_move: dex.moves.get(constrained).name,
        assumptions: 'Both moves are known, have PP, and can be Encored. Encore application succeeded; no Choice lock, Disable, Taunt or other action modifier. This asks which move is attempted, not whether it hits.'
      }, 'Which move does Encore cause the user to attempt?', ['Tackle', 'Growl'],
      dex.moves.get(constrained).name, dex.moves.get(observed).name,
      'data/moves.ts:encore.condition.onOverrideAction; actual Battle.runEvent OverrideAction');
    } finally { b.destroy(); }
  }
  for (const maxhp of [300, 301]) for (const hp of [75, 76, 150]) for (const existing of [false, true]) {
    const ctx = {NOT_FAIL: '', add() {}};
    const result = dex.moves.get('substitute').onTryHit.call(ctx,
      {hp, maxhp, volatiles: existing ? {substitute: {hp: 50}} : {}});
    const expected = !existing && hp > maxhp / 4;
    add(`substitute-creation-${maxhp}-${hp}-${existing}`, 'substitute_creation_hp_gate', {
      phase: 'Substitute execution', current_hp: hp, maximum_hp: maxhp, existing_substitute: existing,
      assumptions: 'User can act and has enough PP. No Taunt, Assault Vest or other blocker. Only existing-substitute and HP creation checks are tested.'
    }, 'Can a new substitute be created under these HP and existing-substitute conditions?', ['Yes', 'No'],
    expected ? 'Yes' : 'No', result === undefined ? 'Yes' : 'No', 'data/moves.ts:substitute.onTryHit (direct hook)');
  }
  assert.equal(new Set(out.map(r => r.id)).size, out.length);
  return out;
}
module.exports = {rows};
if (require.main === module) {
  const r = rows();
  console.log(JSON.stringify({passed: true, count: r.length, rules: [...new Set(r.map(x => x.rule_id))]}));
}
