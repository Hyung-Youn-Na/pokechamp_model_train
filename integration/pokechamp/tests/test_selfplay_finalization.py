"""Synthetic final-publication guards; all browser/export work stays in tmp_path."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.pokechamp.selfplay import config, finalize as f, prepare, reporting
from integration.pokechamp.selfplay.storage import atomic, read, sha, write_jsonl, Clock
from integration.pokechamp.tests.test_selfplay_reporting import prediction


CHECKS = ('cpu_validation', 'gpu_preflight', 'first_eight_audit', 'training',
          'policy_selection', 'calibration_decision', 'resume_validation')


@pytest.fixture
def run_directory(tmp_path):
    root = tmp_path / 'EX-072'
    root.mkdir()
    # Full planned denominator, with one normally trained/dev-complete candidate.
    teams = prepare.split_teams([dict(signature=f'composition-{i:03d}', team_id=f'team-{i}',
                                      text=str(i), packed=str(i)) for i in range(92)])
    schedule = prepare.make_schedule(teams)
    atomic(root / 'manifest.json', dict(experiment_id='EX-072', protocol=config.PROTOCOL,
                                       source={}, synthetic_test_only=True))
    atomic(root / 'prepared/schedule.json', schedule)
    atomic(root / 'prepared/teams.json', teams)
    atomic(root / 'prepared/manifest.json', dict(experiment='EX-072', seed=config.SEED,
        files={'schedule.json': sha(root / 'prepared/schedule.json'),
               'teams.json': sha(root / 'prepared/teams.json')}))
    atomic(root / 'resource.json', dict(physical_gpu=3, uuid='synthetic-unused-GPU', synthetic_test_only=True))
    Clock(root, start=True)
    snapshots = {}
    for name in ('initial', 'round-1', 'selected-before', 'selected-after', 'final'):
        path = root / 'snapshots' / (name + '.pt')
        atomic(path, ('synthetic-no-model-' + name).encode())
        snapshots[name] = dict(path=str(path), sha256=sha(path))
    snapshots['selected'] = dict(snapshots['selected-before'])
    checkpoint = root / 'checkpoints/checkpoint.pt'
    atomic(checkpoint, b'synthetic-no-checkpoint')
    atomic(root / 'latest.json', dict(path=str(checkpoint), sha256=sha(checkpoint), global_updates=1))
    selection = dict(model='round-1', round=1, mean_score=.5)
    calibration = dict(adopt=False, head='before', complete=True, reason='synthetic tie')
    atomic(root / 'state.json', dict(phase='finalize', round=1, checks={name: True for name in CHECKS},
        selected=selection, calibration_decision=calibration, calibration_complete=True,
        snapshot_paths=snapshots, trainer=dict(global_updates=1)))
    atomic(root / 'selection.json', dict(selection=selection))
    atomic(root / 'calibration-decision.json', calibration)
    atomic(root / 'evaluation-lock.json', dict(selected=selection, final=snapshots['final'], head='before',
                                               clock=read(root / 'clock.json'),
                                               schedule_sha256=sha(root / 'prepared/schedule.json')))
    for name in ('cpu', 'preflight', 'first-eight', 'first-update', 'resume', 'calibration-policy'):
        atomic(root / 'verification' / (name + '.json'), dict(passed=True, synthetic_test_only=True))
    atomic(root / 'supervisor-exit.json', dict(returncode=0, attempts=2))
    atomic(root / 'cleanup.json', dict(passed=True, records=[], synthetic_test_only=True))
    atomic(root / 'cleanup-receipt.json', dict(passed=True, records=[], synthetic_test_only=True))
    for slot in schedule:
        normal = (slot['stage'] == 'test' or slot['stage'] == 'train' and slot['round'] == 1
                  or slot['stage'] == 'dev' and slot['model'] in ('initial', 'round-1')
                  or slot['stage'] in ('calibration', 'calibration_dev'))
        if not normal:
            continue
        outcome = dict(slot, status='completed', result='draw', turns=2, audit_passed=True,
                       actors_cleaned=True, server_cleaned=True)
        if slot['stage'] == 'test':
            outcome['result'] = 'loss' if slot['model'] == 'initial' else 'win'
        game = root / 'games' / slot['slot_id']
        atomic(game / 'outcome.json', outcome)
        count = 8 if slot['stage'] == 'train' else 1
        atomic(game / 'audit.json', dict(passed=True, valid_decisions=count, synthetic_test_only=True))
        decisions = [prediction(outcome, index=i, after=[.7, .2, .1]) for i in range(count)]
        for decision in decisions:
            decision['decision_id'] = slot['slot_id'] + ':' + decision['decision_id']
        write_jsonl(game / 'decisions.jsonl', decisions)
    return root


@pytest.fixture
def fake_publication(monkeypatch):
    calls = SimpleNamespace(exports=[], browsers=[], remaining=900, browser_passed=True,
                            export_error=None, source_before={})
    monkeypatch.setattr(f, 'Clock', lambda _directory: SimpleNamespace(
        remaining=lambda *args: calls.remaining, deadline=lambda stage: f.time.time() + calls.remaining))
    original_bootstrap = reporting.paired_bootstrap
    monkeypatch.setattr(reporting, 'paired_bootstrap',
                        lambda left, right, **kwargs: original_bootstrap(left, right, draws=16))

    def export(source, output, **kwargs):
        source, output = Path(source), Path(output)
        calls.exports.append((source, output))
        calls.source_before = f.viewer.verify_source(source)
        if calls.export_error:
            raise calls.export_error
        output.mkdir(parents=True)
        for name in ('manifest.json', 'result.json', 'report.md'):
            atomic(output / name, (source / name).read_bytes())
        atomic(output / 'index.html', b'<html><body><a href="report.md">report</a><a href="battle-001/index.html">battle</a></body></html>')
        atomic(output / 'provenance.json', dict(experiment_id='EX-072',
            source=str(source), source_files=calls.source_before,
            source_seal_sha256=sha(source / 'checksums.sha256'),
            copied_files={name: sha(output / name) for name in ('manifest.json', 'result.json', 'report.md')}))
        f.seal(output)
        rows = read(source / 'result.json')['outcomes']
        return dict(index=str(output / 'index.html'), matches=[], planned=len(rows),
                    completed=sum(r['status'] == 'completed' for r in rows),
                    export_sha256=sha(output / 'checksums.sha256'))

    def browser(command, **kwargs):
        calls.browsers.append((command, kwargs))
        report = Path(command[command.index('--report') + 1])
        atomic(report, dict(passed=calls.browser_passed, moved=True, offline=True,
                            synthetic_test_only=True), immutable=True)
        return SimpleNamespace(returncode=0 if calls.browser_passed else 1,
                               stdout='synthetic browser stub\n', stderr='')

    monkeypatch.setattr(f.viewer, 'export', export)
    monkeypatch.setattr(f.subprocess, 'run', browser)
    return calls


def published_results(directory, export):
    paths = [directory / 'final/result.json', directory / 'final/battles/result.json',
             export / 'result.json', export / 'viewer/result.json']
    return {str(path): read(path) for path in paths if path.exists()}


def test_success_publishes_authoritative_result_only_after_browser_and_preserves_source(run_directory, tmp_path, fake_publication):
    export = tmp_path / 'exports/ex072'
    receipt = f.finalize(run_directory, export_root=export)
    assert receipt['closed'] and receipt['experiment_complete']
    assert fake_publication.exports and fake_publication.browsers
    result = read(run_directory / 'final/result.json')
    assert result['experiment_complete'] and result['performance_improved']
    assert result['incomplete_requirements'] == []
    assert read(export / 'result.json') == result
    assert sha(run_directory / 'final/result.json') == receipt['result_sha256']
    source = run_directory / 'final/battles'
    assert not read(source / 'result.json')['experiment_complete']
    assert f.viewer.verify_source(source) == fake_publication.source_before
    sealed = read(run_directory / 'final/artifact-manifest.json')
    assert 'latest.json' in sealed and 'snapshots/final.pt' in sealed
    assert all(sha(run_directory / name) == digest for name, digest in sealed.items())
    assert f.finalize(run_directory, export_root=export) == receipt


@pytest.mark.parametrize('failure', ['browser', 'export'])
def test_viewer_failure_never_publishes_any_completed_report(run_directory, tmp_path, fake_publication, failure):
    export = tmp_path / 'exports/ex072'
    if failure == 'browser':
        fake_publication.browser_passed = False
    else:
        fake_publication.export_error = ValueError('synthetic export failure')
    receipt = f.finalize(run_directory, export_root=export)
    assert receipt['closed'] and not receipt['experiment_complete']
    reports = published_results(run_directory, export)
    assert reports and all(not result['experiment_complete'] for result in reports.values()), reports
    assert 'viewer' in receipt['incomplete_requirements']


@pytest.mark.parametrize('missing', CHECKS)
def test_missing_required_stage_gate_can_never_be_promoted_by_export(run_directory, tmp_path, fake_publication, missing):
    state = read(run_directory / 'state.json')
    state['checks'].pop(missing)
    atomic(run_directory / 'state.json', state)
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert not receipt['experiment_complete']
    assert missing in receipt['incomplete_requirements']


@pytest.mark.parametrize('missing', ['latest.json', 'checkpoints/checkpoint.pt', 'snapshots/final.pt'])
def test_missing_model_or_resume_artifact_prevents_completed_closure(run_directory, tmp_path, fake_publication, missing):
    (run_directory / missing).unlink()
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert not receipt['experiment_complete']


def test_missing_selected_test_probabilities_prevents_completed_closure(run_directory, tmp_path, fake_publication):
    for row in read(run_directory / 'prepared/schedule.json'):
        if row['stage'] == 'test' and row['model'] == 'selected':
            (run_directory / 'games' / row['slot_id'] / 'decisions.jsonl').unlink()
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert not receipt['experiment_complete']


def test_altered_final_weights_do_not_pass_hash_seal(run_directory, tmp_path, fake_publication):
    atomic(run_directory / 'snapshots/final.pt', b'changed model bytes')
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert not receipt['experiment_complete']


def test_altered_prepared_schedule_cannot_acquire_a_new_final_seal(run_directory, tmp_path, fake_publication):
    rows = read(run_directory / 'prepared/schedule.json')
    # Preserve all matchup semantics: even an unregistered field changes the
    # frozen input artifact and must fail its original hash before publication.
    rows[0]['changed_after_freeze'] = True
    atomic(run_directory / 'prepared/schedule.json', rows)
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert not receipt['experiment_complete']
    assert not fake_publication.exports


def test_non_ex072_directory_is_rejected_before_any_write(tmp_path, fake_publication):
    old = tmp_path / 'EX-071'
    atomic(old / 'manifest.json', dict(experiment_id='EX-071'))
    original = (old / 'manifest.json').read_bytes()
    with pytest.raises((ValueError, FileNotFoundError)):
        f.finalize(old, export_root=tmp_path / 'exports/ex072')
    assert (old / 'manifest.json').read_bytes() == original
    assert sorted(p.name for p in old.iterdir()) == ['manifest.json']
    assert not fake_publication.exports


def test_expired_budget_skips_export_and_reports_incomplete(run_directory, tmp_path, fake_publication):
    fake_publication.remaining = 0
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert receipt['closed'] and not receipt['experiment_complete']
    assert not fake_publication.exports and not fake_publication.browsers


def test_false_cleanup_gate_cannot_be_hidden_by_successful_viewer(run_directory, tmp_path, fake_publication):
    row = next(row for row in read(run_directory / 'prepared/schedule.json') if row['stage'] == 'test')
    path = run_directory / 'games' / row['slot_id'] / 'outcome.json'
    outcome = read(path)
    outcome['actors_cleaned'] = False
    atomic(path, outcome)
    receipt = f.finalize(run_directory, export_root=tmp_path / 'exports/ex072')
    assert not receipt['experiment_complete']
    assert 'cleanup' in receipt['incomplete_requirements']


def test_repeated_closure_detects_changed_authoritative_result(run_directory, tmp_path, fake_publication):
    export = tmp_path / 'exports/ex072'
    f.finalize(run_directory, export_root=export)
    atomic(run_directory / 'final/result.json', dict(experiment_complete=True, corrupted=True))
    with pytest.raises(ValueError):
        f.finalize(run_directory, export_root=export)


def test_existing_legacy_catalog_content_is_preserved(run_directory, tmp_path, fake_publication):
    export = tmp_path / 'exports/ex072'
    catalog = export.parent / 'index.html'
    atomic(catalog, b'<html><body><p id="preserve">EX-071 historical evidence</p></body></html>')
    f.finalize(run_directory, export_root=export)
    assert '<p id="preserve">EX-071 historical evidence</p>' in catalog.read_text()


def test_existing_viewer_refusal_never_overwrites_any_prior_report(run_directory, tmp_path, fake_publication):
    export = tmp_path / 'exports/ex072'
    prior = {'report.md': b'previous report', 'result.json': b'{"previous":true}',
             'manifest.json': b'{"immutable":true}', 'index.html': b'previous viewer'}
    for name, data in prior.items():
        atomic(export / name, data, immutable=True)
    try:
        receipt = f.finalize(run_directory, export_root=export)
    except FileExistsError:
        # A refusal may be raised or written as an incomplete closure, but it
        # must never mutate the prior independently preserved publication.
        pass
    else:
        assert not receipt['experiment_complete']
    assert {p.name: p.read_bytes() for p in export.iterdir()} == prior
    assert not fake_publication.exports


def test_cli_intentional_interrupt_remains_resumable_without_finalizing(run_directory, monkeypatch):
    from integration.pokechamp.selfplay import __main__ as cli, execution
    calls = []
    monkeypatch.setattr(execution, 'supervisor', lambda *args, **kwargs: 130)
    monkeypatch.setattr(f, 'finalize', lambda *args, **kwargs: calls.append(True))
    assert cli.main(['run', '--output', str(run_directory)]) == 130
    assert not calls


def test_cli_budget_interrupt_closes_as_incomplete_instead_of_silently_skipping_report(run_directory, monkeypatch):
    from integration.pokechamp.selfplay import __main__ as cli, execution
    calls = []
    atomic(run_directory / 'supervisor-exit.json', dict(returncode=130, reason='budget'))
    monkeypatch.setattr(execution, 'supervisor', lambda *args, **kwargs: 130)

    def finalize(*args, **kwargs):
        calls.append(args[0])
        return dict(closed=True, experiment_complete=False)

    monkeypatch.setattr(f, 'finalize', finalize)
    assert cli.main(['run', '--output', str(run_directory)]) == 0
    assert calls == [run_directory]
