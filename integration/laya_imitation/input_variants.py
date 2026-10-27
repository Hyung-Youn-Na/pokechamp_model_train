"""EX-139 (D-196): the EX-124 v2+Tera checkpoint served zero-shot on D-195-corrected inputs (no retraining).

Two live renderers, both `compact_v5.render` over `features_v5.compute` facts (opponent items resolved from the D-195
`item_state` field):
- `v2fix`: the v2 modules only. The text keeps the v2 format; only values change (damage with a removed item gone and
  Air Balloon never assumed, ground `x0` against a held balloon / revealed Levitate, Knock Off power, item speed).
- `v2info`: v2 modules plus the v5 `items` and `counters` modules, i.e. wording v2t never saw in training.
The serving checks both the v2 dataset (what EX-124 was trained on) and the v5 dataset (where `compact_v5` /
`features_v5` come from) against the live files, and reports the actual render next to the trained one.
"""
from __future__ import annotations

from . import config as c
from .storage import read, sha

V2_MODULES = ('damage', 'moves', 'speed', 'switch')
RENDERS = {'v2fix': V2_MODULES, 'v2info': V2_MODULES + ('counters', 'items')}


def renderer(render, calc):
    from . import compact_v5, features_v5
    modules = RENDERS[render]
    return lambda value: compact_v5.render(value, modules, features_v5.compute(value, calc))


def matches():
    from .serving import renderer_matches_dataset
    return renderer_matches_dataset('v2') and renderer_matches_dataset('v5')


def identity(render):
    """Serving identity fields: the render actually used, the render EX-124 was trained on, and the live file hashes."""
    from . import compact_v5
    from .serving import V5_RENDER_FILES
    package = c.ROOT / 'integration/laya_imitation'
    return dict(render=compact_v5.version(RENDERS[render]), trained_render=read(c.V2_DATASET / 'manifest.json')['render'],
                renderer_sources={name: sha(package / name) for name in V5_RENDER_FILES})
