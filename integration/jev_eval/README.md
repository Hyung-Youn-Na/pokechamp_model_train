# 공개 정보 v6 JEV 평가 실행기

EX-091(D-138/EP-144/C-069)은 `ytbai/MiniCPM5-2B-Jev`의 계산기 포함 단독 평가를 완료했다.
조건·결과 원문은 `project_context/experiments/EX-091-minicpm5-2b-jev.md`다. 아래 준비/실행 명령은
기존 출력의 재실행을 거부하며 현재 결과는 status로 읽는다. workflow·단계 감지기는 종료됐다.

```bash
scripts/jev-eval download --experiment EX-091
scripts/jev-eval prepare --experiment EX-091
scripts/jev-eval execute --experiment EX-091
scripts/jev-eval status --experiment EX-091
```

기존 JEV 모델 환경에서 두 고정 revision의23공식 파일을 전용 모델 폴더에 검증한다.
BF16 backbone·비병합 FP32 LoRA·FP32255×2048 헤드·저장 온도/K별 prior를 사용한다.
공식 채팅/질문/선택/답변 틀에 원state·후보 JSON과 원지시문을 손실 없이 넣으며 기본 서버의
평탄화/strip/절단을 우회한다. 제어토큰처럼 쓰인 사용자 문자열은 일반 텍스트 token ID로
보존한다. 후보 순환 PriDe·날짜 보강·환경변수 덮어쓰기는 거부하며 기본 서버 재현으로 표기하지 않는다.

CPU 준비는 EX-0891,139입력의 원정보·명령/순서·실제 token ID/길이를 전수 확인하고
저장 계산은 다시 실행하지 않는다. 준비·모델·경기 감사·usage가 같은 formatter를 선택한다.
GPU0 한 장·allocator40GiB/전체44GiB·소유호스트32GiB와 단일 적재/최대8추론을 적용한다.
EX-091의 디스크 한도만null이며 기존 자료·새 가중치/출력/뷰어·임시복사 사용량과 실제공간/I/O
오류는 계속 기록한다. 뷰어의 Damage-calc는 저장 계산을 연결하고 최대5대표 화면에서 함께 검증한다.
현재 대화에 연결한 별도30초 단계 감지기는 진행 로그/경기 수를 읽지 않고 실행을 제어하지 않는다.
EX-091은 다른 모델의 선행/후속 실행이 없고 재경기·보충·자동 재개를 지원하지 않는다.

아래 EX-090과 EX-088/089 안내는 해당 완료 프로필의 보존된 조건이다.

EP-143/D-137/C-068의 EX-090(9B)은 신규32경기 평가와 종결 검증을 완료했다.
현재 결과는 `status`와 EX-090 기록에서 확인하며, 기존 출력의 재실행은 거부한다.
조건 원문은 `project_context/experiments/EX-090-jev9b-no-damage.md`다.
`jev-choice-v6-no-damage`는 피해 예측의 생성·실행과 해당 필드 설명을 생략하며
스피드 비교·기본 능력치·기술 위력·타입표·공개 정보·역할·턴 로그는 유지한다.
기존 EX-086/087/088/089의 매핑·원자료·뷰어·봉인은 보존한다.

```bash
scripts/jev-eval prepare --experiment EX-090
scripts/jev-eval execute --experiment EX-090
scripts/jev-eval status --experiment EX-090
```

`prepare`는 새 출력에서 CPU 검사와 EX-089의 저장1,139입력 전체 대조를 수행한다.
원 관측/prefix/자기팀에서 새 입력을 생성하고 피해 필드·프롬프트 설명·버전 외 값과 후보/명령/
순서가 동일한지, 실제 계산 호출이 speed뿐인지 검사한다. 기준선 피해량은 다시 계산하지 않는다.
영수증은 `evidence/no-damage-baseline.json`으로 source·자료 identity와 함께 연결한다.
같은 프로필로 대표8요청을 재생성하고 CPU에서 무절단 길이를 검증한다.
기존 모델/actor/browser 환경을 사용하며 모델 backbone과 GPU를 적재하지 않는다.
기존 출력은 덮어쓰지 않고 준비 이후 source가 바뀌면 실행 진입을 거부한다.

