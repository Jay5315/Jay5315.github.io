# 차곡 · 재경관리사 문제은행

**서비스:** https://jay5315.github.io/jaegyeong/

**다른 AI가 이어서 작업할 때:** [HANDOFF.md](HANDOFF.md)를 먼저 읽으세요.

**개념 노트:** [파트별 핵심 개념·학습 팁](CONCEPT_NOTES_PLAN.md) — 74개 중 15개 파트 작성, 나머지는 '준비 중' 표시

과목·74개 파트별 기출 풀이, 파트별 핵심 개념 노트, 즉시 채점, 오답 노트, 즐겨찾기, 이어 풀기, 기록 백업·복원을 제공하는 정적 웹앱입니다. HTML/CSS/JavaScript만으로 실행되며 외부 API나 서버 애플리케이션, 프런트엔드 빌드가 필요하지 않습니다.

## 폴더

| 경로 | 용도 |
|---|---|
| `index.html`, `assets/app.css`, `assets/app.js` | 실행 화면과 기능 |
| `assets/bank-data.js` | 웹앱용으로 생성한 데이터 번들 |
| `sources/`, `images/` | 원본 PDF·답안과 문항 이미지 |
| `data/` | 원본문항, 중복·변형 매핑, 파트 분류, 검토 목록, 개념 노트(`concept-notes.json`) |
| `scripts/` | 추출·중복 정리·분류·번들 생성·테스트·패키징 |
| `review.html` | 중복 후보·원문 보류·분류 검토용 화면 |
| `reports/` | 검토 결과, 문항 목록 CSV, 화면 확인 자료 |
| `research/intake/` | 초기 파일 수신·분석 기록 (역사 자료) |

## 실행

저장소 루트에서 아래 명령을 실행하고 `/jaegyeong/` 경로로 접속합니다.

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

메인 웹앱은 일반 스크립트 번들이어서 폴더 전체를 받은 뒤 `index.html`을 로컬 브라우저에서 열도록도 구성했습니다. 관리형 브라우저의 파일 실행 제한 및 모바일 OS에 따라 HTTP(S)가 필요할 수 있습니다. `review.html`은 JSON을 fetch하므로 HTTP 서버가 필요합니다.

## 데이터 재생성

아래 명령은 저장소 루트 기준이며 Python 3.12 환경에서 확인했습니다. 일반 웹앱 이용에는 Python 패키지가 필요하지 않습니다.

```sh
python3 -m venv jaegyeong/.venv
. jaegyeong/.venv/bin/activate
python -m pip install -r jaegyeong/requirements.txt

# 기존 문항 데이터를 사용해 중복·변형·분류·웹앱 번들을 모두 갱신
python jaegyeong/scripts/build_bank.py

# 분류만 갱신 (웹앱 번들도 함께 갱신)
python jaegyeong/scripts/classify_parts.py

# 웹앱 번들만 갱신
python jaegyeong/scripts/build_app_data.py

# PDF부터 다시 추출해야 할 때만 실행: 이미지와 파생 데이터를 다시 만듦
python jaegyeong/scripts/build_bank.py --reextract
```

원본 위치는 `data/source-exams.json`에 상대 경로로 저장했습니다. 과거 업로드 파일이나 이 대화, `/workspace/attachments/`가 없어도 재생성할 수 있습니다. SHA-256은 `data/source-manifest.json`에 있습니다.

## 검증

```sh
python jaegyeong/scripts/test_bank.py
python jaegyeong/scripts/test_parts.py
python jaegyeong/scripts/test_concepts.py

# 브라우저 테스트용 추가 설치
python -m pip install -r jaegyeong/requirements-dev.txt
python -m playwright install chromium

# 위 HTTP 서버가 별도 터미널에서 실행 중일 때
python jaegyeong/scripts/test_app.py
python jaegyeong/scripts/test_browser.py
```

기본 테스트 주소는 `http://127.0.0.1:8000/jaegyeong/`입니다. 다른 포트나 앱 폴더를 직접 제공하는 경우 `APP_BASE_URL` 환경변수로 바꿉니다. 설치된 시스템 `chromium`을 우선 사용하며, 없으면 Playwright가 설치한 브라우저를 사용합니다. 테스트 스크린샷은 Git에서 제외한 `_artifacts/`에 저장합니다.

```sh
APP_BASE_URL=http://127.0.0.1:8002/jaegyeong/ python jaegyeong/scripts/test_app.py
python jaegyeong/scripts/package_app.py
```

패키지는 Git에서 제외한 `jaegyeong/dist/`에 생성됩니다. 이미지·PDF가 이미 저장소에 있으므로 대용량 ZIP이나 추출 캐시를 다시 커밋할 필요가 없습니다.

## 현재 범위와 기록

원본 4,560문항, 중복 정리 4,322항목, 학습 가능 4,321항목, 기본 유형 대표 4,144항목입니다. 중복 유사 후보 1,649쌍과 파트 분류 검토 126항목은 추가 검토 대상으로 보존합니다. 자세한 기준은 [중복 정리 결과](reports/중복정리결과.md)와 [파트 분류 결과](reports/파트분류결과.md)를 확인하세요.

## 개념 노트

편집 원본은 `data/concept-notes.json`이며 `build_app_data.py`가 번들에 넣습니다(분류·문항 데이터는 바뀌지 않음). 노트마다 `review_status`를 둡니다.

| 상태 | 뜻 | 현재 |
|---|---|---|
| `source_checked` | 법령 조문을 판본별로 원문 대조 (전문가 검수 전) | 세무 6개 (C02·C08·C11·I02·V03·V04) |
| `calc_checked` | 계산식·예시 검증, 외부 출처 미대조 | 원가 5개 (M05·M07·M08·M11·M14) |
| `needs_source` | 초안, 회계기준 원문 대조 필요 | 재무 4개 (F04·F05·F15·F21) |

세법 노트는 2024·2025·2026년 시행 판본을 비교했고, 연도별로 다른 수치는 `year_table`에 연도 열로 나눴습니다(예: 2026년 법인세율 1%p 인상, 배당가산율 11%는 2027년 지급분부터). 문제의 `taxYear`와 노트 대조 범위를 비교해 풀이 화면에 표시합니다. 출처·확인 방법은 파일의 `verification`, `sources`에 있습니다.

개인 학습 기록은 `localStorage`의 `chagok.study.v1`에 저장합니다. GitHub에는 개인 오답·즐겨찾기 기록이 올라가지 않습니다. 브라우저나 기기를 바꾸기 전에 앱에서 백업하고 새 브라우저에서 복원하세요. 문항별 해설, 로그인, 자동 기기 동기화, 최신 법령에 따른 정답 재검증은 제공하지 않습니다.

## 배포

`main`에 반영하면 기존 GitHub Pages의 `pages build and deployment`가 실행됩니다. 해당 커밋의 배포 성공을 확인하세요. 원래 사이트의 `/`, `privacy.html`, `terms.html`, `style.css`는 문제은행과 별개입니다.
