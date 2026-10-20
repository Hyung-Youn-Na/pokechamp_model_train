"""Explicit package and single-GPU serving identity; no fallback profiles."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.pokechamp-data/tacit9b-runtime'
MODEL_DIR = RUNTIME / 'model'
PYTHON = RUNTIME / '.venv/bin/python'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep163'
MODEL_ID = 'morriszjm/Tacit-9B'
REVISION = '884838f1698d1fd746625b3c20c8ec2be077a183'
def model_spec():
    return dict(name='tacit9b', model_id=MODEL_ID, revision=REVISION,
        runtime_name='planner-ex104', model_runtime_name='ex104', provenance_experiment='EX-104',
        model_dir=str(MODEL_DIR), tokenizer_dir=str(MODEL_DIR), evidence_dir=str(EVIDENCE),
        python=str(PYTHON), formatter_module='integration.tacit9b.formatting',
        physical_gpus=[0], layers=[], input_tokens=32768, max_options=16,
        allocator_bytes=40 * 1024**3, gpu_bytes=44 * 1024**3, host_bytes=32 * 1024**3,
        disk_bytes=None, thinking_mode='always', cot_max_tokens=8192,
        temperature=0.6, top_p=0.95, top_k=20, attention='sdpa', gdn='torch-native')