`execute`는 GPU0–3을 독점하는 서버를 한 번 적재해 최대8회 사전 추론한 뒤 같은 서버로
신규32슬롯을 각각 한 번 시도한다. EX-090은 다른 모델의 선행/후속 실행을 요구하지 않는다.
실행 불가능한 선택은 해당 경기 실패로 격리하고 입력/감사/무결성·자원/서빙 결함은 관련 수집을
중단한다. 수집 재개·재경기·보충은 지원하지 않는다.

run은 보존 루트 `runs/model-training/EX-090`, 뷰어는 `exports/battle_viewers/ex090/`에 쓴다.
경기별 관측 감사는 한 번 수행하며 피해 예측 비활성화·피해 계산0·스피드 기록을 확인한다.
최종 검사는 receipt·전체 기록·산술을 확인한다. EX-090−EX-089는 공통 유효 진영교환쌍에서
계산하고 실패·무효·미실행을 별도 분모로 남긴다. 입력 길이·생성/추론/결정 지연·호출·턴수·
자원과 사전 비용은 `evidence/comparison.json` 및 `cost-comparison.json`에 저장한다.
디스크100GiB에는 기존 모델/환경/참조와 EP-142의 두 Damage-calc판본·증거, 새 run/viewer/증거·
이동용 임시복사를 처음부터 함께 센다.

보존된 EX-088/089 코호트의 조건은 각 EX 원문을 따른다. 당시 EX-089의 EX-088 선행 관계와
같은 코호트 내 CPU receipt 재사용은 기존 매핑에만 적용하며 EX-090에 상속하지 않는다.

`status`는 저장 JSON만 읽는다. `--help`는 실행에 진입하지 않는다. 로그를 run 내부로
리다이렉트하려면 `prepare` 이후에 경로를 만들며, 실행기의 마지막 출력까지 기록한 다음
run을 봉인하므로 종료 후 로그에 더 쓰지 않는다.

## 완료 실험의 Damage-calc 판본

EP-142의 표시 재내보내기는 저장된 `input_audit`의 `damage`를 결정 ID별로 연결한다.
새 경기·모델 호출·피해 재계산 없이 완료된 EX-088/089에만 사용할 수 있다.

```bash
scripts/jev-eval reexport --experiment EX-088
scripts/jev-eval reexport --experiment EX-089
```

원 run·collection·기존 뷰어 봉인을 검증하고 `ex088-damage-v1`·`ex089-damage-v1`을 생성한다.
같은 판본/검증 경로가 이미 있으면 덮어쓰지 않는다. 검증 중에는 별도 building 경로를 쓰고,
전수 대조와 모델별 최대5대표 오프라인 화면 검사가 통과하면 최종 경로로 옮긴다.
검증 결과는 `project_context/exec-plans/evidence/ep142/EX-088|EX-089`에 둔다.
원 실행 디스크 범위에 두 새 판본·증거·이동용 임시복사를 더해100GiB 상한을 확인한다.

Damage-calc 탭의 기술별 범위·사유는 당시 모델 입력 그대로다. 개별 시나리오는 저장 순서로
50행씩 표시하고 방향·기술·테라 분기·상대 가정 세트로 필터링한다. 상세 조건·롤·연속타·
KO/생존 기록과 계산 JSON 복사/다운로드를 제공한다. 상대 추천 세트/절대 HP와 공개 확정 정보는
구분하며, 미제공 값을 추정하지 않는다. 개별 비율은 저장 피해HP/방어자최대HP의 표시 환산이다.
결정별 로컬 스크립트를 탭을 열 때 읽으므로 폴더 전체를 옮겨 `file://`로 열 수 있다.
빠른 탐색에서는 선택이 바뀌기 전 요청의 뒤늦은 응답을 현재 화면에 적용하지 않는다.

`provenance.json`의 `collected_source`는 수집 당시 소스/봉인,
`renderer_source`와 `renderer-source/`는 새 표시 구현의 소스/복사본이다.
기존 수집 source와 새 renderer가 같다는 검사를 완화해 실험을 재개하는 경로가 아니다.
