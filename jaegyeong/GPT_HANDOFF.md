# GPT 인수인계 가이드 (2026-10-21)

이 문서는 다음 작업자(GPT)가 바로 이어서 일할 수 있도록 **규칙·구조·절차·남은 일**을 한곳에 모은 것입니다. 세부 이력은 [HANDOFF.md](HANDOFF.md)(맨 위가 최신)에 있습니다.

## 1. 먼저 읽을 것 (순서대로)

1. [AGENTS.md](AGENTS.md) — 이 폴더의 기본 규칙
2. 이 문서
3. [HANDOFF.md](HANDOFF.md) 맨 위 5~6개 항목 — 최근 변경과 실제 검사 결과
4. [README.md](README.md) — 기능·실행·데이터 재생성 방법
5. [EXPLANATIONS.md](EXPLANATIONS.md) — 해설 작성·검증 방식(해설 데이터를 다룰 때만)
6. [reports/lazy-loading-validation.json](reports/lazy-loading-validation.json), [reports/portable-runtime-verification.json](reports/portable-runtime-verification.json) — 로딩·ZIP 구조와 검증 한계

## 2. 현재 상태

| 항목 | 값 |
|---|---|
| 서비스 | https://jay5315.github.io/jaegyeong/ (GitHub Pages, `main` 브랜치) |
| 문항 | 원본 4,560 → 중복 정리 4,322 · 학습 가능 4,321 · 대표 4,144 |
| 해설 | 4,281 (source_checked 4,160 · partial 121), **미등록 검토 40건** (`reports/explanation-expansion.json`의 `review`) |
| 개념 노트 | 74 (source_checked 66 · partial 8) |
| 기능 | 검색(회차·번호 정확 검색)·파트 필터·채점·오답·즐겨찾기·이어 풀기·결과/기록·백업/복원·개념 노트·간격 복습·오프라인·글자 크기·인쇄 |

다음 기능 후보: 사용자가 **실전 시험 모드는 하지 않기로** 했습니다. 간격 복습은 구현 완료(2026-10-19).

**바로 할 일:** 7절의 키보드·화면낭독기 미수정 5건. 그다음은 사용자 요청에 따릅니다.

## 3. 절대 규칙

- 루트 사이트(`/index.html`, `privacy.html`, `terms.html`, `style.css` 등)는 수정하지 않습니다. 작업 범위는 `jaegyeong/`입니다.
- 문항 ID·공식 정답·`chagok.study.v1` 저장 형식(키·버전·필드)을 바꾸지 않습니다. 새 상태가 필요하면 **별도 키**를 씁니다(아래 저장 키 참고).
- 원문에 없는 조건·보기·계산 가정을 넣어 답을 맞추지 않습니다. 공식 정답이 의심돼도 바꾸지 말고 검토 의견으로만 표시합니다.
- 실제로 읽은 출처만 확인했다고 씁니다. 미실행·미검증은 완료라고 보고하지 않습니다.
- 기존 감사 이력·보호 해시 검사를 삭제하거나 약화하지 않습니다. 테스트를 고칠 때는 범위를 줄이지 말고 더 정확하게 만듭니다.
- `assets/bank-data.js`·`assets/bank-manifest.json`·`assets/bank/*`는 직접 수정하지 않습니다. 원본(`data/`)이나 생성 로직을 고친 뒤 `scripts/build_app_data.py`로 재생성합니다.
- `jaegyeong/index.html`은 한정된 변경 감사로 보호됩니다(`scripts/loader_entrypoint.py`, `reports/runtime-entrypoint.json`). 수정하지 마세요. 초기 적용이 필요한 설정은 `app.js` 시작 시 처리합니다.
- 환경 정책이나 TLS 검증을 끄지 않습니다. 커밋 대상에서 `dist/`, `_artifacts/`, `.venv/`, 캐시, 자격 증명은 제외합니다.

## 4. 구조 요약

