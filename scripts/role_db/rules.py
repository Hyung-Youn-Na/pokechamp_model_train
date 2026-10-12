"""실제 제출 세트의 기계적 기능을 역할 후보에 연결한다. 전략적 효능/OU prior 추정 아님."""
from dataclasses import dataclass

BANNED_ROLES = {('zamazenta', 'speed_control'), ('heatran', 'defensive_check')}


@dataclass(frozen=True)
class Signal:
    rule: str
    role: str
    conditions: tuple
    functions: tuple
    explanation: str

    def evidence(self):
        children = [dict(type=k, value=v, explanation=self.explanation) for k, v in self.conditions]
        if len(children) == 1:
            return children[0]
        return dict(type='all_of', conditions=children, explanation=self.explanation)


# 원본 사전의 기능 ID를 재사용하고, 새 효과에 필요한 ID만 별도 정의한다.
EXTRA_FUNCTIONS = {
    'benefit_from_snow': '눈에서 특성에 따른 스피드·회복·회피 효과를 활용할 수 있다. 현재 날씨를 보장하지 않는다.',
    'copy_opponent_configuration': '변신 성공 시 상대 능력치·변화 단계·기술 등을 복사한다. 자기 HP·아이템은 유지하며 스피드 우위를 보장하지 않는다.',
    'slow_opponents': '기술 또는 특성의 조건이 충족되면 상대의 스피드 단계를 낮춘다.',
    'spread_sleep': '면역·명중·발동 조건을 고려해 상대 수면을 유발할 수 있다.',
}

HAZARDS = {
    'stealthrock': 'set_stealth_rock', 'stoneaxe': 'set_stealth_rock',
    'spikes': 'set_spikes', 'ceaselessedge': 'set_spikes',
    'toxicspikes': 'set_toxic_spikes', 'stickyweb': 'set_sticky_web',
}
REMOVAL = {'rapidspin', 'mortalspin', 'defog', 'tidyup'}
PIVOT_ATTACK = {'uturn', 'voltswitch', 'flipturn'}
PIVOT_SUPPORT = {'teleport', 'partingshot', 'chillyreception', 'batonpass'}
SCREENS = {'reflect', 'lightscreen', 'auroraveil'}
WEATHER_MOVES = {'sunnyday': 'set_sun', 'raindance': 'set_rain', 'sandstorm': 'set_sand',
                 'snowscape': 'set_snow', 'chillyreception': 'set_snow'}
WEATHER_ABILITIES = {'drought': 'set_sun', 'drizzle': 'set_rain', 'sandstream': 'set_sand', 'snowwarning': 'set_snow'}
WEATHER_BENEFIT = {
    'chlorophyll': 'benefit_from_sun', 'solarpower': 'benefit_from_sun',
    'swiftswim': 'benefit_from_rain', 'raindish': 'benefit_from_rain', 'dryskin': 'benefit_from_rain', 'hydration': 'benefit_from_rain',
    'sandrush': 'benefit_from_sand', 'sandforce': 'benefit_from_sand', 'sandveil': 'benefit_from_sand',
    'slushrush': 'benefit_from_snow', 'icebody': 'benefit_from_snow', 'snowcloak': 'benefit_from_snow',
}
DISRUPTION = {
    'taunt': 'lock_moves', 'encore': 'lock_moves', 'disable': 'lock_moves', 'torment': 'lock_moves',
    'imprison': 'lock_moves', 'psychicnoise': 'deny_recovery', 'healblock': 'deny_recovery',
    'haze': 'remove_stat_boosts', 'clearsmog': 'remove_stat_boosts', 'topsyturvy': 'remove_stat_boosts',
    'roar': 'phaze', 'whirlwind': 'phaze', 'dragontail': 'phaze', 'circlethrow': 'phaze',
    'trick': 'disrupt_items', 'switcheroo': 'disrupt_items',
}
BINDING = {'infestation', 'whirlpool', 'firespin', 'sandtomb', 'magmastorm', 'wrap', 'bind', 'snaptrap', 'thundercage'}
HEAL_TEAM = {'wish', 'healingwish', 'lunardance'}
CURE_TEAM = {'healbell', 'aromatherapy'}
STATUS_FUNC = {'brn': 'burn', 'par': 'paralyze', 'psn': 'poison', 'tox': 'poison', 'slp': 'spread_sleep'}
CONTACT_STATUS = {'static': 'paralyze', 'flamebody': 'burn', 'poisonpoint': 'poison', 'effectspore': 'spread_status'}
RECOVERY = {'recover', 'roost', 'slackoff', 'softboiled', 'milkdrink', 'shoreup', 'synthesis', 'morningsun', 'moonlight', 'rest', 'strengthsap'}
# 콜백 구현 때문에 일반 boosts 필드만으로 읽을 수 없는 자기 강화 효과.
CALLBACK_BOOSTS = {'tidyup': {'atk': 1, 'spe': 1}, 'bellydrum': {'atk': 6},
                   'filletaway': {'atk': 2, 'spa': 2, 'spe': 2}, 'shiftgear': {'atk': 1, 'spe': 2},
                   'noretreat': {'atk': 1, 'spa': 1, 'def': 1, 'spd': 1, 'spe': 1},
                   'scaleshot': {'spe': 1, 'def': -1}, 'clangoroussoul': {'atk': 1, 'spa': 1, 'def': 1, 'spd': 1, 'spe': 1},
                   'growth': {'atk': 1, 'spa': 1}, 'curse': {'atk': 1, 'def': 1, 'spe': -1}}


