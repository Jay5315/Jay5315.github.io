#!/usr/bin/env python3
"""Register explanations for the remaining held items reviewed one by one (round 17).

Usage: python3 scripts/register_round17_explanations.py AUTHORED.json REVIEWS.json

Same rules as round 13 (see register_round13_explanations.py), recorded under the ledger
`round17_registrations`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from register_round13_explanations import main  # noqa: E402

POLICY = ('정답 이의 판정이 걸린 문항과 이미 등록하지 않기로 한 문항을 뺀 나머지 보류 문항을 하나씩 다시 검토했습니다. '
          '실제로 읽은 원문과 비슷한 문항·공식 답안을 근거로 삼되 원문에 없는 사실을 만들어야 하는 문항은 등록하지 않았고, '
          '작성자와 다른 검수자가 네 보기를 모두 통과시킨 경우에만 등록했습니다.')

if __name__ == '__main__':
    main(*sys.argv[1:3], ledger='round17_registrations', policy=POLICY)
