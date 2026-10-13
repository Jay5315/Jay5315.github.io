#!/usr/bin/env python3
"""Register explanations for held items whose official answer was upheld (round 14).

Usage: python3 scripts/register_round14_explanations.py AUTHORED.json REVIEWS.json

Same rules as round 13 (see register_round13_explanations.py), recorded under the ledger
`round14_registrations`. Covers the 자가제조/외부구입 cluster whose answer keys were judged
consistent (2023-06-112 resolution) and 2025-01-055 (official_supported).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from register_round13_explanations import main  # noqa: E402

POLICY = ('공식 정답이 지지된 보류 문항과 같은 진술을 공유하는 문항만 대상으로, 각 문항의 보류 사유를 실제로 읽은 '
          '원문으로 해소하거나 남은 한계를 미확인 항목에 밝히고, 작성자와 다른 검수자가 네 보기를 모두 통과시킨 '
          '경우에만 등록했습니다.')

if __name__ == '__main__':
    main(*sys.argv[1:3], ledger='round14_registrations', policy=POLICY)
