"""CPU protocol fixtures: target attribution and strict public-prefix boundaries."""
import unittest
from integration.replay_ko_system1 import parser

MOVES = {name: {'category': 'Physical'} for name in
         ('tackle', 'bulletseed', 'uturn', 'futuresight', 'explosion')}
MOVES['sleeptalk'] = {'category': 'Status'}
PREFIX = '''|gametype|singles
|gen|9
|tier|[Gen 9] OU
|player|p1|PLAYER_ONE|1
|player|p2|PLAYER_TWO|2
|rated|Rated battle
|c|PLAYER_ONE|PRIVATE_CHAT
|poke|p1|Mew, L100
|poke|p2|Blissey, L100
|start
|switch|p1a: FIRST_NICK|Mew, L100|100/100
|switch|p2a: SECOND_NICK|Blissey, L100|60/100
|turn|1'''
MOVE = '|move|p1a: FIRST_NICK|Tackle|p2a: SECOND_NICK'
KO = '|-damage|p2a: SECOND_NICK|0 fnt\n|faint|p2a: SECOND_NICK'
SURVIVE = '|-damage|p2a: SECOND_NICK|20/100'
TAIL = '|upkeep|\n|turn|2\n|win|PLAYER_ONE'


def replay(block=KO, move=MOVE, tail=TAIL, prefix=PREFIX):
    return '\n'.join((prefix, move, block, tail))


def rows(text):
    return parser.extract(text, MOVES)[0]


