"""EX-191 (EP-237): the v12 datasets — v11's rows, order, splits and labels re-rendered with `render_v12`.

    python -m integration.laya_v12.data_v12 rows tour|ladder     # measure (budget), rows, live parity
    python -m integration.laya_v12.data_v12 merge                # v12-ladder-merged (v11-ladder-merged's games)

Same sources and stores as EX-170 (`laya_v11.data_v11.configure`: item-state, v5 facts, early-history and the v2
engine-judge stores); only the renderer (v11 + v12) and the outputs differ. `render_v12.install()` runs before any
worker starts (forked workers inherit it). The usage extension is not installed (v11 rows were built without it).
"""
from __future__ import annotations

import json
import sys

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import sha
from integration.laya_v10 import data_v10, paths as p10
from integration.laya_v11 import data_v11

from . import render_v12

GENERATED = c.SHARED / 'datasets/generated'
RUN = c.SHARED / 'runs/model-training/EX-191'
SOURCES = dict(
    tour=dict(data_v11.SOURCES['tour'], rows=GENERATED / 'laya-compact-imitation/v12-all', run=RUN / 'tour'),
    ladder=dict(data_v11.SOURCES['ladder'], rows=GENERATED / 'laya-compact-imitation/v12-ladder', run=RUN / 'ladder'))
MERGED = GENERATED / 'laya-compact-imitation/v12-ladder-merged'
V12_FILES = ('laya_v12/observe.py', 'laya_v12/sets.py', 'laya_v12/render_v12.py', 'laya_v12/data_v12.py',
             'laya_v12/data/foulplay_full_sets_gen9ou.json')
_v11_configure = data_v11.configure
README = """# laya-compact-imitation %(name)s

렌더러 v12(EP-237, EX-191)로 만든 laya 학습 행이다(원천 %(source)s). 행·순서·분할·라벨은 v11(EX-170)과 같고 입력만
다르다: foul-play의 경기 중 추론(속도 순서, 지워진 아이템·특성, 세트 결합, 피해 역산, 타이머, 환영)을 반영했다.
manifest의 `experiment`는 EX-170 코드 경로를 그대로 써서 `EX-170`으로 적혀 있다. 판본은 `render` 값(`laya-compact-v12[...]`)으로 구별한다.

- 길이 한도는 v11과 같다(2,048 / head 768 / 선택지 64). 넘는 행은 `exclusions.jsonl`에 남겼다(%(excluded)d행).
- 생성 시점 소스: `generator-source/`. 봉인: `checksums.sha256`
"""


def configure(source):
    """EX-170's configuration for `source`, then the v12 outputs and renderer."""
    _v11_configure(source)
    where = SOURCES[source]
    p10.V10_DATASET = where['rows']
    p10.RUN_V10_TRAINING = where['run']
    render_v12.install()
    files = tuple(data_v10.RENDER_FILES)
    data_v10.RENDER_FILES = files + tuple(n for n in V12_FILES if n not in files)
    data_v10.renderer_matches_dataset = lambda dataset=None: all(
        sha((dataset or where['rows']) / 'generator-source' / n) == sha(data_v10.INTEGRATION / n)
        for n in data_v10.RENDER_FILES)
    return where


def _patch():
    """Run EX-170's `rows` / `merge` code with the v12 configuration, sources and labels."""
    data_v11.configure = configure
    data_v11.SOURCES = SOURCES
    data_v11.MERGED = MERGED
    data_v11.RUN = RUN
    data_v11.ROWS_README = README


def rows(source, workers=64):
    _patch()
    manifest = data_v11.rows(source, workers=workers)
    return manifest


def merge():
    _patch()
    return data_v11.merge()


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'rows':
        rows(sys.argv[2], workers=int(sys.argv[3]) if len(sys.argv) > 3 else 64)
    elif cmd == 'merge':
        merge()
    else:
        raise SystemExit(__doc__)
