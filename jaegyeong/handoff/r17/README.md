# 19차(round17_registrations) 작성·독립 검수 작업물

77건을 검토해 51건을 앱에 등록하고 26건을 보류했습니다. 19차의 감사 원장 이름은 사용자 지시대로 `round17_registrations`입니다. `claude/practical-allen-zjsicv`에서 시작한 작업입니다.

- `brief0~7.json`: 77건의 원문·공식 답·보류 이유·비슷한 문항. 초기 파일은 보존했습니다.
- `out0~3.json`: 인계받은 검수 전 원본 초안. 변경하지 않았습니다.
- `out4~7.json`: 이번 작성자의 원본 초안. 독립 검수 후 출처 정규화가 반영된 최종본과 구분합니다.
- **`AUTHORED.json` / `REVIEWS.json`**: 수정·재검수까지 끝난 최종 77건. 모든 초안에 작성자, 모든 검수에 다른 검수자와 정확한 행 SHA를 기록합니다. 이미 적용한 원장을 다시 등록하지 마세요.
- `quality-history.json`: 초기 검수, 정확 교체 전후 객체, 재검수, 출처·날짜·해시 결속 보완 기록. 이전 검수는 덮어쓰지 않았습니다.
- `AUTHOR.md`, `REVIEW.md`, `example_draft.json`, `example_review.json`: 기존 작성·검수 규칙과 형식.
- 등록: `scripts/register_round17_explanations.py AUTHORED.json REVIEWS.json`. 생성: `scripts/build_app_data.py`. 기존 감사 단계는 테스트의 `REGISTRATION_LEDGERS` 역순 구조로 계속 검사합니다.

외부 PDF/HTML 본문은 배포하지 않습니다. 실제 파일 SHA·판본·읽은 범위는 [사전검증](../../reports/round19-preflight.json)과 등록 원장에 남겼습니다. [상세 결과](../../reports/round19-review.md)·[테스트와 배포](../../reports/round19-validation.json)·[최신 인계](../../HANDOFF.md)를 확인하세요. `partial`은 미확인 항목이 남아 있으며 전문가 검수 완료를 뜻하지 않습니다.
