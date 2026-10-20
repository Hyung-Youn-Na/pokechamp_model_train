"""외부 서버에 신호·GPU 소유권을 보내지 않는 CPU 모의 수명/감시 검사."""
import asyncio
import json
from pathlib import Path
import signal
from types import SimpleNamespace

import pytest

from integration.jev_planner import external_runtime as external, runtime, server


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(external, 'ROOT', tmp_path)
    monkeypatch.setattr(external, 'start_ticks', lambda pid: str(pid))
    monkeypatch.setattr(external, 'verify_identity', lambda receipt, **kw: True)
    monkeypatch.setattr(external.os, 'getpid', lambda: 100)
    receipt = dict(server_pid=200, engine_pid=201, gpu_uuid='gpu1')
    return external.ExternalMonitor(tmp_path, receipt, budget_root=tmp_path / 'run')


def test_sample_unions_owned_and_external_trees_and_checks_gpu1(isolated, monkeypatch):
    import psutil
    from integration.jev27b import resource
    class Process:
        def __init__(self,pid): self.pid=pid
        def children(self,recursive):
            return [Process(101),Process(201)] if self.pid==100 else [Process(201)]
        def memory_info(self):return SimpleNamespace(rss=self.pid)
    monkeypatch.setattr(psutil,'Process',Process)
    monkeypatch.setattr(resource,'gpu_facts',lambda: {0:dict(uuid='untouched',memory_used_mib=999999),
        1:dict(uuid='gpu1',memory_used_mib=44*1024)})
    row=isolated.sample('begin')
    assert row['rss_bytes']==100+101+200+201  # Shared member never counted twice.
    assert row['gpu']['uuid']=='gpu1' and row['errors']==[]
    assert len(row['members'])==4
    monkeypatch.setattr(resource,'gpu_facts',lambda: {1:dict(uuid='gpu1',memory_used_mib=44*1024+1)})
    with pytest.raises(RuntimeError,match='gpu1_memory_exceeded'):isolated.sample('poll')
    recorded=[json.loads(l) for l in (isolated.directory/'external-resources.jsonl').read_text().splitlines()]
    assert recorded[-1]['errors']==['gpu1_memory_exceeded']


def test_host_32gib_limit_includes_external_server(isolated,monkeypatch):
    import psutil
    from integration.jev27b import resource
    class Process:
        def __init__(self,pid):self.pid=pid
        def children(self,recursive):return []
        def memory_info(self):return SimpleNamespace(rss=32*1024**3 if self.pid==200 else 1)
    monkeypatch.setattr(psutil,'Process',Process)
    monkeypatch.setattr(resource,'gpu_facts',lambda:{1:dict(uuid='gpu1',memory_used_mib=100)})
    with pytest.raises(RuntimeError,match='host_memory_exceeded'):isolated.sample('poll')


@pytest.mark.parametrize('owner_reused',[False,True])
def test_limit_failure_signals_only_original_controller(isolated,monkeypatch,owner_reused):
    signals=[]
    monkeypatch.setattr(external.os,'kill',lambda pid,sig:signals.append((pid,sig)))
    monkeypatch.setattr(isolated.stop,'wait',lambda _seconds:False)
    monkeypatch.setattr(isolated,'sample',lambda phase:(_ for _ in ()).throw(RuntimeError('limit')))
    if owner_reused:monkeypatch.setattr(external,'start_ticks',lambda pid:'changed')
    isolated._watch()
    assert signals==([] if owner_reused else [(100,signal.SIGTERM)])
    assert all(pid not in (200,201) for pid,_ in signals)
    assert json.loads((isolated.directory/'external-resource-stop.json').read_text())['type']=='RuntimeError'


def test_monitor_begin_before_thread_and_end_after_join(isolated,monkeypatch):
    calls=[]
    class Thread:
        def __init__(self,**kw):calls.append('thread-created')
        def start(self):calls.append('thread-start')
        def join(self,timeout):calls.append('thread-join')
        def is_alive(self):return False
    monkeypatch.setattr(external.threading,'Thread',Thread)
    monkeypatch.setattr(isolated,'sample',lambda phase:calls.append(phase))
    with isolated:calls.append('owned-front-lifetime')
    assert calls==['begin','thread-created','thread-start','owned-front-lifetime','thread-join','end']


