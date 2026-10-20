"""Pinned EX-105 external serving identity and CPU frontend profile."""
from pathlib import Path
from integration.tacit9b.config import MODEL_DIR, MODEL_ID, REVISION, PYTHON

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep164'
ENDPOINT = 'http://127.0.0.1:18847/v1'
SERVED_MODEL = 'tacit9b'
MAX_CONTEXT = 49152
HTTP_LIMIT = 768


def model_spec():
    return dict(name='tacit9b-vllm', model_id=MODEL_ID, revision=REVISION,
        runtime_name='planner-ex105', model_runtime_name='ex105', provenance_experiment='EX-105',
        model_dir=str(MODEL_DIR), tokenizer_dir=str(MODEL_DIR), evidence_dir=str(EVIDENCE),
        python=str(PYTHON), formatter_module='integration.tacit9b_vllm.formatting',
        physical_gpus=[1], layers=[], input_tokens=32768, max_options=16,
        allocator_bytes=None, gpu_bytes=44 * 1024**3, host_bytes=32 * 1024**3,
        disk_bytes=None, external_server=True, external_endpoint=ENDPOINT,
        external_served_model=SERVED_MODEL, external_http_limit=HTTP_LIMIT,
        thinking_mode='always', cot_max_tokens=8192, temperature=0.6, top_p=0.95, top_k=20)
