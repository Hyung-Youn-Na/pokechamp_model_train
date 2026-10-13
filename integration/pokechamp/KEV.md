# Kev-4B pokechamp r1 배틀 연결

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.


`kev-joint-noul-v1`은 공식 관측과 공개 cutoff에서 기존 JointInput을 만들고, 각 합법 후보의
noul p(true) 최댓값을 제출한다. 동률은 원 후보 순서다. 단일 후보도 호출한다. 요청의 state는
`JointInput.payload_json` 문자열 그대로이며 학습 QUESTION/describe 외 프롬프트나 criteria를
추가하지 않는다. private root의 원 Abyssal 선택은 입력에 전달하지 않는다.

연결 수락 범위는 [EX-068](../../project_context/experiments/EX-068-kev-battle.md)의 validation3관측과
1경기 smoke다. 별도 [EX-069](../../project_context/experiments/EX-069-kev-test-battles.md)는
기존 test20대진의 고정 정책 본 평가다. Tera는 허용하며 사용 시점과 이후
결정을 감사한다. 입력/명령/응답 불량·누락·비유한 값·만료·rqid/합법 목록 변경은 전송하지 않는다.

## 준비와 실행

workspace의 CPU 경로는 `pokechamp/.venv/bin/python`을 쓴다. 서버를 시작하는 기능은 없다.
원 unmerged 실행은 첫 dev 예측 불일치로 중단했고 당시 실제 배틀은0이다. 이후 사용자가
[D-109](../../project_context/decisions/D-109-kev-fused-validation.md)로 승인한 `ex068-v3`의
fused·merged 검증은3관측·24후보 모두 일치했고,1경기·57결정·fallback0의 연결 검증과
감사·뷰어·소유 서버 정리를 완료했다. 승인된 추가3요청과 전체1경기는 모두 사용했다.
원 admission과 실패는 보존한다. [최종 보고](../../project_context/exec-plans/evidence/ep111-fused/report.md),
[원 중단 보고](../../project_context/exec-plans/evidence/ep111/report.md).

아래는 완료된 실행의 명령 순서다. 같은 원장을 삭제하거나 출력 폴더를 바꿔 다시 실행하지
않으며, 새 실험은 별도 승인·등록 범위에서 준비한다.

```bash
scripts/pokechamp-kev prepare
scripts/pokechamp-kev status
scripts/pokechamp-kev probe
scripts/pokechamp-kev battle
scripts/pokechamp-kev export
```

prepare는 팀/seed·source/자산/모델 해시·worker cwd와 validation 입력 byte 재현을 보존한다.
probe는 같은 서버 프로세스의 세 관측 예측을 development rows p[1]과 소수 넷째 자리에서
대조한다. 실패는 보존하며 배틀을 차단한다. battle은 해당 receipt와 현재 서버·source를
재검증한 뒤 한 번만 진입한다. 원 `ex068-probe-admission.json`은 유지하고 D-109의 추가3요청은
`ex068-fused-probe-admission.json`으로 한 번만 허용한다. 배틀은 원 `ex068-battle-admission.json`을
공동 사용하여 전체1경기만 허용한다. 출력 폴더를 바꿔도 한도를 늘릴 수 없고 이 파일을 삭제하지 않는다.

EX-068의 준비/실행 산출물은 `.pokechamp-data/kev/ex068-v3/`의 configuration/source, validation,
live에 저장한다. 최초 준비본/서버 원장은 `ex068/`, 첫 응답과 PID 교정 준비는 `ex068-v2/`에
봉인 보존한다. 추가 실행은 merged·fused 설정과 승인된3관측 요청만 바꾸며 모델 파일·입력·대진·seed와
전체1경기 상한은 유지한다.
내보낸 [뷰어](../../exports/battle_viewers/ex068/index.html)는 이동 후 오프라인 검사까지 통과했다.
실행기는 소유 배틀 서버와 worker를 종료하며 사용자가 준비한 Kev 서버는 종료하지 않는다.
별도 승인으로 직접 시작한 Kev 서버는 승인된 종료 절차로 정리한다. 원자료와 모델은 학습에 재사용하지 않는다.

## 기존 test20 본 실행

[D-110](../../project_context/decisions/D-110-kev-test-battles.md)은 사용자의 본 테스트 직접 실행과
기존80경기 test 분할 확인 지시를 EX-069의 원20대진으로 구체화한다. 분할은 train50·validation10·
test20이며 새 팀/seed를 추출하지 않았다. 양 packed 팀·p2·simulator seed·양 actor seed를
원 manifest대로 유지하고 통과한 fused/merged 정책을 그대로 사용했다.

사용자 지시로 추가 단위검사·validation·smoke는 생략했다. 아래는 완료된 본 수집의 명령이다.
prepare는 metadata/source/model identity만 동결하고, run은 실제 진입의 동일성 확인과
경기별 기록 감사를 포함하여20경기를 한 번씩 시도한다.

```bash
scripts/pokechamp-kev-main prepare
scripts/pokechamp-kev-main run
```

별도 소유 서버 시작·정리는 `project_context/exec-plans/evidence/ep112/server_lifecycle.py`와
해당 실행의 authorization/owner receipt로 기록했다. 동일한 기존 서버 시작 승인을 재사용했다.
원 `.pokechamp-data/kev/ex069-battle-admission.json`의20회는 전부 사용했으므로 이 원장을
삭제하거나 출력 폴더를 바꾸어 재실행하지 않는다. 새 실험은 별도 승인·등록 범위가 필요하다.

