# 25차 남은 문항 및 최근 부분 해설 추가 검토

## 검토 범위

남은 40건을 실제 하위 에이전트 6명이 조사하고, 작성자와 다른 담당자가 160개 보기를 교차 검수했습니다. 최근 부분 해설 7개도 별도로 대조했습니다. **신규 해설·기존 해설 수정·정답 판정 변경은 모두 0건**입니다. 현재 해설 **4,281개**(출처 확인 4,159·부분 확인 122), 미등록 **40건**(출처 10·원문 10·정답 의심 18·계산 2)을 유지합니다.

기준 커밋은 `71b24a29d7a905d13a27fcce6f1f5efd3e917d26`이며 사용자 시간대 Asia/Seoul 기준 2026-10-15 작업입니다. 전체 4,322개 중 학습 가능 4,321개를 등록 해설 4,281개와 미등록 40개가 나눕니다. 기존 해설 전체를 다시 작성한 작업이 아니며, 실제 하위 에이전트 6개를 새로 생성해 최대 6개를 동시에 사용했습니다. 재귀 생성과 사람 전문가 검수는 없습니다.

## 발견한 오류와 추가 확인

- 통근차량 관련 회신에서 ‘차량 이용으로 절감한 교통비는 과세소득이 아니다’라는 문장은 질의자의 주장입니다. 이를 국세청 답변으로 취급하면 잘못된 근거가 됩니다. 실제 답변은 현금 출퇴근 수당과 출장 실비를 구별하므로 원문 ㄷ의 판정을 확정하지 못합니다.
- 공급일부터의 대손세액 공제기간과 채권 소멸시효·소송에 따른 중단은 서로 다른 쟁점입니다. 새로 읽은 기간 경과 회신도 원문의 2012년 공급에 없는 특례를 부여하지 않습니다.
- CD 취득시 만기·위험, 현금결제 주식기준보상의 권리 공정가치, 주당이익의 발행시점은 여전히 원문에서 확인되지 않습니다. 관련 IFRIC 문서가 있다는 이유로 해당 사실을 추가하지 않았습니다.
- 자가운전보조금의 실제 출장비 지급 여부, 면세전용 재화의 실제 매입세액 공제, 학자금의 급여·가지급금 성질은 명칭만으로 확정되지 않습니다. 새 회신의 사실관계를 해당 문항에 옮기지 않았습니다.
- 원가 교재의 기존 자료를 다른 검색 경로로 다시 받은 경우 과거와 SHA가 같음을 확인해 신규 문헌으로 세지 않았습니다. 수치 반례 검산은 정답을 고친 작업이나 공식 정정본 확보가 아닙니다.
- 추가 조사 초안에서 2023-03-083의 5,250원 진단 계산을 ‘다른 보조부문’이라고 표시한 라벨 오류가 발견됐습니다. 교안의 제조부문인 포장부문으로 라벨 1개만 고치고 같은 검수자가 재검수했습니다. 수식·기대값과 기존 학습 해설은 그대로이며 [변경 전후 기록](round25-revisions.json)을 보존합니다.

## 실제 확인 근거와 판본

작성자와 검수자의 실제 읽기 기록은 97개, URL/파일 SHA 조합은 49개입니다. 같은 파일의 재독·기존 기준서·영상 프레임도 포함하므로 신규 문헌 수가 아닙니다. 파일별 SHA·URL·판본·실제 읽은 범위는 [사전 대조](round25-preflight.json), [작성 결과](round25-proposals.json), [독립 검수](round25-independent-reviews.json), [조사 기록](round25-research.json)에 보존했습니다.

이번 확인에는 IFRIC의 2022년 요구불예금·2005년 미사용 결손금 및 세액공제 자료, 국세청 법인22601-271(1991-02-09), 서면1팀-390(2008-03-21), 기준-2020-법령해석부가-0280, 법인46013-2681(1998-09-21), 사전-2019-법령해석부가-0686(2019-12-10), 서면-2019-법인-4024(2020-05-26) 등이 포함됩니다. 과거 회신은 당시 사실관계·조문 범위로 한정하며 시험 연도에 그대로 적용했다고 주장하지 않습니다. 기존 자료의 재독과 새로 확보한 본문은 각 source_reads에서 구분합니다.

