"""EX-166 (D-208): recent ladder replays -> an EX-071-layout source (`laya-ladder-source/v1`), CPU only.

select   EP-100 classifier on the downloaded logs, then D-208's filters: `candidate` only, last turn > 10, neither
         team's six species equal to an evaluation team (EX-071's historical teams, EX-071's and EX-120's schedules).
         Newest first. The newest 150 kept games are the test pool, the next 60 the validation pool, the rest train.
corpus   Metamon gen9ou teams, all species (D-207), evaluation-team signatures excluded, validated as in EX-071; then
         per pool, a supplement set for every revealed slot no corpus set matches: the nearest corpus sets of the
         species with the revealed fields swapped in (their other moves, item, ability, Tera, nature and EVs kept),
         else missing fields from the replay month's Smogon gen9ou-1500 usage stats; first validator-legal one, count 1.
         A pool's games only ever see their own pool's supplement.
recover  EX-071's CPU recovery (Metamon bridge, ability provenance fix) with team validation and EX-071's row rules
         (labels, eligibility, Qwen state-token check). One cached result per replay, like EX-071's `recovered/`.
         Prepared inputs keep EX-071's pre-D-195 snapshot layout; the item-state store adds the optional fields.
split    validation / test: EX-071's `balanced` 512 / 1,024 from their pools; train: the train pool newest first, whole
         games, up to the row budget EX-167's measurement fixed, then EX-071's train order. Writes
         `preparation/replays.jsonl`, `prepared/{train,validation,test}.jsonl` and the manifest the stores check.
"""
from __future__ import annotations
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
from multiprocessing import Pool
import os
from pathlib import Path
import random
import re
import subprocess
import time

from integration.laya_imitation.storage import atomic, read, seal, sha, write_jsonl

from . import paths

POOLS = dict(test=150, validation=60)
MIN_TURNS = 10
SEED = 20261104
TRIES = 40
ABILITY_FIX = Path(__file__).with_name('abilities.py')


def _replay(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


# ------------------------------------------------------------------------------------------------ select

def evaluation_signatures():
    """Six-species signatures of every team an evaluation plays: EX-071's historical teams and schedule, EX-120."""
    from integration.laya_imitation import comparison
    from integration.pokechamp.imitation import config as ic
    from integration.pokechamp.imitation.dataset import existing_teams, signature, to_id
    out = {t['signature']: 'ex071_historical' for t in existing_teams()}
    for name, path in (('ex071_schedule', ic.OUTPUT / 'schedule.json'),
                       ('ex120_schedule', comparison.COLLECTION / 'schedule.json')):
        for slot in read(path):
            for team in slot['teams'].values():
                packed = team.get('packed') or team.get('before_validation')
                species = [(f.split('|')[1] or f.split('|')[0]) for f in packed.split(']')]
                out.setdefault(signature([to_id(s) for s in species]), name)
    return out


def classify(out=paths.RUN_DATA / 'classify'):
    if (out / 'manifest.json').exists():
        return read(out / 'summary.json')
    empty = paths.RUN_DATA / 'classify-normalized-empty'
    empty.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([str(paths.ROOT / 'pokechamp/.venv/bin/python'), 'scripts/replay_eligibility/classify.py',
                           '--raw', str(paths.RAW / 'raw'), '--normalized', str(empty), '--output', str(out)],
                          cwd=paths.ROOT)
    return read(out / 'summary.json')


def select():
    """Kept games newest first with their pool, and every exclusion with its reason."""
    from integration.pokechamp.imitation.dataset import preview, signature
    out = paths.RUN_DATA / 'select'
    if (out / 'kept.jsonl').exists():
        return [json.loads(line) for line in open(out / 'kept.jsonl')]
    classify()
    order = [json.loads(line) for line in open(paths.RAW / 'selection.jsonl')]
    classes = {r['replay_id']: r for r in map(json.loads, open(paths.RUN_DATA / 'classify/classification.jsonl'))}
    evaluation = evaluation_signatures()
    kept, excluded = [], []
    for row in order:
        rid = row['id']
        path = paths.RAW / 'raw' / (rid + '.json.json')
        if not path.exists():
            excluded.append(dict(replay_id=rid, reason='not_downloaded'))
            continue
        cls = classes.get(rid)
        if cls is None or cls['category'] != 'candidate':
            excluded.append(dict(replay_id=rid, reason='rule_' + (cls['category'] if cls else 'missing')))
            continue
        raw = _replay(path)
        turns = max([int(l.split('|')[2]) for l in raw['log'].splitlines() if l.startswith('|turn|')] or [0])
        if turns <= MIN_TURNS:
            excluded.append(dict(replay_id=rid, reason='short_game', turns=turns))
            continue
        try:
            sigs = [signature(v) for v in preview(raw['log']).values()]
        except ValueError:  # a ladder team may bring fewer than six; EX-071's path needs six distinct species
            excluded.append(dict(replay_id=rid, reason='not_six_species'))
            continue
        hit = sorted({evaluation[s] for s in sigs if s in evaluation})
        if hit:
            excluded.append(dict(replay_id=rid, reason='evaluation_team', sources=hit))
            continue
        kept.append(dict(replay_id=rid, uploadtime=raw['uploadtime'], rating=row.get('rating'), turns=turns,
                         raw_path=str(path), raw_sha256=sha(path), signatures=sigs))
    kept.sort(key=lambda r: (-r['uploadtime'], r['replay_id']))
    for i, r in enumerate(kept):
        r['pool'] = 'test' if i < POOLS['test'] else 'validation' if i < POOLS['test'] + POOLS['validation'] else 'train'
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / 'kept.jsonl', kept, immutable=True)
    write_jsonl(out / 'excluded.jsonl', excluded, immutable=True)
    atomic(out / 'summary.json', dict(downloaded=len(order), kept=len(kept), pools=dict(Counter(r['pool'] for r in kept)),
                                      excluded=dict(Counter(e['reason'] for e in excluded)),
                                      evaluation_signatures=len(evaluation)), immutable=True)
    return kept