결과는0승·0무·20패, 유효20/20이며1,398결정·9,982후보 전수 감사·fallback0을 확인했다.
원 Abyssal20결과는 설정 동결 뒤 참고 비교에만 읽었다. 실행 방식이 달라 학습의 단독 효과로
해석하지 않는다. [보고](../../project_context/exec-plans/evidence/ep112/report.md),
[20경기 뷰어](../../exports/battle_viewers/ex069/index.html),
[원자료](../../.pokechamp-data/kev/ex069/result.json)를 참조한다. 소유 서버/GPU3 정리는 끝났으며
C-047의20경기 오프라인 전수 확인도 통과했다. 첫 브라우저 도구의 로딩 대기 오류와
수집 영향0의 별도 교정 확인은 최종 보고에 보존했다.

## 후속 정책 질문 진단

[D-111/EX-070](../../project_context/experiments/EX-070-kev-continuation-question.md)은
`kev-continuation-noul-v1`을 명시적으로 선택하여 후보 질문만 바꾸는 동일 첫 대진1경기다.
기존 프로필·기본 질문·JointInput·학습 타깃은 유지한다. 프로필은 설정에서 worker·Session·
HTTP 생성/검증으로 전달되며 알 수 없는 프로필이나 선언과 다른 질문은 감사·뷰어에서도 거부한다.
정확한 질문과 진단의 해석 한계는 EX-070에 있다.

```bash
scripts/pokechamp-kev-continuation prepare
scripts/pokechamp-kev-continuation run
```

전용 실행기는 CPU 검증 receipt와 모델/팀/서빙 동일성을 확인하고 GPU3의 소유 서버를 시작·정리한다.
서버 시작부터3600초, 마지막60초 정리·경기1800초·요청600초이며 별도 영속 admission으로
시작과 경기 각각1회만 허용한다. 원장 삭제/출력 폴더 변경으로 재진입하지 않는다.
추가 GPU 예측 대조·재시도·재수집0, `/ref/kev` 수정0·GPU1 학습 보존이다.

EX-070은 유효1/1·122턴 패배로 종료했다. 전수 감사·뷰어·봉인·소유 서버/GPU3 반환과
EX-066/GPU1 보존을 확인했으며 승인된1회는 모두 사용했다. 학습/기본 프로필은 유지하고
이번 단일 결과의 성능 효과는 확정하지 않는다. [최종 보고](../../project_context/exec-plans/evidence/ep113/report.md) ·
[1경기 뷰어](../../exports/battle_viewers/ex070/index.html).

## Kev 서버 경계

서버를 직접 시작할 때는 해당 실행의 사용자 지시·승인 근거를 확인하며 같은 범위의 유효한
기존 승인은 재사용한다. D-109/EX-068, D-110/EX-069와 D-111/EX-070의 소유 서버는 종료했다.
현재 Kev 서버는 없다. `/ref/kev`는 읽기 전용이며 다음은 실제 사용한 v3/본 테스트 설정이다.
GPU3만 사용하며 그 GPU에 다른 작업을 함께 돌리지 않는다.

```bash
cd /ref/kev
CUDA_VISIBLE_DEVICES=3 KEV_TEMPERATURE=1 KEV_DTYPE=bf16 \
KEV_MERGE=1 KEV_FUSED=1 KEV_DATE_FACTS=0 KEV_LORA_SCALE=1 \
KEV_BACKEND=torch KEV_CUDA_GRAPHS=1 HF_HUB_OFFLINE=1 \
PYTHONDONTWRITEBYTECODE=1 /ref/kev/.venv/bin/python -m kev.serve \
  --run runs/pokechamp-r1/4b-kev4b-delta --host 127.0.0.1 --port 8019
```

`uv run/sync`와 `/ref/kev` 수정은 사용하지 않는다. 필요하면 서버와 CPU 클라이언트에 같은
`KEV_API_KEY`를 설정한다. 키·인증 헤더를 요청 기록에 넣지 않는다. loopback HTTP만 허용하며
proxy/redirect/HTTP 재시도는 없다.

현재 bb7185c에서는 FLA0.5.2가 있으면 기본 fused 경로가 bf16 adapter도 merge한다.
원 unmerged 실행은 `KEV_MERGE=0 KEV_FUSED=0`이었으며, 위 명령의 변경은 D-109의 별도 승인에 따른다.
`/v1/models`에는 merge 여부·Base revision·checkpoint hash가 없으므로 그 응답만으로 동일성을
주장하지 않고 local process/GPU3·source/체크포인트 해시도 확인한다. EX-068의 development 예측과
불일치하면 원인을 분리하여 보고하고 smoke를 진행하지 않는다. EX-069는 통과한 정책과 별도
사용자 지시에 따라 추가 사전 예측 대조를 생략한 본 실행이다.

## 기록과 검증

`events.jsonl`은 JointInput SHA-256, 정확한 요청/응답, 순서 있는 모든 p, 선택/명령,
입력/HTTP/결정 지연, rqid/합법성 재검증, 실제 transport 전송을 기록한다. 저장된 공개
protocol을 cutoff에서 다시 공식 관측기로 재생하여 live 입력과 전수 대조한다. 재검증 실패와
전송 실패는 무전송/미확정으로 남기며 정상 경기로 집계하지 않는다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m pytest \
  ../integration/pokechamp/tests/test_kev*.py
```

CPU 검사는 서버·실제 배틀을 시작하지 않는다. 잠긴 Kev `test.jsonl`과 저장 test 모델 입력/타깃은
열람하지 않는다. D-110에서 허용한 test 팀·seed 메타데이터의 live 설정 사용과 구분한다.
