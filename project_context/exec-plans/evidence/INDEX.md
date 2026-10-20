# 증거 탐색

증거는 해당 [실험 record](../../experiments/INDEX.md) 또는 [개별 plan](../INDEX.md)의 최종 보고서부터
읽는다. 보고서 → manifest → 필요한 원자료·source/config·정정 분석으로 범위를 좁힌다.
이 색인은 결과 원문이나 실행 지시가 아니며 기존 자료의 보존·판정을 변경하지 않는다.

## 원자료와 정정 근거

| 필요한 근거 | 실제 위치와 읽기 범위 |
|---|---|
| 후보별 요약 EX112 분모미달 종결 | [보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/report.md) → [비교](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/comparison/report.md) · [사례](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/case-review.md) · [종결](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-112/evidence/completion.json) · [뷰어](../../../exports/battle_viewers/ex112/index.html) |
| JevK5-9B v6 상세32 EX111 | [보고](ep181/report.md) → [오프라인](ep181/final-browser.json) · [봉인](ep181/seal-receipt.json) · [뷰어](../../../exports/battle_viewers/ex111/index.html) |
| 후보별 현재대면 요약 EP182 | [보고](ep182/report.md) → [전후예시](ep182/examples.md) · [보존/coverage](ep182/validation.json) · [검사](ep182/tests.log) · [종결](ep182/completion.json) |
| OpenAI Decisions v6 상세32 EX110 | [보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/report.md) → [지표](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/metrics.json) · [종결](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-110/evidence/completion.json) · [뷰어](../../../exports/battle_viewers/ex110/index.html) |
| 학습 Tacit 실전32 EX-108 | [보고](ep176/report.md) → [지표](ep176/final-summary.json) · [감사](ep176/audit.json) · [브라우저](ep176/browser-check.json) · [무결성/반환](ep176/final-integrity.json) · [종결](ep176/completion.json) |
| Tacit 규칙QA LoRA EX-107 | [보고](ep173/report.md) → [감사](ep173/final-audit.json) · [블라인드검토](ep173/semantic-review.json) · [checkpoint](ep173/checkpoint-audit.json) · [종결/봉인](ep173/seal-receipt.json) |
| Smogon OU 전략 전수 수집 | [보고](ep175/report.md) → [통계](ep175/statistics.json) · [원문 대조](ep175/validation.json) · [브라우저](ep175/browser-validation.json) · [Parquet](ep175/parquet-validation.json) · [종결](ep175/completion.json) |
| Strategist 첫 배틀 EX-106 | [보고](ep172/report.md) → [지표](ep172/report.json) · [감사](ep172/audit.json) · [오프라인 뷰어](ep172/browser-check.json) · [종결/봉인](ep172/completion.json) |
| Tacit vLLM low EX-105 | [보고](ep164/report.md) → [감사](ep164/audit.json) · [비교](ep164/comparison.md) · [사례](ep164/case-review.md) · [속도](ep164/decision-latency.json) · [뷰어](ep164/browser.json) · [종결](ep164/completion.json) |
| Tacit Thinking low EX-104 부분 종결 | [보고](ep163/report.md) → [부분 감사](ep163/partial-audit.json) · [비교](ep163/partial-comparison.json) · [뷰어 검증](ep163/browser.json) · [종결](ep163/completion.json) |
| Omni low EX-103 | [보고](ep162/report.md) → [감사](ep162/audit.json) · [비교](ep162/comparison.json) · [오프라인](ep162/browser.json) · [자원](ep162/resources.json) |
| 매치업 사건 high EX-102 | [보고](ep161/report.md) → [사건감사](ep161/trigger-audit.json) · [비교](ep161/comparison.json) · [오프라인](ep161/browser.json) · [자원](ep161/resources.json) |
| 매치업 사건 EX-101 | [보고](ep160/report.md) → [사건감사](ep160/trigger-audit.json) · [비교](ep160/comparison.json) · [오프라인](ep160/browser.json) · [자원](ep160/resources.json) |
| GLM-5.3 low EX-100 | [보고](ep159/report.md) → [감사](ep159/audit.json) · [비교](ep159/comparison.json) · [오프라인](ep159/browser.json) · [자원](ep159/resources.json) |
| 시간null·GLM 최대출력 EX-099 | [보고](ep158/report.md) → [감사](ep158/audit.json) · [비교](ep158/comparison.json) · [오프라인](ep158/browser.json) · [자원](ep158/resources.json) |
| GLM high 동일대진 EX-098 | [보고](ep157/report.md) → [감사](ep157/audit.json) · [low 비교](ep157/comparison.json) · [오프라인](ep157/browser.json) · [자원](ep157/resources.json) |
| GLM 기본온도0·형식 재시도 EX-097 | [보고](ep156/report.md) → [감사](ep156/audit.json) · [브라우저](ep156/browser.json) · [자원](ep156/resources.json) · [실패 재생](ep156/replay-failure.json) |
| NVFP4 확률 진단 EX-096 | [실패 종결](ep155/report.md) → [감사](ep155/audit.json) · [브라우저](ep155/browser.json) · [자원](ep155/resources.json); 7턴 스키마 오류·정상0/1 |
| JEV-35B-NVFP4 GPU0 동일 대진 | [실패 종결](ep154/report.md) → [감사](ep154/audit.json) · [반복 쌍](ep154/all-repeats.json) · [브라우저](ep154/browser.json) · [자원](ep154/resources.json); 8사전추론 반복성 실패·GLM0·본경기 미실행1 |
| 새 GLM·JEV 디스크 상한 해제 | [보고](ep153/report.md) → [설정](ep153/settings.json) · [CPU](ep153/tests.xml) · [자원/배치](ep153/placement-tests.xml); disk=null·기록/기타한도 유지·새 호출0 |
| GLM JSON 구문 재시도·EX-094 | [완료 보고](ep152/report.md) → [CPU](ep152/final-tests.xml) · [실패 재생](ep152/replay-failure.json) · [실제 감사](ep152/audit.json) · [브라우저](ep152/browser.json) · [GPU/반환](ep152/resources.json); 정상1경기/64턴 패배·실제구문재시도0 |
| 변경 수행 지시문 실제 샘플1경기 | [실패 종결](ep151/report.md) → [감사](ep151/audit.json) · [브라우저](ep151/browser.json) · [자원](ep151/resources.json) · [행동 비교](ep151/comparison.json); 14턴 GLM JSON 오류·정상0/1·부분기록 보존 |
| GLM·JEV 탭·리플레이 통합 뷰어 | [완료 보고](ep150/report.md) → [전수 대조·브라우저](ep150/verification.json) · [브라우저 회귀](ep150/browser-tests.xml); 기존 EX-088/092 보존·새 호출/배틀0 |
| JEV 계획 목표 충족 확인 지시 | [보고](ep149/report.md) → [CPU 연결 검증](ep149/verification.json) · [기존 검사](ep149/tests.xml); 새 기본 지시·기존 동결 입력 보존 |
| EX-092 GLM planner–JEV 실제 샘플1경기 | [최종 보고](ep148/report.md) → [완료](ep148/completion.json) · [독립 감사](ep148/audit.json) · [브라우저](ep148/browser.json) · [자원](ep148/resources.json); 55턴 승리·1경기 범위 |
| Planner/JEV 후보 표시 이름 | [보고](ep147/report.md) → [완료](ep147/completion.json) · [저장입력 대조](ep147/saved-verification.json) · [화면](ep147/browser.json); ID/명령 보존·모의재생·실제 API/GPU/새배틀0 |
| Planner 역할·승리경로·자원 안내 | [완료 보고](ep146/report.md) → [검증](ep146/completion.json) · [메시지 미리보기](ep146/preview.json); 문헌/CPU 검증·실제 API/GPU/새배틀0 |
| GLM planner–JEV 호출/프롬프트 설정 환경 | [최종 보고](ep145/report.md) → [완료](ep145/completion.json) · [CPU 검사](ep145/cpu-tests.log) · [브라우저](ep145/browser.json); 모의/CPU 검증·실제 API/GPU0 |
| EX-091 MiniCPM5-2B-Jev·EX-089 비교 | [최종 보고](ep144/report.md) → [완료](ep144/completion.json) · [독립 산술](ep144/final-arithmetic.json) · [봉인/반환/알람](ep144/final-integrity.json); GPU0·계산기 포함 새32/16쌍·패키지 탐색 비교 |
| EX-090 피해 예측 제거·EX-089 비교 | [최종 보고](ep143/report.md) → [완료](ep143/completion.json) · [독립 산술/봉인/반환](ep143/final-check.json) · [디스크](ep143/disk-accounting.json); 새32/16쌍·과거 결과 재사용·스피드 유지 |
| EX-088/089 Damage-calc 표시 판본 | [완료 보고](ep142/report.md) → [전수 대조·브라우저·봉인/디스크](ep142/completion.json); 기존 봉인 보존·저장 시나리오 연결·새 계산/모델 호출0 |
| EX-088/089 교정v6 신규64평가 | [최종 보고](ep141/report.md) → [완료](ep141/completion.json) · [3종 비교](ep141/final-comparisons.json) · [봉인](ep141/final-integrity.json) · [반환](ep141/closure.json); 각32경기/16쌍·이전 중단 결과 별도 보존 |
| EX-086/087 공개 정보 v6·턴 로그·중단/교정 | [중단 보고](ep140/report.md) → [종결/분모](ep140/completion.json) · [입력 교정](ep140/poststop-input/report.md) · [집계 교정](ep140/poststop-accounting/correction.json); 27B실패1/미실행31·9B미실행32·추가GPU0 |
| EX-085 JEV-9B 단일 Choice 동일32 평가 | [최종 보고](ep139/report.md) → [완료/봉인/자원 반환](ep139/completion.json) · [공유 환경 계수 보완](ep139/disk-accounting.json); 새32경기·EX-083 공통쌍 비교 |
| EX-084 Quyet-Medium 2단계 동일32 평가 | [최종 보고](ep138/report.md) → [완료/봉인/자원 반환](ep138/completion.json); 새32경기·단계별 사용량·EX-083 공통쌍 비교 |
| EX-083 JEV-27B 4GPU 계승 평가 | [최종 보고](ep137/report.md) → [완료/봉인/자원 반환](ep137/completion.json); 정상23 계승·신규9·고유32/16쌍·원실패 포함33시도 |
| EX-082 JEV-27B 개선 입력 동일32 재현·자원 중단 | [중단 보고](ep134/report.md) → [최종 감사](ep134/live-audit.json)·[최종 오프라인 뷰어](ep134/viewer-browser-v2.json)·[종결 확인](ep134/closure.json) · [메모리 후속 교훈](ep134-lessons/report.md) |
| EX-079 종료조건 추가 학습·독립시험 | [최종 보고](ep131/report.md) · [종결 검증](ep131/completion-verification.json); 주효능 미달·초기상대 우세 |
| EX-078 첫라운드 복구·학습 완료 및 모델 전후 비교 | [복구 보고](ep129/report.md) · [동일 관측 비교](ep130/report.md); 독립 성능 미평가 |
| EX-076 고정 A/B GPU 실험·교정 재개·예산 중단 | [최종 보고](ep125/budget-report.md) → [비용 하한](ep125/pilot-cost-lower-bound.json)·[종결](ep125/budget-closure.json); 학습/test 미실행 |
| 고정 A/B 공개 상태 MCTS 구현·CPU 합성 검증 | [EP-124 보고](ep124/report.md) → [검사 로그](ep124/tests-final.log)·[CLI 검증](ep124/verify.json); 실제 실험 미실행 |
| EX-070 Kev 후속 정책 질문·동일 첫 대진1경기 진단 | [최종 보고](ep113/report.md) → [동일 입력 비교](ep113/comparison.json)·[오프라인 뷰어](ep113/browser.json)·[봉인/정리](ep113/closure.json) |
| EX-069 Kev 기존 test20 본 평가·기준선 참고 비교 | [최종 보고](ep112/report.md) → [독립 집계](ep112/independent-summary.json)·[오프라인 뷰어 확인](ep112/browser-v2.json)·[봉인/정리](ep112/closure.json) |
| EX-068 Kev fused 연결 수락 완료·원 실패 보존 | [최종 보고](ep111-fused/report.md) → [완료 검증](ep111-fused/verification-final.json)·[독립 감사](ep111-fused/independent-audit.json)·[오프라인 뷰어](ep111-fused/viewer-offline.json) |
| EX-068 원 unmerged dev 예측 gate 실패 | [중단 보고](ep111/report.md) → [서버 응답](../../../.pokechamp-data/kev/ex068-v2/validation/server-probe.json)·[토큰 대조](ep111/token-diagnosis.json)·[종료](ep111/closure.json) |
| EX-067 Abyssal Tera 보완 수집·뷰어·학습 자료 복사 | [최종 보고](../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/report.md) → [완료 검증](ep110/completion.json)·[원 파일럿 보존](ep110/parent-v1-preservation.json)·[브라우저 검증](../../../.pokechamp-data/experiments/ex067-abyssal-tera-joint-q/versions/public-tera-v2/final/browser-verification.json) |
| EX-065 공동 q 수집·학습 자료 복사 | [동결 최종 보고](../../../.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5/final/report.md) → [완료/봉인](../../../.pokechamp-data/experiments/ex065-joint-q/completion-verification.json)·[복사 검증](ep107/copy-training-verification.json)·[복사 종료](ep107/copy-training-closure.json) |
| Qwen 후보 상태·결정별 지침·저장3조건 비교 | [EP-106 보고](ep106/report.md) → [모델 원문 검토](ep106/model-output-review.md)·[수집/종료](ep106/collection-verification.json)·[종료 후 보정](ep106/post-correction-validation.md)·[오프라인 화면](../../../exports/qwen_candidate_state/ex064/index.html) |
| 뷰어 실제 행동 이름 표시 | [EP-105 보고](ep105/report.md) → [Qwen 오프라인](ep105/qwen-offline.json)·[JEV 오프라인](ep105/jev-offline.json)·[보존](ep105/preservation.json) |
| EX-063 Qwen 학습 원대진·정정 전수 감사 | [EP-104 보고](ep104/report.md) → [원 감사 실패](ep104/audit-original.json)·[정정 감사](ep104/audit-corrected.json)·[정정 결과](ep104/result-corrected.json)·[뷰어 검증](ep104/viewer-offline.json)·[정리](ep104/cleanup.json) |
| EX-062 Qwen 로컬 서빙·GPU 대조·배틀 미완료 | [EP-103 보고](ep103/report.md) → [GPU 대조](ep103/gpu-probe/verification.json)·[원 실패](../../../.pokechamp-data/qwen/ex062-live/result.json)·[교정](ep103/source-v2/manifest.json)·[정리](ep103/closure.json) |
| EX-061 Qwen3.5-4B 첫 LoRA·조건부 q 개발 검증 | [EP-102 보고](ep102/report.md) → [전수 검사](ep102/final-verification.json)·[source-v1](ep102/source-v1/hashes.json)·[메타데이터 교정](ep102/source-v2/manifest.json)·[봉인/정리](ep102/closure.json) |
| EX-060 한 경기22상태·167행동·5,344분기 수집 | [EP-101 보고](ep101/report.md) → [독립 점검](ep101/independent-review.md)·[뷰어 검증](ep101/viewer-verification.json)·[봉인/정리](ep101/closure.json) |
| RLCD-Lite 독립 명명 환경·CUDA 호환 설치·모델 검증 | [EP-098 보고](ep098/report.md) → [호환 diff](ep098/compatibility-diff.patch)·[활성화](ep098/activation-check.json)·[환경 검증](ep098/environment-check.json) |
| EVE-RLCD 독립 명명 환경·공개 모델 검증 | [EP-097 보고](ep097/report.md) → [활성화](ep097/activation-check.json)·[환경 검증](ep097/environment-check.json)·[모델 출처](ep097/model-download.json) |
| EX-059 자기 벤치 축약 동일32·EX-058 비교 | [EP-095 보고](ep095/report.md) → [전후 비교](ep095/comparison.json)·[감사](ep095/live-audit.json)·[뷰어 검증](ep095/viewer-verification.json)·[정리](ep095/closure.json) |
| EX-058 개선 입력 동일32·EX-057 비교 | [EP-094 보고](ep094/report.md) → [전후 비교](ep094/comparison.json)·[감사](ep094/live-audit.json)·[뷰어 검증](ep094/viewer-verification.json)·[정리](ep094/closure.json) |
| JEV 오프라인 입력·세트별 스피드 불확실성·축약 비교 | [EP-093 보고](ep093/report.md) → [현재 샘플](ep093/certainty-v1/samples.json)·[검증](ep093/verification.json)·[요구별 완료 감사](ep093/completion-audit.json) |
| 기술별 피해량 범위 오프라인 샘플 | [EP-082 비교 보고](ep082/report.md) → [선택/크기/출처](ep082/samples.json)·[검증](ep082/verification.json)·개별 전후 JSON/원시 계산 |
| EX-057 JEV v3 동일32·v2 전후 비교 | [EP-081 보고](ep081/report.md) → [전후 비교](ep081/comparison.json)·[감사](ep081/live-audit.json)·[뷰어 검증](ep081/viewer-verification.json)·[정리](ep081/closure.json) |
| EX-056 JEV v3 동일32·v2 전후 비교 | [EP-080 보고](ep080/report.md) → [전후 비교](ep080/comparison.json)·[감사](ep080/live-audit.json)·[뷰어 검증](ep080/viewer-verification.json)·[정리](ep080/closure.json) |
| EX-054 JEV v3 동일32·v2 전후 비교 | [EP-077 보고](ep077/report.md) → [전후 비교](ep077/comparison.json)·[감사](ep077/live-audit.json)·[뷰어 검증](ep077/viewer-verification.json)·[정리](ep077/closure.json) |
| provider 오류 재시도3회·원장/기한/취소·과거 감사 | [EP-076 보고](ep076/report.md) → [검증](ep076/verification.json)·[검사](ep076/tests-final.log)·[과거 감사](ep076/historical-audit.json) |
| EX-053 JEV v3 동일32·v2 전후 비교 | [EP-075 보고](ep075/report.md) → [전후 비교](ep075/comparison.json)·[감사](ep075/live-audit.json)·[뷰어 검증](ep075/viewer-verification.json)·[정리](ep075/closure.json) |
| JEV v3 기본 지식·효과 사전·EX-052 오프라인 대조 | [EP-074 보고](ep074/report.md) → [재생성/크기](ep074/replay/result.json)·[검사](ep074/tests.log)·[보존](ep074/replay/preserved-files.json) |
| EX-051 교정 JEV 입력 실제2경기 | [EP-071 보고](ep071/report.md) → [실제 감사](ep071/live-audit.json)·[선봉 검사](ep071/live-leads.json)·[뷰어 검증](ep071/viewer-verification.json)·[정리](ep071/closure.json) |
| EX-050 JEV 선봉 입력 사후 교정·오프라인 검증 | [EP-070 보고](ep070/report.md) → [전후 입력](ep070/replay/corrections.json)·[과거 감사](ep070/historical-audit.json)·[보존](ep070/preservation-final.json) |
| EX-046 다운로드용 단일 폴더·ZIP | [EP-060 보고](ep060/report.md) → [이동 후 검증](ep060/verification.json)·[파일 hash](ep060/package.json) |
| EX-046 비동기 교정본 공식 관측 선봉 비교 완료 | [EP-059 최종 보고](ep059/final-report.md) → [전수 검증](ep059/final-verification.json)·[점수/종료 대조](ep059/closure-audit.json)·[manifest](ep059/final-manifest.json) |
| 공식 관측 비동기 완료 경계 교정 | [EP-058 보고](ep058/report.md) → [검증 viewer](ep058/index.html)·[전수 동등성](ep058/saved-equivalence.json)·[로컬 동시 검증](ep058/local-summary.json)·[봉인](ep058/final-manifest.json) |
| EX-045 공식 관측 선봉 비교·추적기 처리 오류 중단 | [EP-057 최종 보고](ep057/final-report.md) → [원인](ep057/input-defect.json)·[오프라인 재현](ep057/defect-diagnostic.json)·[manifest](ep057/final-manifest.json) |
| 공식 관측 B/B2 통합·새 기본값 | [EP-056 보고](ep056/report.md) → [전수/로컬 viewer](../../../.pokechamp-data/official-observation/ep056/index.html)·[준비/호환](ep056/default-preparations.json)·[보존/자원](ep056/preservation-and-resources.json) |
| 플레이어별 parser/B2/공식 클라이언트 관측 추적 진단 | [EP-055 보고](ep055/report.md) → [최초 반사 차이](ep055/magic-bounce.json)·[검증](ep055/verification.json)·[manifest](ep055/final-manifest.json) |
| EX-044 사전 검사 생략 본실험·반사 기술 입력 결함 | [EP-054 최종 보고](ep054/final-report.md) → [원인](ep054/input-defect.json)·[정정 근거](ep054/report-correction.json)·[manifest](ep054/final-manifest.json) |
| EX-043 교정 B2 개선 선봉·설정 오류 중단 | [EP-053 최종 보고](ep053/final-report.md) → [정정 근거](ep053/report-correction.json)·[전수 감사](ep053/poststop-input-audit.json)·[manifest](ep053/final-manifest.json) |
| Court Change·EX-042 전체 입력 감사·사후 무효 정정 | [EP-051 보고](ep051/report.md) → [정정 분석](ep051/impact.md)·[전수 분모](ep051/final-summary.json)·[최종 검증](ep051/final-verification.json)·[manifest](ep051/manifest.json) |
| 선봉 전략·Dex 규칙 독립 개선 | [EP-050 보고](ep050/report.md) → [32선봉 재생](ep050/offline-v2/replay.json)·[주장 사례](ep050/offline-v2/claim-cases.json)·[봉인](ep050/manifest.json) |
| 공급자 오류 재시도·EX-042 정상 경기 목록 | [EP-049 보고서](ep049/report.md) → [테스트 범위](ep049/test-coverage.json)·[로컬 검증](ep049/local-v1/verification.json)·[브라우저](ep049/browser-results.json)·[보존](ep049/preservation-final.json)·[manifest](ep049/manifest.json) |
| EX-042 공급자4+4 B2 선봉32 | [EP-048 최종 보고서](ep048/final-report.md) → [최종 감사 v2](ep048/final-audit-v2.json)·[실패 영향](ep048/failure-impact.json)·[manifest](ep048/final-manifest.json) |
| 응답 대기·연결 오류 재시도 | [EP-047 보고서](ep047/report.md) → [전체 회귀](ep047/final-full-tests.log)·[로컬 검증](ep047/local-v3/verification.json)·[과거 봉인](ep047/historical-seals.json)·[manifest](ep047/manifest.json) |
| 배틀·선봉 구조와 상세 효과 사전 | [EP-046 보고서](ep046/report.md) → [전수 입력 감사](ep046/offline-complete/report.json)·[실제 모의 전송](ep046/wire-audit-final.json)·[봉인 목록](ep046/manifest.json) |
| EX-041 Z.ai 기본 동시성4·B2 선봉32 | [EP-045 최종 보고서](ep045/final-report.md) → [구현·로컬 검증](ep045/implementation-report.md)·[독립 감사](ep045/final-audit.json)·[manifest](ep045/final-manifest.json) |
| EX-040 Z.ai B2 선봉32 | [EP-044 최종 보고서](ep044/final-report.md) → [독립 감사](ep044/final-audit.json)·[manifest](ep044/final-manifest.json)·[429 원발생](ep044/rate-limit-origin.json) |
| B2 선봉 실험·감시 전체 종료 | [종료 기록](ep041/closure/report.md) → [종료 감사](ep041/closure/shutdown-audit.json)·[종료 manifest](ep041/closure/manifest.json) |
| B2 선봉 실제 비교·사용자 보류 시점 부분 결과 | [EP-041 부분 보고서](ep041/held-report.md) → [정정 근거](ep041/output-recovery-evaluation-correction.json)·[부분 감사](ep041/held-reconciliation-audit.json)·[manifest](ep041/held-manifest.json) |
| B2 선봉 구현·로컬 검증과 미승인 후속안 | [EP-040 보고서](ep040/report.md) → [요건별 감사](ep040/completion-audit.json)·[source 보존](ep040/source-preservation.json)·[봉인 목록](ep040/manifest.json) |
| 계산기 감사의 최종 검증 | [EP-023 보고서](ep023/report.md) → [최종 검증](ep023/final-verification.json)·[검증 범위](ep023/verification-matrix.json) |
| 과거 입력 오염·의존 비교·주석의 적용 한계 | [별도 정정 분석](ep023/impact.md) → 필요 행만 [impact.json](ep023/impact.json)과 대조 |
| 진단기 자체 실패와 정정 연결 | [EP-023 근거와 방법](ep023/report.md#근거와-방법) → 수정 전 [replay-before](ep023/replay-before/index.json), 정정한 [replay-baseline](ep023/replay-baseline/index.json), [최종 replay](ep023/replay-final/index.json) |
| EP-037 원자료 보존 기준 manifest | [원 보존 결과](ep037/preservation-result.json) → [manifest 연결 보완](ep039/ep037-manifest-recovery.md) |

중간 후보 replay·반복 시험 로그는 해당 보고서가 지목할 때 읽는다. 일상 읽기에서 제외해도
실패·정정 근거로서의 의미는 유지된다. 원자료·동결 protocol·최종 검증·독립 기준을 크기나
파일명만으로 불필요하다고 판단하지 않는다. 이번 정리에서 기존 자료는 이동·삭제하지 않았다.
