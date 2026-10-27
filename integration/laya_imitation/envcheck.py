"""EP-207 environment check on GPU0: CUDA math/backward and pinned-checkpoint inference.

Run with the laya 0.4.13 interpreter: `python -m integration.laya_imitation.envcheck <out.json>`.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
import time

from . import config as c
from .resources import gpu0


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main(out):
    with gpu0() as (env, device):
        os.environ.update(env)
        import torch
        import laya
        result = dict(device=device, laya=laya.__version__, torch=torch.__version__,
                      cuda=torch.version.cuda, visible=torch.cuda.device_count())
        x = torch.randn(1024, 1024, device='cuda', requires_grad=True)
        loss = (x @ x.T).square().mean()
        loss.backward()
        torch.cuda.synchronize()
        result['backward_grad_finite'] = bool(torch.isfinite(x.grad).all())
        expected = dict(line.split()[::-1] for line in (c.MODEL_DIR / 'checksums.sha256').read_text().splitlines())
        result['model_files_match'] = all(sha(c.MODEL_DIR / name) == digest for name, digest in expected.items())
        started = time.perf_counter()
        agent = laya.load(str(c.MODEL_DIR), device='cuda')
        result['load_seconds'] = round(time.perf_counter() - started, 3)
        q = {'action': {'type': 'choice', 'instructions': 'Which department should handle this?',
                        'criteria': {'billing': 'invoices, payments, refunds', 'technical': 'bugs, outages'}}}
        answer = agent.predict('We were billed twice for March, please refund.', q)['answers']['action']
        result['smoke_choice'] = answer['choice']
        result['parameters'] = sum(p.numel() for p in agent.model.parameters())
        result['max_len'] = agent.cfg.get('max_len')
        result['peak_allocated_gib'] = round(torch.cuda.max_memory_allocated() / 2**30, 3)
    with open(out, 'w') as f:
        json.dump(result, f, indent=1)
    print(json.dumps(result))
    return 0 if result['backward_grad_finite'] and result['model_files_match'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
