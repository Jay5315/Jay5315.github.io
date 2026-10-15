# 차곡 · 재경관리사 문제은행

**서비스:** https://jay5315.github.io/jaegyeong/

**다른 AI가 이어서 작업할 때:** [HANDOFF.md](HANDOFF.md)를 먼저 읽으세요.

**개념 노트:** [파트별 핵심 개념·학습 팁](CONCEPT_NOTES_PLAN.md) — 74개 파트 작성, 출처 대조 66개·부분 확인 8개(미확인 범위 별도 표시), 20차에서18개 파트에 팁·자체 예제 추가

과목·74개 파트별 기출 풀이, 파트별 핵심 개념 노트, 즉시 채점, 오답 노트, 즐겨찾기, 이어 풀기, 기록 백업·복원을 제공하는 정적 웹앱입니다. HTML/CSS/JavaScript만으로 실행되며 외부 API나 서버 애플리케이션, 프런트엔드 빌드가 필요하지 않습니다. 글꼴은 Pretendard 웹폰트(jsDelivr CDN)를 쓰며, 불러오지 못하면(오프라인 ZIP 등) 시스템 한글 글꼴로 대체됩니다.

**2026-10-16 사용성 개선:** 회차·문항 번호를 정확히 검색하고, 다른 회차 대표 문항은 요청 회차와 원문을 함께 표시합니다. 첫 방문 저장 완료 후 문제 텍스트·해설을 오프라인으로 다시 열 수 있습니다. 원본 이미지·PDF는 최근에 열었던 일부 자료만 저장됩니다. 해설은 출처 대조·계산 검산·부분 확인을 구분하며, 파트 진도는 선택한 변형·분류 조건에 맞춰 계산합니다. [검증 결과](reports/ui-reliability-validation.json)

**문항 해설:** 총 4281문항에 단계별 풀이·보기별 설명을 제공합니다(24차 부분 확인 해설 4개 추가, 현재 미등록 검토 40개). 홈의 '해설 4281문항 풀기', 문제 목록의 '해설 있는 문제만', 채점 후 풀이, 오답 노트의 '해설'에서 확인할 수 있습니다. [해설 작성·검증 방법](EXPLANATIONS.md)을 참고하세요.

**정답 검토 의견:** 주 판정 51건과 별도 해설 등록 문항 1건의 유효 판정은 [정답의심판정.md](reports/정답의심판정.md)에 있습니다. 공식 정답은 바꾸지 않았고, 법령 충돌·복수 후보·표현 모호·근거 보완 필요 23건만 채점 후·미리보기·오답 노트에서 "검토 의견"으로 보여줍니다.

**26차 최신 보강:** 부분 확인 해설 **122개 전부를 검토하여 49개를 보완**했습니다(재무 16·세무 10·원가 23). **2026-01-092 1개는 국내 교재 화면으로 남은 근거를 확인해 source_checked로 승격**했습니다. 현재 해설 **4,281개**(출처 확인 4,160·부분 확인 121), 미등록 **40건**은 유지합니다. 개념 노트 **8개를 보강**해 핵심 설명 13개·주의점 9개·공식 4개·자체 예제 8개를 추가하고 새 검산식 46개를 확인했습니다. 개념은 총 74개(출처 확인 66·부분 확인 8)이며, 남은 미확인 조건을 유지합니다. [상세 보고](reports/round26-review.md)·[최종 제안](reports/round26-proposals.json)·[독립 검수](reports/round26-independent-reviews.json)·[실제 출처 읽기](reports/round26-research.json)·[수정 이력](reports/round26-revisions.json)·[사전 검증](reports/round26-preflight.json)·[실제 테스트](reports/round26-validation.json)

