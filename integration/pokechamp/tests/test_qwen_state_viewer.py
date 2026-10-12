"""Offline export coverage and literal HTML/script-like candidate names."""
import base64
import copy
import gzip
import json
import re

import pytest

from integration.pokechamp import qwen_state_study as study
from integration.pokechamp import qwen_state_viewer as viewer


def test_script_payload_escapes_end_tags_without_changing_data():
    original = dict(name='</script><script>alert("unsafe")</script>&<img src=x onerror=alert(1)>')
    encoded = viewer.script_json(original)
    assert '</script>' not in encoded
    assert '<img' not in encoded
    assert json.loads(encoded) == original
    assert 'innerHTML' not in viewer.HTML
    assert '.textContent' in viewer.HTML


def test_saved_18_decision_export_counts_and_overwrite_refusal(tmp_path):
    decisions = study.read(study.v.ROOT / 'exports/battle_viewers/ex063/battle-1/decisions.json')['decisions']
    source = tmp_path / 'study'
    source.mkdir()
    records = [dict(decision=d['id'], body=copy.deepcopy(d['request']),
        original_selection=d['selection'], original_wire=d['wire']) for d in decisions]
    malicious = '</script><img src=x onerror=alert(1)>'
    records[0]['body']['actions'][0]['description']['pokemon'] = malicious
    for condition in study.CONDITIONS:
        (source / condition).mkdir()
        for record in records:
            study.append(source / condition / 'inputs.jsonl', record)
    cases = study.diagnostic_cases(records)
    study.write_new(source / 'diagnostic-cases.json', cases)
    study.write_new(source / 'rubric.json', [study.rubric_for(c) for c in cases])
    study.append(source / 'comparisons.jsonl', dict(decision=records[0]['decision'], C1_C2=[], C2_C3=[]))
    costs = dict(input_tokens=0, input_generation_seconds=0, selection_seconds_mean=None,
                 selection_seconds_max=None)
    summaries = {c: dict(completed=0, observed_candidates=0, costs=costs) for c in study.CONDITIONS}
    diagnostics = {c: dict(attempted=0, input_tokens=0, output_tokens=0, roundtrip_seconds=0)
                   for c in study.CONDITIONS}
    study.write_new(source / 'result.json', dict(predictions=[], rankings=[], calculated_states=[],
                                               q=summaries, diagnostics=diagnostics))
    study.write_new(source / 'report.json', dict(model_calls=0))
    output = tmp_path / 'export'
    receipt = viewer.export(source, output)
    assert receipt['decisions'] == 18 and receipt['candidates_per_condition'] == 121
    assert receipt['diagnostic_cases_per_condition'] == 30
    assert receipt['model_calls'] == 0 and not receipt['original_battle_viewer_changed']
    html = (output / 'index.html').read_text()
    assert malicious not in html
    data = json.loads((output / 'comparison.json').read_text())
    assert data['decisions'][0]['actions'][0]['label'] == '선봉 ' + malicious
    assert all((output / 'conditions' / (c + '.json')).exists() for c in study.CONDITIONS)
    bundled = re.search(r'<script type="application/json" id="download-data">(.*?)</script>',
                        html, re.DOTALL)
    assert bundled is not None
    downloads = json.loads(bundled.group(1))
    assert set(downloads) == set(viewer.DOWNLOAD_FILES) and len(downloads) == 7
    for name, encoded in downloads.items():
        compressed = base64.b64decode(encoded, validate=True)
        assert compressed[4:8] == b'\0\0\0\0'
        assert gzip.decompress(compressed) == (output / name).read_bytes()
    assert downloads == viewer.embedded_downloads(output)
    restored_c3 = json.loads(gzip.decompress(base64.b64decode(downloads['conditions/C3.json'])))
    assert restored_c3 == records
    assert 'event.preventDefault()' in html and 'URL.createObjectURL' in html
    with pytest.raises(FileExistsError):
        viewer.export(source, output)
