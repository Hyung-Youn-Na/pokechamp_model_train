"""Runs only in the pinned poke-env interpreter; receives one actor's stream."""
import json
import sys
from contextlib import redirect_stdout


def main():
    with redirect_stdout(sys.stderr):
        from integration.qwen_mcts.vendor.opponent.actor import Actor

    actor = None
    for line in sys.stdin:
        try:
            value = json.loads(line)
            if value["op"] == "init":
                with redirect_stdout(sys.stderr):
                    actor = Actor(value["side"], value["side"], value["seed"], value["team"],
                                  policy_id="abyssal-tera-v1")
                result = {"initialized": True}
            elif value["op"] == "choose" and actor is not None:
                if set(value) != {"op", "id", "logs", "request"}:
                    raise ValueError("actor RPC rejected extra information")
                with redirect_stdout(sys.stderr):
                    actor.feed(value["logs"])
                    actor.feed(["|request|" + json.dumps(value["request"], separators=(",", ":"))])
                    result = {"command": actor.choose()}
            else:
                raise ValueError("invalid actor operation")
            print(json.dumps({"id": value["id"], "ok": True, "result": result}), flush=True)
        except Exception as error:
            print(json.dumps({"id": value.get("id"), "ok": False,
                              "error": {"message": f"{type(error).__name__}: {error}"}}), flush=True)


if __name__ == "__main__":
    main()
