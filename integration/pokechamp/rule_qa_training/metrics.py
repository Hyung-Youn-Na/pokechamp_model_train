"""Frozen first-answer scoring, clustered uncertainty, and blind review exports."""
import re
import unicodedata
from collections import defaultdict
import numpy as np


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def score(row, text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ''
    if row['representation'] != 'state_mc':
        return dict(correct=normalize(first) == normalize(row['answer']), format_error=not bool(first), answer_line=first)
    options = {o['id'] for o in row['options']}
    match = re.match(r'^([A-Z])(?:[.):](?:\s|$)|$)', first)
    # A second explicit option label or standalone ID makes the answer ambiguous.
    ids = re.findall(r'(?<!\w)([A-Z])(?=[.):](?:\s|$)|\s*(?:/|or\b|and\b|$))', first)
    valid = bool(match) and match[1] in options and len(ids) == 1
    return dict(correct=bool(valid and match[1] == row['answer_id']), format_error=not valid, answer_line=first)


def summarize(rows):
    def subset(items):
        pairs = defaultdict(list)
        for r in items:
            pairs[r['group_id']].append(r['correct'])
        assert all(len(v) == 2 for v in pairs.values())
        return dict(n=len(items), correct=sum(r['correct'] for r in items),
                    accuracy=sum(r['correct'] for r in items)/len(items),
                    pair_accuracy=sum(all(v) for v in pairs.values())/len(pairs),
                    format_errors=sum(r['format_error'] for r in items),
                    capped=sum(r['capped'] for r in items),
                    nll=sum(r['nll'] for r in items)/len(items))
    forms = {form: subset([r for r in rows if r['representation']==form])
             for form in ['short_qa','state_qa','state_mc']}
    rules = {rule: {form: subset([r for r in rows if r['rule_id']==rule and r['representation']==form])
                   for form in forms} for rule in sorted({r['rule_id'] for r in rows})}
    return dict(forms=forms, rules=rules, assistant_nll=sum(r['nll'] for r in rows)/len(rows))


def choose(epochs):
    return min(epochs, key=lambda r: (-r['metrics']['forms']['state_mc']['accuracy'],
                                      r['metrics']['assistant_nll'], r['epoch']))


def bootstrap(base, selected, seed=20261019, repetitions=10000):
    selected = {r['id']:r for r in selected}
    clusters = defaultdict(list)
    for row in base:
        if row['representation'] == 'state_mc':
            other = selected[row['id']]
            assert other['component'] == row['component']
            clusters[row['component']].append(int(other['correct'])-int(row['correct']))
    values = list(clusters.values())
    sums = np.array([sum(v) for v in values])
    counts = np.array([len(v) for v in values])
    rng = np.random.default_rng(seed)
    indices = rng.integers(len(values), size=(repetitions,len(values)))
    differences = sums[indices].sum(1)/counts[indices].sum(1)
    return dict(components=len(values), repetitions=repetitions,
                difference=float(sums.sum()/counts.sum()),
                ci95=np.quantile(differences,[.025,.975]).tolist(), unit='duplicate connected component')