def test_identity_ignores_response_time_but_rejects_server_model_change(monkeypatch):
    # Real verify_identity, mocked /proc and GET /models; no endpoint connection.
    verify=external.verify_identity
    monkeypatch.setattr(external,'start_ticks',lambda pid:str(pid))
    monkeypatch.setattr(Path,'read_bytes',lambda self:b'python\0vllm\0')
    receipt=dict(server_pid=200,server_start_ticks='200',engine_pid=201,engine_start_ticks='201',
        server_command=['python','vllm'],models_response=[dict(id='tacit9b',root='/model',max_model_len=49152)])
    monkeypatch.setattr(external,'get_models',lambda:dict(data=[dict(receipt['models_response'][0],created=1)]))
    assert verify(receipt)
    monkeypatch.setattr(external,'get_models',lambda:dict(data=[dict(receipt['models_response'][0],id='different')]))
    with pytest.raises(ValueError,match='endpoint identity'):verify(receipt)
    monkeypatch.setattr(external,'start_ticks',lambda pid:'reused')
    with pytest.raises(ValueError,match='process identity'):verify(receipt,health=False)


def test_runtime_close_reaps_front_before_monitor_end_and_preserves_external(tmp_path,monkeypatch):
    from integration.jev27b import execute,resource
    calls=[]
    monkeypatch.setattr(runtime,'validate_resources',lambda cfg:dict(external_server=True,runtime_name='external'))
    owned=runtime.OwnedRuntime(tmp_path,{})
    owned.directory.mkdir();owned.created=True
    owned.process=SimpleNamespace(pid=101,returncode=0)
    async def close_executor():calls.append('executor-close')
    owned.executor=SimpleNamespace(close=close_executor)
    owned.monitor=SimpleNamespace(__exit__=lambda *args:calls.append('monitor-end'))
    monkeypatch.setattr(execute,'stop_owned_process',lambda proc:calls.append(('front-stop',proc.pid)))
    monkeypatch.setattr(resource,'wait_owned_gpu_release',lambda *a,**kw:pytest.fail('external GPU release forbidden'))
    receipt=dict(server_pid=200,engine_pid=201)
    (owned.directory/'external-identity.json').write_text(json.dumps(receipt))
    monkeypatch.setattr(external,'verify_identity',lambda value:calls.append(('external-health',value['server_pid'])))
    asyncio.run(owned.close())
    assert calls==['executor-close',('front-stop',101),'monitor-end',('external-health',200)]
    assert json.loads((owned.directory/'external-preserved.json').read_text())['passed']


def test_external_front_never_acquires_gpu_and_only_closes_adapter(tmp_path,monkeypatch):
    from integration.jev27b import resource,server as local_server
    from integration.jev_planner import config
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps(dict(executor=dict(model='tacit9b-vllm'))))
    monkeypatch.setattr(config,'validate_mode',lambda *a:None)
    monkeypatch.setattr(server,'validate_resources',lambda c:dict(external_server=True,model_dir=str(tmp_path/'model'),
        model_id='Tacit',revision='pin',runtime_name='external'))
    monkeypatch.setattr(resource,'own_gpus',lambda *a,**kw:pytest.fail('external GPU acquire forbidden'))
    monkeypatch.setattr(server.signal,'signal',lambda *a:None)
    monkeypatch.setattr(server.os.environ,'update',lambda **kw:None)
    calls=[]
    class Model:
        def load(self):calls.append('model-load');return self
        def metadata(self):return dict(loaded=True)
        def close(self):calls.append('adapter-close')
    class Service:
        def __init__(self,*a,**kw):pass
        def close(self):calls.append('service-close')
    class HTTP:
        def __init__(self,*a,**kw):pass
        def serve_forever(self,**kw):calls.append('serve')
        def server_close(self):calls.append('http-close')
    monkeypatch.setattr(server,'create_model',lambda c:Model())
    monkeypatch.setattr(local_server,'LocalService',Service)
    monkeypatch.setattr(local_server,'LocalHTTPServer',HTTP)
    server.main(['--config',str(cfg),'--directory',str(tmp_path),'--port','18845'])
    assert calls==['model-load','serve','http-close','service-close','adapter-close']
