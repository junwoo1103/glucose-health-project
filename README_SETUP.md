# GitHub Pages 배포 방법

이 폴더의 **내용 전체**를 GitHub 저장소 `glucose-health-project`의 루트에 올리세요.

최종 구조는 다음처럼 보이면 됩니다.

```text
glucose-health-project/
├── index.html
├── README_SETUP.md
├── data/
│   └── meals.json
├── scripts/
│   └── fetch_meals.py
└── .github/
    └── workflows/
        └── update-meals.yml
```

## 1. NEIS 인증키는 저장소 소유자만 한 번 등록

학생은 인증키를 입력하지 않습니다.

GitHub 저장소에서:

`Settings → Secrets and variables → Actions → New repository secret`

- Name: `NEIS_API_KEY`
- Secret: 나이스 교육정보 개방 포털에서 발급받은 인증키

사이트 HTML에는 인증키가 들어가지 않으며 GitHub Actions만 Secret을 사용합니다.

## 2. GitHub Pages 배포 방식을 Actions로 설정

저장소에서:

`Settings → Pages → Build and deployment → Source → GitHub Actions`

으로 설정하세요.

## 3. 최초 1회 실행

`Actions → Update meals and deploy Pages → Run workflow`

를 눌러 실행하세요.

워크플로는 다음을 한 번에 수행합니다.

1. NEIS에서 양천고등학교 중식 데이터를 가져옴
2. `data/meals.json` 갱신
3. 변경된 급식 데이터를 저장소에 자동 커밋
4. 최신 `index.html`과 `data/meals.json`으로 GitHub Pages를 즉시 재배포

따라서 자동 급식 갱신 커밋이 Pages 재배포를 유발하는지 여부에 의존하지 않습니다. 같은 workflow가 직접 Pages 배포까지 수행합니다.

## 4. 자동 실행

매일 한국시간 오전 6시 10분에 workflow가 자동 실행되어 급식 데이터와 사이트를 함께 갱신합니다.

## 간식 선택 문제 수정

간식 선택 항목은 JavaScript가 실행된 뒤 동적으로 생성하는 대신 `index.html` 자체에 기본 옵션을 넣었습니다.
따라서 페이지가 열리면 다음 5종이 즉시 보입니다.

- 블루 레몬에이드
- 뽕따 소다맛
- 꽃게랑 오리지널
- 꼬꼬스낵
- 프링글스 오리지널 53 g

JavaScript에서는 선택된 항목의 영양정보와 실험 보정값만 갱신합니다.

## 주요 사이트 기능

- 양천고등학교 날짜별 급식 자동 로드
- 학생별 혈당 민감도: 낮음 / 중간 / 높음
- 급식만 vs 급식 + 간식 혈당곡선 비교
- 최고혈당 추가 상승량, 140/180 mg/dL 이상 체류시간 변화 설명
- 최소 간식 대기시간을 0~240분에서 5분 간격으로 계산
- 거꾸로 식사법 설명 및 적용 전후 수치 비교
- 약동학의 흡수속도상수 `k_a`, 회복/제거상수 `k_e`, 구획 모델 설명
