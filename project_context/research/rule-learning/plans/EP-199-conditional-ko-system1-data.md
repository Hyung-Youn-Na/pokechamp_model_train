# EP-199 — 조건부 확정 KO 판정 자료

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 사용자 “조건부 확정 KO 학습 데이터로 표시해줘.” / D176
- 연구선/checkout/commit: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존변경보존.
- 원천: EP198 봉인자료 읽기전용. 관측KO를확정KO로재명명하지않는다.
- 소스: integration/conditional_ko_system1/, scripts/conditional-ko-system1-data, CPU Node/Python tokenizer.
- 출력: /mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/conditional-ko-system1/v1
- 제공: /workspace/exports/conditional-ko-system1-v1 및ZIP, evidence/ep199.

## 범위와 조건

공개리플레이에정확한원세트·비급소피해범위가없어기존3981건은조건부판정근거미확인으로별도표시한다.
이 표시는실제원경기의KO불가능/정보부족정답이아니라변환자격metadata다. 기존관측라벨·봉인은보존한다.
새학습문제는리플레이공개prefix에서얻은공격자종/대상종/주어진기술을원천으로하는명시적제어계산장면이다.
원경기의숨은세트복원이나실제HP를추정하지않는다. 원경기의조건부KO라벨이라고주장하지않는다.

계산조건: Gen9, 양측level100/IV31/EV0/Hardy, item없음/No Ability, 상태/boost/날씨/terrain/screens/volatile없음,
Tera없음, 명중판정성공·비급소·1타, 면역은적용, HP1인경우등정확한최대HP는engine값.
고정위력·단타·일반공격만채택하고변동위력/다단/고정피해/강제급소/기술변환·특수콜백은보수적으로제외한다.
16개피해난수85..100을실제Showdown getDamage로계산하고각정수피해와최소/최대범위를보존한다.
범위의경계에따라정확한목표HP를제어해학습문항을만든다. 해당HP가실제리플레이HP라고표시하지않는다.

입력은명시조건·정확한대상HP·검증된피해범위이다. 학습과제는피해계산기출력의KO판정이며독립피해량예측이아니다.
라벨: min>=HP면조건부확정KO, max>=HP>min이면난수KO가능, max<HP면조건부KO불가.
원시3981의관측급소/KO라벨은새조건·라벨계산에사용하지않는다. 근거없는행은훈련정답으로변환하지않는다.

## 완료 기준

- [x] 원자료봉인·원판정과새합성조건의분리·대상종/기술출처와제외분모
- [x] engine16roll·면역0·경계동치·직접HP기절조건의독립검증
- [x] System1유일정답·native token/metadata누출·저장대응·CPU선택CE
- [x] 별도지정자료/원자료적격표시·사용안내/manifest/ZIP·상태/색인완료

## 진행·중단

INDEX/CHARTER/매뉴얼·현재/중단색인·규칙학습설계·EP198/D175의해석경계를확인했다.
데이터생성전용으로학습/모델forward/GPU/서빙변경0, EX/C047해당없음.
검증실패시새내보내기차단·원자료/실패근거보존.기존평가재개없음.

## 결과

3698개 원천종/기술프로필 중2329개를지원하고1369개를명시사유로제외했다.
16난수와유효HP경계검증으로8582문항을생성했다: 조건부확정2290/난수가능2200/불가4092.
원자료3981건은조건부근거미확인(라벨null·학습target사용false)으로별도표시했다. 원관측자료재라벨0.
전수16롤·엔진HP적용/경계동치·native template/누출/저장대응, CPU경계7/오류3/선택CE검사통과.
독립에이전트가23문항과기존3981건의미판정표시를검토했다. 입력875~906토큰이며모델forward/학습/GPU0.
[최종보고](../../../exec-plans/evidence/ep199/report.md) · [사용안내](../../../../exports/conditional-ko-system1-v1/README.md) ·
[한국어판정CSV](../../../../exports/conditional-ko-labels-v1.csv).
새문제는명시조건과제공된피해범위의판정이며원경기의숨은세트/HP복원또는독립피해량예측성능을뜻하지않는다.
