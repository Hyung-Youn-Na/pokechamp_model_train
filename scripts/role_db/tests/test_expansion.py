"""역할 추론의 과잉 일반화·예외·ID/세트 파싱 회귀 검사."""
import json
import sys
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from rules import infer
from expand_team_pool import match,known,parse_team,cleaned_source,ROOT
DEX=json.loads((ROOT/'project_context/exec-plans/evidence/ep091/mechanics.json').read_text())


def mon(species,moves,item='leftovers',ability=None,tera='normal'):
    d=DEX['species'][species]
    ability=ability or ''.join(c for c in next(iter(d['abilities'].values())).lower() if c.isalnum())
    return dict(id=species,pokemon=d['name'],moves=moves,item=item,ability=ability,types=d['types'],tera_type=tera)


def roles(m):return {s.role for s in infer(m,DEX)}


class RuleTests(unittest.TestCase):
    def test_boots_ogerpon_has_actual_hazards_and_taunt(self):
        m=mon('ogerponcornerstone',['spikes','ivycudgel','powerwhip','taunt'],'cornerstonemask','sturdy','rock')
        self.assertTrue({'hazard_setter','disruption'}<=roles(m))
        self.assertNotIn('item_remover',roles(m))

    def test_balloon_ditto_not_scarf_speed(self):
        m=mon('ditto',['transform'],'airballoon','imposter')
        self.assertIn('revenge_killer',roles(m));self.assertNotIn('speed_control',roles(m))
        self.assertTrue(all('스피드' in s.explanation for s in infer(m,DEX)))

    def test_booster_energy_does_not_prove_speed(self):
        m=mon('ironvaliant',['moonblast','closecombat'],'boosterenergy','quarkdrive','fairy')
        self.assertNotIn('speed_control',roles(m));self.assertNotIn('cleaner',roles(m))

    def test_choice_item_requires_matching_damage_category(self):
        m=mon('alakazam',['psychic'],'choiceband','magicguard','psychic')
        self.assertNotIn('wallbreaker',roles(m))
        m['item']='choicespecs';self.assertIn('wallbreaker',roles(m))

    def test_fixed_damage_not_boosted_by_choice_band(self):
        m=mon('chansey',['seismictoss'],'choiceband','naturalcure')
        self.assertNotIn('wallbreaker',roles(m))

    def test_swordsdance_with_only_special_attacks_not_sweeper(self):
        m=mon('samurott',['swordsdance','hydrocannon','icebeam','protect'],'salacberry','torrent','water')
        self.assertNotIn('setup_sweeper',roles(m));self.assertIn('speed_control',roles(m))

    def test_contrary_self_drops_need_correct_ability(self):
        a=mon('enamorus',['superpower','moonblast'],'heavydutyboots','contrary','stellar')
        b=dict(a,ability='cutecharm')
        signals=[s for s in infer(a,DEX) if s.role=='setup_sweeper']
        self.assertTrue(signals)
        self.assertTrue(all(not match(s.evidence(),known(b)) for s in signals))
        self.assertNotIn('setup_sweeper',roles(b))

    def test_sheer_force_secondary_status_not_inferred(self):
        a=mon('nidoking',['sludgebomb'],'lifeorb','sheerforce','poison')
        b=dict(a,ability='poisonpoint')
        self.assertFalse(any(s.rule=='status_move' for s in infer(a,DEX)))
        signals=[s for s in infer(b,DEX) if s.rule=='status_move']
        self.assertTrue(signals)
        self.assertTrue(all(not match(s.evidence(),known(a)) for s in signals))

    def test_sheer_force_still_allows_direct_toxic(self):
        a=mon('nidoking',['toxic'],'lifeorb','sheerforce','poison')
        self.assertTrue(any(s.rule=='status_move' for s in infer(a,DEX)))

    def test_self_rest_does_not_spread_sleep(self):
        self.assertNotIn('status_spreader',roles(mon('snorlax',['rest'],'leftovers','thickfat')))

    def test_foul_play_does_not_use_own_swordsdance(self):
        a=mon('grimmsnarl',['foulplay','swordsdance'],'leftovers','prankster','dark')
        self.assertNotIn('setup_sweeper',roles(a))

    def test_ghost_type_is_checked_at_assessment_time(self):
        a=mon('gengar',['shadowball'],'leftovers','cursedbody','normal')
        s=next(s for s in infer(a,DEX) if s.role=='spinblocker')
        self.assertTrue(match(s.evidence(),known(a)))
        self.assertFalse(match(s.evidence(),known(dict(a,types=['normal']))))

    def test_loaded_dice_only_matching_multihit(self):
        a=mon('kyurem',['iciclespear'],'loadeddice','pressure','ice')
        b=dict(a,moves=['icebeam'])
        self.assertIn('wallbreaker',roles(a));self.assertNotIn('wallbreaker',roles(b))

    def test_tinted_lens_has_resistance_pressure(self):
        self.assertIn('wallbreaker',roles(mon('noctowl',['hurricane','roost'],'leftovers','tintedlens','flying')))

    def test_no_generic_role_for_splash(self):
        self.assertEqual(roles(mon('magikarp',['splash'],'none','swiftswim','water')),{'weather_abuser'})
        self.assertEqual(roles(mon('magikarp',['splash'],'none','rattled','water')),set())

    def test_explicit_user_role_deletions_remain(self):
        self.assertNotIn('speed_control',roles(mon('zamazenta',['agility','closecombat'],'choicescarf','dauntlessshield')))
        self.assertNotIn('defensive_check',roles(mon('heatran',['rest'],'leftovers','flashfire')))

    def test_one_move_ditto_and_nicknamed_gendered_species_parse(self):
        fixed=(ROOT/'pokechamp/poke_env/data/static/teams/gen9ou/gen9ou11.txt').read_text()
        parsed=parse_team(fixed,DEX)
        self.assertEqual(parsed[1]['moves'],['transform'])
        parsed=parse_team((ROOT/'pokechamp/poke_env/data/static/teams/gen9ou/gen9ou12.txt').read_text(),DEX)
        self.assertEqual([m['id'] for m in parsed],['ninetales','ceruledge','venusaur','hatterene','greattusk','walkingwake'])

    def test_invalid_species_fails_instead_of_silent_omission(self):
        with self.assertRaises(ValueError):parse_team('NotAPokemon @ Leftovers\nAbility: Static\nTera Type: Normal\n- Tackle',DEX)

    def test_all_of_does_not_match_partial_configuration(self):
        e={'type':'all_of','conditions':[{'type':'item','value':'choicescarf'},{'type':'move','value':'moonblast'}]}
        a=mon('enamorus',['moonblast'],'heavydutyboots','contrary','stellar')
        self.assertFalse(match(e,known(a)))
        self.assertTrue(match(e,known(dict(a,item='choicescarf'))))


if __name__=='__main__':unittest.main()
