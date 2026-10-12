"""Joint-q observer with explicit, snapshot-stable continuation policies."""
from __future__ import annotations
import copy
import io
import logging
import pickle
from types import SimpleNamespace
from poke_env.player.baselines import AbyssalPlayer
from poke_env.ps_client.account_configuration import AccountConfiguration
from .policy import Actor as BaseActor, _ActorBattle, _CACHE_FIELDS
from .battle_adapter import update_team_from_request, identity, BattleEnvironmentError
from .storage import digest

BASE_POLICY_ID = 'abyssal'
_SNAPSHOT_VERSION = 3
_PUBLIC_POLICY_EVENTS = frozenset({
    'move', 'switch', 'drag', 'replace', 'detailschange', '-formechange',
    '-terastallize', '-ability', '-endability', '-transform',
})


def _restore_gen_data(fields):
    from poke_env.data.gen_data import GenData
    value = object.__new__(GenData)
    for name, field in fields.items():
        setattr(value, name, field)
    return value


def normalize_policy(value=None):
    """Validate the private policy descriptor, including its frozen hash."""
    if value is None:
        return dict(policy_id=BASE_POLICY_ID, config={}, config_hash=digest({}))
    if not isinstance(value, dict) or set(value) != {'policy_id', 'config', 'config_hash'}:
        raise ValueError('policy descriptor requires ID, config and config hash')
    policy_id = value['policy_id']
    config = value['config']
    if not isinstance(config, dict):
        raise ValueError('policy config must be an object')
    if policy_id == BASE_POLICY_ID:
        if config:
            raise ValueError('legacy Abyssal has no configurable policy settings')
        expected = digest(config)
    else:
        from .abyssal_tera import POLICY_ID, policy_config_hash
        if policy_id != POLICY_ID:
            raise ValueError('unknown actor policy ID')
        expected = policy_config_hash(config)
    if value['config_hash'] != expected:
        raise ValueError('actor policy config hash mismatch')
    return copy.deepcopy(value)


class JointBattle(_ActorBattle):
    def _update_team_from_request(self, side):
        if not getattr(self,'_benchmark_request_bound',False):
            from poke_env.data import to_id_str
            preview=list(self._team.values())
            # Canonical Pokemon.species intentionally maps keldeoresolute to
            # keldeo (pokemon.py). Its actual _species and public preview still
            # preserve Keldeo-Resolute. Bind by that exact raw species too.
            if any(to_id_str(r['details'].split(',')[0])=='keldeoresolute' for r in side['pokemon']):
                mapped={}
                used=set()
                for request in side['pokemon']:
                    role,key=identity(request['ident'])
                    species=to_id_str(request['details'].split(',')[0])
                    candidates=[p for p in preview if species in (p.species,p._species) and id(p) not in used]
                    if role!=self._player_role or key in mapped or len(candidates)!=1:
                        raise BattleEnvironmentError('ambiguous exact cosmetic request binding')
                    mapped[key]=candidates[0]
                    used.add(id(candidates[0]))
                if len(used)!=len(preview):
                    raise BattleEnvironmentError('cosmetic request does not cover preview')
                self._team=mapped
                self._benchmark_request_bound=True
        return update_team_from_request(self,side)


