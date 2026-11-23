"""v13 serving (EP-240 / D-218): `integration.foulplay.serve_v11` with the v13 input bugfixes.

    python -m integration.laya_v13.serve_v13 --checkpoint DIR --model laya-v11rtc --ready-file F [--device cpu|cuda]

Applies `render_v13.install()` (v12 + formespec, teradefence, roostground, ivycudgel) in place of `render_v12.install()`.
The ready file / health record keeps `v11_render` and `v12_render` and adds `v13_render`.
"""
from integration.foulplay.serve_v11 import MODELS

if __name__ == '__main__':
    from integration.laya_v10 import serve_v10
    from integration.laya_v11 import render_v11
    from integration.laya_v12 import render_v12
    from integration.laya_v13 import render_v13

    serve_v10.MODELS = serve_v10.MODELS + tuple(m for m in MODELS if m not in serve_v10.MODELS)
    render_v13.install()
    v13 = render_v13.version()
    record = dict(
        version=render_v13.VERSION,
        judge=render_v11.judge_identity(),
        code=v13['v13']['code'],
        v12_code=v13['v12']['code'],
        v11_code=v13.get('v11_code'),
    )
    print('[serve] v13 input: %s' % render_v13.VERSION, flush=True)
    create_server = serve_v10.create_server

    def create_server_with_v13(*args, **kwargs):
        server = create_server(*args, **kwargs)
        server.model_identity.update(v11_render=record, v12_render=v13['v12'], v13_render=v13['v13'])
        return server

    serve_v10.create_server = create_server_with_v13
    serve_v10.main()
