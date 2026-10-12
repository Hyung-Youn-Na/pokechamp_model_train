"""EP-056's two approved, unrepeated local matches; no experiment registration."""

VERSION = "ep056-team-swap-v1"
LIMIT = 600


def schedule():
    result = []
    for swap in (0, 1):
        teams = ["6", "12"] if not swap else ["12", "6"]
        policies = ["seeded_random", "llm_lead"] if not swap else ["llm_lead", "seeded_random"]
        result.append(dict(
            slot_id="ep056-s" + str(swap), paired_slot_id="ep056", block_id="local",
            repetition=1, swap=swap, methods=["io", "io"], pair=["io", "io"],
            actor_conditions=["B", "B"], actor_settings=[dict(team_preview_policy=p) for p in policies],
            teams=teams, battle_seed="18280,52471,51036,2470",
            actor_seeds=[2462494423, 2416696055] if not swap else [2416696055, 2462494423],
            actor_delivery=["B", "B2"] if not swap else ["B2", "B"],
            submission_order=swap + 1,
        ))
    return result
