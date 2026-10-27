# 보관 자료·모델 안내

<a id="archived-datasets"></a>

### 6.1 보관한 Pokémon Showdown 데이터셋

추가 JSONL 보관본은 [6.2절 pokechamp-pretrain-data](../../RESEARCH_MANUAL.md#pretrain-dataset)와
[6.3절 pokemon-training-data](../../RESEARCH_MANUAL.md#pokemon-training-dataset)를 참조한다.

두 자료는 **경기 전체 리플레이**와 **리플레이에서 가공한 턴별 SFT 대화**라는 관계다.
SFT의 원자료 출처는 작성자 README의 설명이며, 원경기별 대응이나 원자료 test와의 중복은
확인하지 않았다. 아래는 보관한 고정 revision 기준 안내다. 다운로드·파일 검증의 상세 원문은
[EP-165](plans/EP-165-showdown-sft-archive.md)·
[EP-166](plans/EP-166-pokechamp-dataset-archive.md) 및 각 manifest에 둔다.

보관 루트: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/`.

| 항목 | `milkkarten/pokechamp` | `stevenkhan/pokemon-showdown-battle-sft` |
|---|---|---|
| 한 행의 단위 | 경기 1개의 Showdown 이벤트 로그 | 특정 턴의 상태·행동 추천 대화 1개 |
| 분할·행 수 | train 1,916,868 / test 213,356; 총 2,130,224 | train 500,057; 별도 test 없음 |
| Parquet 구성 | `data/train-*.parquet` 37개, `data/test-*.parquet` 5개 | `data/train-*.parquet` 2개 |
| 전체 원본 구성·용량 | 45개, 5,566,414,178 bytes (약 5.57 GB) | 4개, 537,045,320 bytes (약 537 MB) |
| 보관 폴더 | [milkkarten/pokechamp](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp) | [stevenkhan/pokemon-showdown-battle-sft](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft) |
| 원문 | [README](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/README.md) | [README](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/README.md) |
| 출처·revision·검증 | [manifest.json](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp/manifest.json) | [manifest.json](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/stevenkhan/pokemon-showdown-battle-sft/manifest.json) |
| 원문 라이선스 표기 | 보관 README에 선언 없음 | `apache-2.0` 선언 |

용량은 원본 파일 합계이며 보관용 `manifest.json`과 CLI의 `.cache/huggingface/`는 제외한다.
두 폴더 모두 원본 README·.gitattributes와 data 구조를 유지하며, pokechamp에는
`resource/method.png`도 포함된다. 고정 revision은 다음과 같다.

- `milkkarten/pokechamp`: `b5820ff5d0c8d5e5cec692d55f756b6e5a66a203`
- `stevenkhan/pokemon-showdown-battle-sft`: `8acf5b03d84cc3cad9a52906f237c4db199bd59a`

**경기 로그 구조.** pokechamp의 컬럼은 모두 문자열이다.

| 필드 | 의미 |
|---|---|
| `text` | `|turn|`, `|move|`, `|switch|`, `|-damage|`, `|win|` 등 시간순 경기 이벤트 |
| `month_year` | 월·연도, 예: `May2024` |
| `gamemode` | 세대·경기 형식, 예: `gen9nu` |
| `elo` | 레이팅 구간 문자열, 예: `1000-1199` |
| `battle_id` | 경기 식별자 |

작성자는 Gen 1–9, 37개 이상 형식, 여러 레이팅 구간과 2024–2025년 자료를 설명한다.
이는 작성자 설명이며 실제 분포의 전수 집계 결과는 아니다. 경기 ID와 메타데이터를 이용해
원경기를 추적·필터링할 수 있다. 턴별 학습 입력에는 이벤트 파싱과 의사결정 시점의 관측 재구성이
필요하며, 공개 리플레이에 드러나지 않은 정보는 이 schema만으로 확정할 수 없다.

**SFT 구조.** 최상위 컬럼은 `messages` 하나이며,
`list<struct<role: string, content: string>>` 형태다. 모든 행에 다음 메시지가 각 1개씩 있다.

| role | content의 역할 |
|---|---|
| `system` | 배틀 전략가 역할·응답 지침 |
| `user` | 턴·형식, 현재 포켓몬·HP·상태, 공개 기술·특성, 벤치·상대 공개 정보·필드 등의 상태 요약 |
| `assistant` | `Action: Use ...` 또는 `Action: Switch to ...`와 설명 |

작성자는 pokechamp에서 ELO 1400 이상·승자가 있는 경기·의미 있는 턴 3개 이상을 필터링하고
승자 측 행동을 추출했다고 설명한다. Gen 9 비중 약75%라는 설명과 필터 충족 여부는
독립적으로 재검증하지 않았다. 전략 설명은 가공 과정에서 생성된 것으로, 원 플레이어의
사고 기록이나 모든 행동의 최적성을 입증하는 자료가 아니다. 원경기 ID·날짜·레이팅의 별도
컬럼이 없어 원자료와의 대응·중복 확인에는 추가 작업이 필요하다.

**확인한 범위.** 두 자료 모두 원격 파일 목록·크기·파일 정체성 대조를 통과했다.
SFT는 전체500,057행의 메시지 구조를 검사했다. pokechamp는42개 Parquet의 schema와
footer 행 수를 확인하고 파일마다 첫32행을 읽었다. 내용의 전략적 정확성, 상태와 행동의
시점 정합성, 학습 적합성이나 두 자료 간 평가 오염 여부를 검증한 것은 아니다.
데이터 사용 조건·분할·오염 통제는 위6절의 학습 설계와 해당 EX에서 정한다.

<a id="pretrain-dataset"></a>

### 6.2 보관한 pokechamp-pretrain-data

[`milkkarten/pokechamp-pretrain-data`](https://huggingface.co/datasets/milkkarten/pokechamp-pretrain-data)의
고정 revision `be424eb903daf07deb57a579f48be319c02d6224`를
[EP-168](plans/EP-168-pretrain-data-archive.md)에서 보관했다.
위6.1절의 두 Parquet 자료와 별도 폴더에 둔 JSONL 자료다.

- 보관 경로: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/`
- [폴더](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data) · [manifest.json](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/manifest.json) · [원본 통계](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp-pretrain-data/stage_1a_stats.json)
- 원본3개 파일: `.gitattributes`, `stage_1a.jsonl`, `stage_1a_stats.json`.
- 원본 합계 **63,051,202,721 bytes (약63.05 GB)**. CLI metadata와 보관 manifest는 제외한다.
- JSONL **121,960,458행**이며 원본 stats의 `total_samples`와 일치한다.
- 이 revision에는 README·라이선스 선언·train/test 분할 설명이 없다.

첫32행 JSON 표본의 필드와 자료형은 다음과 같다. 필드 설명은 표본 내용에 근거하며,
전체 데이터의 의미·분포를 확정한 결과는 아니다.

| 필드 | 표본 자료형 | 표본에서 확인한 내용 |
|---|---|---|
| `prompt` | string | 경기 형식·턴·현재 포켓몬·HP·기술·상대 정보 등을 담은 입력 |
| `response` | string | 행동 문자열; 빈 문자열인 표본도 있음 |
| `opponent_action` | string | 상대 행동 문자열 |
| `reward` | float | 보상 수치; 계산 규칙은 원본에 별도 설명 없음 |
| `done` | bool | 종료 여부를 나타내는 필드 |
| `turn` | int | 턴 번호 |
| `format` | string | 경기 형식, 예: `gen1ou` |

원격3파일의 목록·크기·해시 대조, JSONL 전체 물리 행 수 집계와 stats 대조,
첫32행의 JSON 디코딩·동일 구조 확인을 완료했다. 모든 행의 JSON 구문·전략적 정확성·
상태와 행동의 시점 정합성·다른 자료와의 중복은 검증하지 않았다.
학습 사용 조건·분할·오염 통제는 위6절의 설계/EX 안내를 따른다.

<a id="pokemon-training-dataset"></a>

### 6.3 보관한 pokemon-training-data

[`milkkarten/pokemon-training-data`](https://huggingface.co/datasets/milkkarten/pokemon-training-data)의
고정 revision `4bdd862f098852498ed0c696a2bbc4d64e43801e`를
[EP-170](plans/EP-170-pokemon-training-data-archive.md)에서 원구조로 보관했다.

- 보관 경로: `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/`
- [폴더](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data) · [manifest.json](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokemon-training-data/manifest.json)
- 원본4파일 합계 **131,243,573,620 bytes (약131.24 GB)**. CLI metadata와 보관 manifest는 제외한다.
- README·라이선스 선언·dataset card·정답 행 수 통계·train/test 분할 설명은 없다.

| JSONL 상대 경로 | 원본 bytes | 실측 물리 행 수 | 첫32행 표본 필드 |
|---|---:|---:|---|
| `stage1a/stage_1a.jsonl` | 129,097,783,886 | 123,740,223 | prompt, response, opponent_action, reward, done, turn, format |
| `stage2a/stage_2a_reasoning.jsonl` | 1,547,316,444 | 500,000 | stage1a와 같은7필드 + outcome, reasoning, response_with_reasoning |
| `stage2b/counterfactual_actions.jsonl` | 598,470,628 | 1,000,000 | format, game_id, turn, prompt, response, action_idx, rating, source |

나머지 원본은 `.gitattributes`(2,662 bytes)다. JSONL 합계125,240,223행을 직접 집계했으며,
원격4파일의 목록·크기·해시 대조를 통과했다. 파일별 첫32행은 Python json으로 디코딩했다.
**stage2b 첫32행 모두 `rating: NaN`을 포함**한다. Python json 기본 모드는 허용하지만
표준 JSON 상수는 아니므로 엄격한 parser는 거부할 수 있다. 원본 bytes는 수정하지 않았고
manifest에 표본 검사 결과와 `passed_with_source_format_note` 상태를 남겼다.
전체 행의 JSON 구문·내용·보상 의미는 검증하지 않았다.

6.2절의 `pokechamp-pretrain-data`와 파일명이 일부 같아도 동일 파일로 취급하지 않는다.
이 보관본의 stage1a는 크기·행 수가 다르며 두 자료의 포함 관계·중복은 확인하지 않았다.
학습 사용 조건·분할·오염 통제는 위6절의 설계/EX 안내를 따른다.

<a id="generated-ruleqa"></a>

### 6.4 생성한 Showdown 규칙 Q&A v1

[EP-169](../../research/rule-learning/plans/EP-169-showdown-ruleqa.md)에서 새 CPU Gen9 장면으로 만든 영어 규칙 자료다.
기존 replay/EX 입력은 학습에 넣지 않았다. 총5,760문항이며 train4,608 / validation576 / test576이다.
기반1,920상황의 짧은 QA·전체 State QA·전체 State 선택형은 파생 표현이다. 두 export를 독립 표본으로 합산하지 않는다.

- [보관 폴더](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1)
- [manifest](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/manifest.json) · [한국어 검토 보고](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/report.txt)
- [SFT messages](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/exports/messages) · [선택형](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/exports/multiple_choice)
- [입력/target 구분과 사용 예시](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1/README.txt) · [재생성 CLI](../../../integration/pokechamp/rule_qa/README.md)

State는 jev-ruleqa-state-v1이며 v6 관측·수치·후보를 보존하고 혼란 상태 설명만 별도 교정했다.
추천세트 피해 범위는 조건부 값이다. evidence/의 내부 세트·oracle·실패본을 모델 입력으로 사용하지 않는다.
전수 기계 검사와96상황 의미 검토, 두 tokenizer 무절단 검사를 통과했다. 자기1–2마리/상대1마리의
제어 장면이며 자연6대6 경기나 미지 템플릿의 독립 평가를 대신하지 않는다. EP169에서는 학습·모델 추론을 하지 않았다.
후속 [EX107](../../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md)의 규칙QA 학습·오프라인 평가를 완료했고 실제 배틀은 별도 [EX108](../../research/rule-learning/experiments/EX-108-tacit-ruleqa-battle32.md)의32경기 탐색으로 완료했다.

<a id="archived-strategist-model"></a>

### 6.5 보관한 Pokémon Showdown Strategist 모델

`stevenkhan/pokemon-showdown-strategist`의 고정 revision
`f2726381423690cbe48f581c8027ce8b01012dae`를 [EP-171](plans/EP-171-strategist-model-archive.md)에서 보관했다.
[정보·검증 보고](../../exec-plans/evidence/ep171/report.md)에서 모델 카드와 실제 설정의 차이를 확인한다.

- 경로: `/mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist/`
- [폴더](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist) · [manifest](../../../../mnt/digicap/combined/hyna/backup/pokechamp-research/models/stevenkhan/pokemon-showdown-strategist/manifest.json)
- 원본11파일·92,248,228 bytes. `Qwen/Qwen3-0.6B`용 **LoRA 어댑터**이며 기반 가중치는 포함되지 않는다.
- 실제 어댑터 rank32/alpha16/dropout0.05, 28층·7모듈, FP32 tensor392개·20,185,088 parameter.
- 저장 학습 args는 max_length512·학습률0.0002·1epoch 설정이다. 공개 학습 스크립트의 모델/rank/길이와 달라 실제 사용 데이터 수·학습 완료·성능은 확정하지 않는다.
- 원격 파일 크기·해시 및 safetensors 헤더·rank/구조 검증 완료. 어댑터 README의 라이선스 표기는 불명확하다.
- 모델 실행·GPU·추론·학습·배틀은 수행하지 않았다. 기반 모델 결합과 실행기 연결은 별도 작업이다.

### 6.6 Smogon Gen9 OU 전략 수집본

[EP-175](plans/EP-175-smogon-ou-strategy-data.md)의 새 자료는
사용자 지정 `/workspace/data/smogon-dex/strategies/gen9ou-20261019/`에 있다.
[사용 안내](../../../data/smogon-dex/strategies/gen9ou-20261019/README.txt) ·
[manifest](../../../data/smogon-dex/strategies/gen9ou-20261019/manifest.json) ·
[검증 보고](../../exec-plans/evidence/ep175/report.md).

EP-174의110링크를 모두 보존하고 공유 폼 관계와 원문 빈 설명, 오래된 분석을 구분한다.
포켓몬별 전체 JSON/JSONL과 중복 없는 세트/전략 JSONL·Parquet, 원 HTML/JSON을 제공한다.
기존 raw/normalized의8월 보관본과 별도이며 학습 데이터 포함이나 새 평가 조건을 승인하지 않는다.

