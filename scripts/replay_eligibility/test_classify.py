"""금지 판정·파생 효과·가려진 폼·출력의 의미를 검증한다."""
import gzip
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from classify import ROOT, Classifier, digest, local_rules, run


TEAM = ['Great Tusk', 'Gholdengo', 'Dragonite', 'Kingambit', 'Iron Valiant', 'Dragapult']


def replay(events='', team=None, id='test-gen9ou'):
    team = team or TEAM
    lines = ['|gen|9', '|gametype|singles', '|tier|[Gen 9] OU']
    for side, members in [('p1', team), ('p2', TEAM)]:
        lines += [f'|poke|{side}|{s}|' for s in members]
    lines += ['|teampreview', '|start', f'|switch|p1a: Test|{team[0]}|100/100',
              '|switch|p2a: Enemy|Great Tusk|100/100', '|turn|1', events, '|win|p1']
    return dict(id=id, formatid='gen9ou', log='\n'.join(lines))


class ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = local_rules()
        cls.reviewed_path = ROOT / 'export/teams/gen9ou_reviewed108_teams.json'
        cls.reviewed = json.loads(cls.reviewed_path.read_text())['reviewed_species_ids']
        cls.c = Classifier(cls.rules, cls.reviewed)

    def check_category(self, data, category):
        row = self.c.classify(data)
        self.assertEqual(row['category'], category, row['reasons'])
        return row

    def test_legal_rest_and_reviewed(self):
        r = self.check_category(replay('|move|p1a: Test|Rest|p1a: Test'), 'candidate')
        self.assertEqual(r['reviewed108'], 'pass')

    def test_species_tier_and_local_family_ban(self):
        for species in ['Volcarona', 'Zoroark-Hisui', 'Zorua-Hisui', 'Zamazenta-Crowned']:
            with self.subTest(species=species):
                r = self.check_category(replay(team=[species] + TEAM[1:]), 'incompatible')
                self.assertTrue(any(i['code'] == 'banned_species' for i in r['reasons']))

    def test_sleep_ohko_and_explicit_move_bans(self):
        for move in ['Spore', 'Hypnosis', 'Yawn', 'Fissure', 'Baton Pass', 'Shed Tail',
                     'Last Respects', 'Revival Blessing']:
            with self.subTest(move=move):
                self.check_category(replay(f'|move|p1a: Test|{move}|p2a: Enemy'), 'incompatible')

    def test_cancelled_banned_move(self):
        self.check_category(replay('|cant|p1a: Test|par|Spore'), 'incompatible')

    def test_multiple_violations_and_coordinates(self):
        r = self.check_category(replay('|move|p1a: Test|Spore|p2a: Enemy\n'
                                       '|move|p1a: Test|Fissure|p2a: Enemy'), 'incompatible')
        moves = [i for i in r['reasons'] if i['code'] == 'banned_moves']
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[0]['turn'], 1)
        self.assertEqual(moves[0]['side'], 'p1')
        self.assertEqual(replay('|move|p1a: Test|Spore|p2a: Enemy\n'
                                 '|move|p1a: Test|Fissure|p2a: Enemy')['log'].splitlines()[moves[0]['line_number']-1],
                         moves[0]['raw'])

    def test_called_or_reflected_move(self):
        for source in ['move: Metronome', 'ability: Magic Bounce', 'ability: Dancer']:
            r = self.check_category(replay(f'|move|p1a: Test|Spore|p2a: Enemy|[from] {source}'), 'candidate')
            self.assertTrue(r['derived_banned_effects'])
        # Sleep Talk은 자신의 기술을 호출한다.
        self.check_category(replay('|move|p1a: Test|Spore|p2a: Enemy|[from] move: Sleep Talk'), 'incompatible')

    def test_unknown_call_source(self):
        self.check_category(replay('|move|p1a: Test|Spore|p2a: Enemy|[from] move: Unknown'), 'needs_review')

    def test_transform_does_not_change_original_species(self):
        events = ('|-transform|p1a: Test|p2a: Enemy\n'
                  '|detailschange|p1a: Test|Volcarona\n'
                  '|move|p1a: Test|Spore|p2a: Enemy\n'
                  '|-ability|p1a: Test|Moody')
        r = self.check_category(replay(events), 'candidate')
        self.assertEqual(r['reviewed108'], 'pass')
        self.assertEqual(len(r['derived_banned_effects']), 2)

    def test_switch_resets_transform(self):
        events = ('|-transform|p1a: Test|p2a: Enemy\n'
                  '|switch|p1a: Test|Great Tusk|100/100\n'
                  '|move|p1a: Test|Spore|p2a: Enemy')
        self.check_category(replay(events), 'incompatible')

    def test_mimic_uncertainty(self):
        self.check_category(replay('|move|p1a: Test|Mimic|p2a: Enemy\n'
                                   '|move|p1a: Test|Spore|p2a: Enemy'), 'needs_review')

    def test_native_and_copied_ability(self):
        self.check_category(replay('|-ability|p1a: Test|Moody'), 'incompatible')
        r = self.check_category(replay('|-ability|p1a: Test|Moody|[from] move: Skill Swap'), 'candidate')
        self.assertTrue(r['derived_banned_effects'])
        self.check_category(replay('|-ability|p1a: Test|Moody|[from] ability: Trace|[of] p2a: Enemy'), 'incompatible')

    def test_native_removed_and_transferred_item(self):
        self.check_category(replay("|-item|p1a: Test|King's Rock"), 'incompatible')
        self.check_category(replay("|-enditem|p1a: Test|King's Rock|[from] move: Knock Off"), 'incompatible')
        self.check_category(replay("|-item|p1a: Test|King's Rock|[from] ability: Frisk|[of] p2a: Enemy"), 'incompatible')
        self.check_category(replay("|-item|p1a: Test|King's Rock|[from] move: Trick\n"
                                   "|-damage|p1a: Test|90/100|[from] item: King's Rock"), 'needs_review')

    def test_banned_effect_owner(self):
        r = self.check_category(replay('|-damage|p2a: Enemy|90/100|[from] ability: Moody|[of] p1a: Test'), 'incompatible')
        self.assertEqual(r['reasons'][0]['side'], 'p1')

    def test_masked_form_resolved_or_unresolved(self):
        team = [TEAM[0], 'Zamazenta-*'] + TEAM[2:]
        d = replay(team=team)
        self.check_category(d, 'needs_review')
        d['log'] = d['log'].replace('|win|p1', '|switch|p1a: Dog|Zamazenta|100/100\n|win|p1')
        self.check_category(d, 'candidate')
        d['log'] = d['log'].replace('|Zamazenta|100/100', '|Zamazenta-Crowned|100/100')
        self.check_category(d, 'incompatible')

    def test_reviewed_independent_and_exact_forms(self):
        r = self.check_category(replay(team=['Pikachu'] + TEAM[1:]), 'candidate')
        self.assertEqual(r['reviewed108'], 'fail')
        r = self.check_category(replay(team=['Zoroark-Hisui'] + TEAM[1:]), 'incompatible')
        self.assertNotEqual(r['reviewed108'], None)

    def test_required_item_form_and_preview_mismatch(self):
        d = replay(team=['Zamazenta-*'] + TEAM[1:])
        d['log'] = d['log'].replace('|Zamazenta-*|100/100', '|Zamazenta|100/100')
        d['log'] = d['log'].replace('|turn|1', '|detailschange|p1a: Test|Zamazenta-Crowned\n|turn|1')
        self.check_category(d, 'incompatible')
        d = replay('|switch|p1a: Wrong|Pikachu|100/100')
        self.check_category(d, 'needs_review')

    def test_unknown_species_or_move(self):
        self.check_category(replay(team=['MissingSpecies'] + TEAM[1:]), 'needs_review')
        self.check_category(replay('|move|p1a: Test|MissingMove|p2a: Enemy'), 'needs_review')

    def test_missing_structure_and_other_format(self):
        d = replay(); d['log'] = d['log'].replace('|teampreview', '')
        self.check_category(d, 'needs_review')
        d = replay(); d['formatid'] = 'gen8ou'
        self.check_category(d, 'other_format')
        self.check_category(replay('|-transform|p1a: Test'), 'needs_review')

    def test_duplicate_species_clause(self):
        self.check_category(replay(team=[TEAM[0]] * 2 + TEAM[2:]), 'incompatible')

    def test_cli_outputs_duplicates_and_input_preservation(self):
        # tmp入力もworkspace内に置き、実データを変更しない。
        with tempfile.TemporaryDirectory(dir=ROOT / '.artifacts') as tmp:
            base = Path(tmp); raw = base/'raw'; normalized = base/'normalized'
            raw.mkdir(); normalized.mkdir()
            payload = json.dumps(replay()).encode()
            (raw/'a.json').write_bytes(gzip.compress(payload))
            (raw/'duplicate.json').write_bytes(payload)
            other = replay(id='other'); other['formatid'] = 'gen8ou'
            (raw/'b.json').write_text(json.dumps(other))
            before = {p.name: digest(p.read_bytes()) for p in raw.iterdir()}
            out = base/'output'
            with redirect_stdout(StringIO()):
                run(raw, normalized, out, self.reviewed_path)
            summary = json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['raw_files'], 3)
            self.assertEqual(summary['unique_replays'], 2)
            self.assertEqual(summary['duplicates'], 1)
            self.assertEqual((out/'candidate-reviewed108.txt').read_text(), 'test-gen9ou\n')
            self.assertEqual(before, {p.name: digest(p.read_bytes()) for p in raw.iterdir()})
            with self.assertRaises(FileExistsError):
                run(raw, normalized, out, self.reviewed_path)

    def test_duplicate_conflict_stops_without_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.artifacts') as tmp:
            base = Path(tmp); raw = base/'raw'; normalized = base/'normalized'
            raw.mkdir(); normalized.mkdir()
            (raw/'a.json').write_text(json.dumps(replay()))
            (raw/'b.json').write_text(json.dumps(replay('|move|p1a: Test|Spore|p2a: Enemy')))
            out = base/'output'
            with self.assertRaisesRegex(ValueError, '내용 충돌'):
                run(raw, normalized, out, self.reviewed_path)
            self.assertFalse(out.exists())

    def test_normalized_stored_file_provenance(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(dir=ROOT / '.artifacts') as tmp:
            base = Path(tmp); raw = base/'raw'; normalized = base/'normalized'
            raw.mkdir(); normalized.mkdir()
            payload = json.dumps(replay()).encode()
            compressed = gzip.compress(payload)
            (raw/'a.json').write_bytes(compressed)
            source = dict(replay_id='test-gen9ou', canonical_url='https://example.test/replay',
                          parent_url=None, source_parent_urls='[]', snapshot_id='test',
                          raw_sha256=digest(compressed), input_log=None)
            pq.write_table(pa.Table.from_pylist([source]), normalized/'a.parquet')
            out = base/'output'
            with redirect_stdout(StringIO()):
                run(raw, normalized, out, self.reviewed_path)
            self.assertEqual(json.loads((out/'summary.json').read_text())['normalized_linked'], 1)
            source['raw_sha256'] = 'bad'
            pq.write_table(pa.Table.from_pylist([source]), normalized/'a.parquet')
            with self.assertRaisesRegex(ValueError, '해시 불일치'):
                run(raw, normalized, base/'bad-output', self.reviewed_path)
            self.assertFalse((base/'bad-output').exists())


if __name__ == '__main__':
    unittest.main()
