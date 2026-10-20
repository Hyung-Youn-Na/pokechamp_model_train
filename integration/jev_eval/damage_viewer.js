'use strict';
// Local script packets also work from file://. Late responses never change another decision.
(() => {
  const branches = {current:'현재', self_tera:'자기 테라', opponent_tera:'상대 테라', both_tera:'양측 테라'};
  const directions = {outgoing:'자기 → 상대', incoming:'상대 → 자기'};
  const reasons = {lead_or_forced_switch_out_of_scope:'선봉·강제교체는 당시 계산 범위 밖',
    status_move:'변화 기술', recharge_action:'반동 대기 행동', no_compatible_recommended_set:'양립하는 추천 세트 없음',
    not_calculated:'당시 계산되지 않음', input_audit_not_recorded:'결정의 감사 자료 연결 미기록',
    damage_not_recorded:'감사 자료에 피해 계산 미기록', unsupported_saved_damage_format:'지원하지 않는 저장 계산 형식',
    move_requires_unrepresented_history_or_action:'기록되지 않은 이력·행동이 필요한 미지원 기술'};
  const reasonText = value => value == null ? '사유 미제공' : typeof value === 'object' ? pretty(value) : (reasons[value] ? reasons[value] + ' · ' : '') + String(value);
  const valueText = value => value === undefined ? '미제공' : value === null ? '미제공 (null)' : value === '' ? '없음 (빈 값)' : typeof value === 'object' ? pretty(value) : String(value);
  const rangeText = value => Array.isArray(value) && value.length === 2 && value.every(Number.isFinite) ? value.map(String).join('–') : '미제공';
  const percentText = result => Array.isArray(result?.damage_range_hp) && result.damage_range_hp.length === 2 && result.damage_range_hp.every(Number.isFinite) && Number.isFinite(result.defender_max_hp) && result.defender_max_hp > 0 ? result.damage_range_hp.map(v => (100 * v / result.defender_max_hp).toFixed(2)).join('–') + '%' : '미제공';
  const pending = new Map(), cache = new Map();
  let epoch = 0, packet = null, currentId = null, pageNumber = 0;
  let candidates = new Map(), filtered = [];
  const buttons = () => document.querySelectorAll('[data-copy="damage"],[data-download="damage"]');
  function remember(key, value) {
    cache.delete(key); cache.set(key, value);
    while (cache.size > 2) cache.delete(cache.keys().next().value);
  }
  window.__jevDamageLoaded = value => {
    const task = pending.get(value?.decision_id);
    if (!task) return;
    if (value.version !== 'jev-damage-viewer-v1' || value.experiment !== data.experiment ||
        value.status !== task.reference.status || pretty(value.input_audit) !== pretty(task.reference.input_audit) ||
        (Array.isArray(value.damage?.calculations) ? value.damage.calculations.length : 0) !== task.reference.calculations) {
      task.fail(new Error('계산 자료의 결정·출처·개수가 일치하지 않습니다.')); return;
    }
    remember(value.decision_id, value); task.done(value);
  };
  function load(d, reference) {
    if (cache.has(d.id)) return Promise.resolve(cache.get(d.id));
    if (pending.has(d.id)) return pending.get(d.id).promise;
    let done, fail;
    const promise = new Promise((resolve, reject) => { done = resolve; fail = reject; });
    const script = document.createElement('script');
    const finish = fn => value => { pending.delete(d.id); script.remove(); fn(value); };
    pending.set(d.id, {promise, reference, done:finish(done), fail:finish(fail)});
    script.onerror = () => pending.get(d.id)?.fail(new Error('로컬 계산 파일을 열 수 없습니다. 내보낸 폴더 전체를 함께 이동하세요.'));
    script.onload = () => pending.get(d.id)?.fail(new Error('이 결정에 맞는 계산 자료가 없습니다.'));
    script.src = reference.src; script.async = true; document.head.append(script);
    return promise;
  }
  function summaries(d) {
    if (!d) { $('damage-summary').textContent = '이 턴에는 결정 시점의 저장 입력이 없습니다.'; return; }
    const state = payload(d).state, rows = [];
    for (const [team,direction] of [['self_team','outgoing'],['opponent_team','incoming']]) {
      for (const mon of state[team] || []) {
        if (!mon.active) continue;
        const moves = mon.current_move_slots || mon.moves;
        if (!Array.isArray(moves)) continue;
        for (const move of moves) {
          if (!move.damage) continue;
          const dm = move.damage;
          const cells = Object.keys(branches).map(branch => {
            if (dm.ranges == null) return '미제공 · ' + reasonText(dm.reason);
            if (!Object.hasOwn(dm.ranges, branch)) return '분기 미제공';
            return dm.ranges[branch] == null ? '미제공 · ' + reasonText(typeof dm.reason === 'object' ? dm.reason?.[branch] : dm.reason) : rangeText(dm.ranges[branch]) + '%';
          });
          rows.push([directions[direction], move.name || move.move || move.id,
            dm.target_species || '대상 미확인', ...cells]);
        }
      }
    }
    $('damage-summary').innerHTML = rows.length ? table(['방향','기술','대상',...Object.values(branches)], rows) : '<p class="muted">이 결정의 모델 입력에는 기술별 피해 요약이 없습니다.</p>';
  }
  function moveName(row) { return row.result?.move?.name || row.move || '기술 미제공'; }
  function candidateName(id) {
    const c = candidates.get(id);
    return c ? (c.set_name || c.species || '추천 세트') + ' · ' + id : (id || '세트 미제공');
  }
  function rowState(row) {
    if (row.error != null) return '계산 실패 · ' + reasonText(row.error);
    if (row.result?.excluded_with_reason != null) return '미지원/제외 · ' + reasonText(row.result.excluded_with_reason);
    return rangeText(row.result?.damage_range_hp) === '미제공' ? '결과 미제공' : '계산 결과';
  }
  function jsonBlock(title, value) {
    return '<h4>' + esc(title) + '</h4><pre class="code">' + (value === undefined ? '미제공' : highlight(value)) + '</pre>';
  }
  function monDetails(name, mon) {
    const opts = mon?.options || {};
    return '<h4>' + esc(name) + '</h4>' + table(['조건','저장값'], [
      ['포켓몬', valueText(mon?.name)], ['HP (현재 / 최대)', valueText(opts.curHP) + ' / ' + valueText(mon?.expectedStats?.hp)],
      ['능력치 (저장된 항목만)', valueText(mon?.expectedStats)], ['능력치 변화', valueText(opts.boosts)],
      ['도구 / 특성', valueText(opts.item) + ' / ' + valueText(opts.ability)],
      ['테라 / 배틀 타입', valueText(opts.teraType) + ' / ' + valueText(mon?.battle_types)],
      ['레벨 / 성격 / 상태', valueText(opts.level) + ' / ' + valueText(opts.nature) + ' / ' + valueText(opts.status)],
      ['EV / IV', valueText(opts.evs) + ' / ' + valueText(opts.ivs)],
    ]);
  }
  function detailBody(row) {
    const result = row.result, scenario = row.scenario, candidate = candidates.get(row.candidate_id);
    const d = selected(), opponents = payload(d)?.state.opponent_team || [];
    const publicMon = opponents.find(m => m.active);
    const publicMoves = Array.isArray(publicMon?.moves) ? publicMon.moves : [];
    const moveKnowledge = row.direction === 'incoming' ? (publicMoves.some(m => m.id === row.move) ? '상대 공개 기술 (저장 입력)' : '상대 추천 세트의 기술 가정 · 모델 입력의 공개 기술로 확정되지 않음') : '자기 기술';
    return '<p class="damage-assumption">' + esc(moveKnowledge) + '</p>' +
      monDetails('공격자 · ' + (row.direction === 'incoming' ? '상대 가정' : '자기'), scenario?.attacker) +
      monDetails('방어자 · ' + (row.direction === 'outgoing' ? '상대 가정' : '자기'), scenario?.defender) +
      jsonBlock('공격/방어 방향에 맞춘 필드 조건', scenario?.field) +
      jsonBlock('상대 가정 세트 · 공개 확정 정보와 구분', candidate) +
      jsonBlock('피해 롤', result?.damage_rolls) +
      jsonBlock('연속타·횟수별 저장 결과', result?.damage_variants) +
      '<h4>저장된 KO·생존 정보</h4>' + table(['항목','저장값'], [
        ['명중 조건 KO', valueText(result?.ko_chance_given_hit)], ['명중 조건 생존', valueText(result?.survival_given_hit)]]) +
      jsonBlock('시나리오 원문 · 조건/결과/오류 전체', row);
  }
  function renderRows() {
    const rows = packet?.damage?.calculations || [];
    const tests = [['direction','damage-direction'],['move','damage-move'],['branch','damage-branch'],['candidate_id','damage-candidate']];
    filtered = rows.map((row,n) => ({row,n})).filter(({row}) => tests.every(([field,id]) => !$(id).value || row[field] === $(id).value));
    const pages = Math.max(1, Math.ceil(filtered.length / 50)); pageNumber = Math.min(pageNumber, pages - 1);
    const visible = filtered.slice(pageNumber * 50, (pageNumber + 1) * 50);
    $('damage-table').innerHTML = '<div class="table-wrap"><table><thead><tr>' + ['#','공격 방향','기술','테라 분기','상대 가정 세트','피해 HP','최대 HP 대비','상태 · 상세'].map(v => '<th>' + esc(v) + '</th>').join('') + '</tr></thead><tbody>' + visible.map(({row,n}) =>
      '<tr data-damage-index="' + n + '"><td>' + (n + 1) + '</td><td>' + esc(directions[row.direction] || valueText(row.direction)) + '</td><td>' + esc(moveName(row)) + '</td><td>' + esc((branches[row.branch] || valueText(row.branch)) + (row.opponent_new_tera ? ' · 상대 ' + row.opponent_new_tera : '')) + '</td><td class="damage-assumption">' + esc(candidateName(row.candidate_id)) + '</td><td class="damage-hp">' + esc(rangeText(row.result?.damage_range_hp)) + '</td><td class="damage-pct">' + esc(percentText(row.result)) + '</td><td><details class="damage-detail" data-row="' + n + '"><summary>' + esc(rowState(row)) + '</summary><div class="damage-detail-body"></div></details></td></tr>').join('') + '</tbody></table></div>' + (visible.length ? '' : '<p class="empty">' + (rows.length ? '필터에 맞는 시나리오가 없습니다.' : '저장된 개별 시나리오가 없습니다. 위 모델 입력의 사유와 계산 자료를 확인하세요.') + '</p>');
    for (const element of $('damage-table').querySelectorAll('details')) element.ontoggle = () => {
      if (element.open && !element.dataset.rendered) {
        element.querySelector('.damage-detail-body').innerHTML = detailBody(rows[Number(element.dataset.row)]); element.dataset.rendered = 'true';
      }
    };
    $('damage-page').textContent = `${pageNumber + 1} / ${pages} 페이지 · ${filtered.length} / ${rows.length}행`;
    $('damage-previous').disabled = pageNumber === 0; $('damage-next').disabled = pageNumber === pages - 1;
  }
  function setupFilters() {
    const rows = packet.damage.calculations;
    candidates = new Map((packet.damage.candidates || []).map(c => [c.candidate_id,c]));
    for (const [id,field,label] of [['damage-direction','direction',r => directions[r.direction] || r.direction],['damage-move','move',moveName],['damage-branch','branch',r => branches[r.branch] || r.branch],['damage-candidate','candidate_id',r => candidateName(r.candidate_id)]]) {
      const options = new Map();
      for (const row of rows) if (row[field] != null && !options.has(row[field])) options.set(row[field],label(row));
      $(id).innerHTML = '<option value="">전체</option>' + [...options].map(([value,text]) => '<option value="' + esc(value) + '">' + esc(text) + '</option>').join('');
      $(id).onchange = () => { pageNumber = 0; renderRows(); };
    }
    pageNumber = 0; renderRows();
  }
  function show(value) {
    packet = value;
    for (const button of buttons()) button.disabled = value.damage == null;
    const count = value.damage?.calculations?.length || 0;
    $('damage-status').dataset.state = value.status;
    $('damage-status').textContent = '결정 ' + value.decision_id + ' · ' + (value.status === 'available' ? '저장 시나리오 ' + count + '개' : reasonText(value.reason));
    const usable = value.status === 'available'; $('damage-loaded').hidden = !usable;
    if (!usable) return;
    const d = selected(), op = payload(d).state.opponent_team.filter(m => m.active);
    $('damage-context').innerHTML = '<details><summary>저장 입력의 상대 공개 정보 · 가정과 별도</summary>' + jsonBlock('당시 모델 입력의 출전 상대',op) + '</details>' +
      '<details><summary>가정 세트 출처·공개 근거·제외 사유</summary>' + jsonBlock('추천 자료 출처',value.damage.source) + jsonBlock('공개 이력',value.damage.history) + jsonBlock('제외된 후보',value.damage.excluded_candidates) + '</details>';
    setupFilters();
  }
  function update() {
    const token = ++epoch, d = selected();
    if (currentId !== d?.id) { packet = null; currentId = d?.id ?? null; }
    if ($('damage-panel').hidden) return;
    const disabled = data.treatment?.damage_predictions_enabled === false;
    $('damage-summary-section').hidden = disabled;
    $('damage-loaded').hidden = true;
    for (const button of buttons()) button.disabled = true;
    $('damage-table').textContent = ''; $('damage-context').textContent = '';
    if (disabled) {
      packet = null; $('damage-summary').textContent = '';
      $('damage-note').textContent = '이 실험에서는 피해 예측용 계산을 실행하지 않습니다.';
      $('damage-status').dataset.state = 'disabled';
      $('damage-status').textContent = '피해 예측 비활성화 · 스피드 비교 유지. 스피드 비교는 당시 요청 JSON에서 확인할 수 있습니다.';
      return;
    }
    summaries(d);
    if (!d) {
      packet = null; $('damage-status').dataset.state = 'no_decision';
      $('damage-status').textContent = '이 턴에는 결정이 없어 연결할 계산 자료가 없습니다.'; return;
    }
    const ref = data.damage_index?.[d.id];
    if (!ref) {
      packet = null; $('damage-status').dataset.state = 'missing';
      $('damage-status').textContent = '이 판본에는 이 결정의 계산 자료 연결이 없습니다.'; return;
    }
    $('damage-status').dataset.state = 'loading'; $('damage-status').textContent = '결정 ' + d.id + ' · 로컬 계산 자료 불러오는 중…';
    load(d,ref).then(value => {
      if (token === epoch && selected()?.id === value.decision_id && !$('damage-panel').hidden) show(value);
    }).catch(error => {
      if (token !== epoch) return;
      packet = null; $('damage-status').dataset.state = 'load_error'; $('damage-status').textContent = error.message;
    });
  }
  $('damage-previous').onclick = () => { pageNumber--; renderRows(); };
  $('damage-next').onclick = () => { pageNumber++; renderRows(); };
  $('damage-reset').onclick = () => { for (const id of ['direction','move','branch','candidate']) $('damage-' + id).value = ''; pageNumber = 0; renderRows(); };
  window.jevDamageView = {update, value:() => packet && packet.decision_id === selected()?.id ? packet.damage : null};
  update();
})();