# ------------------------------------------------------------------------------------------------ corpus

def base_corpus(out):
    """Every Metamon gen9ou team set (validated, collapsed with counts), evaluation-team signatures excluded."""
    from integration.pokechamp.imitation.dataset import TeamValidatorClient, signature
    from integration.pokechamp.imitation.storage import digest
    path = out / 'corpus-base.jsonl'
    if path.exists():
        return [json.loads(line) for line in open(path)]
    evaluation = evaluation_signatures()
    files = sorted(Path(paths.METAMON_TEAMS).iterdir())
    collapsed, rejected = {}, Counter()
    with TeamValidatorClient() as validator:
        for start in range(0, len(files), 200):
            chunk = files[start:start + 200]
            entries = [dict(text=p.read_text(), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in chunk]
            for p, entry, team in zip(chunk, entries, validator.normalize(entries), strict=True):
                if 'individual' not in team:
                    rejected['team_unusable'] += 1
                    continue
                if signature(team['species']) in evaluation:
                    rejected['evaluation_team'] += 1
                    continue
                for slot, row in enumerate(team['individual'], 1):
                    if row['problems']:
                        rejected['set_illegal'] += 1
                        continue
                    s = dict(row['set'])
                    s.pop('name', None)
                    agg = collapsed.setdefault(digest(s), dict(set=s, count=0, sources=[]))
                    agg['count'] += 1
                    agg['sources'].append(dict(path=p.name, sha256=entry['sha256'], slot=slot))
    corpus = [collapsed[k] for k in sorted(collapsed)]
    write_jsonl(path, corpus, immutable=True)
    atomic(out / 'corpus-base.json', dict(teams=len(files), unique_sets=len(corpus), rejected=dict(rejected)),
           immutable=True)
    return corpus


_aug = {}


def _guarded(init):
    """A pool initializer that records its failure for the first task to raise: a raising initializer makes
    `multiprocessing.Pool` respawn workers forever instead of failing."""
    def wrapper(*args):
        try:
            init(*args)
        except BaseException as exc:   # noqa: BLE001 -- re-raised by the first task
            _failed.append(repr(exc))
    return wrapper


_failed = []


def _check_init():
    if _failed:
        raise RuntimeError('pool worker initialization failed: ' + _failed[0])


def _aug_init(base_path):
    from integration.pokechamp.imitation.impute import SetCorpus
    _aug['corpus'] = SetCorpus([json.loads(line) for line in open(base_path)])
    _aug['node'] = subprocess.Popen(['node', str(Path(__file__).with_name('complete_sets.cjs'))],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    _aug['stats'] = {}


def _usage(month):
    from integration.pokechamp.imitation.impute import ident
    latest = max(m for m in os.listdir(paths.STATS) if re.fullmatch(r'\d{4}-\d{2}', m))
    month = min(month, latest)   # no stats yet for the current month
    if month not in _aug['stats']:
        data = json.load(open(paths.STATS / month / 'gen9ou-1500.json'))['data']
        _aug['stats'][month] = {ident(k): v for k, v in data.items()}
    return month, _aug['stats'][month]


def _draw(rng, dist, exclude=()):
    items = [(k, v) for k, v in sorted(dist.items()) if k not in exclude and k not in ('', 'nothing') and v > 0]
    if not items:
        return None
    u = rng.random() * sum(v for _, v in items)
    for k, v in items:
        u -= v
        if u <= 0:
            return k
    return items[-1][0]


def _choice(obs):
    from integration.pokechamp.imitation.impute import ident
    return obs.get('multiple_original_item_moves') and ident(obs['item'] or '') in ('choiceband', 'choicespecs', 'choicescarf')


def _nearest(obs, rng):
    """Corpus sets of the species, most revealed moves contained first, then item/ability/Tera agreement; ties in a
    seeded frequency-weighted order. Each with the revealed fields swapped in."""
    from integration.pokechamp.imitation.impute import ident, species_ident
    rows = _aug['corpus'].by_species.get(species_ident(obs['species']), [])
    revealed = {ident(m) for m in obs['moves']}

    def score(row):
        st = row['set']
        return (len(revealed & {ident(m) for m in st['moves']}),
                sum(obs[f] is not None and ident(obs[f]) == ident(st.get(f, '')) for f in ('item', 'ability', 'teraType')))
    keyed = sorted(((score(r), rng.random() ** (1 / r['count']), r) for r in rows), key=lambda k: (k[0], k[1]),
                   reverse=True)
    for _, _, row in keyed[:TRIES]:
        st = row['set']
        moves = [ident(m) for m in obs['moves']]
        moves += [ident(m) for m in st['moves'] if ident(m) not in moves][:4 - len(moves)]
        item = obs['item'] or st.get('item', '')
        if obs.get('multiple_original_item_moves') and ident(item) in ('choiceband', 'choicespecs', 'choicescarf'):
            continue
        yield dict(species=obs['species'], moves=moves, item=item, ability=obs['ability'] or st.get('ability'),
                   teraType=obs['teraType'] or st.get('teraType') or 'Normal', nature=st.get('nature', 'Serious'),
                   evs=st['evs'], gender=obs.get('gender'), level=obs.get('level', 100), base=row['id'])


def _from_usage(obs, usage, rng):
    from integration.pokechamp.imitation.impute import ident
    for _ in range(TRIES):
        moves = [ident(m) for m in obs['moves']]
        while len(moves) < 4:
            m = _draw(rng, usage['Moves'], exclude=moves)
            if m is None:
                break
            moves.append(m)
        items = {k: v for k, v in usage['Items'].items()
                 if not (obs.get('multiple_original_item_moves') and k in ('choiceband', 'choicespecs', 'choicescarf'))}
        spread = _draw(rng, usage['Spreads']) or 'Serious:84/84/84/84/84/84'
        nature, evs = spread.split(':')
        yield dict(species=obs['species'], moves=moves, item=obs['item'] or _draw(rng, items) or '',
                   ability=obs['ability'] or _draw(rng, usage['Abilities']),
                   teraType=obs['teraType'] or _draw(rng, usage.get('Tera Types') or {}) or 'Normal',
                   nature=nature, evs=dict(zip(('hp', 'atk', 'def', 'spa', 'spd', 'spe'), map(int, evs.split('/')))),
                   gender=obs.get('gender'), level=obs.get('level', 100))


def _legal(candidates):
    _aug['node'].stdin.write(json.dumps(dict(candidates=candidates)) + '\n')
    _aug['node'].stdin.flush()
    return json.loads(_aug['node'].stdout.readline())


def _supplement(game):
    """Supplement rows for one game's unmatched revealed slots (ability provenance fixed, as the recovery sees it)."""
    from integration.pokechamp.imitation.impute import ident
    from .abilities import revealed_original_sets
    _check_init()
    raw = _replay(game['raw_path'])
    revealed, unsupported = revealed_original_sets(raw)
    bad = {side for side, _ in unsupported}
    out, counts = [], Counter()
    for side in ('p1', 'p2'):
        if side in bad:
            continue
        for slot, obs in enumerate(revealed[side], 1):
            if _aug['corpus'].impute([obs], game['replay_id'], side)[0] is not None:
                continue
            counts['no_match_slots'] += 1
            seed = int.from_bytes(hashlib.sha256(f"augment:{SEED}:{game['replay_id']}:{side}:{slot}".encode())
                                  .digest()[:8], 'big')
            rng = random.Random(seed)
            source, res = None, None
            near = list(_nearest(obs, rng))
            if near:
                res = _legal(near)
                if res['set'] is not None:
                    source = dict(kind='nearest_corpus_set', base=near[res['tried'] - 1]['base'])
            if source is None:
                month, usage = _usage(dt.datetime.utcfromtimestamp(game['uploadtime']).strftime('%Y-%m'))
                usage = usage.get(ident(obs['species']))
                if usage is not None:
                    res = _legal(list(_from_usage(obs, usage, rng)))
                    if res['set'] is not None:
                        source = dict(kind='usage_completion', stats=month + '/gen9ou-1500')
            if source is None:
                counts['no_legal_completion'] += 1
                continue
            counts[source['kind']] += 1
            out.append(dict(set=res['set'], count=1, sources=[dict(source, replay_id=game['replay_id'], side=side,
                                                                    slot=slot, revealed=obs)]))
    return out, counts


def corpora(kept, workers=48):
    """`preparation/corpus-<pool>.jsonl` = base corpus + that pool's supplement."""
    stage = paths.SOURCE / 'preparation'
    stage.mkdir(parents=True, exist_ok=True)
    base = base_corpus(stage)
    summary = {}
    for pool in ('test', 'validation', 'train'):
        path = stage / ('corpus-%s.jsonl' % pool)
        if path.exists():
            continue
        games = [g for g in kept if g['pool'] == pool]
        supplement, counts = [], Counter()
        with Pool(workers, initializer=_guarded(_aug_init), initargs=(str(stage / 'corpus-base.jsonl'),)) as p:
            for rows, c_ in p.imap(_supplement, games, chunksize=8):
                supplement += rows
                counts.update(c_)
        write_jsonl(stage / ('supplement-%s.jsonl' % pool), supplement, immutable=True)
        write_jsonl(path, base + supplement, immutable=True)
        summary[pool] = dict(games=len(games), supplement=len(supplement), **counts)
    if summary:
        atomic(stage / 'supplement.json', summary)
    return base


# ------------------------------------------------------------------------------------------------ recover

RECOVERY_FILES = ('replay.py', 'metamon_bridge.py', 'impute.py', 'schema.py', 'dataset.py', 'config.py', 'teams.cjs',
                  'model.py')
_rec = {}


def recovery_identity():
    from integration.pokechamp.imitation import dataset
    folder = Path(dataset.__file__).parent
    out = {n: sha(folder / n) for n in RECOVERY_FILES}
    out['laya_ladder/abilities.py'] = sha(ABILITY_FIX)
    out['laya_ladder/bridge.py'] = sha(Path(__file__).with_name('bridge.py'))
    return out


def _rec_init(corpus_path, identity):
    from integration.pokechamp.imitation.dataset import TeamValidatorClient
    from integration.pokechamp.imitation.model import load_tokenizer
    from .bridge import Client
    _rec['bridge'] = Client(corpus_sets=[json.loads(line) for line in open(corpus_path)])
    _rec['validator'] = TeamValidatorClient()
    _rec['tok'] = load_tokenizer()
    _rec['identity'] = identity


def _recover(game):
    """EX-071 `prepare`'s per-replay body: cached recovery, team validation, rows."""
    from integration.pokechamp.imitation.dataset import _label_kind
    from integration.pokechamp.imitation.model import _kev, encode_input
    from integration.pokechamp.imitation.schema import from_snapshot
    from integration.pokechamp.imitation.storage import digest
    _, kev = _kev()
    _check_init()
    replay_id = game['replay_id']
    cache = paths.SOURCE / 'preparation/recovered' / (replay_id + '.json.gz')
    if cache.exists():
        cached = _replay(cache)
        if cached['source_sha256'] != game['raw_sha256'] or cached['recovery_source'] != _rec['identity']:
            raise ValueError('recovery cache identity differs: ' + replay_id)
        result = cached['result']
    else:
        result = _rec['bridge'].recover(_replay(game['raw_path']), replay_id)
        cached = dict(source_sha256=game['raw_sha256'], recovery_source=_rec['identity'], result=result)
        atomic(cache, gzip.compress(json.dumps(cached, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
                                    .encode(), compresslevel=1, mtime=0), immutable=True)
    original = result['original_sets']
    validation = _rec['validator'].normalize([dict(sets=s, sha256=digest(s)) for s in original.values()]) \
        if original else []
    legal = dict(zip(original, validation, strict=True))
    invalid = {side for side, v in legal.items() if not v.get('legal')}
    exclusions = [dict(replay_id=replay_id, perspective=s, reason='imputed_team_illegal') for s in invalid]
    exclusions += [dict(replay_id=replay_id, **{k: v for k, v in e.items() if k != 'revealed'})
                   for e in result['exclusions']]
    records, quarantined = [], 0
    assignment = dict(split=game['pool'], group_id=replay_id)
    for rec in result['records']:
        if rec['perspective'] in invalid or rec.get('audit', {}).get('quarantined_perspective'):
            quarantined += 1
            continue
        if not rec['actions']:
            quarantined += 1
            reason = rec.get('audit', {}).get('mask_reason') or 'no_proven_legal_candidates'
            exclusions.append(dict(replay_id=replay_id, perspective=rec['perspective'], cutoff_line=rec['cutoff_line'],
                                   reason=reason, automatic_event=reason.startswith('automatic_continuation:')))
            continue
        value = _legacy(from_snapshot(rec['snapshot'], rec['actions']))
        label = rec['label']
        if label is not None and label not in value.action_ids:
            raise ValueError('restored label absent from candidates')
        sample_id = f"{replay_id}:{rec['perspective']}:{rec['cutoff_line']}:{rec['decision_kind']}"
        row = dict(sample_id=sample_id, replay_id=replay_id, **assignment, perspective=rec['perspective'],
                   cutoff_line=rec['cutoff_line'], decision_kind=rec['decision_kind'], label_kind=_label_kind(rec),
                   tera_used=not rec['snapshot']['can_tera'], label=label, input=value.body,
                   audit=dict(**rec.get('audit', {}), source_sha256=game['raw_sha256']))
        try:
            encoded = encode_input(value, _rec['tok'])
        except kev.ContextOverflow as exc:
            row.update(eligible=False, exclusion_reason='state_tokens_exceeded', token_error=str(exc))
        else:
            row.update(token_count=encoded.tokens, state_tokens=encoded.state_tokens,
                       input_sha256=encoded.input_sha256, eligible=label is not None and len(value.action_ids) > 1,
                       exclusion_reason=('unknown_selection' if label is None else
                                         'single_candidate' if len(value.action_ids) == 1 else None))
        records.append(row)
    return replay_id, records, exclusions, quarantined


def _legacy(value):
    """The EX-071 layout of an input: EX-071 was prepared before D-195's optional snapshot fields, which the
    item-state store carries and merges back (`item_state.merge`), so prepared rows hold the stripped snapshot."""
    from integration.laya_imitation.item_state import strip
    from integration.laya_imitation.storage import canonical
    from integration.pokechamp.imitation.schema import ImitationInput
    state = json.loads(value.body['state'])
    body = dict(value.body, state=canonical(dict(version=state['version'], snapshot=strip(state['snapshot']))))
    return ImitationInput.from_body(body)


def recover(kept, workers=32):
    """All kept games per pool with that pool's corpus; rows and exclusions under `RUN_DATA/rows/`."""
    out = paths.RUN_DATA / 'rows'
    out.mkdir(parents=True, exist_ok=True)
    (paths.SOURCE / 'preparation/recovered').mkdir(parents=True, exist_ok=True)
    identity = recovery_identity()
    stage = paths.SOURCE / 'preparation'
    if (stage / 'recovery-source.json').exists():
        if read(stage / 'recovery-source.json') != identity:
            raise ValueError('recovery source changed; keep the earlier cache before correcting')
    else:
        atomic(stage / 'recovery-source.json', identity, immutable=True)
    for pool in ('test', 'validation', 'train'):
        if (out / ('%s.jsonl' % pool)).exists():
            continue
        games = [g for g in kept if g['pool'] == pool]
        rows, exclusions, quarantined, started = [], [], 0, time.time()
        with Pool(workers, initializer=_guarded(_rec_init), initargs=(str(stage / ('corpus-%s.jsonl' % pool)), identity)) as p:
            for i, (rid, recs, excl, q) in enumerate(p.imap(_recover, games, chunksize=4)):
                rows += recs
                exclusions += excl
                quarantined += q
                if i % 500 == 0:
                    atomic(out / 'progress.json', dict(pool=pool, done=i + 1, of=len(games), rows=len(rows),
                                                       seconds=round(time.time() - started)))
        write_jsonl(out / ('%s-exclusions.jsonl' % pool), exclusions, immutable=True)
        write_jsonl(out / ('%s.jsonl' % pool), rows, immutable=True)
        atomic(out / ('%s-summary.json' % pool), dict(games=len(games), rows=len(rows),
                                                      eligible=sum(r['eligible'] for r in rows),
                                                      quarantined=quarantined,
                                                      exclusions=dict(Counter(e['reason'] for e in exclusions)),
                                                      seconds=round(time.time() - started)), immutable=True)


# ------------------------------------------------------------------------------------------------ split

def eligible_rows(pool):
    return [r for r in map(json.loads, open(paths.RUN_DATA / 'rows' / ('%s.jsonl' % pool))) if r['eligible']]


def split(kept, train_rows):
    """`prepared/` with EX-071's selection rules; train = whole newest train-pool games up to `train_rows`."""
    from integration.pokechamp.imitation.dataset import balanced, ranked
    prepared = paths.SOURCE / 'prepared'
    if (prepared / 'manifest.json').exists():
        return read(prepared / 'manifest.json')
    order = {g['replay_id']: i for i, g in enumerate(kept)}
    by_game = {}
    for r in eligible_rows('train'):
        by_game.setdefault(r['replay_id'], []).append(r)
    train, used = [], []
    for rid in sorted(by_game, key=order.get):
        if len(train) >= train_rows:
            break
        train += by_game[rid]
        used.append(rid)
    selected = dict(train=sorted(train, key=lambda r: ranked('train_order', r['sample_id'])),
                    validation=balanced(eligible_rows('validation'), 512, 'validation_samples'),
                    test=balanced(eligible_rows('test'), 1024, 'test_samples'))
    games = {g['replay_id']: g for g in kept}
    keep = set(used) | {r['replay_id'] for s in ('validation', 'test') for r in selected[s]}
    stage = paths.SOURCE / 'preparation'
    write_jsonl(stage / 'replays.jsonl', [dict(replay_id=rid, raw_path=games[rid]['raw_path'],
                                               raw_sha256=games[rid]['raw_sha256'], pool=games[rid]['pool'],
                                               uploadtime=games[rid]['uploadtime'])
                                          for rid in sorted(keep, key=order.get)], immutable=True)
    prepared.mkdir(parents=True, exist_ok=True)
    for name, rows in selected.items():
        write_jsonl(prepared / (name + '.jsonl'), rows, immutable=True)
    oldest = min(games[rid]['uploadtime'] for rid in used) if used else None
    month = Counter(dt.datetime.utcfromtimestamp(games[r['replay_id']]['uploadtime']).strftime('%Y-%m') for r in train)
    counts = dict(selected_split={k: len(v) for k, v in selected.items()},
                  train_games=len(used), train_pool_games=len(by_game), train_rows_budget=train_rows,
                  train_oldest_upload=oldest and dt.datetime.utcfromtimestamp(oldest).isoformat() + 'Z',
                  train_rows_by_month=dict(sorted(month.items())),
                  pool_eligible={p: len(eligible_rows(p)) for p in ('train', 'validation', 'test')})
    manifest = dict(experiment='EX-166', decision='D-208', created_at=time.time(), seed=SEED, counts=counts,
                    files={n + '.jsonl': sha(prepared / (n + '.jsonl')) for n in selected},
                    replays_sha256=sha(stage / 'replays.jsonl'),
                    recovery_source_sha256=sha(stage / 'recovery-source.json'),
                    select_sha256=sha(paths.RUN_DATA / 'select/kept.jsonl'))
    atomic(prepared / 'manifest.json', manifest, immutable=True)
    seal(prepared)
    return manifest
