# EP-198 — 실제 리플레이 KO 결과 예측 System 1 자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “실제 리플레이에서 KO 상황에 대한 system one 판단 문제” 생성 요청.
- 해석: 공개정보로확정KO를보장하기어려워실제관측된직접KO여부예측을기본으로진행한다고고지했다. 선택적질문도제시했으며답변도착시반영한다.
- 관련: D175, RD오염/정보경계, C055의시점원칙(기존EX071학습조건은승계하지않음), EP193선택CE.
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존변경보존.
- 원천: 보관 milkkarten/pokechamp revision b5820ff5d0c8d5e5cec692d55f756b6e5a66a203, train Parquet만읽기전용.
- 소스: integration/replay_ko_system1/, scripts/replay-ko-system1-data; CPU PyArrow/NodeDex/Python tokenizer.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/replay-ko-system1/v1
- 제공: /workspace/exports/replay-ko-system1-v1 및ZIP, evidence/ep198. 외부게시/추가다운로드0.

## 문제·라벨

공개관전자정보의실제기술실행직전prefix와조건으로제시한공격자/기술/대상만입력한다.
후보는해당공격의직접피해로대상이KO된실제관측결과/그렇지않은실제관측결과2개다.
미래move행에서공격ID/대상을추출하는것은명시적조건이며이동작의선택확률·선택정답을예측하지않는다.
이후damage/faint/결과로그는라벨/evidence전용이다. 실현된단일결과를확정KO/KO확률100%/최적행동으로바꾸지않는다.
미공개능력치·세트·원HP·난수는복원하지않고공개HP표시와이력만쓴다. 모델은공개관전자뷰를받는다.

직접target damage0fnt와같은공격프레임의faint가일치해야양성이다.
명확한생존직접타격 또는 miss/immunity/protection은음성후보로구분한다.
잔여독/날씨/설치물·반동/연계출처혼동·지연공격·변신/일루전·불명확상황은보수적으로제외/사유기록한다.
현재Gen9OU합법성이나전체후보행동의반사실KO를주장하지않는다. 기록당시gamemode/gen정보에따른역사적Gen9OU다.

## 채택·분할·한도

train샤드의정렬순서로Gen9OU 최대10000경기를검토하고, 양성/음성각1개이상있는최대1000경기를채택한다.
경기당hash정렬로양성최대2/음성최대2, 토큰6144초과는절단없이제외한다. 규모는상한이며실제분모/제외를보고한다.
경기ID/공개로그중복제거. 기존로컬원경기ID와EX071 validation/test팀서명 및기존평가팀서명을보수적으로제외한다.
원dataset test는읽지않고수정0. 알려지지않은crossdataset중복/팀근접성해소를보장하지않는다.
모두학습pool, 경기ID/양팀서명metadata로추후분할을보조한다. 양성/음성제한표집이자연KO빈도를보존하지않음을명시한다.
선수명·닉네임·채팅·레이팅·경기승패/ID·미래결과를모델입력에서제거한다.
허용된전체공개mechanics prefix를보존하고모델입력절단/후반정보소급0.

## 완료 기준

- [x] 출처train정체성·선별분모·중복/알려진평가오염제외·예외parser검증
- [x] 직접KO라벨·프레임경계·공개prefix/미래분리·개인식별표시제거 전수대조
- [x] 실제양성/음성/복수타격/회피 등대표사례의독립검토와무절단native토큰/저장대응
- [x] System1선택/토큰·canonical/evidence·source좌표·안내/manifest/ZIP·상태/색인종결

## 실행·중단

자료전용CPU작업이며모델forward/학습/GPU/API/새배틀/기존서빙변경0. EX/C047해당없음.
INDEX/CHARTER/매뉴얼·현재/중단색인·자료매뉴얼·EP100/166·규칙/정책학습설계와계약을확인했다.
오류시내보내기를차단하고원자료/실패/교정근거보존. 기존Blocked실험재개·실험시계/재경기해당없음.

## 결과

실제1000경기/3981문항을생성했다. 직접KO1983, 생존타격1817/빗나감71/면역51/보호59의비KO1998이다.
train1샤드의16312행중Gen9OU1135경기를검토했고 알려진평가팀27경기와양쪽라벨부족108경기를제외했다.
길이초과후보40개를절단없이제외했다. 입력606~6127토큰, 숨은세트복원/정답completion0.
17parser검사·독립구현원본라벨감사3981·native입력/누출/저장대응·CPU선택CE를통과했다.
독립에이전트가11대표유형+추가20문항(29경기)을원본에대조했다. 인간블라인드검토는아니다.
[최종보고](../../../exec-plans/evidence/ep198/report.md) · [독립검토](../../../exec-plans/evidence/ep198/independent-review.json) ·
[사용안내](../../../../exports/replay-ko-system1-v1/README.md).
관측결과예측이며확정KO/확률보정/최적행동자료가아니다. 전부학습pool이고실제모델학습/forward/GPU/서빙변경0.
