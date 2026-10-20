from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
STORE = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
DATA = STORE/'datasets/generated/showdown-ruleqa/v1'
OUTPUT = STORE/'runs/model-training/EX-113'
REVISION = 'd6521a18a86999190e9d775c915af3d6d6772fc4'
MODEL = Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots')/REVISION
PYTHON = '/ref/kev/.venv/bin/python'
TARGETS = ['q_proj','k_proj','v_proj','o_proj','in_proj_qkvz','in_proj_ba',
           'in_proj_qkv','in_proj_z','in_proj_b','in_proj_a','out_proj']
CONFIG = dict(experiment='EX-113',model='alibiserikbay/JevK5-9B',revision=REVISION,
 seed=20261020,epochs=3,steps=192,steps_per_epoch=64,accumulation=8,world_size=3,
 batch_size=1,max_length=6144,learning_rate=3e-5,betas=[0.9,0.999],eps=1e-8,
 weight_decay=0.,warmup=6,clip=1.,r=16,alpha=32,dropout=.05,targets=TARGETS,
 trainable_parameters=18112512,physical_gpus=[1,2,3],memory_limit_bytes=44*1024**3,
 host_limit_bytes=64*1024**3,
 packages={'torch':'2.8.0+cu128','transformers':'5.17.0','peft':'0.21.0'})
