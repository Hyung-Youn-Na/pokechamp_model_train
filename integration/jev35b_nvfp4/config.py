"""Explicit package and single-GPU serving identity; no fallback profiles."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.pokechamp-data/jev35b-nvfp4-runtime'
MODEL_DIR = RUNTIME / 'model'
PYTHON = RUNTIME / '.venv/bin/python'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep154'
MODEL_ID = 'autotrust/JEV-35B-NVFP4'
REVISION = '10c2c62610e315e31a75baca849ad79d526e4658'
ENGINE_PORT = 18846
ENGINE_LENGTH = 32769
WHEEL = ('https://github.com/vllm-project/vllm/releases/download/v0.31.0/'
         'vllm-0.31.0%2Bcu129-cp38-abi3-manylinux_2_28_x86_64.whl')


def model_spec():
    return dict(name='jev35b-nvfp4', model_id=MODEL_ID, revision=REVISION,
        runtime_name='planner-ex095', model_runtime_name='ex095', provenance_experiment='EX-095',
        model_dir=str(MODEL_DIR), tokenizer_dir=str(MODEL_DIR), evidence_dir=str(EVIDENCE),
        python=str(PYTHON), formatter_module='integration.jev35b_nvfp4.formatting',
        physical_gpus=[0], layers=[], input_tokens=32768, max_options=16,
        allocator_bytes=40 * 1024**3, gpu_bytes=44 * 1024**3, host_bytes=32 * 1024**3,
        disk_bytes=None, engine_port=ENGINE_PORT, engine_length=ENGINE_LENGTH)


def engine_command():
    targets = ('down_proj gate_proj up_proj in_proj_qkv in_proj_z out_proj '
               'q_proj k_proj v_proj o_proj lm_head').split()
    return [str(PYTHON), '-B', str(MODEL_DIR / 'serve_decide.py'),
        '--model', str(MODEL_DIR), '--served-model-name', MODEL_ID,
        '--host', '127.0.0.1', '--port', str(ENGINE_PORT),
        '--enable-lora', '--max-lora-rank', '320',
        '--lora-modules', 'jev-decision=' + str(MODEL_DIR / 'adapter_vllm'),
        '--lora-target-modules', *targets,
        '--logprobs-mode', 'processed_logprobs', '--max-logprobs', '256',
        '--max-model-len', str(ENGINE_LENGTH), '--max-num-seqs', '1',
        '--tensor-parallel-size', '1', '--moe-backend', 'marlin',
        '--dtype', 'bfloat16', '--enforce-eager', '--gpu-memory-utilization', '0.80',
        '--enable-prefix-caching', '--mamba-cache-mode', 'align',
        '--trust-request-chat-template', '--limit-mm-per-prompt', '{"image": 0}']
