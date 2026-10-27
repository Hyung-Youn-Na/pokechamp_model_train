"""EX-132: replay outcome parsing, per-row weights (mean 1) and the soft-CE scaling the training relies on."""
import pytest

from integration.laya_imitation import outcome_weights as ow
from integration.laya_imitation.training import EX124, EX132, weigh_items

LOG = '\n'.join(['|j|☆RRENES', '|player|p1|RRENES|1|1440', '|player|p2|carbon life-form meme|2|1482', '|turn|1',
                 '|win|Carbon Life Form Meme', '|player|p1|'])


def test_outcome_from_log_maps_sides_by_showdown_id():
    assert ow.outcome_from_log(LOG) == dict(p1='loss', p2='win')
    assert ow.outcome_from_log('|player|p1|a|\n|player|p2|b|\n|tie') == dict(p1='tie', p2='tie')
    assert ow.outcome_from_log('|player|p1|a|\n|player|p2|b|\n|turn|9') is None
    assert ow.outcome_from_log('|player|p1|a|\n|player|p2|b|\n|win|c') is None


def test_weights_have_mean_one_and_keep_the_ratio():
    results = {'r1': dict(p1='win', p2='loss'), 'r2': dict(p1='tie', p2='tie')}
    ids = ['r1:p1:10:turn_action', 'r1:p2:10:turn_action', 'r1:p1:20:switch', 'r2:p1:5:turn_action']
    weights, unmatched, counts = ow.weigh(ids, results)
    assert unmatched == [] and counts['win'] == 2 and counts['loss'] == 1 and counts['tie'] == 1
    assert sum(weights.values()) / len(weights) == pytest.approx(1.0)
    assert weights['r1:p2:10:turn_action'] / weights['r1:p1:10:turn_action'] == pytest.approx(ow.LOSER / ow.WIN)
    _, missing, _ = ow.weigh(['r3:p1:1:turn_action'], results)
    assert missing == ['r3:p1:1:turn_action']


def test_replay_id_may_hold_dashes():
    assert ow.replay_of('smogtours-gen9ou-884619:p1:2407:turn_action') == ('smogtours-gen9ou-884619', 'p1')


def test_weigh_items_scales_targets_and_soft_ce_linearly():
    torch = pytest.importorskip('torch')
    laya_train = pytest.importorskip('laya.train')
    rows = [dict(sample_id='a'), dict(sample_id='b')]
    items = [dict(target=[0.0, 1.0, 0.0]), dict(target=[1.0, 0.0, 0.0])]
    weigh_items(rows, items, dict(a=1.25, b=0.625))
    assert items[0]['target'] == [0.0, 1.25, 0.0] and items[1]['target'] == [0.625, 0.0, 0.0]
    logits = torch.tensor([[0.1, 0.7, -0.2]])
    mask = torch.ones(1, 3, dtype=torch.bool)
    unit = laya_train.soft_ce_loss(logits, torch.tensor([[0.0, 1.0, 0.0]]), mask)
    scaled = laya_train.soft_ce_loss(logits, torch.tensor([items[0]['target']]), mask)
    assert float(scaled) == pytest.approx(1.25 * float(unit))
    with pytest.raises(ValueError):
        weigh_items([dict(sample_id='z')], [dict(target=[1.0])], {})


def test_ex132_is_ex124_plus_weights_on_gpu0():
    for key in ('dataset', 'head', 'max_exclusion_rate', 'extra_train', 'hours'):
        assert getattr(EX132, key) == getattr(EX124, key)
    assert EX132.weights is not None and EX124.weights is None and EX132.gpu[0] == 0
    assert EX132.same_split_as == EX124.out
