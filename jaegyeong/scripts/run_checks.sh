#!/bin/bash
# Run every regression suite one at a time (parallel browser load caused a timeout once).
# Usage from the repository root or jaegyeong/: bash jaegyeong/scripts/run_checks.sh [--zip]
set -u
APP="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP" || exit 1
export PATH="$APP/.venv/bin:$PATH"
if ! curl -s -o /dev/null "http://127.0.0.1:8000/jaegyeong/"; then
  (cd "$APP/.." && nohup python3 -m http.server 8000 --bind 127.0.0.1 >/dev/null 2>&1 &)
  sleep 1
fi
fail=0
for t in test_bank test_parts test_concepts test_explanations test_app test_browser test_explanations_app test_offline; do
  out=$(timeout 900 python3 "scripts/$t.py" 2>&1); rc=$?
  echo "== $t rc=$rc $(echo "$out" | tail -1 | cut -c1-100)"
  if [ $rc -ne 0 ]; then fail=1; echo "$out" | grep -E 'line [0-9]+, in|Error' | head -6; fi
done
if [ "${1:-}" = "--zip" ]; then
  (cd "$APP/.." && python3 jaegyeong/scripts/package_app.py && timeout 900 python3 jaegyeong/scripts/test_portable_runtime.py | grep '"result"') || fail=1
fi
exit $fail
