"""Read sealed match results and link existing viewers without rebuilding them."""

import base64
import hashlib
import html
import os
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from . import benchmark as b

SCRIPT = """const rows=[...document.querySelectorAll('tbody tr')];
const filters=[...document.querySelectorAll('select')];
function filter(){let n=0;for(const r of rows){r.hidden=filters.some(f=>f.value&&r.dataset[f.id]!==f.value);if(!r.hidden)n++;}
document.getElementById('count').textContent=n+'경기 표시';}
filters.forEach(f=>f.addEventListener('change',filter));filter();"""


def build_viewer(report_directory, output):
    report_directory, output = Path(report_directory).resolve(), Path(output).resolve()
    summary = b.read_sealed(report_directory / "summary.json")
    matches = b.read_sealed(report_directory / "matches.json")
    valid = [r for r in matches if r["status"] == "valid_completed"]
    if len(valid) != summary["valid_completed"] or len(matches) != summary["planned"]:
        raise ValueError("viewer report denominator mismatch")
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise ValueError("viewer output already exists")
    checksums = {str(report_directory / name): b.digest(report_directory / name)
                 for name in ("summary.json", "matches.json")}
    def escape(value):
        return html.escape(str(value), quote=True)
    outcomes = {"player_won": "LLM 승", "player_lost": "무작위 승", "tied": "무승부"}
    pairs = Counter(r["paired_slot_id"] for r in valid)

    def link(path, label):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("missing viewer artifact: " + str(path))
        checksums[str(path)] = b.digest(path)
        relative = quote(os.path.relpath(path, output.parent), safe="/.")
        return f'<a href="{escape(relative)}">{escape(label)}</a>'

    rows = []
    for row in sorted(valid, key=lambda r: (r["provider_id"], r["paired_slot_id"], r["swap"])):
        actor_links = []
        for role in ("p1", "p2"):
            actor = row["actors"][role]
            bundle = Path(actor["bundle"])
            if not b.verify_bundle(bundle)["valid"]:
                raise ValueError("invalid actor bundle: " + str(bundle))
            if Path(actor["viewer"]).resolve() != (bundle / "report.html").resolve():
                raise ValueError("viewer does not belong to actor bundle")
            policy = "LLM 선봉" if role == row["llm_role"] else "무작위 선봉"
            actor_links.append(link(actor["viewer"], f"{role} · {policy}") + " · "
                               + link(bundle / "replay.html", "Replay"))
        pair = row["paired_slot_id"]
        turns = max(row["actors"][r]["turns"] for r in ("p1", "p2"))
        cells = [row["slot_id"], row["provider_id"], row["block_id"],
                 pair + (" · 짝 경기 미완료" if pairs[pair] != 2 else ""),
                 outcomes[row["outcome"]], turns]
        rows.append(f'<tr data-provider="{escape(row["provider_id"])}" '
                    f'data-pair="{escape(pair)}" data-result="{escape(row["outcome"])}">'
                    + ''.join(f'<td>{escape(c)}</td>' for c in cells)
                    + ''.join(f'<td>{links}</td>' for links in actor_links) + '</tr>')

    def select(key, title, choices):
        return f'<label>{title}<select id="{key}"><option value="">전체</option>' + ''.join(
            f'<option value="{escape(value)}">{escape(label)}</option>' for value, label in choices
        ) + '</select></label>'

    controls = select("provider", "공급자", [(p, p) for p in sorted({r["provider_id"] for r in valid})])
    controls += select("pair", "대응쌍", [(p, p) for p in sorted(pairs)])
    controls += select("result", "경기 결과", outcomes.items())
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    csp = f"default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; base-uri 'none'; object-src 'none'"
    status = "비교 완료" if summary["collection_complete"] else "비교 미완료"
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(csp)}">
<title>{escape(summary['experiment'])} 정상 완료 경기</title><style>
body{{font:16px system-ui,sans-serif;background:#f1f5f9;color:#172033;margin:0}}main{{max-width:1450px;margin:auto;padding:24px}}
h1{{margin-bottom:8px}}.summary,.filters{{background:white;padding:18px;border-radius:10px;margin:16px 0}}
.filters{{display:flex;gap:20px;flex-wrap:wrap}}label{{display:grid;gap:6px}}select{{font:inherit;padding:8px;max-width:100%}}
.table-wrap{{overflow:auto}}table{{width:100%;background:white;border-collapse:collapse}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dbe2ec}}
th{{background:#e2e8f0}}a{{color:#174f9c}}tr[hidden]{{display:none}}@media(max-width:600px){{main{{padding:12px}}.filters{{display:grid}}}}
</style></head><body><main><h1>{escape(summary['experiment'])} 정상 완료 경기</h1>
<section class="summary"><strong>유효 {len(valid)}/{summary['planned']}경기 · 완료 {summary['completed_pairs']}/{summary['planned_pairs']}대응쌍 · {status}</strong>
<p>정상 완료 경기의 양쪽 관점과 replay를 열 수 있습니다. 짝 경기가 미완료인 정상 경기도 포함합니다.</p>
<p>공급자·선봉 정책의 우열을 확증하는 결과가 아닙니다. 설명 정확성·전략적 최적성은 미평가입니다.</p>
{link(report_directory / 'report.md', '원 보고서')}</section>
<section class="filters">{controls}</section><p id="count">{len(valid)}경기 표시</p>
<div class="table-wrap"><table><thead><tr>{''.join('<th>'+s+'</th>' for s in ['경기','공급자','Block','대응쌍','결과','턴','p1 관점','p2 관점'])}</tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></main><script>{SCRIPT}</script></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(document)
    receipt = dict(report_directory=str(report_directory), index=str(output), matches=len(valid),
                   actor_viewers=2 * len(valid), completed_pairs=summary["completed_pairs"],
                   collection_complete=summary["collection_complete"], source_checksums=checksums,
                   index_sha256=b.digest(output), existing_artifacts_modified=False)
    b.seal_json(output.with_suffix(".manifest.json"), receipt)
    return receipt
