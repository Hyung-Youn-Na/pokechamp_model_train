"""Independent split, schedule, provenance and BC-train isolation checks."""
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest

from integration.pokechamp.imitation import schema
from integration.pokechamp.imitation.storage import atomic, sha
from integration.pokechamp.selfplay import prepare as p
from integration.pokechamp.tests.test_imitation_data import snapshot


def teams():
    return [dict(signature=f'composition-{i:03d}', team_id=f'team-{i}', text=str(i), packed=str(i))
            for i in range(92)]


def bc_row(number):
    value = schema.from_snapshot(snapshot(), [dict(id='switch:2', description='second'),
                                               dict(id='move:tackle:normal', description='first')])
    return dict(sample_id=f'sample-{number}', replay_id='replay', group_id='group', split='train',
                eligible=True, label='switch:2', input=value.body)


class TeamAndScheduleTests(unittest.TestCase):
    def test_splits_are_deterministic_disjoint_and_exact(self):
        result = p.split_teams(teams())
        self.assertEqual(result, p.split_teams(list(reversed(teams()))))
        self.assertEqual({name: len(rows) for name, rows in result.items()}, p.SPLIT_COUNTS)
        duplicate = teams()
        duplicate[-1]['signature'] = duplicate[0]['signature']
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            p.split_teams(duplicate)

    def test_complete_schedule_denominators_and_sampling_identity(self):
        split = p.split_teams(teams())
        rows = p.make_schedule(split)
        self.assertEqual(len(rows), 584)
        self.assertEqual(len({row['slot_id'] for row in rows}), 584)
        self.assertEqual(Counter(row['stage'] for row in rows),
                         dict(train=256, dev=120, calibration=64, calibration_dev=24, test=120))
        self.assertEqual(rows, p.make_schedule(split))
        for round_index in range(1, 5):
            selected = [r for r in rows if r['stage'] == 'train' and r['round'] == round_index]
            self.assertEqual(Counter(r['opponent'] for r in selected),
                             {'current': 32, 'snapshot': 16, 'abyssal': 8, 'abyssal-tera-v1': 8})
            self.assertEqual(len({r['learner_team']['signature'] for r in selected}), 32)
            for a, b in zip(selected[::2], selected[1::2]):
                self.assertEqual(a['teams']['p1'], b['teams']['p2'])
                self.assertEqual(a['teams']['p2'], b['teams']['p1'])
                self.assertEqual(a['opponent_snapshot_index'], b['opponent_snapshot_index'])
            for row in selected:
                if row['opponent'] == 'snapshot':
                    self.assertIn(row['opponent_snapshot_index'], range(max(1, round_index - 1)))

    def test_test_pairing_preserves_simulator_teams_sides_and_rng(self):
        rows = p.make_schedule(p.split_teams(teams()))
        test = [r for r in rows if r['stage'] == 'test']
        for initial, selected in zip(test[:60], test[60:], strict=True):
            for key in ('pair_id', 'model_side', 'opponent', 'teams', 'simulator_seed',
                        'model_seed', 'opponent_seed'):
                self.assertEqual(initial[key], selected[key])
        self.assertEqual(len({r['pair_id'] for r in test}), 10)
        self.assertEqual(Counter(r['opponent'] for r in test[:60]),
                         {'initial': 20, 'abyssal': 20, 'abyssal-tera-v1': 20})
        dev_seeds = {tuple(r['simulator_seed']) for r in rows if r['stage'] == 'dev'}
        calibration_seeds = {tuple(r['simulator_seed']) for r in rows if r['stage'] == 'calibration_dev'}
        self.assertFalse(dev_seeds & calibration_seeds)

    def test_illegal_and_excluded_compositions_cannot_be_selected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entries = []
            for i in range(6):
                species = [f'species{i}-{n}' for n in range(6)]
                path = root / f'{i}.txt'
                path.write_text(json.dumps(species))
                entries.append(dict(path=path.name, species=species, sha256=sha(path)))
            registry = dict(default_team_root=str(root), teams=entries,
                            reviewed_species_ids={p.signature(row['species']).split('|')[0]
                                                  for row in entries})
            registry['reviewed_species_ids'] = [s for e in entries for s in p.signature(e['species']).split('|')]

            def normalize(values):
                species = json.loads(values[0]['text'])
                return [dict(legal='species1-0' not in species, species=species, sets=[], packed='', text='')]

            excluded = {p.signature(entries[0]['species'])}
            chosen, _ = p.choose_teams(registry, excluded, normalize, count=4)
            self.assertEqual(len(chosen), 4)
            self.assertNotIn(p.signature(entries[0]['species']), {r['signature'] for r in chosen})
            self.assertNotIn(p.signature(entries[1]['species']), {r['signature'] for r in chosen})
            self.assertEqual(chosen, p.choose_teams(dict(registry, teams=list(reversed(entries))),
                                                   excluded, normalize, count=4)[0])
            with self.assertRaisesRegex(ValueError, 'only 4'):
                p.choose_teams(registry, excluded, normalize, count=5)


class ProvenanceAndBCTests(unittest.TestCase):
    def test_entire_raw_corpus_is_excluded_regardless_of_replay_eligibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'data/showdown-replays/raw'
            directory.mkdir(parents=True)
            path = directory / 'ineligible.json'
            species = [f'Species{i}' for i in range(6)]
            log = '\n'.join(f'|poke|p1|{s}, L100' for s in species) + '\n|start|'
            atomic(path, dict(id='ineligible', log=log))
            manifest = root / 'manifest.json'
            atomic(manifest, dict(raw_file_sha256={str(path.relative_to(root)): sha(path)}))
            rows = p.replay_compositions(manifest, root)
            self.assertEqual(rows[0]['signatures']['p1'], p.signature(species))
            self.assertIn('p2', rows[0]['non_six_distinct_previews'])
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                p.replay_compositions(manifest, root)

    def test_new_unmanifested_replay_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'data/showdown-replays/raw'
            directory.mkdir(parents=True)
            (directory / 'unknown.json').write_text('{}')
            manifest = root / 'manifest.json'
            atomic(manifest, dict(raw_file_sha256={}))
            with self.assertRaisesRegex(ValueError, 'inventory'):
                p.replay_compositions(manifest, root)

    def test_bc_hash_selection_is_label_independent_and_retains_candidate_order(self):
        rows = [bc_row(i) for i in range(10)]
        assignments = {'replay': dict(split='train', group_id='group')}
        first, count = p.choose_bc(rows, assignments, limit=4)
        changed = copy.deepcopy(list(reversed(rows)))
        for row in changed:
            row['label'] = 'move:tackle:normal'
        second, _ = p.choose_bc(changed, assignments, limit=4)
        self.assertEqual(count, 10)
        self.assertEqual([r['sample_id'] for r in first], [r['sample_id'] for r in second])
        for row in first:
            self.assertEqual(tuple(row['input']['questions']['action']['criteria']),
                             ('switch:2', 'move:tackle:normal'))

    def test_bc_rejects_nontrain_and_ineligible_samples(self):
        assignments = {'replay': dict(split='train', group_id='group')}
        for mutation in [dict(split='test'), dict(eligible=False), dict(label='switch:6'), dict(group_id='wrong')]:
            row = dict(bc_row(0), **mutation)
            with self.assertRaises(ValueError):
                p.choose_bc([row], assignments, limit=1)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            p.choose_bc([bc_row(0), bc_row(0)], assignments, limit=1)
        with self.assertRaisesRegex(ValueError, 'only 1'):
            p.choose_bc([bc_row(0)], assignments, limit=4)


if __name__ == '__main__':
    unittest.main()
