# EX-191 — laya v12 학습 자료(렌더러 v12로 v11 행 재렌더)

- 상태: Completed
- 생성일: 2026-11-20
- 책임자: Claude Code
- 관련 exec plan: [EP-237](../plans/EP-237-laya-observed-public-info-input.md)
- 비교 대상: [EX-170](EX-170-laya-v11-data.md)(v11 자료, 같은 행·순서·분할·라벨)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-170의 행을 렌더러 v12(`integration/laya_v12/render_v12.py`)로 다시 렌더해 v12 학습 자료를 만든다. 행 수·라벨·선택지 id는 바뀌지 않아야 하고, 토큰 예산(2,048 / head 768 / 선택지 64) 밖 행이 생기면 남긴다.

## 조건

- 실행: `python -m integration.laya_v12.data_v12 rows tour` → `rows ladder` → `merge`(laya env, 작업자 64, mem-guard). EX-170과 같은 원천·저장소(item-state, v5 facts, early-history, v2 엔진 판정). 사용 통계 확장은 넣지 않는다(EX-170과 같음).
- 출력: `datasets/generated/laya-compact-imitation/v12-all`, `v12-ladder`, `v12-ladder-merged`, 실행 기록 `runs/model-training/EX-191/`.
- 코드 경로는 `laya_v11.data_v11`의 `rows`·`merge`를 v12 설정으로 다시 쓴다. 그래서 manifest의 `experiment`는 `EX-170`으로 남고, 판본은 `render`(`laya-compact-v12[...]`)와 README로 구별한다.
- qualification: 행 수가 원천과 같다(`counts_match_source`), 토큰 예산 제외율이 v10 상한 이하, 생성 후 live parity(재렌더와 저장 행 일치) 통과.

## 결과

- 5회차로 완료했다(2026-11-20T07:57Z~08:59Z). 1~4회차는 렌더러 수정·검토·캐시 오류로 멈췄고 로그는 `EX-191/attempt{1-before-fix,2-before-review,3-cache-error,4-before-review2}/`에 남겼다.
- 행 수: 대회 train 130,411 / validation 512 / test 1,024, 래더 train 1,580,283 / validation 512 / test 1,024. 모두 `counts_match_source` true.
- 토큰 예산 제외 0행(두 원천, 모든 분할). 측정 512행 기준 전체 p99 1,309·최대 1,392, head 최대 587, state 최대 847.
- 병합 `v12-ladder-merged` 생성(08:59Z). 이어서 EX-192 DDP 검사가 통과했다(loss 차이 0, grad 상대 차이 1.5e-6).
- live parity: 대회·래더 각 512행 재렌더가 저장 행과 모두 일치(불일치 0, generator 일치). `EX-191/{tour,ladder}/diagnostics/parity.json`
- 소요: 대회 약 5분, 래더 약 56분, 병합 약 1분.

## 결론 및 후속 작업

- v12 자료는 v11과 같은 행·분할·라벨이고, 예산 밖 행이 없다. EX-192 학습에 썼다.
- 남은 한계(EP-237): Zoroark `replace` 미처리, 공개 아이템 상대의 약 22%는 맞는 세트가 없다.
