"""EX-140 (D-197): two zero-shot changes to how the EX-124 v2+Tera checkpoint is served on `v2fix` inputs.

- Tera-pooled decision (`laya-v2t-fix-tp1`, `-tp3`): the policy's Tera options are pooled onto the best one with weight
  `k` (the other Tera options get 0, then renormalised). The argmax of this decision distribution is the served choice,
  so the EX-071 player's argmax check holds unchanged. Without a Tera option nothing changes; with one, Tera is chosen
  iff k * (total Tera probability) > the best non-Tera option, and every other decision equals plain argmax. The model's
  own distribution is returned next to it as `model_probabilities` (recorded in the `http_response` events).
- Tera defence text (`laya-v2t-fix-tdef`, render `v2fixtd`): every `move:*:tera` option of the `v2fix` text gets the
  defensive matchup after Terastallizing in the switch-candidate wording, `; takes <foe type> xN ...; worst xN`, right
  after `; terastallize <type>` (Stellar keeps the original typing: no text). Plain argmax.
"""
from __future__ import annotations
import re

from . import config as c
from .storage import sha

FACTORS = {'laya-v2t-fix-tp1': 1, 'laya-v2t-fix-tp3': 3, 'laya-v2t-fix-tp3-initial': 3}
RENDER = 'v2fixtd'
RULE = 'tera-pooled-argmax'
TEXT = 'tera-defence-v1'
_TERA = re.compile(r'; terastallize \w+')


def pooled(ids, probabilities, factor):
    """Decision distribution over `ids`: Tera mass times `factor` on the best Tera option, renormalised."""
    tera = [k for k in ids if k.endswith(':tera')]
    mass = sum(probabilities[k] for k in tera)
    if not tera or mass <= 0:
        return dict(probabilities)
    best = max(tera, key=lambda k: probabilities[k])
    total = 1 - mass + factor * mass
    return {k: (factor * mass if k == best else 0.0 if k in tera else probabilities[k]) / total for k in ids}


def decide(policy, factor):
    """Wrap `policy.predict` with the pooled decision; returns the serving result body."""
    predict = policy.predict

    def wrapped(value):
        result = predict(value)
        ids = result['action_ids']
        decision = pooled(ids, result['probabilities'], factor)
        return dict(result, probabilities=decision, model_probabilities=result['probabilities'],
                    choice=max(ids, key=lambda key: decision[key]))
    return wrapped


def decision_identity(model):
    return dict(rule=RULE, factor=FACTORS[model], applies_to='decisions with a Tera option',
                probabilities='decision distribution; model_probabilities is the policy output')


def defence_text(value):
    """{tera action id: '; takes ...; worst xN'} for the active mon of a validated input (v5 item-resolved view)."""
    from . import compact, dex_v2, features
    from .features_v5 import resolved
    _, view = resolved(value)
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    if me is None or foe is None:
        return {}
    tera = me['original_set'].get('teraType', me['tera_type'])
    tera = dex_v2.to_id(tera) if tera else None
    if not tera or tera == 'stellar':
        return {}
    taken = ' '.join('%s x%g' % (t, m) for t in compact._types(foe) for m in [compact.dex.multiplier(t, [tera])]
                     if m is not None)
    worst = features._worst_seen(foe, dict(me, terastallized=True, tera_type=tera), view)
    text = ('; takes ' + taken if taken else '') + ('; worst x%g' % worst['mult'] if worst else '')
    return {k: text for k in value.action_ids if k.endswith(':tera')} if text else {}


def renderer(calc):
    from .input_variants import renderer as variant
    base = variant('v2fix', calc)

    def render(value):
        state, question = base(value)
        extra = defence_text(value)
        if not extra:
            return state, question
        criteria = {}
        for k, text in question['criteria'].items():
            if k in extra:
                found = _TERA.search(text)
                text = text[:found.end()] + extra[k] + text[found.end():] if found else text + extra[k]
            criteria[k] = text
        return state, dict(question, criteria=criteria)
    return render


def identity():
    """Serving identity fields of `v2fixtd`: the `v2fix` ones plus the added text and this file's hash."""
    from .input_variants import identity as variant
    out = variant('v2fix')
    out['render'] = dict(out['render'], render=out['render']['render'] + '+' + TEXT)
    out['renderer_sources']['tera_decision.py'] = sha(c.ROOT / 'integration/laya_imitation/tera_decision.py')
    return out
