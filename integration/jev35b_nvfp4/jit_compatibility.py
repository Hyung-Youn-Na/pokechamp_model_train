"""Actual compiler/driver compatibility for the engine's Triton CUDA path."""
import triton
import triton.language as tl


@triton.jit
def _increment(source, destination, block: tl.constexpr):
    offsets = tl.arange(0, block)
    tl.store(destination + offsets, tl.load(source + offsets) + 1)


def check_jit():
    import torch
    source = torch.ones(128, device='cuda', dtype=torch.bfloat16)
    destination = torch.empty_like(source)
    _increment[(1,)](source, destination, block=128)
    torch.cuda.synchronize()
    if not torch.equal(destination, source + 1):
        raise RuntimeError('Triton CUDA kernel returned incorrect BF16 values')
    return dict(passed=True, triton_version=triton.__version__, elements=128)
