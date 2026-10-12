"""Move the complete export, disconnect the browser, and inspect every decision."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from playwright.sync_api import sync_playwright


def check(source, output):
    errors, observations, candidates = [], 0, 0
    with tempfile.TemporaryDirectory(prefix='ex062-offline-') as temporary:
        moved = Path(temporary) / 'viewer'
        shutil.copytree(source, moved)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport=dict(width=1600, height=1000), accept_downloads=True)
            context.route('https://**/*', lambda route: route.abort())
            context.route('http://**/*', lambda route: route.abort())
            context.set_offline(True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto((moved / 'index.html').as_uri())
            for folder in sorted(moved.glob('battle-*')):
                data = json.loads((folder / 'decisions.json').read_text())
                page.goto((folder / 'index.html').as_uri())
                assert page.locator('#decision option').count() == len(data['decisions'])
                if not data['decisions']:
                    assert '입력 없음' in page.locator('#selection').inner_text()
                    assert page.frame_locator('iframe').locator('body').inner_text()
                    continue
                for i, d in enumerate(data['decisions']):
                    page.locator('#decision').select_option(str(i))
                    assert json.loads(page.locator('#request').inner_text()) == d['request']
                    assert json.loads(page.locator('#response').text_content()) == d['response']
                    expected = [a['action_id'] for a in d['request']['actions']]
                    actual = page.locator('#q-values tr').evaluate_all('rows=>rows.map(r=>r.dataset.actionId)')
                    assert actual == expected
                    labels = []
                    for action in d['request']['actions']:
                        desc = action['description']
                        if desc['kind'] == 'move':
                            ref = desc['move_ref']
                            owner = next(p for p in d['request']['observation']['state']['self_team']
                                         if p['slot'] == ref['self_team_slot'])
                            move = next(m for m in owner['current_move_slots'] if m['slot'] == ref['current_move_slot'])
                            labels.append(move['name'] + (' · 테라스탈' if desc['terastallize'] else ''))
                        else:
                            labels.append(('선봉' if desc['kind'] == 'team' else '교체') + ' → ' + desc['pokemon'])
                    actual_labels = page.locator('#q-values tr').evaluate_all('rows=>rows.map(r=>r.cells[0].textContent)')
                    assert actual_labels == labels
                    chosen_label = labels[expected.index(d['selection']['choice'])]
                    assert chosen_label in page.locator('#selection').inner_text()
                    assert chosen_label in page.locator('#decision option').nth(i).inner_text()
                    assert chosen_label in page.locator('#sent-action').inner_text()
                    values = page.locator('#q-values tr').evaluate_all('rows=>rows.map(r=>Number(r.cells[1].textContent))')
                    assert values == [d['response']['q_values'][key] for key in expected]
                    selected = page.locator('#q-values tr.chosen').get_attribute('data-action-id')
                    assert selected == d['selection']['choice']
                    assert json.loads(page.locator('#technical').text_content())['wire']['command'] == d['wire']['command']
                    observations += 1
                    candidates += len(expected)
                page.locator('#decision').select_option('0')
                page.locator('#next').click()
                assert page.locator('#decision').input_value() == '1'
                page.locator('h1').click()
                page.keyboard.press('ArrowLeft')
                assert page.locator('#decision').input_value() == '0'
                with page.expect_download() as download:
                    page.locator('[data-download=request]').click()
                assert json.loads(Path(download.value.path()).read_text()) == data['decisions'][0]['request']
                page.locator('[data-copy=request]').click()
                page.screenshot(path=str(output.parent / f'{folder.name}.png'))
                replay = page.frame_locator('iframe')
                assert replay.locator('body').inner_text()
            browser.close()
    result = dict(passed=not errors, moved_folder=True, offline=True, observations=observations,
                  candidates=candidates, action_names_exact=observations > 0, navigation=observations > 0,
                  download_exact=observations > 0, copy_clicked=observations > 0,
                  skipped_no_decisions=observations == 0,
                  browser_errors=errors)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.source, args.output), ensure_ascii=False))
