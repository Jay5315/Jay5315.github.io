#!/usr/bin/env python3
"""Register explanations for clusters of near-identical held items across sittings (round 16).

Usage: python3 scripts/register_round16_explanations.py AUTHORED.json REVIEWS.json

Same rules as round 13 (see register_round13_explanations.py), recorded under the ledger
`round16_registrations`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from register_round13_explanations import main  # noqa: E402

POLICY = ('여러 회차에 거의 같은 문장으로 출제된 보류 문항 묶음을 대상으로, 실제로 읽은 기준서·교재와 각 회차 공식 답안의 '
          '일관성을 함께 근거로 삼았습니다. 공식 답안에 기댄 부분은 교재 본문이 아니라 출제기관의 판단으로 밝히고 미확인 항목에 '
          '적었으며, 작성자와 다른 검수자가 네 보기를 모두 통과시킨 경우에만 등록했습니다.')

if __name__ == '__main__':
    main(*sys.argv[1:3], ledger='round16_registrations', policy=POLICY)
