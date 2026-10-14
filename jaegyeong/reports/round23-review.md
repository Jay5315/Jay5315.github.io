# 23차 후속 조사·부분 해설 등록 (2026-10-14)

## 검토 범위

기준 커밋 `d467cfcfa9a7921e1e40470e6fe7227d7aa06f06`, 범위 `jaegyeong/`, 작업 브랜치 `claude/practical-allen-zjsicv`입니다. 남은 45건을 실제 하위 에이전트 6명에게 중복 없이 나누고 작성자와 다른 담당자가 교차 검수했습니다. **`2026-01-085`의 부분 확인 해설 1개**를 등록했습니다. 현재 해설 **4,277개**(source_checked 4,159·partial 118), 미등록 **44건**(출처 13·원문 11·정답 의심 18·계산 2)입니다. 새 해설은 국내 교재의 방법별 분류로 공식 ②를 설명하지만, 원문의 넓은 가능성 진술에 대한 정답 유일성은 미확인이라고 요약·② 설명·미확인란에 명시합니다. 기존 4,276개 해설·공식 키·문항 ID·학습 기록·개념 74개는 그대로입니다.

전체 4,322문항 중 학습 가능은 4,321개입니다. 추가 근거 대상 14건을 2·2·3·3·4건, 정정 원문이 필요한 31건을 별도 묶음으로 배정했습니다. 이전 작업의 실제 6개 담당자 세션을 재사용했으며 최대 동시 하위 에이전트는 6명, 새 세션이나 재귀 생성은 없습니다. 검수 배정은 0→1, 1→4, 2→0, 3→1, 4→5, 5→3입니다. 작성자와 검수자가 다른 것은 실제 에이전트 역할 분리를 뜻하며 사람 전문가 검수는 아닙니다.

## 실제 확인 근거와 판본

