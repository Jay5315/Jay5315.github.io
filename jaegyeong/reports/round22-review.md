# 22차 병렬 조사·추가 해설 등록 (2026-10-14)

## 검토 범위와 결과

기준 커밋 `aa6ef9d4b42acdc5c18d3275ffc95292a738dd2a`, 작업 브랜치 `claude/practical-allen-zjsicv`, 범위 `jaegyeong/`입니다. 실행 한도인 하위 에이전트 6명 모두를 47건의 6개 독립 조사 묶음(5·9·9·6·6·12건)에 동시에 배정하고, 작성자와 다른 담당자가 교차 검수했습니다. **새 해설 2개**를 등록했습니다: `2024-05-091` 정상적 표준은 `source_checked`, `2026-09-022` 자기주식은 K-IFRS 적용 한계를 밝힌 `partial`입니다. 현재 해설 **4,276개**(source_checked 4,159·partial 117), 미등록 **45건**(출처 14·원문 11·정답 의심 18·계산 2)입니다. 기존 해설 4,274개·공식 정답·문항 ID·학습 저장 형식·개념 74개는 그대로입니다.

전체 문제는 4,322개, 학습 가능은 4,321개입니다. 이번 등록은 출처 미확인 16건 중 2건이며, 다른 31건은 원문·숫자·공식 키 문제가 남아 새 사실을 만들어 등록하지 않았습니다. 하위 에이전트는 실제 6개 세션이며 최대 동시 6명, 재귀 생성은 없습니다. 먼저 6명 모두 조사한 뒤 완료한 담당자에게 다른 묶음의 검수를 배정했습니다. 작성/검수 배정은 0→1, 1→4, 2→3, 3→2, 4→5, 5→4입니다.

## 실제 확인한 새 근거