**25차 당시 검토:** 남은 40건을 실제 하위 에이전트 6명이 조사하고, 작성자와 다른 담당자가 160개 보기를 교차 검수했습니다. 최근 부분 해설 7개도 별도로 대조했습니다. **신규 해설·기존 해설 수정·정답 판정 변경은 모두 0건**입니다. 현재 해설 **4,281개**(출처 확인 4,159·부분 확인 122), 미등록 **40건**(출처 10·원문 10·정답 의심 18·계산 2)을 유지합니다. [상세 보고](reports/round25-review.md)·[작성 결과](reports/round25-proposals.json)·[독립 검수](reports/round25-independent-reviews.json)·[실제 조사](reports/round25-research.json)·[사전 대조](reports/round25-preflight.json)·[남은 문항](reports/round25-remaining.csv)·[테스트·배포](reports/round25-validation.json)

**24차 당시 검토:** 남은 44건을 실제 하위 에이전트 6명에게 나누어 조사하고 작성자와 다른 담당자가 176개 보기를 교차 검수했습니다. **부분 확인 해설 4개**를 추가했습니다. 현재 해설 **4,281개**(source_checked 4,159·partial 122), 미등록 **40건**(출처 10·원문 10·정답 의심 18·계산 2)입니다. 새 4개는 조건 해석·정답 유일성의 한계를 본문에 명시하며, 모든 쟁점을 완전히 해결한 해설로 표시하지 않습니다. 기존 4,277개 해설·공식 정답·문항 ID·학습 기록·개념 74개는 보존했습니다. [상세 보고](reports/round24-review.md)·[작성 입력](reports/round24-proposals.json)·[독립 검수](reports/round24-independent-reviews.json)·[실제 조사](reports/round24-research.json)·[사전검증](reports/round24-preflight.json)·[초안 수정 이력](reports/round24-revisions.json)·[테스트·배포](reports/round24-validation.json)

**23차 당시 검토:** 남은 45건을 실제 하위 에이전트 6명에게 중복 없이 나누고 작성자와 다른 담당자가 교차 검수했습니다. **`2026-01-085`의 부분 확인 해설 1개**를 등록했습니다. 현재 해설 **4,277개**(source_checked 4,159·partial 118), 미등록 **44건**(출처 13·원문 11·정답 의심 18·계산 2)입니다. 새 해설은 국내 교재의 방법별 분류로 공식 ②를 설명하지만, 원문의 넓은 가능성 진술에 대한 정답 유일성은 미확인이라고 요약·② 설명·미확인란에 명시합니다. 기존 4,276개 해설·공식 키·문항 ID·학습 기록·개념 74개는 그대로입니다. [상세 보고](reports/round23-review.md)·[작성 입력](reports/round23-proposals.json)·[독립 검수](reports/round23-independent-reviews.json)·[실제 출처·탐색](reports/round23-research.json)·[사전검증](reports/round23-preflight.json)·[초안 수정 이력](reports/round23-revisions.json)·[테스트·배포](reports/round23-validation.json)

**22차 당시 검토:** 실행 한도인 하위 에이전트 6명 모두를 47건의 6개 독립 조사 묶음(5·9·9·6·6·12건)에 동시에 배정하고, 작성자와 다른 담당자가 교차 검수했습니다. **새 해설 2개**를 등록했습니다: `2024-05-091` 정상적 표준은 `source_checked`, `2026-09-022` 자기주식은 K-IFRS 적용 한계를 밝힌 `partial`입니다. 현재 해설 **4,276개**(source_checked 4,159·partial 117), 미등록 **45건**(출처 14·원문 11·정답 의심 18·계산 2)입니다. 기존 해설 4,274개·공식 정답·문항 ID·학습 저장 형식·개념 74개는 그대로입니다. [상세 보고](reports/round22-review.md)·[작성 결과](reports/round22-proposals.json)·[독립 검수](reports/round22-independent-reviews.json)·[실제 조사](reports/round22-research.json)·[사전검증](reports/round22-preflight.json)·[형식 정정 이력](reports/round22-revisions.json)·[7개 테스트·배포](reports/round22-validation.json)

