"""EX-073 팀·동결 대진의 독립 불변식 검사."""
import unittest
from collections import Counter
from integration.pokechamp.abyssal_rl import prepare as p
from integration.pokechamp.tests import test_selfplay_prepare as original
from unittest.mock import patch


class ProvenanceTests(original.ProvenanceAndBCTests):
    def setUp(self):
        self.patch = patch.object(original, "p", p)
        self.patch.start()
        self.addCleanup(self.patch.stop)


def teams():
    return [dict(signature=f'composition-{i:03d}', team_id=f'team-{i}') for i in range(416)]


class PrepareTests(unittest.TestCase):
    def test_group_split_and_train_coverage(self):
        split = p.split_teams(teams())
        self.assertEqual(split, p.split_teams(list(reversed(teams()))))
        self.assertEqual({k: len(v) for k,v in split.items()}, dict(train=256,dev=32,test=128))
        rows = p.make_schedule(split)
        self.assertEqual(Counter(r['stage'] for r in rows), dict(train=8192,dev=8256,calibration=64,calibration_dev=24,test=512))
        self.assertEqual(len({r['slot_id'] for r in rows}), len(rows))
        training = [r for r in rows if r['stage']=='train']
        for start in range(1,129,4):
            block = [r for r in training if start <= r['round'] < start+4]
            self.assertEqual(len({r['learner_team']['signature'] for r in block}),256)
        for row in rows:
            self.assertEqual(row['opponent'], 'abyssal')
            self.assertNotEqual(row['learner_team']['signature'],row['opponent_team']['signature'])
        broken = teams()
        broken[-1]['signature'] = broken[0]['signature']
        with self.assertRaises(ValueError):
            p.split_teams(broken)

    def test_assignment_side_pairing_and_calibration_separation(self):
        rows = p.make_schedule(p.split_teams(teams()))
        test = [r for r in rows if r['stage']=='test']
        for a,b in zip(test[:256],test[256:],strict=True):
            for key in ('pair_id','assignment','model_side','teams','simulator_seed','model_seed','opponent_seed'):
                self.assertEqual(a[key],b[key])
        dev = [r for r in rows if r['stage']=='dev' and r['round']==0]
        for pair in {r['pair_id'] for r in dev}:
            group = [r for r in dev if r['pair_id']==pair]
            self.assertEqual({(r['assignment'],r['model_side']) for r in group},{(a,s) for a in (0,1) for s in ('p1','p2')})
            self.assertEqual(len({r['learner_team']['signature'] for r in group}),2)
        self.assertFalse({tuple(r['simulator_seed']) for r in dev} & {tuple(r['simulator_seed']) for r in rows if r['stage']=='calibration_dev'})

if __name__ == '__main__': unittest.main()
