# 차곡 · 재경관리사 문제은행

**서비스:** https://jay5315.github.io/jaegyeong/

**다른 AI가 이어서 작업할 때:** [HANDOFF.md](HANDOFF.md)를 먼저 읽으세요.

**개념 노트:** [파트별 핵심 개념·학습 팁](CONCEPT_NOTES_PLAN.md) — 74개 중 52개 파트 작성(기존 15개 + 추가 37개), 나머지는 '준비 중' 표시

과목·74개 파트별 기출 풀이, 파트별 핵심 개념 노트, 즉시 채점, 오답 노트, 즐겨찾기, 이어 풀기, 기록 백업·복원을 제공하는 정적 웹앱입니다. HTML/CSS/JavaScript만으로 실행되며 외부 API나 서버 애플리케이션, 프런트엔드 빌드가 필요하지 않습니다. 글꼴은 Pretendard 웹폰트(jsDelivr CDN)를 쓰며, 불러오지 못하면(오프라인 ZIP 등) 시스템 한글 글꼴로 대체됩니다.

**문항 해설:** 총 2,854문항에 단계별 풀이·보기별 설명을 제공합니다(기존 30개 보존, 이번 추가 2,824개). 홈의 '해설 2854문항 풀기', 문제 목록의 '해설 있는 문제만', 채점 후 풀이, 오답 노트의 '해설'에서 확인할 수 있습니다. [해설 작성·검증 방법](EXPLANATIONS.md)을 참고하세요.

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
python jaegyeong/scripts/test_explanations.py

# 브라우저 테스트용 추가 설치
python -m pip install -r jaegyeong/requirements-dev.txt
python -m playwright install chromium

# 위 HTTP 서버가 별도 터미널에서 실행 중일 때
python jaegyeong/scripts/test_app.py
python jaegyeong/scripts/test_browser.py
python jaegyeong/scripts/test_explanations_app.py
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

현재 52개 파트가 작성되어 있습니다. 이번에는 실제 확인한 세무·원가 자료로 37개 노트를 추가했습니다. 출처 대조 43개, 일부 범위 미대조 표시 9개이며 아직 22개 파트는 준비 중입니다. 자세한 배정·범위는 `reports/concept-expansion.json`과 [작업 결과](reports/해설병렬작업결과.md)에 있습니다. 아래 표는 보존한 **초기 15개 노트**의 상태입니다.

편집 원본은 `data/concept-notes.json`이며 `build_app_data.py`가 번들에 넣습니다(분류·문항 데이터는 바뀌지 않음). 노트마다 `review_status`를 둡니다.

| 상태 | 뜻 | 현재 |
|---|---|---|
| `source_checked` | 노트 내용 전체를 법령 조문·K-IFRS 기준서·공개 교재 원문과 대조 (전문가 검수 전) | 세무 6개 (C02·C08·C11·I02·V03·V04), 재무 3개 (F04·F15·F21), 원가 3개 (M07·M11·M14) |
| `partial` (화면: 교재 일반 내용 포함) | 대부분 원문과 대조, 국내 교재의 일반 내용인 문장은 `unchecked_points`·`unchecked`로 분리해 회색 상자로 표시 | F05(정률법·연수합계법 계산식), M05(공손), M08(초변동원가계산) |

원가 노트는 OpenStax *Principles of Accounting* 2권(CC BY-NC-SA 4.0, GitHub `openstax/osbooks-principles-accounting-bundle`)과 Saylor Academy *Managerial Accounting*(CC BY-NC-SA 3.0, GitHub `saylordotorg/text_managerial-accounting`) 원본과 대조했습니다. 재무 노트는 한국회계기준원 '시행 중 K-IFRS' 목록에서 공개로 받을 수 있는 기준서 PDF(제1002·1016·1115·1033호)의 문단과 대조했습니다. 기준서 원문은 IFRS 재단 저작권 자료라 저장소에 넣지 않고 문단 번호만 기록합니다.

세법 노트는 2024·2025·2026년 시행 판본을 비교했고, 연도별로 다른 수치는 `year_table`에 연도 열로 나눴습니다(예: 2026년 법인세율 1%p 인상, 배당가산율 11%는 2027년 지급분부터). 문제의 `taxYear`와 노트 대조 범위를 비교해 풀이 화면에 표시합니다. 출처·확인 방법은 파일의 `verification`, `sources`에 있습니다.

개인 학습 기록은 `localStorage`의 `chagok.study.v1`에 저장합니다. 화면 설정(테마 `chagok.theme`, 다크 모드 원본 이미지 반전 `chagok.img`)은 별도 키라 학습 기록·백업에 영향을 주지 않습니다. GitHub에는 개인 오답·즐겨찾기 기록이 올라가지 않습니다. 브라우저나 기기를 바꾸기 전에 앱에서 백업하고 새 브라우저에서 복원하세요. 이번 미작성 대상 4,291문항을 모두 처리했고 1,467문항은 근거 미확인·원문/답안 의문으로 해설 등록을 보류했습니다. 보류 사유는 [병렬 작업 결과](reports/해설병렬작업결과.md)와 [문항별 검토 목록](reports/explanation-expansion.json)에 있습니다. 기존 재무 10개 해설의 미대조 표시도 유지합니다. 로그인, 자동 기기 동기화, 최신 법령에 따른 전체 문항 정답 재검증은 제공하지 않습니다.

## 배포

`main`에 반영하면 기존 GitHub Pages의 `pages build and deployment`가 실행됩니다. 해당 커밋의 배포 성공을 확인하세요. 원래 사이트의 `/`, `privacy.html`, `terms.html`, `style.css`는 문제은행과 별개입니다.

## 보류 2차 재검토와 개념 노트 확장

1차 보류 1,673개 전부를 실제 6개 작업자에게 20~30개씩 균등 재배정하여 추가 자료·원문과 대조했습니다. 2차에서 206개를 해소해 등록했고 1,467개는 갱신한 검토 사유와 함께 남겼습니다. 감사 JSON의 `rechecks`는 1차 보류 사유와 2차 배정·결과·출력 해시를 보존하고, `review_resolutions`는 해소 근거를 기록합니다. 이미 등록된 해설은 재작성하지 않았습니다. `scripts/merge_explanation_rechecks.py`는 승인된 재검토 출력만 추가하며 기존 해설·출처를 보호합니다.

개념 노트 37개를 추가하여 현재 52개입니다. 기존 15개와 출처 내용은 해시로 보존하고, 새 노트에는 핵심 원리·공식·풀이팁·검산 예시·직접 대조한 판본을 기록했습니다. 제한된 확인 범위와 미확인 특수규정은 따로 표시합니다. K-IFRS 원문을 새로 확인하지 못한 파트는 추정하여 추가하지 않았습니다. 새 세무 노트가 인용하는 국세기본법·소득세법 시행령 등 추가 법령은 새 출처키와 실제 판본을 사용합니다. 기존 데이터 구조와 UI·저장 형식은 유지합니다.