**21차 당시 검토:** 남은 47건을 원문 11건 → 정답 의심 18건 → 출처 16건·계산 2건 순서로 실제 하위 에이전트 6명이 조사하고 작성자와 다른 에이전트가 독립 검수했습니다. **판정 4건과 기존 검토 의견 8건을 교정**했으며 화면 의견은 20개에서 **23개**로 늘었습니다. 신규 해설·원문 교정은 0건입니다. 현재 해설 **4,274개**(source_checked 4,158·partial 116), 해설 미등록 **47건**(출처 16·원문 11·정답 의심 18·계산 2), 개념 74개(출처 대조 66·부분 확인 8)는 유지합니다. [상세 보고](reports/round21-review.md)·[작성 입력](reports/round21-proposals.json)·[독립 검수](reports/round21-independent-reviews.json)·[수정 이력](reports/round21-revisions.json)·[본문 SHA 사전검증](reports/round21-preflight.json)·[실제 테스트·배포](reports/round21-validation.json)

**20차 당시 검토:** 출처 미확인 18건 중 2건 등록·16건 보류, 기존 부분 확인 해설 115건 중 24건 보완·91건 유지, 18개 파트 개념 노트 보강을 순서대로 완료했습니다. 현재 해설 **4,274개**(source_checked 4,158·partial 116), 미등록 검토 **47건**(출처 16·원문 11·정답 의심 18·계산 2)입니다. [검토 보고서](reports/round20-review.md)·[실제 테스트·배포](reports/round20-validation.json)를 확인하세요.

10차 당시에는 보류 127건과 기존 재무 교재 대조 428건을 실제 작업자 6명이 검토해 신규 4개를 등록하고 기존 394개의 출처·본문·미확인 표시를 감사 원장과 함께 수정했습니다. 재무 381개는 국내 근거를 추가했고 47개는 교재 근거를 유지했습니다. 새 partial 5개와 해설 미등록 145개는 구분합니다. 개념 74개는 파일 그대로 보존했습니다. [현재 검토 결과](reports/round10-review.md)·[실제 테스트](reports/round10-validation.json)·[남은 문항 목록](reports/해설추가검토목록.csv)을 확인하세요.

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

74개 파트에 노트가 있으며 `source_checked` 66개, `partial` 8개입니다. 기존 52개에 재무 22개를 추가했고, F01의 추가 핵심 문단은 한국회계기준원 공식 공개 한국어 개념체계와 직접 대조했습니다. 원가 M03·M04·M05·M06·M08·M15·M18·M19의 8개 파트는 확인한 부분만 보강했고 미확인 특수규정은 분리해 `partial`을 유지합니다. 이는 개념체계·기준서·원가 교재의 전체 범위를 모두 검증했다는 뜻이 아닙니다. 자세한 추가 범위는 `reports/concept-expansion.json`, [현재 해설 감사 기록](reports/explanation-expansion.json)과 [미해결 재검토 결과](reports/미해결재검토결과.md)에 있습니다. 아래 표는 **초기 15개 노트 작성 당시**의 상태를 보존한 역사 기록이며 현재 전체 상태가 아닙니다.

편집 원본은 `data/concept-notes.json`이며 `build_app_data.py`가 번들에 넣습니다(분류·문항 데이터는 바뀌지 않음). 노트마다 `review_status`를 둡니다.

| 초기 작성 당시 상태 | 뜻 | 당시 대상 |
|---|---|---|
| `source_checked` | 노트에 수록한 내용의 실제 인용 범위를 원문과 대조 (전문가 검수 전) | 세무 6개 (C02·C08·C11·I02·V03·V04), 재무 3개 (F04·F15·F21), 원가 3개 (M07·M11·M14) |
| `partial` (화면: 교재 일반 내용 포함) | 대부분 원문과 대조, 국내 교재의 일반 내용인 문장은 `unchecked_points`·`unchecked`로 분리해 회색 상자로 표시 | F05(정률법·연수합계법 계산식), M05(공손), M08(초변동원가계산) |

