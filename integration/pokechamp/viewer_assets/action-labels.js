// Resolve only the action's own decision-time observation; no replay lookahead.
function actionLabel(payload, key, description) {
  if (!description) return key ? `이름 미확인 (${key})` : '선택 없음';
  const team = payload?.state?.self_team ?? [];
  const c = description;
  if (c.kind === 'move') {
    const ref = c.move_ref;
    const owner = ref ? team.find(p => p.slot === ref.self_team_slot) : team.find(p => p.active);
    const slot = ref?.current_move_slot ?? c.slot;
    const move = owner?.current_move_slots?.find(m => m.slot === slot);
    const name = move?.name || move?.move || c.move?.name || c.move?.move;
    return `${name || `기술명 미확인 (${c.move?.id || key})`}${c.terastallize ? ' · 테라스탈' : ''}`;
  }
  if (c.kind === 'switch' || c.kind === 'team') {
    const name = c.pokemon || team.find(p => p.slot === c.slot)?.species || `포켓몬명 미확인 (${key})`;
    return `${c.kind === 'team' ? '선봉' : '교체'} → ${name}`;
  }
  return `이름 미확인 (${key})`;
}
