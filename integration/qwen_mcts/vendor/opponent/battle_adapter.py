"""Actor-local compatibility for the pinned Showdown identity parser."""

import re


class BattleEnvironmentError(RuntimeError):
    category = "environment"


def identity(identifier):
    match = re.fullmatch(r"(p[12])[a-z]?: (.+)", identifier)
    if not match:
        raise BattleEnvironmentError(f"invalid Pokemon identifier: {identifier!r}")
    return match[1], f"{match[1]}: {match[2]}"


def exact_get_pokemon(
    self,
    identifier,
    force_self_team=False,
    details="",
    request=None,
    force_opp_team=False,
):
    from poke_env.data import to_id_str
    from poke_env.environment.pokemon import Pokemon

    side, key = identity(identifier)
    mine = side == self._player_role
    if (force_self_team and not mine) or (force_opp_team and mine):
        raise BattleEnvironmentError("identifier side conflicts with requested team")
    team = self._team if mine else self._opponent_team
    if key in team:
        return team[key]
    details = (request or {}).get("details", details)
    species = to_id_str(details.split(",")[0]) if details else None
    # Only a preview placeholder may acquire a new nickname. Never alias another
    # observed nickname or cross the side boundary.
    candidates = []
    if species:
        if mine:
            candidates = [
                (k, p)
                for k, p in team.items()
                if p.species == species
                and k.removesuffix("-*") == f"{side}: {details.split(',')[0]}"
            ]
        else:
            bound = {id(p) for p in team.values()}
            candidates = [
                (None, p)
                for p in self._teampreview_opponent_team
                if p.species == species and id(p) not in bound
            ]
    if len(candidates) > 1:
        raise BattleEnvironmentError(f"ambiguous preview identity: {key} / {details}")
    if candidates:
        old, pokemon = candidates[0]
        if old is not None:
            del team[old]
    else:
        limit = (self._team_size or {}).get(side, 6)
        if len(team) >= limit:
            raise BattleEnvironmentError(
                f"unresolved identity in full team: {key} / {details}"
            )
        pokemon = (
            Pokemon(details=details, gen=self._data.gen, battle_format=self._format)
            if details
            else Pokemon(
                species=key[4:], gen=self._data.gen, battle_format=self._format
            )
        )
    team[key] = pokemon
    if request:
        pokemon.update_from_request(request)
    return pokemon


def update_team_from_request(self, side):
    if not getattr(self, "_benchmark_request_bound", False):
        from poke_env.data import to_id_str
        from poke_env.environment.pokemon import Pokemon

        preview = list(self._team.items())
        mapped = {}
        used = set()
        for request in side["pokemon"]:
            role, key = identity(request["ident"])
            if role != self._player_role or key in mapped:
                raise BattleEnvironmentError("ambiguous request identifiers")
            species = to_id_str(request["details"].split(",")[0])
            matches = [
                p for _, p in preview if p.species == species and id(p) not in used
            ]
            if len(matches) != 1 and preview:
                raise BattleEnvironmentError(
                    f"ambiguous request details: {request['details']}"
                )
            pokemon = (
                matches[0]
                if matches
                else Pokemon(
                    request_pokemon=request,
                    gen=self._data.gen,
                    battle_format=self._format,
                )
            )
            used.add(id(pokemon))
            mapped[key] = pokemon
        if preview and len(used) != len(preview):
            raise BattleEnvironmentError("request does not cover preview team")
        self._team = mapped
        self._benchmark_request_bound = True
    for request in side["pokemon"]:
        _, key = identity(request["ident"])
        if key not in self._team:
            raise BattleEnvironmentError("request changed bound identity")
        self._team[key].update_from_request(request)


def install_identity_adapter():
    """Call only inside an isolated benchmark actor (including local validation)."""
    from poke_env.environment.abstract_battle import AbstractBattle

    AbstractBattle.get_pokemon = exact_get_pokemon
    AbstractBattle._update_team_from_request = update_team_from_request


def guard_parser(player):
    original = player.ps_client._handle_battle_message
    player.benchmark_environment_error = None

    async def guarded(messages):
        try:
            return await original(messages)
        except Exception as error:
            # Model/algorithm failures already have their own terminal channel.
            if getattr(error, "category", None) not in (None, "environment"):
                raise
            player.benchmark_environment_error = BattleEnvironmentError(
                f"{type(error).__name__}: {error}"
            )
            raise player.benchmark_environment_error from error

    player.ps_client._handle_battle_message = guarded