원가 노트는 OpenStax *Principles of Accounting* 2권(CC BY-NC-SA 4.0, GitHub `openstax/osbooks-principles-accounting-bundle`)과 Saylor Academy *Managerial Accounting*(CC BY-NC-SA 3.0, GitHub `saylordotorg/text_managerial-accounting`) 원본과 대조했습니다. 재무 노트는 한국회계기준원 '시행 중 K-IFRS' 목록에서 공개로 받을 수 있는 기준서 PDF(제1002·1016·1115·1033호)의 문단과 대조했습니다. 기준서 원문은 IFRS 재단 저작권 자료라 저장소에 넣지 않고 문단 번호만 기록합니다.

세법 노트는 2024·2025·2026년 시행 판본을 비교했고, 연도별로 다른 수치는 `year_table`에 연도 열로 나눴습니다(예: 2026년 법인세율 1%p 인상, 배당가산율 11%는 2027년 지급분부터). 문제의 `taxYear`와 노트 대조 범위를 비교해 풀이 화면에 표시합니다. 출처·확인 방법은 파일의 `verification`, `sources`에 있습니다.

개인 학습 기록은 `localStorage`의 `chagok.study.v1`에 저장합니다. 화면 설정(테마 `chagok.theme`, 다크 모드 원본 이미지 반전 `chagok.img`)은 별도 키라 학습 기록·백업에 영향을 주지 않습니다. GitHub에는 개인 오답·즐겨찾기 기록이 올라가지 않습니다. 브라우저나 기기를 바꾸기 전에 앱에서 백업하고 새 브라우저에서 복원하세요. 현재 해설 집계와 보류 근거는 [현재 감사 기록](reports/explanation-expansion.json)과 [미해결 재검토 결과](reports/미해결재검토결과.md)에 있습니다. 로그인, 자동 기기 동기화, 최신 법령에 따른 전체 문항 정답 재검증은 제공하지 않습니다.

## 배포

`main`에 반영하면 기존 GitHub Pages의 `pages build and deployment`가 실행됩니다. 해당 커밋의 배포 성공을 확인하세요. 원래 사이트의 `/`, `privacy.html`, `terms.html`, `style.css`는 문제은행과 별개입니다.

## 과거 기록: 1·2차 재검토와 개념 노트 확장

1차 보류 1,673개 전부를 실제 6개 작업자에게 20~30개씩 균등 재배정하여 추가 자료·원문과 대조했습니다. 2차 완료 당시 206개를 해소해 등록했고 1,467개를 갱신한 검토 사유와 함께 남겼습니다. 이 1,467개가 이번 3차의 입력이며 현재 보류 수는 아닙니다. 감사 JSON의 `rechecks`는 1차 보류 사유와 2차 배정·결과·출력 해시를 보존하고, `review_resolutions`는 해소 근거를 기록합니다. 이미 등록된 해설은 재작성하지 않았습니다. `scripts/merge_explanation_rechecks.py`는 승인된 재검토 출력만 추가하며 기존 해설·출처를 보호합니다.

2차 완료 당시 개념 노트 37개를 추가하여 52개였습니다. 기존 15개와 출처 내용은 해시로 보존하고, 새 노트에는 핵심 원리·공식·풀이팁·검산 예시·직접 대조한 판본을 기록했습니다. 제한된 확인 범위와 미확인 특수규정은 따로 표시합니다. K-IFRS 원문을 새로 확인하지 못한 파트는 추정하여 추가하지 않았습니다. 새 세무 노트가 인용하는 국세기본법·소득세법 시행령 등 추가 법령은 새 출처키와 실제 판본을 사용합니다. 기존 데이터 구조와 UI·저장 형식은 유지합니다.

## 과거 기록: 3~7차 재검토 상태

이전 3차부터 마무리까지 실제 사용한 서로 다른 하위 에이전트는 9개(기본 작성자 6개, 재무·원가 마무리 2개, 독립 QA 1개)이며 최대 동시 작업자는 6개였습니다. 메인까지 포함한 동시 슬롯은 7개이고 재귀 에이전트 생성은 없었습니다.

