"""Inspect a moved EX-067 export in offline Chromium; no collection/model calls.

Run with the existing Playwright environment, for example:
  /tmp/ep037/tools/bin/python -m integration.pokechamp.tests.tera_viewer_browser_check \
      --source exports/battle_viewers/ex067 --output /tmp/ex067-browser-check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import traceback

from playwright.sync_api import expect, sync_playwright


DEFAULT_CHROMIUM = Path('/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome')


def _sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''):
            value.update(part)
    return value.hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _name(payload, action):
    """Resolve display names independently from the saved observation fields."""
    team = payload['state'].get('self_team', [])
    kind = action.get('kind')
    if kind in ('team', 'switch'):
        name = action.get('pokemon')
        if not name:
            member = next((m for m in team if m.get('slot') == action.get('slot')), {})
            name = member.get('species', '포켓몬명 미확인')
        return ('선봉' if kind == 'team' else '교체') + ' → ' + name
    if kind == 'move':
        ref = action.get('move_ref')
        if ref:
            owner = next((m for m in team if m.get('slot') == ref['self_team_slot']), {})
            slot = ref.get('current_move_slot', action.get('slot'))
        else:
            owner = next((m for m in team if m.get('active')), {})
            slot = action.get('slot')
        move = next((m for m in owner.get('current_move_slots', []) if m.get('slot') == slot), {})
        label = (move.get('name') or move.get('move') or action.get('move', {}).get('name')
                 or action.get('name') or '기술명 미확인')
        return str(label) + (' · 테라스탈' if action.get('terastallize') else '')
    return action.get('name') or '이름 미확인'


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _check_seal(source):
    files = set()
    for line in (source/'checksums.sha256').read_text().splitlines():
        expected, name = line.split('  ', 1)
        path = (source/name).resolve()
        _require(path.is_relative_to(source), 'checksum path escapes viewer')
        _require(name not in files and path.is_file() and _sha(path) == expected,
                 'viewer checksum mismatch: ' + name)
        files.add(name)
    actual = {str(p.relative_to(source)) for p in source.rglob('*')
              if p.is_file() and p != source/'checksums.sha256'}
    _require(files == actual, 'viewer checksum coverage differs')
    return len(files)


def check(source, output, *, chromium=DEFAULT_CHROMIUM):
    source, output = Path(source).resolve(), Path(output).resolve()
    started = time.time()
    result = dict(passed=False, source=str(source), checker_sha256=_sha(Path(__file__)),
        moved_folder=True, offline=True, blocked_network_schemes=['http', 'https'],
        chromium=str(chromium), chromium_args=['--disable-gpu', '--no-sandbox'],
        games=0, replays=0, observations=0, candidates=0, navigation=False,
        download_exact=False, copy_exact=False, javascript_errors=[], csp_errors=[],
        model_calls=0, api_calls=0)
    try:
        result['sealed_files'] = _check_seal(source)
        result['export_checksums_sha256'] = _sha(source/'checksums.sha256')
        provenance = _json(source/'provenance.json')
        report = _json(source/'report.json')
        _require(provenance['experiment'] == report['experiment'] == 'EX-067', 'wrong viewer experiment')
        with tempfile.TemporaryDirectory(prefix='ex067-viewer-offline-') as temporary:
            moved = Path(temporary)/'viewer'
            shutil.copytree(source, moved)
            _require(_check_seal(moved) == result['sealed_files'], 'moved copy seal differs')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=str(chromium),
                    args=['--disable-gpu', '--no-sandbox'])
                context = browser.new_context(viewport=dict(width=1500, height=1100), accept_downloads=True,
                                              permissions=['clipboard-read', 'clipboard-write'])
                context.route('https://**/*', lambda route: route.abort())
                context.route('http://**/*', lambda route: route.abort())
                context.set_offline(True)
                page = context.new_page()
                page.on('pageerror', lambda error: result['javascript_errors'].append(str(error)))
                page.add_init_script('''window.teraViewerCspErrors = [];
                    document.addEventListener('securitypolicyviolation', event => {
                        window.teraViewerCspErrors.push({directive:event.effectiveDirective,
                            blocked:event.blockedURI, disposition:event.disposition});
                    });''')

                def check_page_errors():
                    for frame in page.frames:
                        errors = frame.evaluate('window.teraViewerCspErrors || []')
                        for error in errors:
                            result['csp_errors'].append(dict(page=page.url, frame=frame.url, **error))
                    _require(not result['javascript_errors'], 'browser JavaScript error')
                    _require(not result['csp_errors'], 'browser CSP violation')

                page.goto((moved/'index.html').as_uri())
                _require('EX-067' in page.locator('h1').inner_text(), 'missing experiment heading')
                check_page_errors()
                interaction_done = False
                for game in provenance['games']:
                    folder = moved/game['game_id']
                    protocol = (folder/'showdown.log').read_text()
                    _require(_sha(folder/'showdown.log') == game['public_log_sha256'], 'public log hash differs')
                    page.goto((folder/'index.html').as_uri())
                    _require(game['game_id'] in page.locator('h1').inner_text(), 'wrong game heading')
                    check_page_errors()
                    page.goto((folder/'replay.html').as_uri())
                    _require(page.locator('pre').text_content() == protocol, 'offline replay protocol differs')
                    _require(page.locator('pre').is_visible(), 'offline replay protocol hidden')
                    check_page_errors()
                    result['replays'] += 1
                    observations = sorted(folder.glob('o[0-9][0-9][0-9][0-9]'))
                    _require(len(observations) == game['observations'], 'game observation denominator differs')
                    for index, observation in enumerate(observations):
                        payload = _json(observation/'model-input.json')
                        target = _json(observation/'targets.json')
                        page.goto((observation/'index.html').as_uri())
                        displayed = json.loads(page.locator('#model-input').text_content())
                        _require(displayed == payload, 'displayed JointInput differs from saved JSON')
                        table = page.locator('table tbody tr').evaluate_all(
                            'rows => rows.map(row => [...row.cells].map(cell => cell.textContent))')
                        _require(len(table) == len(payload['actions']) == len(target['action_ids']),
                                 'displayed candidate denominator differs')
                        for row, action, aid, q, counts in zip(table, payload['actions'], target['action_ids'],
                                                              target['q'], target['counts'], strict=True):
                            _require(row[0] == _name(payload, action), 'candidate display name differs: ' + aid)
                            _require(row[1] == action['action_id'] == aid, 'candidate ID/order differs')
                            _require(row[2] == '미완료' if q is None else float(row[2]) == q,
                                     'displayed candidate q differs: ' + aid)
                            _require(row[3] == f"{counts['win']}/{counts['draw']}/{counts['loss']}",
                                     'displayed candidate WDL differs: ' + aid)
                            _require(row[4] == f"{counts['n']}/32", 'displayed candidate denominator differs: ' + aid)
                        replay = page.frame_locator('iframe')
                        _require(replay.locator('pre').text_content() == protocol,
                                 'observation embedded offline replay differs')
                        check_page_errors()
                        result['observations'] += 1
                        result['candidates'] += len(payload['actions'])
                        if index == 0 and not interaction_done:
                            with page.expect_download() as download:
                                page.locator('a[download][href="model-input.json"]').click()
                            _require(_json(Path(download.value.path())) == payload, 'downloaded JointInput differs')
                            result['download_exact'] = True
                            page.locator('[data-copy-target="model-input"]').click()
                            expect(page.locator('[data-copy-target="model-input"]')).to_have_text('복사됨')
                            _require(page.locator('[data-copy-target="model-input"]').inner_text() == '복사됨',
                                     'copy button did not report success')
                            copied = page.evaluate('navigator.clipboard.readText()')
                            _require(json.loads(copied) == payload, 'copied JointInput differs')
                            result['copy_exact'] = True
                            if len(observations) > 1:
                                page.locator('h1').click()
                                page.keyboard.press('ArrowRight')
                                page.wait_for_url((observations[1]/'index.html').as_uri())
                                _require(json.loads(page.locator('#model-input').text_content()) ==
                                         _json(observations[1]/'model-input.json'), 'next observation navigation differs')
                                check_page_errors()
                                page.locator('h1').click()
                                page.keyboard.press('ArrowLeft')
                                page.wait_for_url((observation/'index.html').as_uri())
                                _require(json.loads(page.locator('#model-input').text_content()) == payload,
                                         'previous observation navigation differs')
                                result['navigation'] = True
                            check_page_errors()
                            interaction_done = True
                    result['games'] += 1
                browser.close()
        _require(result['games'] == report['games'], 'report/browser game denominator differs')
        _require(result['observations'] == report['observations'], 'report/browser observation denominator differs')
        _require(result['candidates'] == report['candidates'], 'report/browser candidate denominator differs')
        _require(result['download_exact'] and result['copy_exact'], 'copy/download never verified')
        _require(result['navigation'], 'no previous/next navigation verified')
        result['passed'] = True
    except Exception as error:
        result.update(error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
    result['elapsed_seconds'] = time.time()-started
    output.parent.mkdir(parents=True, exist_ok=True)
    # Evidence is immutable. Reruns use a new explicitly selected output path.
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--chromium', type=Path, default=DEFAULT_CHROMIUM)
    args = parser.parse_args()
    result = check(args.source, args.output, chromium=args.chromium)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
