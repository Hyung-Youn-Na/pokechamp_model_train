"""One actual CUDA compatibility check, using the pinned environment on GPU 0."""
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

from .config import EVIDENCE


def main():
    import torch
    from integration.jev27b.resource import own_gpus
    directory = EVIDENCE / 'compatibility'
    directory.mkdir(exist_ok=False)
    versions = {key:importlib.metadata.version(key) for key in ('torch','vllm','transformers')}
    result = dict(passed=False, versions=versions, python=platform.python_version(),
                  cuda_runtime=torch.version.cuda, started_at=time.time(),
                  model_loads=0, model_inferences=0, glm_requests=0)
    try:
        assert versions['vllm']=='0.31.0+cu129' and versions['transformers']=='5.17.0'
        assert versions['torch']=='2.13.0+cu129' and torch.version.cuda=='12.9'
        with own_gpus(directory, profile='planner-ex095', budget_root=EVIDENCE):
            # This checks device creation, BF16 operations and an actual kernel,
            # rather than deciding from the driver's version string alone.
            a=torch.ones((32,32),device='cuda',dtype=torch.bfloat16)
            b=a@a
            torch.cuda.synchronize()
            assert b[0,0].item()==32
            result.update(device=torch.cuda.get_device_name(), capability=list(torch.cuda.get_device_capability()))
            from .jit_compatibility import check_jit
            result['triton_jit'] = check_jit()
        result['passed']=True
    except BaseException as error:
        result['error']=dict(type=type(error).__name__,detail=str(error))
    finally:
        result['elapsed_seconds']=time.time()-result['started_at']
        (EVIDENCE/'compatibility.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['passed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