- `2024-05-091`: KOCW 부산가톨릭대학교 신성욱의 2023년 1학기 자격증세미나 [공식 강좌](https://www.kocw.net/home/cview.do?cid=6a926409524b6fea)에서 제5주 표준원가계산의 [05-1.mp4](https://kocw-n.xcache.kinxcdn.com/v/lec/2023/first_term/cup/shinsungwook0918/05-1.mp4)를 확보했습니다. 파일 1690초(28:10)의 교재 표시 173쪽/PDF15쪽은 지문과 같은 정의를 **정상적 표준**으로 직접 명명하고 이상적 표준과 구별합니다. 1700초(28:20)의 174쪽/PDF16쪽은 현실적 표준을 설명합니다. 영상 SHA-256은 `a0cc3b6672d113184e2b2b2a7e80411de324283da5792726b7fe7d54c691dd70`이며, 검수자가 원파일에서 직접 프레임을 추출해 읽었습니다. 교재 출판사·별도 판본은 화면만으로 확정하지 않았고, 전체 영상 청취로 표현하지 않았습니다.
- `2026-09-022`: 한국회계기준원 종전기준 질의회신 **08-026(seq656)**의 실제 본문에서 동일 유형 자본거래의 차손·차익 상계 원리를 읽었습니다. 일반기업회계기준 15.8–15.9와 K-IFRS 제1032호 문단33–35, 제1008호 문단10–12를 함께 대조했습니다. 종전/일반기업회계기준의 부기 모형으로 공식②를 설명하되 K-IFRS의 세부 상계 강제를 확인했다고 쓰지 않았습니다. ①을 K-IFRS 자체에서 반드시 금지된 분개라고 단정하지 않는 한계가 요약·풀이·보기·미확인 사항 모두에 있습니다.
- 새 국세청 회신·신고안내와 2022년 시행 근로복지법령을 읽어 구 사내기금법에서 현 기금법인으로 이어지는 범위, 주택저당 이자 지원과 일반 주택 보조의 차이, 통근차량 질문과 실제 답변 미확보를 구분했습니다. 회사 종류·신고 사실·매입공제·기부금 적용 범위 등을 임의로 추가하지 않았습니다.
- 1992년 수질 부과금 회신1101은 당시 초과배출에 한정한 제19조와 연결됩니다. 법률5095의 부과대상 확대와 1997/2000 분리 시행 부칙을 실제 읽어 구 회신을 현대 부과금 전체에 적용하지 않았습니다. 1102는 수신한 표제와 상세 본문이 달라 실질 근거에서 제외했습니다. 이 관찰만으로 불일치의 원인을 단정하지 않았습니다.
- 추가 KOCW 초변동 강의는 이익결정요인을 ‘판매량과 생산량’으로 적습니다. ㄹ을 무조건 거짓으로 처리하지 않았으며, ㄴ의 특정 산업 비교는 아직 직접 확인하지 못했습니다. 루트도 기본개념 01-1/01-2 영상의 실제 화면을 읽었으나 취득원가와 소멸 비용/손실의 범위를 좁혀 공식키를 맞추지 않았습니다.

정확한 출처·시행판본·실제 읽은 위치·개별 파일 SHA는 [작성/검수 입력](round22-proposals.json), [읽기 영수증](round22-preflight.json), [조사 기록](round22-research.json)에 있습니다. 읽기 기록은 작성자·검수자 합계271개, URL/파일 SHA 조합은124개이며 파생 이미지와 보존본 재독을 포함합니다. 외부 공식 문서124종을 새로 확보했다는 뜻이 아닙니다. 실제 재독·신규 다운로드·21차 원문검수 재사용·PDF메타데이터만 확인한 경우를 구별했습니다. 영상·프레임·외부 교재·기준서 원문 캐시는 커밋하지 않았습니다.

## 발견한 오류와 수정

신규 내용의 독립검수에서 해설 본문 수정 요구는 없었습니다. 적용 전 검수 형식을 맞추는 과정에서 review2의 파일 SHA/행 SHA 필드 매핑9건, review3의 보기별 status/note 필드24건을 원 작성·검수 파일과 내용·판정을 보존하며 정정했습니다. 이전 검수파일과 전후 해시·이유는 [형식 정정 이력](round22-revisions.json)에 있습니다. 원문 경로의 절대경로·앱 상대경로·일치하는 파일명을 모두 같은 실제 원본과 SHA에 결합했습니다.

별도 코드 검수는 QA의 명시 등록거부를 무시할 수 있던 새 적용기의 게이트를 발견했습니다. 등록에는 `approved_decision=register`와 `registration_approved=true`를 반드시 요구하도록 고쳤습니다. 실제 유효 읽기를 넣은 성공·단독거부2개·동시거부를 검사하고, 읽기누락 테스트가 정확히 그 이유로 실패하도록 보완했습니다. 지적·수정 후 검증을 보존했으며 데이터 쓰기 전에 해결했습니다.

## 수정 사항과 무결성

원장은 `round22_followups`, 적용기는 `scripts/apply_round22_followups.py`입니다. 승인된 파일/행 SHA, 다른 작성자/검수자, 실제 본문 SHA, 네 보기, 원본 문항·키·공통지시, 제한 산술을 확인하고 기존4274개 해설·1852개 출처 정의·기존 감사 키·개념 파일을 보호한 뒤 append-only로 반영했습니다. 기존 공식 키·문항 ID·계산식·`chagok.study.v1`·앱 JS/CSS·루트 사이트는 바꾸지 않았습니다. 새 출처 정의3개는 실제 인용된 영상·질의회신·공식 키 자료만 추가했습니다. `assets/bank-data.js`는 생성기로 재생성했습니다. 기존 CSV는 등록2행만 지우고 BOM/LF와 다른 행을 보존했습니다.

테스트는 가장 먼저22차 등록·출처를 되돌리고21차→20차→기존 등록 원장을 보호합니다. 브라우저 채점 대상에 새2문항을 명시적으로 추가했습니다. 개념74개·출처 상태66/8과 화면 검토 의견23개는 그대로이며, 생성 번들에서 바뀐 부분은 explanations와 그 출처 라벨뿐입니다.

## 남은 쟁점

45건=출처14·원문11·정답의심18·계산2입니다. [남은45건 확인사항](남은45건_확인사항.csv)에 각 문항의 이번 보류 이유와 추가 확인 포인트를 적었습니다. 이미 등록한 부분 해설117개와 미등록45건은 다른 집계입니다. 원문11건 중 조건 누락9·수치 모순2, 계산2건의 금리/가격·기간/현가계수 모순, 정답의심18건의 공식 키 문제는 새 가정으로 해결하지 않았습니다. 실제 정정 원본이나 해당 범위를 직접 입증하는 자료가 필요합니다.

출제기관 WWW의 자체301과 비WWW/대체 공식 경로의403 때문에 최신 정오표·수정키를 확보하지 못했습니다. 이것은 정오표가 없다는 확인이 아닙니다. 검색 요약이나 HTML껍데기를 실제 회신 본문으로 쓰지 않았습니다.

## 실제 테스트 결과

7개 테스트 모두 통과했고 이번 테스트 실행 실패는0건입니다. bank10·parts5·concepts7·explanations43, 앱/브라우저, 해설4276개 전체 렌더·신규2문항을 포함한 채점·18개 기존 보강 개념·21차의12의견 미리보기와4공식키 채점·재접속을 확인했습니다. 실제 명령·전체 출력·시간·SHA는 [검증 기록](round22-validation.json)에 있습니다.

- `test_bank`: exit 0; 0.575초; Ran 10 tests in 0.403s / OK
- `test_parts`: exit 0; 0.44초; Ran 5 tests in 0.306s / OK
- `test_concepts`: exit 0; 0.321초; Ran 7 tests in 0.244s / OK
- `test_explanations`: exit 0; 13.005초; Ran 43 tests in 11.457s / OK
- `test_app`: exit 0; 25.802초; PASS: part/count/review filters, grading, reload/resume, incomplete finish, wrong replay, bookmarks, search, multi-answer, quarantine, export/import, history, keyboard, desktop/mobile/text/zoom, concept notes (index/pending/related/part study/quiz-wrong-preview links/tax-year highlight/state kept), choice blocks, arrow keys, next steps, grouped chapters, theme toggle; no browser errors
- `test_browser`: exit 0; 2.535초; PASS: load, images, search, multiple-answer scoring, variants, quarantine, comparison, part filters, subject reset, tag search, classification review filter, mobile layout; no browser errors.
- `test_explanations_app`: exit 0; 100.34초; PASS: all 4276 explanation bodies rendered; 171 grading flows (original 30 + new part/concept/calculation coverage), 18 enriched concept pages and new examples, 12 revised opinion previews and 4 official-key grading/reload checks, no pre-grade reveal, 4 options, review status/year, reload, wrong notebook, related concepts, unchanged records, independent variants, pending content, mobile, explanation-only practice; no browser errors

## 배포

코드·검증 결과를 main과 작업 브랜치에 저장한 뒤 해당 커밋의 Pages 결과와 공개 bank-data.js SHA를 실제 확인하여 덧붙입니다.
