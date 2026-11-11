"""`laya_v10.serve_v10` with the EX-167 model name added (same v10 render, budget and Policy10).

    python -m integration.laya_ladder.serve --checkpoint DIR --model laya-v10rt --ready-file F [--device cuda|cpu]

`MODEL` is imported by the battle workers (pokechamp env, no laya), so serve_v10 is imported only when serving.
"""
MODEL = 'laya-v10rt'

if __name__ == '__main__':
    from integration.laya_v10 import serve_v10
    serve_v10.MODELS = serve_v10.MODELS + (MODEL,)
    serve_v10.main()
