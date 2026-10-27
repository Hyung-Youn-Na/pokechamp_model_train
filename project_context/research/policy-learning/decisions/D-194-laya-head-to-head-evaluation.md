# D-194 — laya 직접 대결 평가(GPU2, EX-120 일정)

- 상태: Accepted
- 날짜: 2026-10-26

## 맥락

- laya 계열의 배틀 평가 상대는 휴리스틱 봇 Abyssal 하나다([D-189](D-189-laya-renderer-v3-opponent-sets.md)에도 "천장에 가깝다"고 적었다).
  - v2+테라는 111-17(0.867)이다.
  - 같은 실행 비교에서 128쌍 중 101~105쌍이 같은 결과다(EX-125·EX-127·EX-129).
  - v2 이후의 차이 +0.070, −0.070, −0.055는 모두 구별되지 않았다.
- 그래서 어느 변경이 실제로 더 강한지 Abyssal로는 가려내기 어렵다.
- laya_imitation 실행기는 Abyssal(`abyssal`, `abyssal-tera-v1`)만 상대로 받는다. 기존 compare는 두 모델이 **각자** Abyssal과 붙는 구조다.
- **사용자 지시**(2026-10-26): 남는 GPU0·GPU2의 개선 방향으로 승패 가중 모방(D-193)과 laya 직접 대결 평가 하네스를 고른다. 이 결정은 뒤의 것만 다룬다.

## 결정

1. **하네스**: `integration/laya_imitation/headtohead.py`로 laya 대 laya 경기를 둔다.
   - 기준 모델은 EX-120 일정 각 슬롯의 model 진영과 그 팀을 맡는다. 비교 모델은 반대 진영과 그 팀을 맡는다.
   - EX-120의 교환쌍이 있으므로 두 모델이 두 팀을 한 번씩 쓴다.
   - 두 진영 모두 EX-071 모델 player와 자기 Session·서빙을 쓴다(argmax, fallback·재질의·재경기 없음).
2. **기록과 감사**:
   - 기준 진영은 기존 시도 폴더 형식이다. 비교 진영은 `opponent/`에 같은 형식(거울 `request.json`, `events.jsonl`)으로 남긴다.
   - 같은 `audit_match`로 두 진영을 각각 감사한다. 하나라도 실패하면 그 경기는 무효다.
   - 기존 `battle.play_slot`에는 선택 인자만 더한다(worker 모듈, 이름 접두, 사전 준비, 감사 함수). 기본값의 Abyssal 경로는 바꾸지 않는다.
3. **판정**:
   - 점수는 기준 모델의 경기 점수다.
   - 조합(32) 클러스터 bootstrap 95%의 하한 > 0.5면 기준 모델 우세, 상한 < 0.5면 비교 모델 우세, 그 외는 구별되지 않음이다.
   - 정상 종료가 120/128 미만이면 판정을 보류한다.
4. **Abyssal 비교(보고 지표)**: 같은 모델들이 같은 슬롯에서 각자 Abyssal과 둔 결과(결정적 경로)를 같은 슬롯 차이로 읽어 함께 보고한다. 두 평가가 같은 방향인지, 어느 쪽이 구별하는지 비교한다.
5. **실험**:
   - [EX-134](../experiments/EX-134-laya-head-to-head512.md): v2+테라 대 v2·v1·v2+테라+효과·v3+테라, 쌍당 128경기, 총 512경기
   - [EX-135](../experiments/EX-135-laya-head-to-head-v2tw-v4t.md): v2+테라 대 승패 가중(EX-132)·v4+테라(EX-130), EX-132·EX-130 봉인 뒤
   - 둘 다 GPU2·포트 8108이고, 실행은 [EP-217](../plans/EP-217-laya-head-to-head-evaluation.md)이 소유한다.
   - [D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 결과와 관계없이 실행한다.

## 거절한 대안

- **Abyssal 경기 수 늘리기**: 두 진영 모두 결정적 경로라 같은 슬롯을 다시 둬도 같은 결과가 나온다. 새 팀 일정이 필요하고, 천장 문제는 그대로다.
- **abyssal-tera-v1 상대**: 같은 휴리스틱 계열이고, laya 계열은 이 상대로 평가한 적이 없다.
- **래더(사람)**: 외부 서버다. 로컬 실행 원칙 밖이고 별도 승인이 필요하다.
- **샘플링으로 경기 다양화**: 배틀 정책(argmax)을 바꾼다.

## 근거와 한계

- 직접 대결은 laya 계열끼리의 상대 강도다. 사람이나 다른 봇 상대의 강도를 직접 말하지 않는다.
- 기준 모델이 모든 쌍에 들어가므로, 쌍 사이 비교는 v2+테라 기준의 상대 비교다.
- 표본은 EX-120의 128슬롯(32조합)이 전부다.

## 영향

- `integration/laya_imitation/`
  - `headtohead.py`와 `tests/test_headtohead.py`를 추가한다.
  - `battle.play_slot`에 선택 인자를 추가한다(기본 동작은 그대로).
  - `browser_check.py`에 `h2h` 모드를 추가한다.
  - 설정 `RUN_H2H*`·`VIEWER_H2H*`·`H2H_HOURS`, CLI `h2h [--study]`, 실행기 경로를 추가한다.
- 뷰어는 경기마다 두 페이지(기준 진영 `battle-NNN`, 비교 진영 `battle-NNNb`)를 둔다. 같은 UI v1 안의 확장이다([변경일지](../../../shared/viewers/CHANGELOG.md#ex134-laya-h2h-v1)).
- GPU2(`GPU-c79ce3fd-…`)와 포트 8108을 쓴다.

## 증거

- mock(2026-10-26, v2+테라 대 v2+테라, EX-120 첫 두 쌍 4경기, 분모 밖): 4/4 정상 종료, 두 진영 감사 통과(예: m13-s1-a 기준 34결정·비교 35결정), 교환쌍은 각각 1승 1패다. `runs/model-training/EX-134/mock/`
- 뷰어 사전 확인(mock 결과로 만든 임시 뷰어): 오프라인 1440px·390px, 두 진영 페이지 모두 8탭, 페이지 오류 0([검사](../../../exec-plans/evidence/ep217/mock-viewer-check.json))
- `tests/test_headtohead.py`: 일정, 거울 진영, 시도 폴더 연결, 판정, EX-135 구성
