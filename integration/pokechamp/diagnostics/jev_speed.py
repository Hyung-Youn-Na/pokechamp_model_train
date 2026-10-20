"""Current effective-Speed support using the EP-082 observation/calculator path.

No frequency prior is silently inferred from the number of recommended sets.
"""
from __future__ import annotations

from .jev_damage import opponent_specs
from ..improved_io.calculator import CalculationError
from ..improved_io.calculations import own_spec


class SpeedOnlyEngine:
    """EX-090 permits the existing effective-Speed calculation and no damage scenarios."""
    def __init__(self, engine):
        self.engine = engine
        self.calls = 0

    def calculate(self, scenario):
        if not scenario['scenario_id'].startswith('speed/') or scenario['move'] != 'splash':
            raise ValueError('damage prediction disabled: non-speed calculator call')
        self.calls += 1
        return self.engine.calculate(scenario)


def compare(audit, dex, engine):
    result = dict(status='unavailable', speed_certainty='unknown',
                  meaning='effective Speed comparison before actions, not action-order probability')
    if 'normalized_active' not in audit:
        result['reason'] = 'no_active_matchup_at_lead_or_forced_switch'
        result['status'] = 'not_applicable'
        result['speed_certainty'] = 'not_applicable'
        return result, []
    own = audit['normalized_active']['self']
    opponent = audit['normalized_active']['opponent']
    candidates = audit['candidates']
    if not candidates:
        result['reason'] = 'no_compatible_recommended_set'
        return result, []
    problem = audit['field'].get('unsupported_reason') or ', '.join(audit['history']['unsupported'])
    if problem:
        result['reason'] = problem
        return result, []
    records = []
    try:
        attacker = own_spec(own)
        for candidate in candidates:
            outcomes = set()
            pairs = set()
            for defender in opponent_specs(opponent, candidate, dex):
                scenario = dict(scenario_id='speed/' + candidate['candidate_id'] + '/hp' + str(defender['options']['curHP']),
                                attacker=attacker, defender=defender, move='splash', field=audit['field'])
                reply = engine.calculate(scenario)
                records.append(dict(candidate_id=candidate['candidate_id'], scenario=scenario, result=reply))
                order = reply.get('conditional_order')
                if not order:
                    raise CalculationError(reply.get('excluded_with_reason', 'speed_not_calculated'))
                a, b = order['attacker_speed'], order['defender_speed']
                outcomes.add('faster' if a > b else 'tie' if a == b else 'slower')
                pairs.add((a, b))
            if not pairs:
                raise CalculationError('empty_public_hp_support')
            candidate_result = dict(candidate_id=candidate['candidate_id'], set_index=candidate['set_index'],
                                    set_name=candidate['set_name'],
                                    outcomes=sorted(outcomes), speed_pairs=sorted(pairs))
            records.append(dict(candidate_summary=candidate_result))
    except CalculationError as error:
        result['reason'] = str(error)
        return result, records
    summaries = [r['candidate_summary'] for r in records if 'candidate_summary' in r]
    pairs = {tuple(p) for row in summaries for p in row['speed_pairs']}
    by_set = []
    for index in sorted({row['set_index'] for row in summaries}):
        rows = [row for row in summaries if row['set_index'] == index]
        set_pairs = {p for row in rows for p in row['speed_pairs']}
        by_set.append(dict(set_name=rows[0]['set_name'],
                           self_effective_speed_range=[min(p[0] for p in set_pairs), max(p[0] for p in set_pairs)],
                           opponent_effective_speed_range=[min(p[1] for p in set_pairs), max(p[1] for p in set_pairs)],
                           self_speed_relation=sorted({v for row in rows for v in row['outcomes']})))
    relations = sorted({v for row in by_set for v in row['self_speed_relation']})
    if len(relations) == 1:
        certainty = 'consistent_within_recommended_support'
        assessment = 'All compatible recommended candidates agree: self is ' + relations[0] + '. This does not establish certainty over all legal opponent sets.'
    elif all(len(row['self_speed_relation']) == 1 for row in by_set):
        certainty = 'depends_on_opponent_set'
        assessment = 'Speed advantage cannot be assured: the Speed relation depends on the opponent set.'
    else:
        certainty = 'depends_on_set_or_unresolved_state'
        assessment = 'Speed advantage cannot be assured: set variants or unresolved public state allow different Speed relations even within a named set.'
    result.update(status='available', speed_certainty=certainty, assessment=assessment,
                  self_speed_relation=relations, by_set=by_set,
                  self_effective_speed_range=[min(p[0] for p in pairs), max(p[0] for p in pairs)],
                  opponent_effective_speed_range=[min(p[1] for p in pairs), max(p[1] for p in pairs)],
                  compatible_set_count=len({c['set_index'] for c in candidates}),
                  expanded_candidate_count=len(candidates),
                  support='Fixed 2026-09-18 Smogon OU recommended sets filtered by public moves/item/ability/level/Tera history; not exhaustive.',
                  conditions='Current boosts, status, abilities/items and field modifiers, before any selected move or new Tera. '
                             'Observed action order is not treated as proof of a Speed inequality. No HP or set probability is invented.')
    return result, records