- **등록 문항 `2026-01-085`**: [KOCW 부산가톨릭대학교 신성욱 자격증세미나](https://www.kocw.net/home/cview.do?cid=6a926409524b6fea), 2023년 1학기 [02-2 영상](https://kocw-n.xcache.kinxcdn.com/v/lec/2023/first_term/cup/shinsungwook0918/02-2.mp4)의 1600·1650초에 표시된 교재 본문을 읽었습니다. 영상 SHA-256은 `fd825a0e7545b6ca563b12f946a980dfd0f8441d6f59f12c35aa1a0130a6d3e7`입니다. ‘부문의 최적 의사결정이 조직 전체의 최적이 되지 않을 수 있다’는 단점 문구가 **단일배분율법** 단락에 있습니다. 이어 이중법의 고정·변동 원가별 기준과 합리성을 설명합니다. 교재 출판사·별도 판본이나 전체 오디오 청취를 확인했다고 쓰지 않았습니다.
- 동시에 중앙대학교 황명철의 2023년 [부문별 원가계산 교안](https://kocw-n.xcache.kinxcdn.com/data/document/2023/cau/hwangmyungcheol0714/09.pdf) PDF21쪽을 재독했습니다(SHA `571a3a3acb70071642d3a8d0678ac302ccb035eb1a6b22beefd3f965fc9856b3`). 이중법에도 최대사용가능량 축소보고 유인과 서비스능력 과소준비 문제가 있을 수 있다는 내용을 보존합니다. 21차 연구에서 썼던 같은 ref `R21_COST_CAU2023_09`를 재사용했으며, 이 문서는 이번에 학습 출처 목록에 처음 등록됐습니다.
- 세무: 새 국세청 2017년 화폐성자산 회신과 2018년 명시 신고 사례, 2007년 팩토링 사례에서 회계평가와 세법상 신고, 금융업이라는 업태와 법정 예외군을 구별했습니다. 2025년 통화선도 회신은 후행·다른 거래의 보조 확인으로 제한하고 2022년 문항에 소급하지 않았습니다. 소득세 2019·부가세 2020 기본통칙, 고려대 세종 2020 공개교안, 지점건물 매각 심사사건도 실제 읽은 판본과 사실관계에 한정했습니다. 통근 현물·일반 주택보조나 농산물만의 분모를 만들어 넣지 않았습니다.
- 재무: 새 국내 K-IFRS 강의와 제1012호 문단34–36·68B·81의 새 지정 범위를 대조했습니다. 장부금액이 없는 비용에도 미래 세무공제와 일시차이가 있을 수 있으므로 ‘자산 미인식이면 일시차이 아님’으로 단정하지 않습니다. 동서대 2024 공개강의의 실제 ‘기타 이월공제’ 단락은 최저한세 미공제액을 다루며 기부금 이월액을 직접 분류하지 않습니다. 기부금의 미래공제를 부정하거나 별도 범주라고 역으로 확정하지 않았습니다. CD의 취득시 만기·목적·위험도 보충하지 않았습니다.
- IFRS재단의 **IFRS for SMEs 교육모듈16·26(2019 저작권)**을 새로 읽었습니다. 스태프 교육자료·IASB 미승인이라는 한계를 구별하며 한국 K-IFRS 본체로 적용하지 않습니다. 용도 미정 토지와 모든 부동산, 주식가격과 SAR 권리공정가치, 행사 내재가치를 구별합니다. 제1033호 적용사례2의 기말주수와 가중평균주수도 별도로 확인했지만 원문의 발행일을 채우지는 못했습니다.
- 원가: 한국외대 2015 목표원가 교안의 시장조사·고객 요구·판매가격·목표원가·제품설계/개발 도표를 실제 읽었습니다. ‘제품개발’을 ‘고객조사’로 바꾸어 보기③을 거짓으로 만들지 않으며, 제품사양 구상과 이후 구체 개발이라는 범위가 남아 복수정답 판정도 확정하지 않았습니다.

작성·검수자의 실제 읽기 기록은 159개, URL/파일 SHA 조합은 73개입니다. 보존본 재독·영상·문항 이미지 등을 포함하며 새 공식 문서의 수가 아닙니다. 모든 개별 실제 파일 SHA를 다시 계산했습니다. 세부 URL·판본·읽은 위치는 [작성 입력](round23-proposals.json)·[독립 검수](round23-independent-reviews.json)·[조사 기록](round23-research.json)·[사전검증](round23-preflight.json)에 있습니다. 영상과 외부 문서 원문·파생 이미지는 커밋하지 않았습니다. 등록 문항은 원문 이미지·PDF34쪽·과목33쪽·전체1쪽·답안1쪽을 작성자와 검수자가 새로 대조했습니다. 다른 보류 문항은 21/22차 원문검사 재사용과 일부 이미지 재독을 구별합니다.

## 발견한 오류

085의 첫 초안은 실제 ㄹ의 ‘불일치할 수 있다’는 진술을 ‘가능성이 없다는 보편 명제’라고 반대로 표현했습니다. 독립 검수는 이를 거부하고, 요약과 ② 설명에도 ‘옳은 것을 모두’라는 원문의 정답 유일성 미확인을 명시하도록 요구했습니다. 작성자가 정확한 세 필드만 고친 새 frozen 입력을 만들고 동일 검수자가 재검수했습니다. 이전 거부 검수·이전 초안·전후 행/파일 SHA·세 필드의 차이를 [수정 이력](round23-revisions.json)에 보존합니다. 첫 초안은 등록하지 않았습니다.

통합 코드의 독립 검수에서 추가 필수 수정은 없었으며, 기존 43개 회귀검사의 AST 보존을 확인했습니다. 실제 필수 테스트의 실패 여부는 아래 결과에 별도로 적습니다.

## 수정 사항과 무결성

`round23_followups`와 `scripts/apply_round23_followups.py`로 승인된 부분 해설 1개·실제 인용 출처 정의 2개만 추가했습니다. 승인·원문 확인 게이트는 기존 검증된 함수를 재사용합니다. 기존 해설 4,276개·출처 정의 1,855개·과거 모든 감사 키·개념 파일은 보호 해시와 객체 대조로 그대로 보존했습니다. 공식 정답 ②·문항 ID·검산식·`chagok.study.v1`·앱 JS/CSS·루트 사이트는 바꾸지 않았습니다. 기존 검토 CSV는 등록 1행만 제거했고 BOM/LF와 나머지 행을 보존했습니다. 번들은 생성기로 재생성했습니다.

신규 전용 회귀검사 1개를 추가하고 가장 먼저 23차→22차→21차→기존 단계로 되돌린 뒤 원래 보호검사를 수행합니다. 브라우저 채점에 새 문항을 추가했습니다. 개념 74개(66 확인·8 부분)와 화면 검토 의견 23개는 그대로입니다.

## 남은 쟁점

미등록 44건 = 출처 13·원문 11·정답 의심 18·계산 2입니다. 등록된 부분 해설 118개와 다른 집계입니다. 새 부분 해설은 원문의 정답 유일성을 확정한 것이 아닙니다. [남은44건 확인사항](남은44건_확인사항.csv)에 이번 보류 이유를 문항별로 기록했습니다.

정정 원문 담당자는 기존 실패 URL 27개를 반복하지 않고 공개 코드·이슈·보존 경로 등 13개 새 시도를 했지만 실제 수정 PDF·확정키를 확보하지 못했습니다. 공개 코드의 과거 사이트 링크나 검색응답을 정정 본문으로 쓰지 않았습니다. 정상 TLS의403·자체301은 정오표 부존재 확인이 아닙니다. 검색 문법422와 로컬 URL 인코딩 오류는 보완 내역과 함께 탐색 기록에 남겼습니다. 원문 누락 사실·수치 모순·시행일 충돌은 가정을 추가해 해결하지 않았습니다.

## 실제 테스트 결과

7개 모두 통과했습니다. 이번 필수 테스트 실행 실패는0건이며 bank 10·parts 5·concepts 7·explanations 44 검사, 전체 4277개 해설 렌더·신규 1개를 포함한 172개 채점 흐름·기존 18개 보강 개념 페이지·21차 의견/공식키·기록/재접속/모바일을 확인했습니다. 전체 출력·명령·실행시간·SHA는 [검증 기록](round23-validation.json)에 있습니다.

- `test_bank`: exit 0; 0.671초; Ran 10 tests in 0.406s / OK
- `test_parts`: exit 0; 0.654초; Ran 5 tests in 0.389s / OK
- `test_concepts`: exit 0; 0.455초; Ran 7 tests in 0.363s / OK
- `test_explanations`: exit 0; 15.627초; Ran 44 tests in 13.792s / OK
- `test_app`: exit 0; 25.393초; PASS: part/count/review filters, grading, reload/resume, incomplete finish, wrong replay, bookmarks, search, multi-answer, quarantine, export/import, history, keyboard, desktop/mobile/text/zoom, concept notes (index/pending/related/part study/quiz-wrong-preview links/tax-year highlight/state kept), choice blocks, arrow keys, next steps, grouped chapters, theme toggle; no browser errors
- `test_browser`: exit 0; 2.37초; PASS: load, images, search, multiple-answer scoring, variants, quarantine, comparison, part filters, subject reset, tag search, classification review filter, mobile layout; no browser errors.
- `test_explanations_app`: exit 0; 100.87초; PASS: all 4277 explanation bodies rendered; 172 grading flows (original 30 + new part/concept/calculation coverage), 18 enriched concept pages and new examples, 12 revised opinion previews and 4 official-key grading/reload checks, no pre-grade reveal, 4 options, review status/year, reload, wrong notebook, related concepts, unchanged records, independent variants, pending content, mobile, explanation-only practice; no browser errors

## 배포

배포 확인 대기: 저장 후 해당 커밋의 Pages 성공과 공개 bank-data.js의 SHA-256을 확인해 덧붙입니다.
