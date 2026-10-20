import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from integration.pokechamp.rule_qa_training import cli


class Child:
    pid=12345
    returncode=0
    def poll(self):return self.returncode


class LauncherTests(unittest.TestCase):
    def test_uuid_isolation_and_lock_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); facts=[dict(index=i,uuid=f'GPU-{i}',memory_bytes=0) for i in range(4)]
            facts[0]['memory_bytes']=2000000000
            with patch.object(cli,'ROOT',root),patch.object(cli,'verify_prepared'),patch.object(cli,'gpu_facts',return_value=facts),patch.object(cli,'processes',return_value=[(444,'GPU-0')]),patch.object(cli.subprocess,'Popen',return_value=Child()) as spawn:
                cli.launch('preflight',root)
                env=spawn.call_args.kwargs['env']
                self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'GPU-1,GPU-2,GPU-3')
                self.assertFalse((root/'.pokechamp-data/locks/gpu0.lock').exists())
                for i in [1,2,3]:
                    with (root/f'.pokechamp-data/locks/gpu{i}.lock').open('a+') as handle:
                        cli.fcntl.flock(handle,cli.fcntl.LOCK_EX|cli.fcntl.LOCK_NB)

    def test_busy_selected_gpu_prevents_torch_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);facts=[dict(index=i,uuid=f'GPU-{i}',memory_bytes=0) for i in range(4)]
            facts[2]['memory_bytes']=2000000000
            with patch.object(cli,'ROOT',root),patch.object(cli,'verify_prepared'),patch.object(cli,'gpu_facts',return_value=facts),patch.object(cli.subprocess,'Popen') as spawn:
                with self.assertRaises(AssertionError):cli.launch('preflight',root)
                spawn.assert_not_called()


if __name__=='__main__':unittest.main()
