"""Read only public exports; retain metadata separately from model tensors."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from .config import CONFIG, DATA, MODEL, ROOT


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def read_rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream]


def write_rows(path, rows):
    with Path(path).open('w') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_identity():
    files = list((ROOT/'integration/pokechamp/rule_qa_training').glob('*.py'))
    files += [ROOT/'scripts/pokechamp-ruleqa-train', ROOT/'integration/pokechamp/rule_qa/records.py']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}


def encode(tokenizer, messages):
    assert [m['role'] for m in messages] == ['system', 'user', 'assistant']
    prefix = tokenizer.apply_chat_template(messages[:2], tokenize=True,
                                          add_generation_prompt=True, enable_thinking=False)["input_ids"]
    full = tokenizer.apply_chat_template(messages, tokenize=True,
                                        add_generation_prompt=False, enable_thinking=False)["input_ids"]
    if full[:len(prefix)] != prefix:
        raise ValueError('generation prefix differs from supervised sequence')
    # The native final newline is formatting after im_end, not a response token.
    eos = tokenizer.convert_tokens_to_ids('<|im_end|>')
    end = len(full)
    while end > len(prefix) and full[end-1] != eos:
        end -= 1
    if end <= len(prefix):
        raise ValueError('assistant response end missing')
    full = full[:end]
    if len(full) > CONFIG['max_length'] or len(prefix) >= len(full):
        raise ValueError('invalid untruncated length')
    return dict(input_ids=full, prefix_length=len(prefix), target_length=len(full)-len(prefix))


def prepare(output):
    from transformers import AutoTokenizer
    from integration.pokechamp.rule_qa.records import messages as project
    output = Path(output)
    if (output/'prepared.json').exists():
        raise FileExistsError('prepared run already exists')
    output.mkdir(parents=True, exist_ok=True)
    assert read_json(DATA/'manifest.json')['status'] == 'exported'
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    clusters = read_json(DATA/'duplicate_clusters.json')
    component = {group: index for index, groups in enumerate(clusters) for group in groups}
    canonical = {r['id']: r for r in read_rows(DATA/'canonical.jsonl')}
    assert len(canonical) == 5760
    used, split_components, summary, identities = set(), {}, {}, {}
    for split, count in [('train', 4608), ('validation', 576), ('test', 576)]:
        rows = read_rows(DATA/f'{split}.jsonl')
        export = read_rows(DATA/f'exports/messages/{split}.jsonl')
        assert len(rows) == len(export) == count
        assert Counter(r['representation'] for r in rows) == dict.fromkeys(['short_qa','state_qa','state_mc'], count//3)
        prepared = []
        for row, conversation in zip(rows, export, strict=True):
            assert canonical[row['id']] == row and row['split'] == split
            assert row['id'] not in used
            used.add(row['id'])
            assert conversation == {'messages': project(row)}
            encoded = encode(tokenizer, conversation['messages'])
            # Only these token IDs enter the model; all other fields are scoring metadata.
            prepared.append(dict(encoded, **{k: row[k] for k in
                ['id','rule_id','group_id','scenario_id','representation','answer','options']},
                answer_id=row.get('answer_id'), component=component[row['group_id']]))
        split_components[split] = {r['component'] for r in prepared}
        write_rows(output/f'{split}.jsonl', prepared)
        summary[split] = dict(rows=count, tokens=sum(len(r['input_ids']) for r in prepared),
                             max_tokens=max(len(r['input_ids']) for r in prepared),
                             target_tokens=sum(r['target_length'] for r in prepared),
                             components=len(split_components[split]))
        for file in [DATA/f'{split}.jsonl', DATA/f'exports/messages/{split}.jsonl']:
            identities[str(file)] = sha(file)
    assert len(used) == 5760 and len(split_components['test']) == 82
    assert not any(split_components[a] & split_components[b] for a,b in
                   [('train','validation'),('train','test'),('validation','test')])
    tokenizer.save_pretrained(output/'tokenizer')
    # Existing pinned model identity is retained; record local file identities once.
    model_files = {p.name: sha(p) for p in sorted(MODEL.iterdir()) if p.is_file() and
                   (p.suffix in ('.json','.safetensors','.jinja') or p.name == 'tokenizer_config.json')}
    write_json(output/'config.json', CONFIG)
    write_json(output/'prepared.json', dict(config=CONFIG, summary=summary, data=identities,
               model_files=model_files, sources=source_identity(),
               prepared_files={s:sha(output/f'{s}.jsonl') for s in summary},
               branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
               commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    (output/'starting-git-status.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True))
    print(json.dumps(summary), flush=True)


def verify_prepared(output):
    manifest = read_json(output/'prepared.json')
    if manifest['config'] != CONFIG or manifest['sources'] != source_identity():
        raise ValueError('configuration/source identity changed after prepare')
    for split, digest in manifest['prepared_files'].items():
        if sha(output/f'{split}.jsonl') != digest:
            raise ValueError('prepared data identity changed')
    return manifest
