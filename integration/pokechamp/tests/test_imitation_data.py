"""Independent contamination/identity/sampling checks for the imitation boundary."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from integration.pokechamp.imitation import dataset as d, schema as s
from integration.pokechamp.imitation.storage import write_jsonl, jsonl, atomic


def snapshot():
    def mon(slot):
        return dict(slot=slot, species=f'species{slot}', hp_percent=100, status=None, boosts={},
                    item='unknown', ability='unknown', moves=[], types=[], tera_type='unknown',
                    terastallized=False, effects={})
    own = [dict(mon(i),original_set=dict(species=f'species{i}', moves=['Tackle'], item='', ability=''))
           for i in range(1,7)]
    return dict(turn=5,decision_kind='turn_action',own_team=own,opponent_team=[mon(i) for i in range(1,7)],
                own_active_slot=1,opponent_active_slot=1,can_tera=True,opponent_can_tera=True,
                weather=None,field={},own_side_conditions={},opponent_side_conditions={},
                history=[dict(turn=1,event='move',args=['self:1','tackle','opponent:1'])])


class ModelBoundaryTests(unittest.TestCase):
    def test_audit_and_opponent_future_set_never_enter_projection(self):
        actions=[dict(id='move:tackle:normal',description='Use Tackle'),dict(id='switch:2',description='Switch to slot 2')]
        value=s.from_snapshot(snapshot(),actions)
        changed=snapshot()
        changed.update(winner='player-secret',metadata={'rating':9999},label='switch:2')
        changed['opponent_team'][0]['original_set']={'moves':['Future Sight'],'item':'secret'}
        changed['own_team'][0]['original_set']['sources']=['private-manifest']
        changed['own_team'][0]['original_set']['name']='trainer-name'
        self.assertEqual(value.body_json,s.from_snapshot(changed,actions).body_json)
        self.assertNotIn('player-secret',value.body_json)

    def test_criterion_permutation_keeps_target_semantics_and_persistence_order(self):
        value=s.from_snapshot(snapshot(),[dict(id='switch:2',description='second'),dict(id='move:tackle:normal',description='first')])
        switched=s.permute(value,[1,0])
        self.assertEqual(switched.action_ids,tuple(reversed(value.action_ids)))
        self.assertEqual(value.body['questions']['action']['criteria']['switch:2'],
                         switched.body['questions']['action']['criteria']['switch:2'])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.jsonl'
            write_jsonl(path,[dict(input=value.body)])
            restored=s.ImitationInput.from_body(next(jsonl(path))['input'])
            self.assertEqual(value.body_json,restored.body_json)
            self.assertEqual(value.sha256,hashlib.sha256(value.body_json.encode()).hexdigest())

    def test_label_dependent_kind_old_history_and_private_current_fields_fail(self):
        actions=[dict(id='move:tackle:normal',description='Use Tackle')]
        for mutate in (lambda x:x.update(decision_kind='voluntary_switch'),
                       lambda x:x['history'][0].update(turn=0),
                       lambda x:x['field'].update(opponent_original_set={'moves':['future']})):
            value=snapshot();mutate(value)
            with self.assertRaises(ValueError):s.from_snapshot(value,actions)

    def test_duplicate_id_unstable_slots_and_invalid_numeric_rejected(self):
        actions=[dict(id='move:tackle:normal',description='Use Tackle')]
        with self.assertRaises(ValueError):s.from_snapshot(snapshot(),actions*2)
        value=snapshot();value['own_team'].reverse()
        with self.assertRaises(ValueError):s.from_snapshot(value,actions)
        value=snapshot();value['own_team'][0]['hp_percent']=float('nan')
        with self.assertRaises(ValueError):s.from_snapshot(value,actions)


class SplitTests(unittest.TestCase):
    def row(self,key,a,b,duplicate=None):
        return dict(replay_id=key,signatures=[a,b],duplicate_key=duplicate or key)

    def test_bond_normalization_keeps_public_six_species_composition(self):
        species=['Greninja','Dragonite','Kingambit','Corviknight','Great Tusk','Gholdengo']
        normalized=['Greninja-Bond',*species[1:]]
        self.assertEqual(d.signature(species),d.signature(normalized))

    def test_transitive_team_and_duplicate_connections_never_split(self):
        rows=[self.row('a','x','y'),self.row('b','y','z'),self.row('c','z','w'),
              self.row('d','q','r','same'),self.row('e','j','k','same')]
        result=d.connected_split(rows)
        self.assertEqual(sorted(g['size'] for g in result['groups']),[2,3])
        ids=result['assignment']
        self.assertEqual(ids['a'],ids['c']);self.assertEqual(ids['d'],ids['e'])
        self.assertEqual(result,d.connected_split(list(reversed(rows))))

    def test_each_greedy_assignment_uses_minimum_preassignment_ratio(self):
        rows=[self.row(str(i),f'a{i//3}',f'b{i}') for i in range(90)]
        result=d.connected_split(rows);used={'train':0,'validation':0,'test':0}
        for group in result['groups']:
            ratios={k:used[k]/(len(rows)*result['target'][k]) for k in used}
            self.assertEqual(ratios[group['split']],min(ratios.values()))
            used[group['split']]+=group['size']
        self.assertEqual(used,result['counts'])

    def test_balanced_sample_cycles_all_groups(self):
        rows=[dict(group_id=str(g),sample_id=f'{g}:{i}') for g in range(3) for i in range(10)]
        chosen=d.balanced(rows,8,'test')
        counts={g:sum(r['group_id']==str(g) for r in chosen) for g in range(3)}
        self.assertEqual(sorted(counts.values()),[2,3,3])
        self.assertEqual(chosen,d.balanced(list(reversed(rows)),8,'test'))

    def test_battles_are_frozen_pairs_in_model_major_order(self):
        teams=[dict(signature=str(i),sets=[],text=str(i),packed=str(i),species=[]) for i in range(10)]
        rows=d.make_schedule(teams)
        self.assertEqual(len(rows),40)
        self.assertTrue(all(r['model']=='initial' for r in rows[:20]))
        for a,b in zip(rows[:20],rows[20:]):
            for key in ('pair_id','model_side','opponent','teams','simulator_seed','opponent_seed','model_seed'):
                self.assertEqual(a[key],b[key])
        for pair in range(5):
            side1=rows[pair*4];side2=rows[pair*4+2]
            self.assertEqual(side1['teams']['p1'],side2['teams']['p2'])

    def test_immutable_write_does_not_overwrite_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock.json';atomic(path,{'a':1},immutable=True)
            with self.assertRaises(FileExistsError):atomic(path,{'a':2},immutable=True)
            self.assertEqual(json.loads(path.read_text()),{'a':1})


if __name__=='__main__':unittest.main()
