"""CPU-only full-input token checks in the existing pinned model environment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import formatter, model_spec, read_json


class TokenGuard:
    def __init__(self, model):
        from transformers import AutoTokenizer, AutoProcessor
        self.spec = model_spec(model)
        self.formatter = formatter(model)
        loader = AutoProcessor if model == 'jev-omni' else AutoTokenizer
        self.tokenizer = loader.from_pretrained(self.spec['tokenizer_dir'],
            local_files_only=True, trust_remote_code=False)

    def __call__(self, payload):
        if len(payload['questions']['action']['criteria']) == 1:
            return dict(input_tokens=None, automatic=True, truncated=False)
        formatted = self.formatter.format_request(payload)
        encoded = self.formatter.tokenize_request(self.tokenizer, formatted,
                                                  max_tokens=self.spec['input_tokens'])
        result = dict(input_tokens=len(encoded['input_ids']), candidate_ids=list(formatted.candidate_ids),
            prompt_sha256=formatted.prompt_sha256, format_version=self.formatter.FORMAT_VERSION,
            model=self.spec['model_id'], revision=self.spec['revision'], truncated=False)
        if 'thinking_input_ids' in encoded:
            result['thinking_input_tokens'] = len(encoded['thinking_input_ids'])
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, choices=('jev9b', 'jev27b', 'minicpm5-jev', 'jev35b-nvfp4', 'jev-omni', 'tacit9b', 'tacit9b-vllm'))
    parser.add_argument('--requests', required=True, type=Path)
    args = parser.parse_args(argv)
    values = read_json(args.requests)
    if not isinstance(values, list):
        values = [values]
    guard = TokenGuard(args.model)
    print(json.dumps(dict(model=args.model, results=[guard(v) for v in values],
                          gpu_inferences=0, api_requests=0), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
