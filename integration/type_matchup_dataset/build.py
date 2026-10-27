"""Generate a complete synthetic type-only training pool, with an engine oracle gate."""
from __future__ import annotations
import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
DEFAULT = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-type-matchup/v1')
PIN = 'e64915c0eab066db1d3e732b1280386468dd7415'
VALUES = (0, 0.25, 0.5, 1, 2, 4)
SYSTEM = ('Calculate only the Generation 9 type-effectiveness multiplier. '
          'The stated attacking type is the final move type. Ordinary attacks use the standard type chart; '
          'a Stellar attack means Stellar Tera Blast used by an attacker already Terastallized into Stellar. '
          'Ignore STAB, abilities, held items, weather, field effects, extra added types, and all other '
          'move-specific exceptions. These are synthetic typing exercises, not claims about legal species or sets.')


def dumps(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def write_jsonl(p, rows):
    with p.open('w') as f:
        for row in rows:
            f.write(dumps(row)+'\n')


def node(*args):
    return json.loads(subprocess.check_output(['node', str(HERE/'oracle.cjs'), *map(str, args)], text=True))


def fmt(v):
    return f'{v:g}x'


def calculate(chart, attack, original, tera):
    effective = [tera] if tera and tera != 'Stellar' else list(original)
    if attack == 'Stellar':
        multiplier = 2 if tera else 1
        factors = []
        explanation = ('The defender has Terastallized, so Stellar Tera Blast has 2x type effectiveness.'
                       if tera else 'The defender has not Terastallized, so Stellar Tera Blast has 1x type effectiveness.')
    else:
        mapping = {0: 1, 1: 2, 2: 0.5, 3: 0}
        factors = [mapping[chart['damage_taken'][t][attack]] for t in effective]
        multiplier = 1
        for f in factors:
            multiplier *= f
        terms = '; '.join(f'{attack} against {t}: {fmt(f)}' for t, f in zip(effective, factors))
        explanation = f'{terms}. The combined multiplier is ' + ' * '.join(fmt(f) for f in factors) + f' = {fmt(multiplier)}.'
    prefix = (f'Ordinary Terastallization replaces the defensive typing with {tera}. ' if tera and tera != 'Stellar' else
              'Stellar Terastallization preserves the original defensive typing. ' if tera == 'Stellar' else '')
    return effective, factors, multiplier, prefix+explanation


def make_rows(chart):
    types = chart['types']
    defenders = [(t,) for t in types]+list(combinations(types, 2))
    for original, tera, attack in product(defenders, [None]+types+['Stellar'], types+['Stellar']):
        effective, factors, answer, rationale = calculate(chart, attack, original, tera)
        key = attack+'__'+'-'.join(original)+'__'+(tera or 'none')
        base = tera is None and attack != 'Stellar'
        semantic = (f'Stellar__terastallized-{bool(tera)}' if attack == 'Stellar'
                    else attack+'__'+'-'.join(effective))
        question = (f'Defender typing before Terastallization: {" / ".join(original)}. '
                    + (f'Defender has Terastallized into {tera}. ' if tera else 'Defender has not Terastallized. ')
                    + f'Attacking move type: {attack}. What is the type-effectiveness multiplier?')
        # Stable per-case option permutation avoids a fixed value-to-letter shortcut.
        ordered = sorted(VALUES, key=lambda v: hashlib.sha256(f'{key}:{v}'.encode()).hexdigest())
        options = {chr(65+i): fmt(v) for i, v in enumerate(ordered)}
        yield dict(id=key, schema='gen9-type-matchup-v1', subset='base' if base else 'extension',
                   split='train_pool', semantic_group=semantic, attack_type=attack,
                   defender_types=list(original), defender_tera_type=tera,
                   effective_defender_types=effective, factors=factors, multiplier=answer,
                   question=question, options=options, answer_id=chr(65+ordered.index(answer)), rationale=rationale)


def validate(rows, chart, output):
    types=chart['types']; defenders=[(t,) for t in types]+list(combinations(types, 2))
    expected=set(product(types+['Stellar'], defenders, [None]+types+['Stellar']))
    actual={(r['attack_type'],tuple(r['defender_types']),r['defender_tera_type']) for r in rows}
    assert len(rows)==len(actual)==len(expected)==64980 and actual==expected
    assert len({r['id'] for r in rows})==len(rows)
    base=[r for r in rows if r['subset']=='base']
    assert len(base)==3078
    assert Counter(r['multiplier'] for r in base)=={0:144,0.25:97,0.5:697,1:1489,2:590,4:61}
    lookup={(r['attack_type'],tuple(r['defender_types']),r['defender_tera_type']):r for r in rows}
    examples=[('Electric',('Ground','Water'),None,0),('Ground',('Fire','Flying'),None,0),
              ('Ice',('Dragon','Flying'),None,4),('Fire',('Grass','Steel'),None,4),
              ('Fire',('Dragon','Water'),None,0.25),('Fire',('Grass','Water'),None,1),
              ('Electric',('Ground','Water'),'Water',2),('Electric',('Ground','Water'),'Stellar',0),
              ('Stellar',('Dragon','Water'),None,1),('Stellar',('Dragon','Water'),'Stellar',2),
              ('Stellar',('Ghost',),'Normal',2)]
    for attack, defender, tera, answer in examples:
        assert lookup[(attack,defender,tera)]['multiplier']==answer
    semantic={}
    for r in rows:
        assert r['multiplier'] in VALUES
        assert len(r['options'])==6 and len(set(r['options'].values()))==6
        assert r['options'][r['answer_id']]==fmt(r['multiplier'])
        assert r['question'].endswith('What is the type-effectiveness multiplier?')
        semantic.setdefault(r['semantic_group'],r['multiplier'])
        assert semantic[r['semantic_group']]==r['multiplier']
    oracle=node('validate',output/'canonical.jsonl')
    assert oracle['passed'] and oracle['checked']==64980
    return dict(passed=True,total=64980,base=3078,extension=61902,
                ordinary_types=18,defender_combinations=171,defender_modes=20,
                semantic_groups=len(semantic),oracle=oracle,boundary_cases=len(examples),
                base_multiplier_counts={str(v):sum(r['multiplier']==v for r in base) for v in VALUES},
                total_multiplier_counts={str(v):sum(r['multiplier']==v for r in rows) for v in VALUES},
                unique_ids=True,complete_cartesian_coverage=True,unique_correct_option=True,
                evaluation_split_created=False)


def export(output, rows):
    exports=output/'exports';exports.mkdir()
    for subset in ('base','extension'):
        selected=[r for r in rows if r['subset']==subset]
        messages=[dict(id=r['id'],semantic_group=r['semantic_group'],messages=[
            {'role':'system','content':SYSTEM},
            {'role':'user','content':r['question']+' Give the multiplier followed by a brief calculation.'},
            {'role':'assistant','content':fmt(r['multiplier'])+'. '+r['rationale']}]) for r in selected]
        choices=[dict(id=r['id'],semantic_group=r['semantic_group'],system=SYSTEM,
                      question=r['question'],options=r['options'],answer_id=r['answer_id'],
                      rationale=r['rationale']) for r in selected]
        write_jsonl(exports/f'{subset}.messages.jsonl',messages)
        write_jsonl(exports/f'{subset}.multiple_choice.jsonl',choices)
        csv_path=exports/f'{subset}.csv'
        with csv_path.open('w',newline='') as f:
            fields=['id','attack_type','defender_types','defender_tera_type',
                    'effective_defender_types','factors','multiplier','semantic_group']
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for r in selected:
                w.writerow({k: dumps(r[k]) if isinstance(r[k],list) else (r[k] if r[k] is not None else 'none') for k in fields})
        # Verify persisted exports rather than only the in-memory renderer.
        saved=[json.loads(s) for s in (exports/f'{subset}.messages.jsonl').read_text().splitlines()]
        saved_mc=[json.loads(s) for s in (exports/f'{subset}.multiple_choice.jsonl').read_text().splitlines()]
        assert len(saved)==len(saved_mc)==len(selected)
        for r,m,c in zip(selected,saved,saved_mc):
            assert m['id']==c['id']==r['id']
            assert m['messages'][0]=={'role':'system','content':SYSTEM}
            assert m['messages'][1]['content']==r['question']+' Give the multiplier followed by a brief calculation.'
            assert m['messages'][2]['content']==fmt(r['multiplier'])+'. '+r['rationale']
            assert c['question']==r['question'] and c['options']==r['options']
            assert c['answer_id']==r['answer_id']
        with csv_path.open(newline='') as f:
            saved_csv=list(csv.DictReader(f))
        assert len(saved_csv)==len(selected)
        assert all(float(c['multiplier'])==r['multiplier'] and c['id']==r['id'] for c,r in zip(saved_csv,selected))


def provenance():
    commit=subprocess.check_output(['git','-C',str(ROOT/'pokemon-showdown'),'rev-parse','HEAD'],text=True).strip()
    assert commit==PIN,('Showdown pin changed',commit)
    sources=list(HERE.glob('*.py'))+list(HERE.glob('*.cjs'))+[ROOT/'scripts/type-matchup-dataset']
    for name in ['sim/dex','sim/pokemon','data/typechart','data/moves']:
        sources += [ROOT/'pokemon-showdown'/f'{name}.ts', ROOT/'pokemon-showdown/dist'/f'{name}.js']
    return dict(showdown_commit=commit,showdown_dirty=subprocess.check_output(
        ['git','-C',str(ROOT/'pokemon-showdown'),'status','--porcelain'],text=True).strip(),
        node=subprocess.check_output(['node','--version'],text=True).strip(),
        sources={str(p.relative_to(ROOT)):sha(p) for p in sources})


def build(output):
    if output.exists():
        raise FileExistsError('Choose a new output directory; existing datasets are preserved')
    identity=provenance()
    assert not identity['showdown_dirty'],'Pinned Showdown source must be clean'
    output.mkdir(parents=True)
    chart=node('chart');write_json(output/'type_chart.json',chart)
    rows=list(make_rows(chart));write_jsonl(output/'canonical.jsonl',rows)
    validation=validate(rows,chart,output)
    export(output,rows)
    validation['persisted_export_alignment']=True
    write_json(output/'validation.json',validation)
    examples=[r for r in rows if (r['attack_type']=='Electric' and r['defender_types']==['Ground','Water']
              and r['defender_tera_type'] in (None,'Water','Stellar')) or
              (r['attack_type']=='Stellar' and r['defender_types']==['Dragon','Water']
              and r['defender_tera_type'] in (None,'Water','Stellar'))]
    write_json(output/'examples.json',examples)
    shutil.copyfile(HERE/'DATASET_README.md',output/'README.md')
    shutil.copyfile(ROOT/'pokemon-showdown/LICENSE',output/'SHOWDOWN_LICENSE')
    src=output/'generator-source';src.mkdir()
    for p in sorted(HERE.glob('*')):
        if p.is_file() and p.suffix in ('.py','.cjs','.md'):
            shutil.copyfile(p,src/p.name)
    manifest=dict(schema='gen9-type-matchup-v1',created_at=datetime.now(timezone.utc).isoformat(),
                  status='validated_training_pool',plan='EP-192',decision='D-174',
                  counts={k:validation[k] for k in ('total','base','extension','semantic_groups')},
                  provenance=identity,split_policy='All training pool; no validation/test split or generalization claim',
                  environment={'gpu':False,'model_calls':0,'training':False},
                  files={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    assert provenance()==identity,'Source changed during generation'
    write_json(output/'manifest.json',manifest)
    (output/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n'
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='checksums.sha256'))
    return validation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    print(json.dumps(build(args.output),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
