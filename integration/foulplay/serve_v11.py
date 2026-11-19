"""EX-175 / EX-176 serving: `laya_v10.serve_v10` with the v11 input (EX-171 v11rt, EX-172 v11rtc).

    python -m integration.foulplay.serve_v11 --checkpoint DIR --model laya-v11rt --ready-file F [--device cpu]

The same steps as laya-play's `integration/laya_v11/serve.py` for a v11 model, minus the parts EX-174's v10rt serving
did not have either, so the two foul-play runs differ only in model and input:
- `render_v11.install()` (fixed judge, forme names, `duel` with recovery, revealed ability) over the v10 render;
- no usage extension and no guard information: the bot plays the argmax of the served distribution, as in EX-174.
The ready file / health record `v11_render` (the v11 renderer version and its code hashes).

`MODELS` is imported by the battle workers (pokechamp env, no laya), so laya modules are imported only when serving.
"""
MODELS = ('laya-v11rt', 'laya-v11rtc')

if __name__ == '__main__':
    from integration.laya_v10 import serve_v10
    from integration.laya_v11 import render_v11
    serve_v10.MODELS = serve_v10.MODELS + tuple(m for m in MODELS if m not in serve_v10.MODELS)
    render_v11.install()
    v11 = dict(version=render_v11.VERSION, judge=render_v11.judge_identity(),
               code=render_v11.version()['v11_code'])
    print('[serve] v11 input: %s' % render_v11.VERSION, flush=True)
    create_server = serve_v10.create_server

    def create_server_with_v11(*args, **kwargs):
        server = create_server(*args, **kwargs)
        server.model_identity.update(v11_render=v11)
        return server
    serve_v10.create_server = create_server_with_v11
    serve_v10.main()
