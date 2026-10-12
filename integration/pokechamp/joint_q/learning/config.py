from pathlib import Path
from ..storage import ROOT

MODEL = 'Qwen/Qwen3.5-4B-Base'
REVISION = '1001bb4d826a52d1f399e183466143f4da7b741b'
RENDERER = 'pokemon-joint-q-readout-v1'
CACHE = ROOT / '.tools/eve-rlcd/worktrees/pokemon-training/.cache/huggingface/hub'
DATA = Path('/mnt/digicap/combined/hyna/backup/pokechamp')
OUTPUT = ROOT / '.pokechamp-data/experiments/ex066-joint-q-training'
CONFIG = dict(experiment='EX-066', model=MODEL, revision=REVISION, renderer=RENDERER,
              max_tokens=32768, hidden_size=2560, seed=20260930, epochs=3,
              updates_per_epoch=205, updates=615, lora_r=8, lora_alpha=16, lora_dropout=0,
              base_dtype='bfloat16', adapter_dtype='float32', head_dtype='float32',
              forward_dtype='bfloat16', readout_dtype='float32', lr=5e-5,
              betas=[.9,.95], weight_decay=0, gradient_clip=1, microbatch=1,
              accumulation=8, checkpointing=True, use_cache=False, physical_gpu=1,
              enable_thinking=False, head_std='0.01/sqrt(hidden_size)', head_bias=0,
              loss='observation_mean_candidate_mean_mse', time_limit=None,
              shuffle='python.Random(seed:kind:epoch[:observation_id]).shuffle',
              attention='sdpa', bootstrap_seed=20260930, bootstrap_replicates=10000)
EXPECTED = {'train':(50,1639,15114), 'validation':(10,320,2991), 'test':(20,709,6369)}