| 경로 | 역할 |
|---|---|
| `index.html` | 진입점(보호). `assets/data-loader.js`만 불러옴 |
| `assets/data-loader.js` | 매니페스트·코어 데이터를 SRI로 확인 후 `app.js` 실행. 실패 시 재시도 화면과 학습 기록 원본 다운로드 제공. `file://`에서는 전체 번들 `bank-data.js` 사용 |
| `assets/app.js`, `assets/app.css` | 앱 전체(한 파일, 대부분 한 줄짜리 함수). 변경 시 `reports/ui-changes.json` 해시 체인에 기록 필요 |
| `assets/offline.js`, `sw.js` | 서비스 워커 등록·빌드별 캐시·준비 상태 표시(`#offline-status` `data-state`: preparing/ready/update/unavailable) |
| `assets/bank-manifest.json`, `assets/bank/` | 생성물: 코어 + 과목별 지연 로딩 해설(내용 해시 파일명) |
| `data/` | 원본: `questions.json`, `explanations.json`, `concept-notes.json`, 분류·매핑 |
| `scripts/` | 생성기·적용 스크립트·테스트 |
| `reports/` | 감사 원장·검증 기록·`ui-changes.json` |

해설 본문은 지연 로딩됩니다. 웹에서 `BANK_DATA.explanations.items`는 처음엔 ID/파트 목록뿐이며, 본문은 `await BANK_DATA_LOADER.explanation(id)` 또는 `await BANK_DATA_LOADER.all()` 이후에 읽습니다.

### localStorage 키

| 키 | 내용 | 비고 |
|---|---|---|
| `chagok.study.v1` | 학습 기록 `{version:1, results, bookmarks, sessions, active}` | **형식 변경 금지** |
| `chagok.study.v1.unreadable[.<시각>]` | 읽지 못한 기록 원문 보관 | 설정 창에서 내려받기 가능 |
| `chagok.review.v1` | 간격 복습 `{version:1, items:{id:{box:1~5, due:ms}}}` | Leitner 1·3·7·14·30일. 백업 파일의 `review` 필드로 내보내고 복원 |
| `chagok.review.v1.unreadable` | 읽지 못한 복습 일정 원문 | |
| `chagok.theme`, `chagok.img`, `chagok.size` | 테마·다크 이미지 반전·글자 크기 | 학습 기록과 무관 |

## 5. 작업 절차

### UI(`app.js`/`app.css`) 수정

1. 코드 수정
2. `python3 scripts/log_ui_change.py "변경 요약"` — 해시 체인에 기록(안 하면 `test_explanations.py` 실패)
3. 저장소 루트에서 `python3 jaegyeong/scripts/build_app_data.py` — 매니페스트·SRI 갱신(안 하면 로더가 새 `app.js`를 거부)
4. 회귀 검사 추가: 기존 파일에 맞춰 `scripts/test_robustness.py`(안정성), `scripts/test_spaced_review.py`(복습), `scripts/test_ui_regressions.py`, `scripts/test_offline.py`(오프라인·로더). 모두 `test_app.py`에서 실행되거나 별도 실행됩니다.
5. 가능하면 **수정 전 코드로 되돌려 새 검사가 실패하는지** 확인 후 복구
6. 전체 검사 → `HANDOFF.md` 맨 위에 기록 → 커밋·푸시 → 배포 확인

`offline.js`·`data-loader.js`·`sw.js`도 런타임 파일이라 수정 후 `build_app_data.py`가 필요합니다(해시 체인 기록은 `app.js`/`app.css`만).

### 데이터 수정

`data/` 원본 또는 적용 스크립트를 수정하고 `build_app_data.py`로 재생성합니다. 기존 감사 원장(`reports/*`)은 보존하고 새 변경은 새 원장·적용 스크립트로 추가합니다(기존 회차 스크립트 `scripts/apply_*`, `register_round*` 참고).

## 6. 검증

```sh
# 저장소 루트에서
python3 -m http.server 8000 --bind 127.0.0.1 &
bash jaegyeong/scripts/run_checks.sh          # 필수 7개 + test_offline.py (순차 실행)
bash jaegyeong/scripts/run_checks.sh --zip    # ZIP 구조·런타임을 바꿨다면 package_app + test_portable_runtime 포함
```