def infer(mon, dex):
    """단일 실제 구성에서 충족하는 신호만 반환한다. fallback 역할은 만들지 않는다."""
    moves = {m: dex['moves'][m] for m in mon['moves']}
    ability, item = mon['ability'], mon['item']
    attacks = {m: v for m, v in moves.items() if v['category'] != 'Status'}
    scalable = {m: v for m, v in attacks.items() if not v.get('fixedDamage') and not v.get('ohko')}
    species_abilities = {''.join(c for c in a.lower() if c.isalnum()) for a in dex['species'][mon['id']]['abilities'].values()}
    out = []

    def add(rule, role, conditions, functions, explanation):
        if (mon['id'], role) in BANNED_ROLES:
            return
        c = tuple(sorted(set(conditions)))
        assert c
        out.append(Signal(rule, role, c, tuple(sorted(set(functions))), explanation))

    def move(m): return ('move', m)
    def ab(): return ('ability', ability)
    def it(): return ('item', item)

    for m, data in moves.items():
        if m in HAZARDS:
            add('hazard_move', 'hazard_setter', [move(m)], [HAZARDS[m]], '관측된 기술로 설치기를 배치할 수 있다. 명중·면역·반사·제거와 실제 진입 상황은 별도 조건이다.')
        if m in REMOVAL:
            add('removal_move', 'hazard_remover', [move(m)], ['remove_hazards'], '관측된 기술의 제거 효과로 설치기를 정리할 수 있다. 기술별 명중·면역·차단 조건에 따른다.')
        if m == 'courtchange':
            add('court_change', 'hazard_remover', [move(m)], ['swap_side_conditions'], '양 진영 효과를 교환해 자기 설치기 부담을 옮길 수 있다. 설치기 자체가 소멸한다는 뜻은 아니다.')
        if m in PIVOT_ATTACK:
            add('attack_pivot', 'offensive_pivot', [move(m)], ['pivot'], '공격과 교체 효과로 아군의 진입을 만들 수 있다. 피해·면역·교체 가능 여부에 따라 실패할 수 있다.')
        if m in PIVOT_SUPPORT:
            add('support_pivot', 'defensive_pivot', [move(m)], ['pivot'], '교체 효과를 통한 지원 피벗 가능성이다. 방어 능력치나 안전한 반복 진입을 보장하지 않는다.')
        if m in SCREENS:
            add('screen_move', 'screen_setter', [move(m)], ['set_screens'], '팀 보호 효과를 설치할 수 있다. Aurora Veil은 필요한 날씨 등 발동 조건이 충족되어야 한다.')
        if m in WEATHER_MOVES:
            add('weather_move', 'weather_setter', [move(m)], [WEATHER_MOVES[m]], '관측된 기술의 날씨 설정 효과를 활용할 수 있다.')
        if m in DISRUPTION:
            add('disruption_move', 'disruption', [move(m)], [DISRUPTION[m]], '관측된 기술로 상대 행동·회복·강화·아이템 또는 출전 위치에 간섭할 수 있다. 명중·면역·차단 조건은 별도다.')
        if m in {'knockoff', 'corrosivegas'}:
            add('item_removal', 'item_remover', [move(m)], ['remove_items'], '기술 성공 시 제거 가능한 상대 아이템을 제거할 수 있다.')
        if m in BINDING:
            add('binding_move', 'trapper', [move(m)], ['restrict_switching'], '기술 성공 시 바인딩 효과로 일반 교체를 제한할 수 있다. 고스트·탈출 수단 등 예외가 있다.')
        if m in HEAL_TEAM | CURE_TEAM:
            fn = 'heal_teammates' if m in HEAL_TEAM else 'cure_team_status'
            add('team_restoration', 'cleric', [move(m)], [fn], '아군 회복·치료 효과를 제공할 수 있다. 교체 타이밍과 기술별 성공 조건을 전제로 한다.')
        if m == 'trickroom':
            add('trick_room', 'speed_control', [move(m)], ['set_trick_room'], '같은 우선도 구간의 스피드 순서를 역전한다. 자기 또는 아군이 이득을 보는지는 실제 스피드에 달려 있다.')
        if m in {'leechseed', 'saltcure', 'ruination', 'superfang', 'naturesmadness'}:
            add('persistent_chip', 'progress_maker', [move(m)], ['generate_chip'], '고정 비율 피해 또는 지속 피해로 누적 이득을 만들 수 있다. 대상 면역과 회복 등을 별도로 고려한다.')
        if m in {'solarblade', 'solarbeam', 'hydrosteam'}:
            add('sun_attack', 'weather_abuser', [move(m)], ['benefit_from_sun'], '해당 기술은 햇빛에서 충전 또는 위력 측면의 이점이 있다. 현재 날씨가 햇빛이라는 의미는 아니다.')
        statuses = set()
        if data.get('status') in STATUS_FUNC:
            statuses.add(data['status'])
        for sec in data.get('secondaries', []):
            if sec.get('chance', 0) >= 30 and sec.get('status') in STATUS_FUNC:
                statuses.add(sec['status'])
        if m == 'yawn': statuses.add('slp')
        # 자기 대상 기술의 자기 상태 부여는 상대 상태이상 역할이 아니다.
        if statuses and data.get('target') != 'self' and (ability != 'sheerforce' or data.get('status') in STATUS_FUNC or m == 'yawn'):
            add('status_move', 'status_spreader', [move(m)] + ([ab()] if 'sheerforce' in species_abilities and data.get('secondaries') else []), [STATUS_FUNC[v] for v in sorted(statuses)], '상대 주요 상태이상을 유발하는 기술 또는 확률적 부가 효과다. 면역·명중·발동 확률을 전제로 한다.')
        if m in {'thunderwave', 'glare', 'stunspore', 'nuzzle', 'stickyweb', 'electroweb', 'icywind', 'stringshot', 'bulldoze', 'rocktomb', 'lowsweep', 'scaryface'} and not (ability == 'sheerforce' and data.get('secondaries')):
            add('speed_reduction', 'speed_control', [move(m)] + ([ab()] if 'sheerforce' in species_abilities and data.get('secondaries') else []), ['paralyze' if m in {'thunderwave','glare','stunspore','nuzzle'} else 'slow_opponents'], '마비 또는 스피드 하락 효과로 행동 순서에 영향을 줄 수 있다. 대상 면역과 실제 행동 순서는 별도다.')
        if data['category'] != 'Status' and data['priority'] > 0:
            add('priority_move', 'speed_control', [move(m)], ['priority_attack'], '양의 우선도 공격으로 행동 순서에 개입한다. 기술별 발동 조건과 상대 우선도·차단 효과에 따른다.')
            if m not in {'fakeout', 'upperhand'}:
                add('priority_revenge', 'revenge_killer', [move(m)], ['priority_attack', 'revenge_kill'], '우선도 공격으로 약해진 상대를 진입 후 마무리할 가능성이 있다. 실제 피해·HP·발동 조건이 필요하다.')

        boosts = {}
        if data.get('target') == 'self': boosts.update(data.get('boosts') or {})
        boosts.update((data.get('self') or {}).get('boosts') or {})
        for sec in data.get('secondaries', []):
            if sec.get('chance') == 100 and ability != 'sheerforce':
                boosts.update((sec.get('self') or {}).get('boosts') or {})
        if m in CALLBACK_BOOSTS and not (m == 'curse' and 'ghost' in mon['types']):
            boosts.update(CALLBACK_BOOSTS[m])
        if m == 'terablast' and mon['tera_type'] == 'stellar':
            boosts = {'atk': -1, 'spa': -1}
        if ability == 'contrary': boosts = {k: -v for k,v in boosts.items()}
        extra = [ab()] if ('contrary' in species_abilities or ('sheerforce' in species_abilities and data.get('secondaries'))) else []
        if m == 'terablast': extra += [('tera_type', 'stellar')]
        for attack, attack_data in scalable.items():
            stat = 'atk' if attack_data['category'] == 'Physical' else 'spa'
            if attack == 'bodypress': stat = 'def'
            # Foul Play uses the target's Attack, so own Attack boosts do not justify this inference.
            if attack == 'foulplay': continue
            if boosts.get(stat,0) > 0:
                add('offensive_setup', 'setup_sweeper', [move(m),move(attack)]+extra,
                    ['boost_defense' if stat=='def' else 'boost_attack' if stat=='atk' else 'boost_special_attack'],
                    '실제 구성에 공격에 사용하는 능력치를 높이는 효과와 해당 공격 기술이 함께 있다. 강화 성공·생존·상대 조건이 필요하며 연속 격파를 보장하지 않는다.')
            if boosts.get('spe',0) > 0:
                add('speed_setup', 'cleaner', [move(m),move(attack)]+extra, ['boost_speed','finish_weakened_targets'],
                    '자기 스피드 상승과 공격 수단이 함께 있는 조건부 마무리 후보다. 강화 후 실제 스피드·피해·상대 HP가 충족되어야 한다.')
        if boosts.get('spe',0) > 0:
            add('speed_boost_move', 'speed_control', [move(m)]+extra, ['boost_speed'], '관측된 기술의 자기 스피드 상승 효과로 행동 순서에 영향을 줄 수 있다. 성공·생존·상대 스피드 조건은 별도다.')

    if ability in WEATHER_ABILITIES:
        add('weather_ability','weather_setter',[ab()],[WEATHER_ABILITIES[ability]],'특성이 정상 발동하면 날씨를 설정한다. 특성 억제·날씨 교체는 별도 고려한다.')
    if ability in WEATHER_BENEFIT:
        add('weather_ability_benefit','weather_abuser',[ab()],[WEATHER_BENEFIT[ability]],'특성에 맞는 날씨에서 효과를 활용할 수 있다. 현재 날씨의 존재나 팀 지원을 확정하지 않는다.')
    if ability == 'toxicdebris':
        add('toxic_debris','hazard_setter',[ab()],['set_toxic_spikes'],'특성이 물리 공격 피격 조건에서 정상 발동하면 Toxic Spikes를 설치한다.')
    if ability == 'magicbounce':
        add('magic_bounce','disruption',[ab()],['reflect_status_moves'],'반사 가능한 변화 기술을 반사할 수 있다. 이미 설치된 설치기를 제거하는 효과는 아니다.')
    if ability in CONTACT_STATUS:
        add('contact_status','status_spreader',[ab()],[CONTACT_STATUS[ability]],'접촉 등 특성별 조건에서 상태이상 부가 효과가 발생할 수 있다. 확정 발동은 아니다.')
    if ability in {'arenatrap','magnetpull','shadowtag'}:
        add('trapping_ability','trapper',[ab()],['restrict_switching'],'특성별 대상 조건이 충족되면 일반 교체를 제한한다. 고스트·부유·탈출 수단 등 예외가 있으며 OU 합법성 보증이 아니다.')
    if ability in {'roughskin','ironbarbs'}:
        add('contact_chip','progress_maker',[ab()],['generate_chip'],'접촉 피격 시 조건부 피해를 누적할 수 있다. 비접촉 공격과 무효화 효과에는 적용되지 않는다.')
    if item == 'rockyhelmet':
        add('helmet_chip','progress_maker',[it()],['generate_chip'],'접촉 피격 시 아이템 효과로 피해를 누적할 수 있다. 실제 피해 조건과 아이템 유지가 필요하다.')
    if 'ghost' in mon['types']:
        add('ghost_spinblock','spinblocker',[('type','ghost')],['block_rapid_spin'],'현재 고스트 타입이면 일반 노말 Rapid Spin의 명중을 막을 수 있다. 다른 제거 기술이나 비고스트 테라까지 막는 것은 아니다.')
    if ability == 'imposter' or 'transform' in moves:
        cond=[ab()] if ability=='imposter' else [move('transform')]
        add('transform_revenge','revenge_killer',cond,['copy_opponent_configuration','revenge_kill'],
            '변신 성공 시 상대 능력치·강화·기술을 복사하여 조건부 대응 공격이 가능하다. 자기 HP·아이템 유지와 변신 실패·스피드 동률 가능성 때문에 선공이나 격파는 보장하지 않는다.')
    for m in RECOVERY & moves.keys():
        if ability in {'regenerator','intimidate','unaware','multiscale','waterabsorb','voltabsorb','flashfire','levitate','thickfat','furcoat','icescales','stamina'}:
            add('recovery_defensive_ability','defensive_check',[move(m),ab()],['recover_health','check_selected_attacks'],
                '회복 수단과 방어적 특성 효과가 함께 있어 제한된 위협에 대응할 가능성이 있다. 광범위한 벽 역할이나 안전한 교체를 보장하지 않는다.')
    for attack, a in scalable.items():
        if item == 'choiceband' and a['category']=='Physical' and attack not in {'foulplay','bodypress'}:
            add('choice_band_attack','wallbreaker',[it(),move(attack)],['pressure_walls'],'Choice Band의 공격 강화와 물리 공격 수단을 함께 가진 조건부 돌파 후보다. 대상 상성·실제 피해를 별도로 확인해야 한다.')
        if item == 'choicespecs' and a['category']=='Special':
            add('choice_specs_attack','wallbreaker',[it(),move(attack)],['pressure_walls'],'Choice Specs의 특공 강화와 특수 공격 수단을 함께 가진 조건부 돌파 후보다. 대상 상성·실제 피해를 별도로 확인해야 한다.')
        if item == 'choicescarf':
            add('choice_scarf_attack','revenge_killer',[it(),move(attack)],['outspeed_threats','revenge_kill'],'Choice Scarf와 공격 기술에 근거한 조건부 리벤지 후보다. 실제 스피드 우위나 격파 피해를 보장하지 않는다.')
        # 관측된 공격 보정과 STAB 고위력 조합만 보조 돌파 근거로 사용한다.
        stat = 'atk' if a['category']=='Physical' else 'spa'
        base = dex['species'][mon['id']]['baseStats'][stat]
        if item=='lifeorb' and a['power']>=80 and a['type'] in mon['types'] and base>=100:
            add('life_orb_stab','wallbreaker',[it(),move(attack),('type',a['type'])],['pressure_walls'],
                f'Life Orb·STAB·기본 위력80 이상 공격 및 해당 종족값100 이상({base})을 함께 만족하는 보조 돌파 추론이다. 노력치·실제 피해·OU 실전성을 보증하지 않는다.')
        if a['power'] >= 60 and attack not in {'foulplay', 'bodypress'}:
            boost_reason = None
            if ability == 'tintedlens':
                boost_reason = 'Tinted Lens는 반감된 공격 피해를 강화한다. 면역을 무시하지 않으며 실제 돌파 여부는 상대 타입·내구에 달려 있다.'
            elif ability == 'waterbubble' and a['type'] == 'water':
                boost_reason = 'Water Bubble과 물 공격의 위력 강화 조합이다. 실제 피해와 상대 물 면역·내구는 별도 조건이다.'
            elif ability in {'hugepower', 'purepower'} and a['category'] == 'Physical':
                boost_reason = '공격 배율 특성과 해당 공격을 사용하는 물리 기술의 조합이다. 상대 방어를 실제로 돌파한다는 보장은 아니다.'
            elif ability == 'sharpness' and a['flags'].get('slicing'):
                boost_reason = 'Sharpness가 강화하는 베기 공격을 실제 세트가 보유한다. 상성·실제 피해는 별도 조건이다.'
            elif ability == 'strongjaw' and a['flags'].get('bite'):
                boost_reason = 'Strong Jaw가 강화하는 물기 공격을 실제 세트가 보유한다. 실제 격파 피해는 별도다.'
            if boost_reason:
                add('ability_boosted_attack', 'wallbreaker', [ab(),move(attack)], ['pressure_walls'], boost_reason)
            if ability == 'guts' and item in {'flameorb','toxicorb'} and a['category'] == 'Physical':
                add('guts_orb_attack','wallbreaker',[ab(),it(),move(attack)],['pressure_walls'],
                    '구슬의 상태이상 부여가 성공하고 Guts가 활성화된 경우 공격이 강화되는 구성이다. 발동 전·상태 면역·상대 내구는 별도 고려한다.')
        if item == 'loadeddice' and isinstance(a.get('multihit'), list) and a['multihit'] == [2,5]:
            add('loaded_dice_attack','wallbreaker',[it(),move(attack)],['pressure_walls'],
                'Loaded Dice가2~5회 연속기의 타격 수를 보완한다. 명중·상대 내구·실제 타격 수에 따른 조건부 돌파 후보다.')
        if ability=='speedboost':
            add('speed_boost_ability','cleaner',[ab(),move(attack)],['boost_speed','finish_weakened_targets'],'턴 종료 스피드 상승과 공격 수단을 함께 이용하는 조건부 마무리 후보다. 실제 생존·스피드·피해 조건은 별도다.')
    if item == 'salacberry':
        add('salac_speed','speed_control',[it()],['boost_speed'],
            'HP 조건에서 Salac Berry를 성공적으로 먹으면 스피드가 상승한다. 발동·생존·상대보다 빠른지는 확정하지 않는다.')
    if ability in {'weakarmor','unburden'}:
        add('conditional_speed_ability','speed_control',[ab()],['boost_speed' if ability=='weakarmor' else 'outspeed_threats'],
            'Weak Armor의 물리 피격 또는 Unburden의 아이템 소실 발동 조건에서 스피드가 상승한다. 현재 발동이나 선공을 확정하지 않는다.')
    if 'tailwind' in moves:
        add('tailwind_order','speed_control',[move('tailwind')],['outspeed_threats'],
            '제한된 턴 동안 아군 스피드 배율을 높인다. 상대보다 빠른지는 실제 스피드와 우선도에 달려 있다.')
    if item=='choicescarf':
        add('choice_scarf_speed','speed_control',[it()],['outspeed_threats'],'Choice Scarf의 스피드 배율 효과를 활용할 수 있다. 상대보다 빠르다는 확정 판단은 아니다.')
    if ability=='speedboost':
        add('speed_boost_ability_order','speed_control',[ab()],['boost_speed'],'정상 발동한 턴 종료 스피드 상승으로 행동 순서에 영향을 줄 수 있다.')
    # 동일 입력에서 동일 조건 신호는 한 번만 반환한다.
    unique = {(s.rule,s.role,s.conditions):s for s in out}
    return [unique[k] for k in sorted(unique)]