출제기관의 기출 페이지·robots·sitemap은 정상 TLS 요청에서 반복 리다이렉트로 본문을 확보하지 못했습니다. 일부 검색·직접 경로의 403과 HTTP로 이동하는 KOCW 응답도 검증 근거에서 제외했습니다. 접근 실패를 정오표나 유효한 근거의 부존재라고 해석하지 않습니다.

## 수정 사항

추가 조사·독립 검수·40건의 최신 보류 이유와 인수인계 문서만 저장했습니다. 학습 데이터에 새 출처나 해설을 등록하지 않았습니다. 기존 해설 4,281개, 부분 해설 122개, 감사 원장, 공식 정답, 문항 ID, `chagok.study.v1`, 개념 74개, 앱 코드, 루트 사이트 및 기존 테스트를 보존했습니다. 데이터 변경이 없어 `bank-data.js`를 재생성하지 않았으며 SHA-256은 `78496f7c5a13c4a80f4c7db489167704d8dfccfde737bba8b0d6ebd885c65e03` 그대로입니다. 불필요한 새 등록 원장·적용 스크립트·보호 테스트 단계를 추가하지 않았습니다.

## 남은 쟁점과 다음 자료

[40건의 문항별 이유](round25-remaining.csv)가 다음 작업의 기준입니다. 누락 조건을 확정할 공식 지문·해설 또는 정오표가 있어야 하는 사례와, 기준서·교재의 직접 설명이 필요한 사례를 구별해 읽어야 합니다. 숫자 모순 2건은 공식 정정 자료가 필요하며, 정답 의심 18건은 기존 판정을 바꿀 새 직접 근거가 필요합니다. 이미 확인한 같은 조문이나 같은 실패 검색만 반복해서 완료 수를 늘리지 않습니다.

## 실제 테스트 결과

필수 7개를 실제 실행했고 모두 통과했습니다. 실패 0건이며 전체 명령·출력·시간·해시는 [검증 기록](round25-validation.json)에 있습니다. 이번 조사에서 새 학습 데이터가 없다는 사실과 기존 앱 기능의 테스트 통과는 별개입니다.

- `test_bank`: 종료 코드 0, 0.631초. Ran 10 tests in 0.394s / OK
- `test_parts`: 종료 코드 0, 0.606초. Ran 5 tests in 0.379s / OK
- `test_concepts`: 종료 코드 0, 0.404초. Ran 7 tests in 0.321s / OK
- `test_explanations`: 종료 코드 0, 16.73초. Ran 45 tests in 14.751s / OK
- `test_app`: 종료 코드 0, 26.211초. PASS: part/count/review filters, grading, reload/resume, incomplete finish, wrong replay, bookmarks, search, multi-answer, quarantine, export/import, history, keyboard, desktop/mobile/text/zoom, concept notes (index/pending/related/part study/quiz-wrong-preview links/tax-year highlight/state kept), choice blocks, arrow keys, next steps, grouped chapters, theme toggle; no browser errors
- `test_browser`: 종료 코드 0, 2.675초. PASS: load, images, search, multiple-answer scoring, variants, quarantine, comparison, part filters, subject reset, tag search, classification review filter, mobile layout; no browser errors.
- `test_explanations_app`: 종료 코드 0, 102.889초. PASS: all 4281 explanation bodies rendered; 176 grading flows (original 30 + new part/concept/calculation coverage), 18 enriched concept pages and new examples, 12 revised opinion previews and 4 official-key grading/reload checks, no pre-grade reveal, 4 options, review status/year, reload, wrong notebook, related concepts, unchanged records, independent variants, pending content, mobile, explanation-only practice; no browser errors

## 배포 확인

문서 저장 후 해당 커밋의 Pages 결과와 공개 bank-data.js의 동일 SHA를 확인해 기록합니다.
