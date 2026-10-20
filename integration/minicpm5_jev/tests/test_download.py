"""Official content receipt coverage and EX-091 physical-resource boundaries."""
from integration.minicpm5_jev.download import inventories, verify_receipt
from integration.jev27b.resource import limit_errors
from integration.jev_eval.config import experiment
from integration.jev_eval.resource import disk_roots


def test_both_official_revisions_have_verified_complete_inventories():
    rows = inventories()
    assert len(rows) == 2
    assert [r['revision'] for r in rows] == ['27afc6f17ceb7eb95b6442047ec54e43fbed5ed1',
                                           'f97400052a43d642bbc6e9975e2397e3ae6a6b52']
    receipt = verify_receipt()
    assert receipt['passed'] and len(receipt['files']) == 23
    assert receipt['disk_limit_bytes'] is None


def test_unbounded_disk_keeps_gpu_and_host_limits_and_legacy_disk_limits():
    sample = dict(rss_bytes=0, disk_bytes=101 * 1024**3,
                  gpus={i: dict(memory_used_mib=0) for i in range(4)})
    assert limit_errors(sample, profile='ex091') == []
    assert limit_errors(sample, profile='ex090') == ['disk_budget_exceeded']
    sample['rss_bytes'] = 33 * 1024**3
    sample['gpus'][0]['memory_used_mib'] = 45 * 1024
    assert limit_errors(sample, profile='ex091') == ['host_memory_exceeded', 'gpu0_memory_exceeded']


def test_disk_usage_still_counts_new_weights_outputs_and_temporary_copies(tmp_path):
    cfg = experiment('EX-091')
    roots = disk_roots(cfg, extra_roots=(tmp_path,))
    for path in (cfg.model_dir, cfg.run, cfg.export, cfg.model_evidence, tmp_path):
        assert any(path.resolve() == p or p in path.resolve().parents for p in roots)
    assert cfg.runtime.physical_gpus == (0,)
    assert cfg.runtime.allocator_bytes == 40 * 1024**3
