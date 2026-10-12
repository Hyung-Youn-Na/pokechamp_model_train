"""The final report must retain denominators and gate its completion claim."""
import tempfile
import unittest
from pathlib import Path

from integration.pokechamp.imitation.outputs import write_report
from integration.pokechamp.imitation.reporting import summarize
from integration.pokechamp.imitation.storage import atomic


class FinalReport(unittest.TestCase):
    def fixture(self, root, viewer_passed):
        counts = dict(source_replays=2793, excluded_replays=82, recovered_decisions=100,
                      eligible_decisions=80, selected_split={'train':60,'validation':10,'test':10},
                      unknown_selection=12, single_candidate=8)
        atomic(root / 'prepared/manifest.json', {'counts': counts})
        atomic(root / 'preparation/inputs.json', dict(groups=630,largest_group=1803,
                                                   split_counts={'train':2169,'validation':271,'test':271}))
        atomic(root / 'audit.json', {'passed':True})
        atomic(root / 'preflight/report.json', dict(samples=[{}]*32,planned_updates=4))
        atomic(root / 'training/selection.json', dict(selected_update=2,checkpoint='checkpoint-2',
                                                    completed_planned_training=True))
        atomic(root / 'reload/serving-parity.json', {'passed':True})
        atomic(root / 'evaluation/report.json', dict(observations_per_model=10,
            nll_difference=-.5,action_match_rate_difference=.2,
            metrics={'initial':{'all':{'nll':2.0,'action_match_rate':.1}},
                     'selected':{'all':{'nll':1.5,'action_match_rate':.3}}}))
        schedule=[];outcomes=[]
        for model in ('initial','selected'):
            for cell in range(20):
                row=dict(slot_id=f'{model}-{cell}',model=model,pair_id=str(cell//4),
                         model_side='p1' if cell%4<2 else 'p2',
                         opponent='abyssal' if cell%2==0 else 'abyssal-tera-v1')
                schedule.append(row)
                outcomes.append(dict(row,status='completed',result='loss'))
        battle=summarize(schedule,outcomes)
        battle.update(all_slots_attempted=True,phase_error=None)
        atomic(root / 'battle/result.json',battle)
        atomic(root / 'final/viewer-check.json',dict(passed=viewer_passed))
        atomic(root / 'execution/resume-completed.json',dict(passed=True))

    def test_completed_report_uses_actual_starting_denominator_and_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,True)
            report=write_report(root)
            text=(root/'final/report.md').read_text()
            self.assertTrue(report['complete'])
            self.assertIn('출발 2,793경기',text)
            self.assertIn('82경기를 제외',text)
            self.assertIn('작은 첫 배틀 평가',text)
            self.assertIn('오프라인 손실 감소만으로 배틀 개선을 주장하지 않는다',text)

    def test_failed_viewer_prevents_completion_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,False)
            self.assertFalse(write_report(root)['complete'])

    def test_missing_actual_resume_is_reported_as_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,True)
            (root/'execution/resume-completed.json').unlink()
            report=write_report(root)
            self.assertFalse(report['complete'])
            self.assertIn('resume',report['missing'])


if __name__ == '__main__':
    unittest.main()
