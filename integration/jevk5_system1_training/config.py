from integration.jevk5_ruleqa_training.config import MODEL, REVISION, ROOT, STORE, PYTHON, TARGETS
OUTPUT = STORE / 'runs/model-training/EX-116'
CONFIG = dict(experiment='EX-116', model='alibiserikbay/JevK5-9B', revision=REVISION,
    seed=20261021, deterministic_algorithms=True, cudnn_benchmark=False, cublas_workspace_config=':4096:8', preflight_checkpoint_prefix='preflight-v2', epochs=3, steps=4068, steps_per_epoch=1356, world_size=3,
    global_batch=96, max_length=6144, microbatch_candidates=[8,4,2,1], padded_token_budget=4096,
    learning_rate=3e-5, betas=[.9,.999], eps=1e-8, weight_decay=0., warmup=123,
    clip=1., r=16, alpha=32, dropout=.05, targets=TARGETS, trainable_parameters=18112512,
    physical_gpus=[1,2,3], memory_limit_bytes=44*1024**3, host_limit_bytes=64*1024**3,
    packages={'torch':'2.8.0+cu128','transformers':'5.17.0','peft':'0.21.0'})
SOURCES = [
 ('type','gen9-type-system1-v1', ['base','extension'],64980),
 ('status','gen9-status-system1-v1',['all'],22423),
 ('priority','gen9-priority-system1-v1',['all'],10160),
 ('weather','gen9-weather-terrain-system1-v1',['all'],12178),
 ('replay','replay-ko-system1-v1',['all'],3981),
 ('conditional','conditional-ko-system1-v1',['all'],8582),
 ('role','smogon-role-system1-v1',['all'],3717),
 ('mechanics','gen9-mechanics-system1-v1',['all'],4128)]
SHARES = dict(type=.10,status=.10,priority=.10,weather=.10,replay=.05,conditional=.10,role=.05,
              mechanics1=.12,mechanics2=.10,mechanics3=.08,mechanics4=.06,mechanics5=.04)
DOMAINS = ['type_tera_ability','status_immunity_cure','priority_execution','weather_entry_residual',
           'ko_prevention_followup','information_sufficiency','conditional_ko_boundary']
