"""EX-193 serving: `integration.foulplay.serve_v11` with the v12 input (EX-192).

    python -m integration.laya_v12.serve_v12 --checkpoint DIR --model laya-v11rtc --ready-file F [--device cpu]

Same steps as `serve_v11` (no usage extension, no guard, argmax by the bot), with `render_v12.install()` (v11 + the
foul-play in-battle inferences) in place of `render_v11.install()`. The ready file / health record keeps the
`v11_render` key the foul-play runner checks and adds `v12_render` (version, sets sha, code hashes).
The model name stays `laya-v11rtc` (the runner's battle workers read `serve_v11.MODELS`); the checkpoint and its
sha256 in the run identity tell the models apart.
"""
from integration.foulplay.serve_v11 import MODELS

if __name__ == '__main__':
    from integration.laya_v10 import serve_v10
    from integration.laya_v11 import render_v11
    from integration.laya_v12 import render_v12
    serve_v10.MODELS = serve_v10.MODELS + tuple(m for m in MODELS if m not in serve_v10.MODELS)
    render_v12.install()
    v12 = render_v12.version()
    record = dict(version=render_v12.VERSION, judge=render_v11.judge_identity(), code=v12['v12']['code'],
                  v11_code=v12.get('v11_code'))
    print('[serve] v12 input: %s' % render_v12.VERSION, flush=True)
    create_server = serve_v10.create_server

    def create_server_with_v12(*args, **kwargs):
        server = create_server(*args, **kwargs)
        server.model_identity.update(v11_render=record, v12_render=v12['v12'])
        return server
    serve_v10.create_server = create_server_with_v12
    serve_v10.main()
