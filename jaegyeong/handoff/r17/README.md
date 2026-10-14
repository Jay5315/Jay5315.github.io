# 19차(round 17) 인계 작업물 — 검수 전 초안

이 폴더는 작업 브랜치 `claude/practical-allen-zjsicv`에만 있는 **검수 전** 작업물입니다. 앱 데이터에 반영되지 않았습니다.

- `brief0~7.json`: 남은 보류 문항 77건(정답 이의 판정 18건, 이전에 등록하지 않기로 한 6건 제외)을 과목·파트 순으로 8묶음으로 나눈 자료. 문항 원문·공식 정답·보류 사유·비슷한 문항(있으면 그 해설)을 담았습니다.
- `out0~3.json`: 묶음 0~3의 작성자 초안(독립 검수 전). 묶음 0: 등록 6·불가 4, 묶음 1: 등록 7·불가 2, 묶음 2: 등록 7·불가 3, 묶음 3: 등록 6·불가 3.
- 묶음 4~7: 초안 없음.
- `AUTHOR.md`, `REVIEW.md`: 작성·검수 규칙(영문). `example_draft.json`, `example_review.json`: 형식 예시.
- 등록 스크립트: `scripts/register_round17_explanations.py AUTHORED.json REVIEWS.json` (작성자와 다른 검수자가 네 보기를 모두 pass로 판정한 초안만 등록). 테스트 `test_round17_registrations_...`가 원장 `round17_registrations`를 검사합니다.