class Actor(BaseActor):
    def __init__(self,side,username,seed,team=None,*,policy_id=BASE_POLICY_ID,
                 policy_config=None,policy_config_hash=None):
        if side not in {'p1', 'p2'}:
            raise ValueError('actor side must be p1 or p2')
        if policy_id == BASE_POLICY_ID:
            config = {} if policy_config is None else policy_config
            config_hash = digest(config)
        else:
            from .abyssal_tera import POLICY_ID, DEFAULT_CONFIG, policy_config_hash as hash_config
            if policy_id != POLICY_ID:
                raise ValueError('unknown actor policy ID')
            config = DEFAULT_CONFIG.as_dict() if policy_config is None else policy_config
            config_hash = hash_config(config)
        self._policy_metadata = normalize_policy(dict(policy_id=policy_id, config=config,
            config_hash=config_hash if policy_config_hash is None else policy_config_hash))
        self.side, self.username = side, username
        self.request, self._rqid = None, 0
        self._last_decision_audit = None
        self.reseed(seed)
        player_type = self._player_type()
        extra = {} if policy_id == BASE_POLICY_ID else dict(policy_config=copy.deepcopy(config))
        with self._rng():
            # Exactly one canonical Player initialization, including its avatar
            # RNG draw; selecting a policy must not advance the stream twice.
            self.player = player_type(account_configuration=AccountConfiguration(username, None),
                battle_format='gen9ou', max_concurrent_battles=1,
                start_listening=False, team=team, **extra)
        self._set_policy(self._policy_state())
        self.battle=JointBattle(battle_tag='battle-gen9ou-branch',username=username,
                               logger=self.player.logger,gen=9)
        self.battle._format='gen9ou'
        self.battle._player_role=side

    @property
    def policy_metadata(self):
        return copy.deepcopy(getattr(self, '_policy_metadata', normalize_policy()))

    def _player_type(self):
        if self.policy_metadata['policy_id'] == BASE_POLICY_ID:
            return AbyssalPlayer
        from .abyssal_tera import AbyssalTeraPlayer
        return AbyssalTeraPlayer

    def _set_policy(self, state):
        self.player = object.__new__(self._player_type())
        self.player.__dict__.update(copy.deepcopy(state))
        self.player.ps_client = SimpleNamespace(username=self.username,
            logger=logging.getLogger(self.username))
        self.player._battles = {}
        self._private_caches = {name: self.player.__dict__[name] for name in _CACHE_FIELDS
                                if name in self.player.__dict__}
        self.validate_policy()

    def validate_policy(self):
        metadata = self.policy_metadata
        if metadata['policy_id'] == BASE_POLICY_ID:
            if any(key in self.player.__dict__ for key in ('policy_config', 'policy_config_hash', '_tera_public_moves')):
                raise ValueError('Tera policy state cannot restore as legacy Abyssal')
        else:
            state_metadata = normalize_policy(dict(policy_id=self.player.policy_id,
                config=self.player.policy_config, config_hash=self.player.policy_config_hash))
            if state_metadata != metadata:
                raise ValueError('actor policy state/config descriptor mismatch')

    def _feed_line(self, line):
        super()._feed_line(line)
        # Requests, raw split blocks, and arbitrary private payloads never reach
        # the public-move observer. The base parser rejects invalid streams first.
        parts = line.split('|')
        if len(parts) > 1 and parts[1] in _PUBLIC_POLICY_EVENTS:
            observer = getattr(self.player, 'observe_public_line', None)
            if observer is not None:
                observer(line)

    def _observation_audit(self):
        active = self.battle.active_pokemon
        return dict(turn=self.battle.turn,
            already_tera=bool(active and active.terastallized),
            tera_used=any(mon.terastallized for mon in self.battle.team.values()))

    def choose(self):
        before = self._observation_audit()
        command = super().choose()
        if self.policy_metadata['policy_id'] != BASE_POLICY_ID:
            if self.request.get('teamPreview'):
                audit = dict(reason='team_preview')
            else:
                audit = copy.deepcopy(self.player.last_policy_audit)
                if not isinstance(audit, dict) or not isinstance(audit.get('reason'), str):
                    raise ValueError('continuation policy omitted its decision audit')
            audit.update(before, command=command, terastallize='terastallize' in command.split())
            self._last_decision_audit = audit
        return command

    def decision_audit(self, *, command=None, forced=False, compact=False):
        """Private evidence only; a forced candidate never invokes the policy."""
        if forced:
            if command is None:
                raise ValueError('forced candidate audit requires its command')
            return dict(self._observation_audit(), reason='forced_candidate', command=command,
                        terastallize='terastallize' in command.split())
        audit = copy.deepcopy(getattr(self, '_last_decision_audit', None))
        if audit is None:
            raise ValueError('no completed policy decision to audit')
        if compact:
            audit = {key: audit[key] for key in
                     ('turn', 'reason', 'command', 'terastallize', 'already_tera', 'tera_used')}
        return audit

    def snapshot(self):
        from poke_env.data.gen_data import GenData
        from .immutable import FrozenGenData
        self.validate_policy()
        state = dict(version=_SNAPSHOT_VERSION, side=self.side, username=self.username,
            battle=self.battle, request=self.request, rqid=self._rqid, policy=self._policy_state(),
            python_rng=self._python_rng, numpy_rng=self._numpy_rng,
            policy_metadata=self.policy_metadata,
            last_decision_audit=getattr(self, '_last_decision_audit', None))
        class Writer(pickle.Pickler):
            def reducer_override(self, value):
                # Blob restores share read-only GenData. A standalone snapshot
                # must reconstruct it without assigning into a frozen instance.
                if isinstance(value, FrozenGenData):
                    return _restore_gen_data, ({name:getattr(value,name) for name in GenData.__slots__},)
                return NotImplemented
        buffer = io.BytesIO()
        Writer(buffer,protocol=pickle.HIGHEST_PROTOCOL).dump(state)
        return buffer.getvalue()

    @classmethod
    def restore(cls, snapshot):
        state = pickle.loads(snapshot)
        if state['version'] not in (1, _SNAPSHOT_VERSION):
            raise ValueError('unsupported actor snapshot version')
        if state['version'] == _SNAPSHOT_VERSION and 'policy_metadata' not in state:
            raise ValueError('actor snapshot omitted policy metadata')
        actor = object.__new__(cls)
        actor._policy_metadata = normalize_policy(
            state['policy_metadata'] if state['version'] == _SNAPSHOT_VERSION else None)
        actor.side, actor.username = state['side'], state['username']
        actor.battle, actor.request, actor._rqid = state['battle'], state['request'], state['rqid']
        actor._python_rng, actor._numpy_rng = state['python_rng'], state['numpy_rng']
        actor._last_decision_audit = copy.deepcopy(state.get('last_decision_audit'))
        actor._set_policy(state['policy'])
        return actor
