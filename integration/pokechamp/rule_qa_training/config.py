from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STORE = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
DATA = STORE / 'datasets/generated/showdown-ruleqa/v1'
OUTPUT = STORE / 'runs/model-training/EX-107'
MODEL = ROOT / '.pokechamp-data/tacit9b-runtime/model'
PYTHON = '/ref/kev/.venv/bin/python'
CONFIG = dict(experiment='EX-107', model='morriszjm/Tacit-9B',
              revision='884838f1698d1fd746625b3c20c8ec2be077a183',
              seed=20261019, epochs=3, steps=576, steps_per_epoch=192,
              accumulation=8, world_size=3, batch_size=1, max_length=5120,
              learning_rate=1e-4, betas=[0.9, 0.95], weight_decay=0.01,
              warmup=18, clip=1.0, r=16, alpha=32, dropout=0.05,
              trainable_parameters=43278336, max_new_tokens=192,
              physical_gpus=[1, 2, 3], memory_limit_bytes=44*1024**3,
              packages={'torch': '2.8.0+cu128', 'transformers': '5.17.0', 'peft': '0.21.0'})
