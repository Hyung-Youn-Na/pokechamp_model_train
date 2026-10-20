"""Enforce the approved allocator budget inside vLLM's actual CUDA worker."""
import json
import os
from pathlib import Path
import threading
import time

from vllm.v1.worker.gpu_worker import Worker


class BoundedWorker(Worker):
    def init_device(self):
        import torch
        # Enforce before vLLM initializes NCCL or allocates model/KV buffers.
        torch.cuda.set_device(self.local_rank)
        properties = torch.cuda.get_device_properties(self.local_rank)
        torch.cuda.set_per_process_memory_fraction(40 * 1024**3 / properties.total_memory, self.local_rank)
        path = Path(os.environ['EX095_ALLOCATOR_DIRECTORY']) / f'allocator-{os.getpid()}.jsonl'
        def sample():
            while True:
                allocated = torch.cuda.memory_allocated(self.local_rank)
                reserved = torch.cuda.memory_reserved(self.local_rank)
                with path.open('a') as stream:
                    stream.write(json.dumps(dict(at=time.time(), pid=os.getpid(), allocated_bytes=allocated,
                                                 reserved_bytes=reserved, allocator_bytes=40 * 1024**3)) + '\n')
                if max(allocated, reserved) > 40 * 1024**3:
                    os.kill(os.getpid(), 15)
                    return
                time.sleep(.5)
        threading.Thread(target=sample, daemon=True).start()
        super().init_device()
