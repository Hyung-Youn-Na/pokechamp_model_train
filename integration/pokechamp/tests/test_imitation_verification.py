"""Reject altered data, qualification receipts and executed CPU dependencies."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integration.pokechamp.imitation.storage import atomic, sha
from integration.pokechamp.imitation import verification as v


class QualificationIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'run'
        source = self.root / 'sim/validator.js'
        atomic(source, b'validated-runtime')
        atomic(self.out / 'environment/source/sim/validator.js', source.read_bytes())
        atomic(self.out / 'environment/manifest.json', {'identity': {'files': {'sim/validator.js': sha(source)}}})
        atomic(self.out / 'audit.json', {'passed': True})
        atomic(self.out / 'prepared/manifest.json', {'data': 'frozen'})
        atomic(self.out / 'diagnostics/cpu.json', {'passed': True})
        atomic(self.out / 'audit-gate.json', dict(passed=True,
            audit_sha256=sha(self.out / 'audit.json'),
            prepared_manifest_sha256=sha(self.out / 'prepared/manifest.json'),
            environment_sha256=sha(self.out / 'environment/manifest.json'),
            qualification={'diagnostics/cpu.json': sha(self.out / 'diagnostics/cpu.json')}))
        self.root_patch = patch.object(v.c, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.qualification_patch = patch.object(v, 'qualification', return_value={
            'diagnostics/cpu.json': sha(self.out / 'diagnostics/cpu.json')})
        self.qualification_patch.start()
        self.addCleanup(self.qualification_patch.stop)

    def test_intact_gate_passes(self):
        self.assertTrue(v.verify_gate(self.out)['passed'])

    def test_changed_prepared_population_is_rejected(self):
        atomic(self.out / 'prepared/manifest.json', {'data': 'changed'})
        with self.assertRaisesRegex(ValueError, 'audited artifact changed'):
            v.verify_gate(self.out)

    def test_changed_runtime_is_rejected(self):
        atomic(self.root / 'sim/validator.js', b'changed')
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            v.verify_gate(self.out)

    def test_changed_preserved_runtime_is_rejected(self):
        atomic(self.out / 'environment/source/sim/validator.js', b'changed')
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            v.verify_gate(self.out)

    def test_changed_regression_evidence_is_rejected(self):
        atomic(self.out / 'diagnostics/cpu.json', {'passed': False})
        with self.assertRaisesRegex(ValueError, 'qualification changed'):
            v.verify_gate(self.out)


if __name__ == '__main__':
    unittest.main()
