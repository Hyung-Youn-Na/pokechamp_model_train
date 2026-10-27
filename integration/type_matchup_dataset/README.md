# Gen9 타입 상성 데이터 생성기

[EP192](../../project_context/research/rule-learning/plans/EP-192-gen9-type-matchup-dataset.md)의 CPU 생성/검증/내보내기 전용 경로다.
기존 Showdown dist와 Python 표준 라이브러리를 사용한다. 환경 설치·GPU·모델 호출은 없다.

```bash
scripts/type-matchup-dataset --output /path/to/new/dataset
```

기존 경로를 덮어쓰지 않는다. Python 타입표 곱셈과 독립 Node Pokemon/Dex oracle이 전수 일치한 뒤 SFT/선택형/CSV를 내보낸다.
기본3078과 확장61902가 서로 겹치지 않는다. 실패 시 출력은 불완전 자료로 보존하며 새 경로에서 교정한다.
자료 범위·학습 필드·평가 경계는 [데이터 안내](DATASET_README.md)를 따른다.