필수 7개: `test_bank`, `test_parts`, `test_concepts`, `test_explanations`, `test_app`, `test_browser`, `test_explanations_app`. 오프라인·로더 변경 시 `test_offline`, ZIP 변경 시 `package_app.py` 후 `test_portable_runtime.py`.

### 배포 확인(배포를 요청받았을 때)

1. `git push origin HEAD:main`(원격이 앞서 있으면 먼저 가져와 병합)
2. GitHub Actions의 `pages build and deployment`가 해당 커밋에서 성공했는지 확인
3. 공개 파일 13개 SHA-256을 로컬과 비교: `index.html`, `sw.js`, `assets/{bank-manifest.json, bank-data.js, app.js, app.css, data-loader.js, offline.js, icon.svg}`, `assets/bank/` 코어 1개 + 과목 해설 3개(매니페스트에 있는 파일명)
4. 결과(실행 링크·일치 개수·미검증 사항)를 `HANDOFF.md`에 기록

### 테스트 하네스 주의점

- **Chromium `set_offline`은 오프라인 상태로 새로고침해 다시 시작된 서비스 워커에는 적용되지 않습니다.** 오프라인 검사는 `test_offline.py`의 `go_offline()`처럼 앱 출처 요청을 `route.abort`로 함께 막아야 실제로 오프라인입니다.
- 여러 브라우저 검사를 같은 서버에서 동시에 돌리면 `test_app.py`가 한 번 시간 초과로 실패한 적이 있습니다(단독 재실행 3회 통과). 검사는 순차로 돌리세요. 다시 나면 대기 시간을 늘리기 전에 원인을 확인하세요.
- 브라우저 검사는 `browser.new_context(service_workers='block')`로 격리하면 오프라인 캐시 영향을 받지 않습니다.
- 수정 중인 `app.js`를 검사 도중 바꾸면 SRI 불일치로 결과가 무의미해집니다.

## 7. 남은 일·미검증

