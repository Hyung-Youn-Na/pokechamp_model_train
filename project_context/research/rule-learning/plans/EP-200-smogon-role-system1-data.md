# EP-200 — Smogon 전략 기반 역할 System 1 자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 포켓몬 역할 System1 자료 요청 및 “최근 Smogon 웹사이트에서 가져온 자료 기준” 정정.
- 관련: D177, EP175 수집 snapshot, C007/연구해석 경계. 기존409종 역할DB 추론라벨은 정답으로 사용하지 않는다.
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존변경보존.
- 원천: data/smogon-dex/strategies/gen9ou-20261019/ 봉인본. 재수집/업데이트/원본변경0.
- 소스: integration/smogon_role_system1/, scripts/smogon-role-system1-data; CPU tokenizer/구조검증.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/smogon-role-system1/v1
- 제공: /workspace/exports/smogon-role-system1-v1 및ZIP·CSV, evidence/ep200.

## 범위·정답 의미

215세트 중사이트outdated=false인208개를구분하고본문있는177개를주석대상으로한다. 현행빈본문31·오래된7은제외기록.
21개명시적역할taxonomy에대해각세트본문을읽고해당세트자신의역할로근거있는긍정주석을작성한다.
기술보유만으로역할을추론하지않으며팀원/상대역할을주어와혼동하지않는다. 선택지/조건부세트는가능한변형의역할로표시한다.
구조화된기술/도구/특성/테라선택지에없는본문의추가대안만을근거로하는역할은제외한다.
세트이름/전략본문/증거문구/기존역할라벨/usage/prior를모델입력에넣지않는다.
입력은Smogon의세트구성(기술·도구·특성·성격·EV/IV·테라선택지보존)과질의역할/일반정의다.

역할별질문은“이수집본의해당세트분석에해당역할의근거가있는가”를묻는다.
정답은supported_by_analysis / not_established_in_analysis. 미언급을실제역할불가/생물학적부정으로해석하지않는다.
같은구성의중복세트는묶고원문긍정근거의합집합을쓴다. 동일구성에상이한정답을만들지않는다.
동일세트의복수역할을허용하며단일주역할을강제하지않는다. Smogon원문에존재하는공식role라벨이아닌본문근거기반에이전트주석임을명시한다.
원문의빈설명은메우지않고오래된분석을현행라벨에섞지않는다. 날짜는20261019snapshot의사이트상태일뿐독립최신메타판정이아니다.

근거는원본문문자오프셋·문장좌표/짧은주석·출처URL로연결하고전체원문을새학습입력으로복사하지않는다.
System1형식은명시입력→2후보logits CE, 설명/정답completion0. source-support multi-label 목록도제공한다.
모두학습pool, 세트/전략/종단위그룹을보존하고독립평가성능·실전역할보장·최적행동주장0.

## 완료 기준

- [x] 원문215상태/177대상/빈본문·outdated제외분모 및봉인·기여자출처 연결
- [x] 본문주어·역할·조건의전수주석/근거위치와교차검토; 근거없는역할추가0
- [x] 역할별긍정/미확인정답·복수역할·제목/본문/라벨누출방지·native token/저장대응
- [x] CPU선택CE·검증/annotation/manifest/안내·ZIP·상태/색인완료

## 진행·중단

INDEX/CHARTER/매뉴얼·현재/중단색인·EP091/175·자료설계를확인했다. 사용자정정에따라EP091역할라벨원천은사용하지않는다.
새모델학습/forward/GPU/API/배틀/서빙변경0. 자료전용으로EX/C047해당없음.
불명확역할은보수적으로미확인·검토기록하며원문을추정으로보충하지않는다. 검증실패시내보내기를차단한다.

주석중 Magic Bounce 등의설치예방을제거/설치유지와혼동하지않도록 hazard_denier를독립역할로추가했다.
학습자료생성전21역할로통일하고이미검토한세트도해당역할근거를재확인한다.

## 완료 결과

최신보관Smogon분석의현행본문177세트/92종에대해21역할을주석했다. 구성도177개모두고유하다.
총3717문항:본문근거확인744/주석에서근거미확인2973. 현행빈본문31·outdated7을제외했고기존409DB라벨은사용하지않았다.
세배치각59전문검토, 배치간30세트교차검토, 최종10문항의별도원문검토와744근거좌표/해시·3717target전수대조를수행했다.
입력407~586토큰,제목/본문/근거/라벨누출0,원세트옵션/EV/IV보존,CPU2후보CE통과.
본문의구조화밖변형은제외했고MagicBounce등은hazard_denier로분리했다. 인간블라인드검토/Smogon공식role라벨은아니다.
[보고](../../../exec-plans/evidence/ep200/report.md) · [독립검토](../../../exec-plans/evidence/ep200/independent-review.json) ·
[한국어역할표](../../../../exports/smogon-role-system1-v1/roles.ko.csv).
실제모델학습/forward/GPU/서빙변경0이며전부학습pool이다. 원자료/기존역할DB/봉인을보존했다.