7차 마무리 당시 등록 해설은 4,145개였으며 그때 추가 확인에서 55개를 순증했습니다. 직전 미해결 231개 전부를 실제 하위 에이전트 6개가 11개 독점 배치로 다시 확인했고 새 공식 원본문 확보 후 62개를 3개 별도 배치로 추가 검토했습니다. 새 후보 57개 전체를 작성자와 다른 에이전트가 독립 검수하여 7차 당시 검토 필요는 176개였습니다. 기존 4,090개 해설 전체 객체·순서·출처, 원문·공식 답안·문항 ID·세법 연도와 학습 기록 형식은 보존했습니다. 개념 노트는 74개·기존 확인 상태를 유지하고 M03의 확인된 원리·예제만 덧붙였습니다. 자세한 결과는 [7차 당시 추가 확인 결과](reports/round7-review.md)를 확인하세요. 이전 6차의 187개 추가·231개 보류와 3차 수치는 역사 기록입니다.

3차 시작 시 등록되어 있던 2,854개 해설의 본문과 계산은 보존했습니다. 초기 재무 10개는 필요한 출처·검토 상태 등 특정 메타데이터만 실제 자료와 추가 대조했으며 본문이나 계산을 재생성하지 않았습니다. 문항 ID·공식 정답·원문의 세법 적용 연도와 `chagok.study.v1` 저장 형식은 바꾸지 않았습니다.

74개 파트에 노트가 있으며 `source_checked` 66개, `partial` 8개입니다. 기존 52개에 재무 22개를 추가했고, F01의 추가 핵심 문단은 한국회계기준원 공식 공개 한국어 개념체계와 직접 대조했습니다. 원가 M03·M04·M05·M06·M08·M15·M18·M19의 8개 파트는 확인한 부분만 보강했고 미확인 특수규정은 분리해 `partial`을 유지합니다. 이는 개념체계·기준서·원가 교재의 전체 범위를 모두 검증했다는 뜻이 아닙니다.

공식 공개 목록에서 로그인·개인정보 등록 없이 받을 수 있는 기준서·개념체계 PDF, 실제 읽은 공개 교재 및 역사 법령 보존본을 확인 범위에 맞춰 기록했습니다. 공식 자료의 원문 PDF나 긴 저작권 본문은 저장소에 재배포하지 않습니다. 공개 Git 미러의 고정 커밋·판본·실제 읽은 위치와 원 발행자 대조 한계도 보존합니다. 세법 연도를 시험 연도로 추정하지 않고, 실제 시행일·부칙과 원문 연도를 대조합니다. 답안 의문·원문 누락·필수 규정 미확인은 해소되지 않은 상태로 보류합니다.

현재 집계와 문항별 해소·보류 근거는 [현재 해설 감사 기록](reports/explanation-expansion.json)과 [미해결 재검토 결과](reports/미해결재검토결과.md)를 기준으로 합니다. 과거 병렬 작업 보고서는 당시 작업 이력을 보존하는 자료입니다.

이번에는 기존 기능과 데이터 구조를 유지하고 검증된 해설과 M03 개념 내용을 추가했습니다. 공개 교재의 근거 안내 문구 교정은 직전 6차, 모바일 CSS 두 줄 교정은 이전 3차 작업입니다.

7차 당시 7개 테스트 스위트를 실행했습니다. 데이터·원문·기존 해설·출처·노트 보존 및 해설 4,145개 렌더링, 실제 채점·학습 기록 흐름을 검사한 결과는 [7차 당시 검증 기록](reports/round7-validation.json)을 확인하세요. 이전 6차의 38개 회귀·4,090개 렌더링 수치는 과거 검증 기록입니다. 배포는 새 main 커밋의 GitHub Pages 실행과 정상 HTTPS 공개 파일 SHA-256 대조로 확인하며, 로컬 브라우저 검사를 공개 HTTPS 브라우저 검사로 표현하지 않습니다.

M07에는 실제 읽은 ACCA 공식 배합·수율 정의와 독립 검산 예제를 추가했습니다. 출처 예제의 수치 불일치는 근거 한계에 기록했고 그 수치를 풀이에 복사하지 않았습니다.
