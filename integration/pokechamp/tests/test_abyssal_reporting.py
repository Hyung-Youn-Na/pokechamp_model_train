"""승률/무승부/실패 분모 및64쌍 대응 통계 검사."""
import copy
import unittest
from integration.pokechamp.abyssal_rl import reporting as r


def outcomes(model, pairs=64, result='win'):
    return [dict(slot_id=f'{model}-{p}-{s}-{a}',pair_id=f'pair{p}',model=model,
                 model_side=s,assignment=a,opponent='abyssal',status='completed',result=result,
                 simulator_seed=[p,0,0,1],model_seed=1,opponent_seed=2,teams={'p1':p,'p2':p+1})
            for p in range(pairs) for a in (0,1) for s in ('p1','p2')]


class ReportingTests(unittest.TestCase):
    def test_draw_is_not_a_win_and_initial_wins_tie(self):
        initial = outcomes('initial',16,'draw')
        trained = outcomes('round-1',16,'draw')
        summary = r.policy_summary(initial)
        self.assertEqual(summary['rates']['win'],0)
        self.assertEqual(summary['mean_score'],.5)
        selected = r.select_policy([dict(model='round-1',round=1,outcomes=trained),dict(model='initial',round=0,outcomes=initial)])
        self.assertEqual(selected['model'],'initial')
        trained[0].update(status='failed',result=None)
        self.assertIsNone(r.select_policy([dict(model='round-1',round=1,outcomes=trained)]))

    def test_full_paired_bootstrap_and_failed_not_result(self):
        initial, selected = outcomes('initial',result='draw'), outcomes('selected')
        value = r.paired_bootstrap(initial,selected,draws=100)
        self.assertEqual(value['win_rate_ci95'],[1,1])
        self.assertEqual(value['ci95'],[1,1])
        self.assertTrue(value['target_achieved'])
        selected[0].update(status='failed',result=None)
        value = r.paired_bootstrap(initial,selected,draws=100)
        self.assertFalse(value['complete'])
        self.assertFalse(value['target_achieved'])
        self.assertIsNone(value['ci95'])
        selected[0]['result']='loss'
        with self.assertRaises(ValueError): r.policy_summary(selected)

    def test_pairing_duplicate_and_missing_assignment_rejected(self):
        initial, selected = outcomes('initial'),outcomes('selected')
        selected[0]['model_seed']=42
        with self.assertRaisesRegex(ValueError,'paired conditions'): r.paired_bootstrap(initial,selected,draws=10)
        with self.assertRaisesRegex(ValueError,'duplicate'): r.evaluation_complete(initial+[initial[0]],expected_pairs=64)
        value = copy.deepcopy(initial)
        value[0]['assignment']=2
        with self.assertRaises(ValueError): r.evaluation_complete(value,expected_pairs=64)

    def test_calibration_incomplete_and_tie_keep_head(self):
        rows=outcomes('selected',6)
        decisions=[dict(slot_id=x['slot_id'],decision_id='1',wdl_before=[1,0,0],wdl_after=[1,0,0]) for x in rows]
        value=r.calibration_decision(rows,decisions)
        self.assertTrue(value['complete'])
        self.assertFalse(value['adopt'])
        self.assertFalse(r.calibration_decision(rows,decisions[:-1])['complete'])

if __name__ == '__main__': unittest.main()