- **해설 미등록 40건**: 새 근거(원문 확인·출처)가 필요합니다. 추정으로 채우지 마세요. 목록은 `reports/explanation-expansion.json`의 `review`, 최근 조사 기록은 `reports/round25-*`, `round26-*`.
- **미검증(환경 제한)**: 실제 `file://` 탐색(관리 브라우저 정책 차단), 공개 사이트 실브라우저 접속(프록시 인증서 신뢰 문제). 우회하지 말고 미검증으로 보고하세요. 로컬 브라우저·ZIP HTTP 실행·공개 파일 13개 해시 대조는 통과합니다.
- **키보드·화면낭독기 점검 결과 — 아직 고치지 않은 5건 (다음 작업 1순위)**: 2026-10-21 하위 에이전트가 키보드만으로 재현했습니다(Playwright `page.keyboard`). 재현 스크립트는 이 환경의 임시 폴더라 저장소에는 없으므로 아래 절차로 다시 재현하세요. 고친 뒤 `scripts/test_robustness.py`에 회귀 검사를 추가하세요.
  1. **분할 버튼 묶음에서 누른 버튼 대신 첫 버튼으로 포커스 이동 (중)** — `restoreView()`가 `data-action`/`data-answer`/`data-id`로만 버튼을 찾습니다. `data-count`(홈 문제 수), `data-subject`(홈 과목 카드·개념 과목 필터), `data-view`(풀이 '텍스트로 읽기/원본 이미지')로 구분되는 버튼은 첫 버튼으로 돌아가 Enter를 한 번 더 누르면 선택이 되돌아갑니다. 수정: `snapshotView`에 `dataset.count/subject/view`(또는 모든 `data-*`)를 저장하고 `restoreView` 선택자에 포함.
  2. **열린 대화상자 내용을 바꿀 때 포커스가 `<body>`로 감 (중)** — `modal()`이 열린 상태에서 `#modal-body.innerHTML`을 교체합니다. 미리보기 → '개념' 버튼, 개념 창의 탭 전환, 설정 → '백업 복원' → 파일 선택 후 확인 창. 수정: `modal()` 끝에서 이미 열려 있던 경우 `#modal-body`의 첫 포커스 가능 요소(탭 전환이면 `[role=tab][aria-selected=true]`)로 포커스.
  3. **즐겨찾기 화면에서 미리보기 창 안의 별을 해제하고 닫으면 포커스 소실 (중)** — `toggleBookmark()`가 목록을 다시 그려 창을 연 버튼이 사라짐. 수정: 대화상자 `close` 리스너에서 `document.activeElement===document.body`이면 `#library-results`(없으면 `#main`)로 포커스.
  4. **채점 피드백 알림 (중)** — `.feedback role="status"`가 이미 내용이 채워진 채 `#main` 전체 다시 그리기로 삽입되고, 해설 지연 도착(`loadExplanation`의 `render(false)`)·보기 전환 때 다시 삽입됩니다. 화면낭독기에 따라 안 읽히거나 여러 번 읽힘. 수정: `.feedback`의 `role="status"` 제거, `#main` 밖에 항상 있는 시각적으로 숨긴 `aria-live="polite"` 요소 하나를 두고 `grade()`에서만 문구를 넣기.
  5. **검색·필터 결과 개수 미알림 (하)** — `#library-results`의 'N개 문제'가 라이브 영역 밖. 수정: 위 공용 라이브 영역에 개수를 입력 중 지연(debounce) 후 알림.
  - 참고(하): 풀이에서 보기 버튼에 포커스가 있을 때 Enter는 버튼 동작이라 채점되지 않습니다. 화면 안내 'Enter 정답 확인'과 다르므로 안내 문구를 고치거나 선택된 보기에서 Enter 시 채점하도록 정하세요.
  - 정상 확인: 홈→풀이→채점→결과→오답 다시 풀기 전 흐름, 모든 대화상자의 첫 포커스(닫기 버튼)·Escape·연 버튼으로 포커스 복귀, 목록 페이지 넘김·'이 문제 풀기'·즐겨찾기 Enter/Space, 개념 목차·관련 노트, 토스트·`#offline-status` 라이브 영역, 모든 컨트롤의 `:focus-visible` 3px 윤곽선(라이트·다크).
- 같은 날 데이터 일관성 검사 결과: 해설 4,281개 모두 `answers`·정답 보기 표시(`is_answer`)가 공식 정답과 일치, 보기 1~4 완비, "정답은 ○" 요약의 번호도 공식 정답과 일치했습니다.
- 간격 복습 범위: 기기별 저장(서버 동기화 없음), 한 번 이상 채점한 문항만 대상, 하루 최대 30문제(`slice(0,30)`), 간격 상수 `REVIEW_DAYS`.

## 8. 최근 변경 흐름 (요약)

2026-10-15~21에 UI 가독성·접근성 개선, 지연 로딩·오프라인(다른 작업자), 그리고 별도 검토 에이전트로 네 차례 버그 점검·수정을 했습니다. 주요 수정: 손상/새 형식 학습 기록 보존, 다른 창 충돌 방지, 저장 공간 초과 처리, 다시 그리기 시 포커스·접힘·커서 유지, 이어 풀기 위치, 오프라인 '새 버전' 안내, 로드 실패 시 기록 다운로드, 간격 복습 도입과 단계 계산 수정, 미리보기 정답 노출 방지, 글자 크기 적용 범위. 항목별 내용·검사·배포 링크는 `HANDOFF.md`에 있습니다.

## 9. 보조 스크립트

| 스크립트 | 용도 |
|---|---|
| `scripts/log_ui_change.py "요약"` | `app.js`/`app.css` 변경을 `reports/ui-changes.json`에 기록 |
| `scripts/run_checks.sh [--zip]` | 모든 검사를 순차 실행(서버 없으면 시작) |
| `scripts/build_app_data.py` | 번들·매니페스트·분할 데이터 재생성 |
| `scripts/package_app.py` | `dist/` ZIP 두 종류 생성(커밋하지 않음) |
