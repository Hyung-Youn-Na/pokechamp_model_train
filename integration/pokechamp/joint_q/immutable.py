"""Read-only lookup sharing; battle, policy and RNG state stay independent."""
from __future__ import annotations
from functools import lru_cache
import pickle
from poke_env.data.gen_data import GenData


def denied(*_args, **_kwargs):
    raise TypeError('frozen EX-065 lookup cannot be mutated')


class FrozenDict(dict):
    __slots__ = ('_joint_blob_id',)
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = denied

    def __deepcopy__(self, memo):
        return self

    def __reduce_ex__(self, protocol):
        return (FrozenDict, (dict(self),))


class FrozenList(list):
    __slots__ = ('_joint_blob_id',)
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = denied

    def __deepcopy__(self, memo):
        return self

    def __reduce_ex__(self, protocol):
        return (FrozenList, (list(self),))


class FrozenGenData(GenData):
    __slots__ = ('_joint_blob_id',)
    __setattr__ = __delattr__ = denied


def freeze(value, memo=None):
    memo = {} if memo is None else memo
    if id(value) in memo:
        return memo[id(value)]
    if isinstance(value, dict):
        result = FrozenDict({k: freeze(v, memo) for k, v in value.items()})
    elif isinstance(value, list):
        result = FrozenList([freeze(v, memo) for v in value])
    elif isinstance(value, tuple):
        result = tuple(freeze(v, memo) for v in value)
    elif isinstance(value, set):
        result = frozenset(freeze(v, memo) for v in value)
    elif isinstance(value, GenData):
        result = object.__new__(FrozenGenData)
        for name in GenData.__slots__:
            object.__setattr__(result, name, freeze(getattr(value, name), memo))
    else:
        return value
    memo[id(value)] = result
    return result


@lru_cache(maxsize=24)
def lookup(directory, identity):
    from .engine import _blob
    value = freeze(pickle.loads(_blob(directory, identity)))
    object.__setattr__(value, '_joint_blob_id', identity)
    return value
