"""원 시계·원본 보존·허용 교정 경계와 checkpoint 복구의 CPU 회귀."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from integration.pokechamp.abyssal_rl_next import recovery
except ImportError:
    spec = importlib.util.spec_from_file_location(
        'integration.pokechamp.abyssal_rl_next.recovery', Path(__file__).with_name('recovery.py'))
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
from integration.pokechamp.abyssal_rl_next.storage import atomic, read, sha
from integration.pokechamp.abyssal_rl_next import config


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.initial = self.root / 'initial'
        atomic(self.initial / 'files.json', {'initial': 'weights'})
        self.patch = patch.object(config, 'INITIAL', self.initial)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        source_root = self.root / 'recoveries/deterministic-v2/source'
        old = {'integration/pokechamp/abyssal_rl_next/model.py': b'old model',
               'integration/pokechamp/abyssal_rl_next/trainer.py': b'unchanged trainer'}
        new = dict(old, **{'integration/pokechamp/abyssal_rl_next/model.py': b'new deterministic model',
                          'integration/pokechamp/abyssal_rl_next/recovery.py': b'narrow validator'})
        for name, content in old.items():
            atomic(self.root / 'source' / name, content)
        for name, content in new.items():
            atomic(source_root / name, content)
        self.old = {name: sha(self.root / 'source' / name) for name in old}
        self.new = {name: sha(source_root / name) for name in new}
        source_patch = patch('integration.pokechamp.abyssal_rl_next.execution.source_files', return_value=self.new)
        source_patch.start()
        self.addCleanup(source_patch.stop)
        self.clock = {'started_at': 100, 'deadline_at': 43300, 'limits': config.PROTOCOL['seconds']}
        atomic(self.root / 'clock.json', self.clock)
        atomic(self.root / 'resource.json', {'gpus': [{'uuid': str(i)} for i in range(4)]})
        atomic(self.root / 'prepared/manifest.json', {'original': True})
        atomic(self.root / 'verification/cpu.json', {'passed': True, 'source': self.old})
        manifest = {'experiment_id': 'EX-075', 'protocol': copy.deepcopy(config.PROTOCOL), 'source': self.old,
                    'prepared_sha256': sha(self.root / 'prepared/manifest.json'),
                    'resource_sha256': sha(self.root / 'resource.json'),
                    'cpu_sha256': sha(self.root / 'verification/cpu.json'),
                    'initial_checkpoint_sha256': sha(self.initial / 'files.json')}
        atomic(self.root / 'manifest.json', manifest)
        atomic(self.root / 'checkpoints/bootstrap.pt', b'original complete step0 bytes including optimizer and RNG')
        self.bootstrap = self.ref('checkpoints/bootstrap.pt')
        atomic(self.root / 'recoveries/deterministic-v2/verification/suite.log', b'passed')
        log = self.root / 'recoveries/deterministic-v2/verification/suite.log'
        cpu = {'passed': True, 'source': self.new, 'prepared_sha256': manifest['prepared_sha256'],
               'gpu_operations': 0, 'tests': [{'returncode': 0, 'log': str(log), 'sha256': sha(log)}]}
        atomic(self.root / 'recoveries/deterministic-v2/verification/cpu.json', cpu)
        reports = []
        for rank in range(4):
            name = f'diagnostics/probe/report-rank-{rank}.json'
            atomic(self.root / name, {'rank': rank, 'passed': True, 'world_size': 4,
                                     'weights_restored': True, 'rng_restored': True, 'optimizer_updates': 0,
                                     'deterministic': True, 'cublas_workspace_config': ':4096:8',
                                     'tolerances': {'logp_wdl_atol':1e-5, 'gradient_atol':1e-5,
                                                    'gradient_rtol':1e-4, 'update_atol':1e-6, 'update_rtol':1e-5}})
            reports.append(self.ref(name))
        proof = {'passed': True, 'world_size': 4, 'original_manifest_sha256': sha(self.root / 'manifest.json'),
                 'bootstrap_checkpoint_sha256': self.bootstrap['sha256'], 'backend': recovery.BACKEND,
                 'tolerances': config.PROTOCOL['numeric_tolerances'], 'weights_restored': True,
                 'rng_restored': True, 'forward_unchanged': True, 'independent_reports': reports}
        atomic(self.root / 'diagnostics/proof.json', proof)
        resources = []
        for index in range(3):
            name = f'diagnostics/run-{index}/receipt.json'
            atomic(self.root / name, {'original_start': 100, 'absolute_deadline': 43300,
                                     'gpu_uuids': [str(i) for i in range(4)], 'started': 101 + index,
                                     'seconds': 1})
            resources.append(self.ref(name))
        changed = {key for key in self.old.keys() | self.new.keys() if self.old.get(key) != self.new.get(key)}
        self.receipt = {'schema': recovery.SCHEMA, 'backend': recovery.BACKEND,
                        'original_manifest_sha256': sha(self.root / 'manifest.json'),
                        'clock_sha256': sha(self.root / 'clock.json'),
                        'prepared_sha256': manifest['prepared_sha256'],
                        'resource_sha256': manifest['resource_sha256'],
                        'original_cpu_sha256': manifest['cpu_sha256'],
                        'initial_checkpoint_sha256': manifest['initial_checkpoint_sha256'],
                        'source': self.new, 'source_root': 'recoveries/deterministic-v2/source',
                        'changes': {key: {'before': self.old.get(key), 'after': self.new[key]} for key in changed},
                        'cpu': self.ref('recoveries/deterministic-v2/verification/cpu.json'),
                        'proof': self.ref('diagnostics/proof.json'), 'bootstrap_checkpoint': self.bootstrap,
                        'diagnostic_resources': resources}
        self.commit()

    def ref(self, name):
        return {'path': name, 'sha256': sha(self.root / name)}

    def commit(self):
        atomic(self.root / 'recovery.json', self.receipt)

    def validate(self):
        return recovery.validate(self.root, current_sources=self.new)

    def test_every_worker_launch_sets_verified_workspace_before_cuda(self):
        from integration.pokechamp.abyssal_rl_next.execution import worker_environment
        with patch.dict('os.environ', {'CUBLAS_WORKSPACE_CONFIG': 'wrong inherited value'}):
            environment = worker_environment({'gpus': [{'uuid': str(i)} for i in range(4)]})
        self.assertEqual(environment['CUBLAS_WORKSPACE_CONFIG'], ':4096:8')
        self.assertEqual(environment['CUDA_VISIBLE_DEVICES'], '0,1,2,3')
        with self.assertRaisesRegex(ValueError, 'four distinct'):
            worker_environment({'gpus': [{'uuid': 'same'}] * 4})

    def test_valid_receipt_preserves_original_and_exact_bootstrap(self):
        originals = {name: sha(self.root / name) for name in ('clock.json', 'manifest.json', 'verification/cpu.json')}
        self.assertEqual(self.validate(), self.receipt)
        payload = {'manifest_sha256': self.receipt['original_manifest_sha256'], 'state': {'phase': 'preflight'}}
        pointer = {'path': str(self.root / self.bootstrap['path']), 'sha256': self.bootstrap['sha256']}
        recovery.checkpoint_compatible(self.root, pointer, payload)
        self.assertEqual(originals, {name: sha(self.root / name) for name in originals})
        payload['recovery_sha256'] = sha(self.root / 'recovery.json')
        recovery.checkpoint_compatible(self.root, pointer, payload)
        self.assertIn(self.root / 'recovery.json', recovery.evidence_paths(self.root, self.receipt))

    def test_unallowlisted_source_change_is_rejected(self):
        name = 'integration/pokechamp/abyssal_rl_next/trainer.py'
        self.new[name] = 'a different optimizer'
        self.receipt['changes'][name] = {'before': self.old[name], 'after': self.new[name]}
        self.commit()
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            self.validate()

    def test_changed_clock_or_tolerances_are_rejected(self):
        bad = dict(self.clock, deadline_at=86501)
        atomic(self.root / 'clock.json', bad)
        with self.assertRaisesRegex(ValueError, 'original artifact'):
            self.validate()
        atomic(self.root / 'clock.json', self.clock)
        manifest = read(self.root / 'manifest.json')
        manifest['protocol']['numeric_tolerances']['gradient_atol'] = 1.0
        atomic(self.root / 'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'protocol'):
            self.validate()

    def test_cpu_log_tamper_is_rejected_before_resume(self):
        atomic(self.root / 'recoveries/deterministic-v2/verification/suite.log', b'changed')
        with self.assertRaisesRegex(ValueError, 'CPU test log'):
            self.validate()

    def test_cpu_source_and_independent_proof_must_match(self):
        cpu = read(self.root / self.receipt['cpu']['path'])
        cpu['source'] = self.old
        atomic(self.root / self.receipt['cpu']['path'], cpu)
        self.receipt['cpu'] = self.ref(self.receipt['cpu']['path'])
        self.commit()
        with self.assertRaisesRegex(ValueError, 'CPU evidence'):
            self.validate()

    def test_failing_or_missing_proof_cannot_authorize_recovery(self):
        proof = read(self.root / 'diagnostics/proof.json')
        proof['passed'] = False
        atomic(self.root / 'diagnostics/proof.json', proof)
        self.receipt['proof'] = self.ref('diagnostics/proof.json')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'proof did not pass'):
            self.validate()
        (self.root / 'diagnostics/proof.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            self.validate()

    def test_rank_cannot_claim_pass_using_widened_tolerance(self):
        path = 'diagnostics/probe/report-rank-0.json'
        report = read(self.root / path)
        report['tolerances']['gradient_atol'] = .1
        atomic(self.root / path, report)
        proof = read(self.root / 'diagnostics/proof.json')
        proof['independent_reports'][0] = self.ref(path)
        atomic(self.root / 'diagnostics/proof.json', proof)
        self.receipt['proof'] = self.ref('diagnostics/proof.json')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'rank failed'):
            self.validate()

    def test_other_untagged_checkpoint_cannot_cross_boundary(self):
        payload = {'manifest_sha256': self.receipt['original_manifest_sha256'], 'state': {'phase': 'preflight'}}
        pointer = {'path': str(self.root / self.bootstrap['path']), 'sha256': 'another hash'}
        with self.assertRaisesRegex(ValueError, 'exact original'):
            recovery.checkpoint_compatible(self.root, pointer, payload)

    def test_all_diagnostic_reservations_are_required_and_accounted(self):
        self.assertAlmostEqual(recovery.resource_accounting(self.root)['diagnostic_gpu_hours'], 12/3600)
        self.receipt['diagnostic_resources'].pop()
        self.commit()
        with self.assertRaisesRegex(ValueError, 'all independent'):
            self.validate()

    def test_recovery_source_copy_and_original_evidence_are_protected(self):
        atomic(self.root / 'source/integration/pokechamp/abyssal_rl_next/model.py', b'changed original')
        with self.assertRaisesRegex(ValueError, 'original source'):
            self.validate()


if __name__ == '__main__':
    unittest.main()
