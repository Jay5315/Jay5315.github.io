#!/usr/bin/env python3
"""Register explanations for held items with near-identical explained siblings (round 15).

Usage: python3 scripts/register_round15_explanations.py AUTHORED.json REVIEWS.json

Same rules as round 13 (see register_round13_explanations.py), recorded under the ledger
`round15_registrations`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from register_round13_explanations import main  # noqa: E402

POLICY = ('다른 회차의 거의 같은 문항에 등록된 해설을 출발점으로 삼되, 이 문항의 적용 연도 원문을 다시 읽어 보류 사유를 '
          '해소하거나 남은 가정을 미확인 항목에 밝히고, 작성자와 다른 검수자가 네 보기를 모두 통과시킨 경우에만 등록했습니다. '
          '원문에 없는 조건을 넣어야만 성립하는 문항은 등록하지 않았습니다.')

if __name__ == '__main__':
    main(*sys.argv[1:3], ledger='round15_registrations', policy=POLICY)
