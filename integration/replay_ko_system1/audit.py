"""Independent selected-row audit against original replay coordinates.

Does not use extract(), parsed damage evidence, or outcome_kind as label truth.
Raises ValueError for an unsupported, inconsistent, or misattributed frame.
"""
import re

_BOUNDARIES = {'move', 'cant', 'switch', 'drag', 'turn', 'upkeep', 'win', 'tie'}
_KO = 'Direct target KO occurred'
_NON_KO = 'No direct target KO occurred'


def audit_raw(text, row):
    lines = text.splitlines()
    start = row['metadata']['move_line_index']
    end = row['evidence']['frame_end_index']

    def require(condition, reason):
        if not condition:
            raise ValueError('Raw KO audit: ' + reason)

    def parts(line):
        return line.rstrip('\r').split('|')

    def kind(line):
        value = parts(line)
        return value[1].lower() if len(value) > 1 else ''

    def identity(value):
        return value.split(':', 1)[0].strip().lower()

    def numerator(value):
        match = re.fullmatch(r'(\d+)(?:/(\d+))?(?:\s+.*)?', value)
        require(match is not None, 'unreadable target HP')
        return int(match.group(1))

    require(type(start) is int and type(end) is int, 'noninteger coordinates')
    require(0 <= start < end < len(lines), 'invalid frame coordinates')
    header = parts(lines[start])
    require(len(header) >= 5 and header[1].lower() == 'move', 'not a move header')
    actor, target = identity(header[2]), identity(header[4])
    require(actor in {'p1a', 'p2a'} and target in {'p1a', 'p2a'} and actor != target,
            'not opposing singles active slots')
    require(not any('[from]' in value.lower() for value in header[5:]), 'called move')
    require(row['input']['state']['proposed_attack'] ==
            {'actor': actor, 'move': header[3], 'target': target}, 'attack identity/extra header fields')
    actual_end = next((i for i in range(start + 1, len(lines))
                       if kind(lines[i]) in _BOUNDARIES), len(lines))
    require(end == actual_end and end < len(lines), 'frame does not end at first action boundary')

    # Independently recover the currently active target's latest public HP.
    previous_hp = None
    for line in lines[:start]:
        f = parts(line)
        event = kind(line)
        if event in {'switch', 'drag'} and len(f) > 4 and identity(f[2]) == target:
            previous_hp = numerator(f[4])
        elif event in {'-damage', '-heal', '-sethp'} and len(f) > 3 and identity(f[2]) == target:
            previous_hp = numerator(f[3])
        elif event == 'faint' and len(f) > 2 and identity(f[2]) == target:
            previous_hp = 0
    require(previous_hp is not None and previous_hp > 0, 'target not known alive before attack')

    direct = []
    indirect = []
    faints = []
    prevented = []
    for index in range(start + 1, end):
        f = parts(lines[index])
        event = kind(lines[index])
        normalized = re.sub(r'[^a-z0-9]', '', lines[index].lower())
        require(not any(x in normalized for x in ('destinybond', 'perishsong', 'futuresight', 'doomdesire')),
                'linked or delayed outcome')
        require(not ('substitute' in normalized and len(f) > 2 and identity(f[2]) == target),
                'unsupported target substitute interaction')
        require(event not in {'-ohko', '-notarget'}, 'unsupported outcome event')
        if event == '-damage' and len(f) > 3 and identity(f[2]) == target:
            value = numerator(f[3])
            if any(x.lower().startswith('[from]') for x in f[4:]):
                indirect.append((index, value))
            else:
                direct.append((index, value))
        elif event == 'faint' and len(f) > 2 and identity(f[2]) == target:
            faints.append(index)
        elif event == '-miss' and len(f) > 3 and identity(f[3]) == target:
            prevented.append('miss')
        elif event == '-immune' and len(f) > 2 and identity(f[2]) == target:
            prevented.append('immune')
        elif event == '-activate' and len(f) > 3 and identity(f[2]) == target and 'protect' in f[3].lower():
            prevented.append('protection')

    zero = [index for index, value in direct if value == 0]
    if zero:
        require(any(z < faint for z in zero for faint in faints), 'direct zero lacks subsequent target faint')
        observed = _KO
    else:
        require(not faints, 'indirect or unattributed target faint')
        require(bool(direct and direct[-1][1] > 0) or bool(prevented), 'no explicit non-KO outcome')
        observed = _NON_KO
    choices = row['input']['question']['criteria']
    index = row['target_index']
    require(type(index) is int and 0 <= index < len(choices), 'invalid target index')
    selected = list(choices.values())[index]
    require(selected == observed, 'label contradicts raw resolution')
    require(row['target_distribution'] == [int(i == index) for i in range(len(choices))],
            'target distribution mismatch')
    return {'passed': True, 'method': 'independent_raw_frame_v1', 'move_line_index': start,
            'frame_end_index': end, 'direct_target_damage_count': len(direct),
            'indirect_target_damage_count': len(indirect), 'target_faint_count': len(faints),
            'observed_outcome': observed, 'proposed_attack_fields_verified': True}
