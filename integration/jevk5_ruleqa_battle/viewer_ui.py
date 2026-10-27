"""EX114 UI v1 rendering with preserved raw HTTP and synchronized public replay."""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
import html
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
ASSETS = ROOT / 'integration/pokechamp/viewer_assets'
UI_VERSION = 'battle-viewer-ui-v1'
RENDERER = 'jevk5-ruleqa-researcher-v1'
EXTENSIONS = ['실제 프롬프트', '선택지 확률', '선택·전송']


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def script_json(value):
    return json_text(value).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def style():
    return (ASSETS / 'jev-researcher.html').read_text().split('<style>', 1)[1].split('</style>', 1)[0]


def render(data):
    script = (ASSETS / 'action-labels.js').read_text() + '\n' + (HERE / 'viewer.js').read_text()
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (f"default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; "
           "frame-src 'self' file:; object-src 'none'; base-uri 'none'; connect-src 'none'")
    replacements = {'__TITLE__': html.escape(f"{data['experiment']} · {data['slot']}경기"),
                    '__CSP__': html.escape(csp, quote=True), '__STYLE__': style(),
                    '__DATA__': script_json(data), '__SCRIPT__': script}
    page = (HERE / 'viewer.html').read_text()
    # Replace source placeholders once, before untrusted data can resemble a placeholder.
    import re
    return re.sub('|'.join(re.escape(k) for k in replacements), lambda m: replacements[m[0]], page)


def render_replay(battle, protocol):
    from integration.pokechamp.observability.render import _replay_html
    page = _replay_html(dict(battle_id=battle, teams=[]), protocol)
    bridge = (ROOT / 'integration/jev_planner/replay.js').read_text()
    script_hash = base64.b64encode(hashlib.sha256(bridge.encode()).digest()).decode()
    page = page.replace('script-src https://play.pokemonshowdown.com;',
                        f"script-src 'sha256-{script_hash}' https://play.pokemonshowdown.com;")
    start = page.index('<script type="text/plain" class="battle-log-data">')
    end = page.index('</script>', start) + len('</script>')
    page = page[:start] + '<script type="application/json" id="replay-protocol">' + script_json(protocol) + '</script>' + page[end:]
    # The existing renderer escapes CSP quotes in its HTML attribute.
    page = page.replace('base-uri &#x27;none&#x27;', 'base-uri https://play.pokemonshowdown.com;')
    page = page.replace('<title>', '<base href="https://play.pokemonshowdown.com/fx/"><title>')
    page = page.replace('<script defer src=', '<script>' + bridge + '</script>\n<script defer src=')
    return page.replace('Static protocol fallback', '오프라인 공개 로그')

