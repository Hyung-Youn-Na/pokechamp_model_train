"""EX-071 정책을 재사용하고 EX-075의 새 head/난수 identity를 적용한다."""
import os
import random
import torch

from ..imitation.model import seed_all
from ..selfplay.model import (SelfPlayPolicy, make_wdl_head, encode_input,
                              EncodedChoice, Scores, MODEL_CONFIG)
from .config import SEED, INITIAL
from . import distributed as collective


class Policy(SelfPlayPolicy):
    def __init__(self, device="cuda:0", checkpoint=INITIAL, tokenizer=None):
        requested = torch.device(device)
        if requested.type == "cuda":
            # EP-120: preserve the original numerical gate and make backward
            # repeatable. The supervisor sets this before starting CUDA workers.
            if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
                raise ValueError("EX-075 requires its verified deterministic cuBLAS workspace")
            torch.use_deterministic_algorithms(True)
            torch.backends.cudnn.deterministic = True
            assigned = requested.index if requested.index is not None else torch.cuda.current_device()
            if collective.world_size() == 4 and assigned != collective.rank():
                raise ValueError("policy device differs from the assigned GPU rank")
            torch.cuda.set_device(assigned)
        super().__init__(device=device, checkpoint=checkpoint, tokenizer=tokenizer)
        # The inherited EX-071 loader verifies its original seed/weights first.
        # Only the new WDL readout and experiment RNG start a fresh identity.
        seed_all(SEED)
        self.wdl_head = make_wdl_head(self.policy.head.q.in_features, device=device)
        self.sampling_generator = random.Random(SEED)
        self.assert_precision()
