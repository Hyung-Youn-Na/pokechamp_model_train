"""EX-074 synchronous collectives; SUM gradients already use global denominators."""
from datetime import timedelta
import torch
import torch.distributed as dist


def initialize(rank, world_size=4, init_method="env://", backend="nccl"):
    if world_size != 4:
        raise ValueError("EX-074 requires exactly four ranks")
    if backend == "nccl":
        torch.cuda.set_device(rank)
    elif backend != "gloo":
        raise ValueError("only NCCL production or Gloo CPU verification is supported")
    dist.init_process_group(backend, init_method=init_method, rank=rank,
                            world_size=world_size, timeout=timedelta(minutes=25))


def close():
    if dist.is_initialized():
        dist.destroy_process_group()


def rank():
    return dist.get_rank() if dist.is_initialized() else 0


def world_size():
    return dist.get_world_size() if dist.is_initialized() else 1


def device():
    return torch.device("cuda", torch.cuda.current_device()) if (dist.is_initialized()
        and dist.get_backend() == "nccl") else torch.device("cpu")


def gather(value):
    if not dist.is_initialized():
        return [value]
    values = [None] * world_size()
    dist.all_gather_object(values, value)
    return values


def assert_same(value, label="snapshot"):
    values = gather(value)
    if any(item != values[0] for item in values):
        raise ValueError("ranks disagree on " + label)


def sum_values(values):
    tensor = torch.tensor(values, dtype=torch.float64, device=device())
    if dist.is_initialized():
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
    return tensor.cpu().tolist()


def any_rank(value):
    tensor = torch.tensor(int(bool(value)), device=device())
    if dist.is_initialized():
        dist.all_reduce(tensor, op=dist.ReduceOp.MAX)
    return bool(tensor.item())


def raise_if_failed(error):
    errors = gather(None if error is None else repr(error))
    if any(item is not None for item in errors):
        raise RuntimeError("collective worker failure: " + repr(errors)) from error


def checked(function, *args, **kwargs):
    """Propagate a local operation's failure before any next collective phase."""
    error, result = None, None
    try:
        result = function(*args, **kwargs)
    except Exception as exc:
        error = exc
    raise_if_failed(error)
    return result


def sum_gradients(parameters):
    """All ranks execute identical collectives, including empty tail shards."""
    parameters = list(parameters)
    error = None
    for p in parameters:
        if p.dtype != torch.float32:
            error = ValueError("trainable parameters must be FP32")
        if p.grad is not None and not bool(torch.isfinite(p.grad).all()):
            error = FloatingPointError("nonfinite local gradient")
    raise_if_failed(error)
    present_counts = sum_values([p.grad is not None for p in parameters])
    for p, present in zip(parameters, present_counts):
        if not present:
            raise ValueError("trainable parameter has no gradient on any rank")
        if p.grad is None:
            p.grad = torch.zeros_like(p)
        if dist.is_initialized():
            dist.all_reduce(p.grad, op=dist.ReduceOp.SUM)


def local_slice(records):
    return records[rank()::world_size()]
