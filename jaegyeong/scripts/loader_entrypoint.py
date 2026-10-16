"""A bounded, reversible audit for replacing exactly the two adjacent runtime script references."""
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OLD = '<script defer src="assets/bank-data.js"></script><script defer src="assets/app.js"></script>'
NEW = '<script defer src="assets/data-loader.js"></script>'
ORIGINAL_SHA = '803ffda69c5daa8a8fc161d00afae2cd1184156ae549b822be51e617f31627be'


def digest(body):
    return hashlib.sha256(body).hexdigest()


def restore_entrypoint(current, record=None):
    if record is None:
        record = json.loads((R / 'reports/runtime-entrypoint.json').read_text())
    if record.get('allowed_change') != {'before': OLD, 'after': NEW}:
        raise ValueError('Unexpected HTML amendment description')
    before = record['before_html'].encode()
    if digest(before) != ORIGINAL_SHA or record['before_sha256'] != ORIGINAL_SHA or before.count(OLD.encode()) != 1:
        raise ValueError('HTML baseline mismatch')
    expected = before.replace(OLD.encode(), NEW.encode(), 1)
    if current != expected or digest(current) != record['after_sha256']:
        raise ValueError('Unapproved HTML change beyond the loader script reference')
    return before


def main():
    path = R / 'index.html'
    before = path.read_bytes()
    if digest(before) != ORIGINAL_SHA:
        restore_entrypoint(before)
        return
    after = before.replace(OLD.encode(), NEW.encode(), 1)
    record = {'date': '2026-10-16', 'reason': '해설을 과목별 지연 로딩하고 초기 전체 번들 다운로드·파싱을 줄입니다.',
              'before_html': before.decode(), 'before_sha256': digest(before), 'after_sha256': digest(after),
              'allowed_change': {'before': OLD, 'after': NEW}}
    restore_entrypoint(after, record)
    (R / 'reports/runtime-entrypoint.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    path.write_bytes(after)


if __name__ == '__main__':
    main()
