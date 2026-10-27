# EP-211 — System One JevK5 선택 어댑터 실전32

- 상태: Completed
- 생성일: 2026-10-23
- 승인: 현재 사용자 GPU1·2·3의32경기테스트 지시 / D186
- 조건 원문: [EX123](../experiments/EX-123-jevk5-system1-battle32.md)
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5. 기존dirty변경보존.
- 관련: EX116/EP203 완료어댑터, EX114/EP191·EP190서빙, EP210 GPU0/8107분리, EP140/183중단보존. 공통RD/C018/046/047·규칙학습계약·UIv1.
- 환경·출력·자원·복구: EX123. 새 integration/jevk5_system1_battle 및scripts wrapper만추가; 기존실행기/봉인보존.

## 완료 기준

- [x] 새D/EP/EX·CPU검사·3shard 모의6경기·UI검증
- [x] 3GPU 동일adapter서빙·각6gate·동결/32경기/16쌍
- [x] 전수감사·비교보고·UIv1내보내기/상위목록·봉인·자원반환

## 진행

GPU1/2/3유휴, GPU0은다른연구사용중임을확인했다. 원본새LoRA의선택epoch2를사용한다. 실제경기/모델호출0.

- CPU25검사·UI4검사, 3shard의모의6경기 전수감사와 각각의이동후오프라인/원문/모바일/리플레이검증을통과했다. 전역목록의6고유링크·3shard 이동후탐색도통과했다. 실제모델호출0이며이제3GPU사전검사/본32경기에진입한다.

- GPU1/2/3의원본/선택adapter 정체성·native token·6요청씩총18gate를통과했다. 같은대표입력의서버간12비교에서선택은모두같았고확률최대차는0.057566859로진단기록했다. 숫자동일성을성공으로주장하지않는다. 동결된12/10/10경기병렬수집을시작했으며중간진행은EX123/progress.json에둔다.

## 실행 결과

정상 32/32, 5승0무27패, 완전16/16쌍. 실패0·무효0·미실행0. [최종 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-123/evidence/report.md) · [뷰어](/workspace/exports/battle_viewers/ex123/index.html). 과거 비교와 전이 한계는 보고서를 따른다.

- 최종독립확인: 원실행7521파일·뷰어1347파일 봉인 대조, 소유서버PID 종료 및3GPU잠금반환을 확인했다. GPU별최대38.420GiB·전체소유host최대27.796GiB. [한국어 최종 보고](../../../exec-plans/evidence/ep211/report.md) · [종결 확인](../../../exec-plans/evidence/ep211/closure.json). 추가모델호출/경기0.
