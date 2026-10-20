"""Explicit package and single-GPU serving identity; no fallback profiles."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.pokechamp-data/jev-omni-runtime'
MODEL_DIR = RUNTIME / 'model'
PYTHON = RUNTIME / '.venv/bin/python'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep162'
MODEL_ID = 'akhilaaa3/Jev-Omni'
REVISION = 'fee89b076e2263bfa8bce8d34142caa4ca733a48'
def model_spec():
    return dict(name='jev-omni', model_id=MODEL_ID, revision=REVISION,
        runtime_name='planner-ex103', model_runtime_name='ex103', provenance_experiment='EX-103',
        model_dir=str(MODEL_DIR), tokenizer_dir=str(MODEL_DIR), evidence_dir=str(EVIDENCE),
        python=str(PYTHON), formatter_module='integration.jev_omni.formatting',
        physical_gpus=[0], layers=[], input_tokens=32768, max_options=16,
        allocator_bytes=40 * 1024**3, gpu_bytes=44 * 1024**3, host_bytes=32 * 1024**3,
        disk_bytes=None)