class ReplayKOParserTest(unittest.TestCase):
    def one(self, text, label):
        data = rows(text)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['target_index'], label)
        return data[0]

    def test_direct_ko_requires_zero_and_faint(self):
        self.one(replay(), 0)
        self.assertEqual(rows(replay('|-damage|p2a: SECOND_NICK|0 fnt')), [])
        self.assertEqual(rows(replay('|faint|p2a: SECOND_NICK')), [])
        self.one(replay(KO.replace('0 fnt', '0')), 0)

    def test_survival_miss_immune_protect(self):
        for block in (SURVIVE, '|-miss|p1a: FIRST_NICK|p2a: SECOND_NICK',
                      '|-immune|p2a: SECOND_NICK', '|-activate|p2a: SECOND_NICK|move: Protect'):
            with self.subTest(block=block):
                self.one(replay(block), 1)

    def test_same_past_opposite_labels_identical_inputs(self):
        positive = self.one(replay(), 0)
        negative = self.one(replay(SURVIVE), 1)
        self.assertEqual(positive['state'], negative['state'])
        self.assertNotEqual(positive['evidence'], negative['evidence'])

    def test_future_critical_item_winner_chat_do_not_change_input(self):
        original = self.one(replay(), 0)
        changed = self.one(replay('|-crit|p2a: SECOND_NICK\n' + KO +
            '\n|-item|p1a: FIRST_NICK|Life Orb', tail=TAIL.replace('PLAYER_ONE', 'PLAYER_TWO')+
            '\n|c|PLAYER_TWO|FUTURE_SECRET'), 0)
        self.assertEqual(original['state'], changed['state'])

    def test_current_move_suffix_is_not_input(self):
        baseline = parser.projection(replay().splitlines(), len(PREFIX.splitlines()))
        for annotation in ('|[miss]', '|[still]', '|[from] move: Sleep Talk'):
            data = replay(move=MOVE+annotation).splitlines()
            self.assertEqual(parser.projection(data, len(PREFIX.splitlines())), baseline)

    def test_names_chat_rating_winner_removed(self):
        original = self.one(replay(), 0)
        altered = replay().replace('FIRST_NICK', 'ALIAS_A').replace('SECOND_NICK', 'ALIAS_B')
        altered = altered.replace('PLAYER_ONE', 'OTHER_PLAYER').replace('PLAYER_TWO', 'ANOTHER_PLAYER')
        altered = altered.replace('PRIVATE_CHAT', 'ALTERED_CHAT').replace('Rated battle', 'UNRATED')
        self.assertEqual(original['state'], self.one(altered, 0)['state'])
        text = str(original['state'])
        for forbidden in ('FIRST_NICK', 'SECOND_NICK', 'PLAYER_ONE', 'PLAYER_TWO', 'PRIVATE_CHAT', '|rated|', '|win|'):
            self.assertNotIn(forbidden, text)

    def test_public_past_hp_change_changes_input(self):
        a = self.one(replay(), 0)
        b = self.one(replay(prefix=PREFIX.replace('60/100', '40/100')), 0)
        self.assertNotEqual(a['state'], b['state'])

    def test_residual_target_faint_is_not_direct_ko(self):
        for cause in ('psn', 'brn', 'Sandstorm', 'move: Leech Seed'):
            block = SURVIVE + '\n|-damage|p2a: SECOND_NICK|0 fnt|[from] ' + cause + '\n|faint|p2a: SECOND_NICK'
            self.assertEqual(rows(replay(block)), [])

    def test_actor_recoil_faint_does_not_make_target_ko(self):
        block = SURVIVE + '\n|-damage|p1a: FIRST_NICK|0 fnt|[from] Recoil\n|faint|p1a: FIRST_NICK'
        self.one(replay(block), 1)

    def test_multihit_sash_then_target_ko(self):
        block = '|-enditem|p2a: SECOND_NICK|Focus Sash\n|-damage|p2a: SECOND_NICK|1/100\n' + KO + '\n|-hitcount|p2a: SECOND_NICK|2'
        record = self.one(replay(block, move=MOVE.replace('Tackle', 'Bullet Seed')), 0)
        self.assertEqual(record['evidence']['hit_count'], 2)

    def test_focus_sash_survival(self):
        self.one(replay('|-enditem|p2a: SECOND_NICK|Focus Sash\n|-damage|p2a: SECOND_NICK|1/100'), 1)

    def test_substitute_resolution_excluded_even_with_later_real_hit(self):
        # This first bounded dataset excludes Substitute interactions, rather than
        # claiming it has implemented all substitute/multihit event attribution.
        block = '|-activate|p2a: SECOND_NICK|Substitute|[damage]\n|-end|p2a: SECOND_NICK|Substitute\n' + KO
        self.assertEqual(rows(replay(block, move=MOVE.replace('Tackle', 'Bullet Seed'))), [])

    def test_pivot_switch_boundary(self):
        tail = '|switch|p1a: NEW_NICK|Dragonite, L100|100/100\n' + TAIL
        rec = self.one(replay(SURVIVE, move=MOVE.replace('Tackle', 'U-turn'), tail=tail), 1)
        self.assertEqual(rec['evidence']['boundary_event'], 'switch')
        self.assertNotIn('NEW_NICK', str(rec['state']))

    def test_truncated_replay_rejected(self):
        self.assertEqual(rows(replay(tail='')), [])
        self.assertEqual(rows(replay('|-crit|p2a: SECOND_NICK', tail='|win|PLAYER_ONE')), [])

    def test_called_self_and_delayed_moves_excluded(self):
        for move in (MOVE+'|[from] move: Sleep Talk', MOVE.replace('p2a: SECOND_NICK', 'p1a: FIRST_NICK'),
                     MOVE.replace('Tackle', 'Future Sight'), MOVE.replace('Tackle', 'Explosion')):
            self.assertEqual(rows(replay(move=move)), [])
        self.assertEqual(rows(replay('|-end|p2a: SECOND_NICK|move: Future Sight\n'+KO)), [])

    def test_later_moves_cannot_supply_this_moves_ko(self):
        tail = '|move|p1a: FIRST_NICK|Tackle|p2a: SECOND_NICK\n'+KO+'\n'+TAIL
        data = rows(replay(SURVIVE, tail=tail))
        self.assertEqual([r['target_index'] for r in data], [1, 0])
        self.assertEqual(data[0]['evidence']['boundary_event'], 'move')

    def test_private_split_and_illusion_replays_rejected(self):
        for line in ('|split|p1', '|replace|p2a: SECOND_NICK|Zoroark|60/100', '|-transform|p1a: FIRST_NICK|p2a: SECOND_NICK'):
            self.assertEqual(rows(replay(prefix=PREFIX+'\n'+line)), [])


if __name__ == '__main__':
    unittest.main()
