import json
import os
from unittest.mock import patch,MagicMock
import pytest
from . import core,resource


def test_isolated_profile():
    assert core.EXPERIMENT=='EX-114' and core.MODEL=='jevk5-ruleqa'
    assert core.GPU_INDEX==2 and core.PORT==8109 and core.SERVER_PORT==18849
    assert core.MAX_CONTEXT==32768 and core.TEMPERATURE==1.4125375446227548
    assert core.RUN.name=='EX-114' and core.ADAPTER.parent.name=='EX-113'
    assert str(core.ADAPTER) not in str(core.RUN)


def test_gpu_stage_rejects_foreign_controller(tmp_path):
    (tmp_path/'owned-server.json').write_text(json.dumps(dict(controller_pid=-1,pid=1)))
    with patch.object(resource,'RUN',tmp_path),pytest.raises(RuntimeError,match='owning pipeline'):
        with resource.borrowed_gpu(tmp_path):pass


def test_gpu_stage_keeps_outer_lock(tmp_path):
    (tmp_path/'owned-server.json').write_text(json.dumps(dict(controller_pid=os.getpid(),pid=1234,ticks='same')))
    with patch.object(resource,'RUN',tmp_path),patch.object(resource.psutil,'pid_exists',return_value=True),patch.object(resource,'ticks',return_value='same'):
        with resource.borrowed_gpu(tmp_path):pass
    assert json.loads((tmp_path/'gpu-borrow-release.json').read_text())['outer_lock_held_until_server_cleanup']


def test_cleanup_targets_only_owned_process_group(tmp_path):
    server=resource.OwnedServer();server.process=MagicMock(pid=1234)
    server.process.poll.side_effect=[None,0]
    with patch.object(resource,'RUN',tmp_path),patch.object(resource.os,'killpg') as kill,patch.object(resource,'gpu_facts',return_value={2:dict(memory_used_mib=0)}):
        server.__exit__(None,None,None)
        kill.assert_called_once_with(1234,resource.signal.SIGTERM)
    assert json.loads((tmp_path/'owned-server-cleanup.json').read_text())['gpu_released']
