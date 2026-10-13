#!/usr/bin/env python3
"""Apply the 2026-10-13 post-review amendments with an auditable before/after record.

Only option reasons (plus one irrelevant summary and its article locator) and three
broken repository links change. Answers, option numbers, is_answer flags, checks and
review status stay as they were. Each change is recorded in
reports/explanation-expansion.json under `post_review_amendments`, so the protected
baseline hashes keep verifying the original content.
"""
import copy
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CHECKED_ON = '2026-10-13'


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


OPTION_REASONS = {
    '2023-11-120': {1: '재무 관점의 단기 성과와 고객·내부 프로세스·학습과 성장 관점의 장기 성과를 함께 관리하므로 BSC의 장점으로 맞는 설명입니다.'},
    '2023-07-120': {3: '재무·고객 관점의 외부 측정치와 내부 프로세스·학습과 성장 관점의 내부 측정치를 함께 다루므로 BSC의 장점으로 맞는 설명입니다.'},
    '2024-05-044': {4: '국세기본법 제48조제2항제2호 가목에 따라 법정신고기한이 지난 후 1개월 이내에 기한 후 신고를 하면 무신고가산세의 50%를 감면하므로 옳은 설명입니다.'},
    '2024-12-072': {
        1: '부가가치세법 제48조제3항에 따라 개인사업자는 원칙적으로 예정신고 대신 예정고지로 납부하고 과세기간마다 한 번씩 1년에 두 번 확정신고하므로, 네 번 신고가 원칙이라는 설명은 틀립니다.',
        2: '면세사업자는 부가가치세 납세의무가 없고, 제39조제1항제7호에 따라 면세사업에 관련된 매입세액은 공제하지 않으므로 틀린 설명입니다.',
        3: '제51조의 주사업장 총괄 납부는 납부만 주된 사업장에서 합산하며, 세금계산서 발급과 신고는 각 사업장별로 하므로 옳은 설명입니다.',
        4: '제2조제3호는 사업 목적이 영리이든 비영리이든 관계없이 사업상 독립적으로 재화·용역을 공급하는 자를 사업자로 정하므로, 영리 목적으로 한정한 설명은 틀립니다.'},
    '2024-06-071': {1: '부가가치세는 제4조·제37조에 따라 각 거래단계의 사업자 공급마다 과세하고 매입세액을 공제하는 다단계거래세이므로, 출고단계에서 한 번만 과세한다는 설명은 틀립니다.'},
    '2024-12-014': {
        2: 'IAS 40 문단 30에 따라 공정가치모형과 원가모형 중 하나를 회계정책으로 선택해 모든 투자부동산에 적용하므로(문단 32A 예외 제외) 옳은 설명입니다.',
        3: 'IAS 40 문단 33은 공정가치로 측정하도록 하고, 같은 부속서에 수록된 IFRS 13 문단 25는 공정가치 측정에 쓰는 가격을 거래원가로 조정하지 않는다고 정하므로, 처분 거래원가를 차감한다는 설명은 틀립니다.'},
    '2023-11-020': {
        1: 'IAS 37 문단 31에 따라 우발자산은 인식하지 않으므로 재무상태표에 자산으로 기록하지 않는다는 설명은 옳습니다.',
        2: 'IAS 37 문단 28에 따라 우발부채는 주석으로 공시하지만 자원 유출 가능성이 아주 낮은(희박한) 경우에는 공시하지 않으므로 틀린 설명입니다.',
        3: 'IAS 37 문단 10의 우발자산 정의(과거사건에서 생겼고 불확실한 미래사건으로만 존재가 확인되는 잠재적 자산)와 일치하므로 옳은 설명입니다.',
        4: 'IAS 37 문단 10의 우발부채 정의 (a)(과거사건에서 생겼고 불확실한 미래사건으로만 존재가 확인되는 잠재적 의무)와 일치하므로 옳은 설명입니다.'},
    '2024-01-020': {
        3: 'IAS 37 문단 10 (b)는 자원 유출 가능성이 높지 않거나 금액을 신뢰성 있게 측정할 수 없어 인식하지 않는 현재의무를 우발부채로 정의하므로 옳은 설명입니다.',
        4: 'IAS 37 문단 27·28에 따라 우발부채는 부채로 인식하지 않고 주석으로 공시하지만, 자원 유출 가능성이 희박하면 공시도 하지 않으므로 틀린 설명입니다.'},
    '2024-12-020': {
        1: 'IAS 37 문단 66에 따라 손실부담계약의 현재의무는 충당부채로 인식하고 측정하므로 옳은 설명입니다.',
        2: 'IAS 37 문단 10의 손실부담계약 정의(회피 불가능한 원가가 기대 경제적효익을 초과하는 계약)와 일치하므로 옳은 설명입니다.',
        3: 'IAS 37 문단 10·66·67은 계약의 종류를 제한하지 않으므로, 확정매입계약도 회피 불가능한 원가가 기대효익을 초과하면 손실부담계약이 됩니다. 될 수 없다는 설명은 틀립니다.',
        4: 'IAS 37 문단 68에 따라 회피 불가능한 원가는 계약 이행원가와 불이행 시 보상금·위약금 중 작은 금액이므로 옳은 설명입니다.'},
}
SUMMARIES = {
    '2024-12-072': '주사업장 총괄 납부는 납부만 주된 사업장에서 합산하고 세금계산서 발급과 신고는 각 사업장별로 하므로 이차장(3번)의 설명이 옳습니다.',
}
LOCATORS = {
    ('2024-12-072', 'VAT24'): '제2조제3호·제6조·제8조·제39조제1항제7호·제48조제3항·제51조',
}
SOURCE_READS = {
    '2023-11-120': 'OpenStax m68099 BSC 관점·균형 설명(기존 출처) 재확인',
    '2023-07-120': 'OpenStax m68099 BSC 관점·균형 설명(기존 출처) 재확인',
    '2024-05-044': 'legalize-kr c76556ac7f 국세기본법 제47조제2항·제48조제2항 원문',
    '2024-12-072': 'legalize-kr 2c23d7c 부가가치세법 제2조·제39조·제48조·제51조 원문',
    '2024-06-071': 'legalize-kr 2c23d7c 부가가치세법 제4조·제37조(기존 출처) 원문',
    '2024-12-014': 'legalize-eu 62b803d EU 2023/1803 IAS 40 문단 30·33·56, IFRS 13 문단 25 원문',
    '2023-11-020': 'legalize-eu 62b803d EU 2023/1803 IAS 37 문단 10·27·28·31·33~35 원문',
    '2024-01-020': 'legalize-eu 62b803d EU 2023/1803 IAS 37 문단 10·14·27·28 원문',
    '2024-12-020': 'legalize-eu 62b803d EU 2023/1803 IAS 37 문단 10·66~68 원문',
}
SOURCE_URLS = {
    # The cited commits exist only under the current repository names (verified with git ls-remote HEAD).
    'RC3_OSX_PROCESS': ('mirror_url', 'openstax/osbooks-accounts-v1/', 'openstax/osbooks-principles-accounting-bundle/'),
    'RC3_OSX_INVENTORY': ('mirror_url', 'openstax/osbooks-accounts-v1/', 'openstax/osbooks-principles-accounting-bundle/'),
    'OS_FIN_R019': ('url', 'openstax/osbooks-finance/', 'openstax/osbooks-principles-finance/'),
}


def main():
    data_path, audit_path = R / 'data/explanations.json', R / 'reports/explanation-expansion.json'
    data, audit = json.loads(data_path.read_text()), json.loads(audit_path.read_text())
    if 'post_review_amendments' in audit:
        raise SystemExit('post_review_amendments already applied')
    notes = {n['question_id']: n for n in data['items']}
    note_records, source_records = [], []
    for id, reasons in OPTION_REASONS.items():
        n = notes[id]
        before = copy.deepcopy(n)
        options = {o['number']: o for o in n['option_notes']}
        for number, reason in reasons.items():
            options[number]['reason'] = reason
        changed = ['option_notes']
        if id in SUMMARIES:
            n['summary'] = SUMMARIES[id]
            changed.append('summary')
        for (qid, ref), locator in LOCATORS.items():
            if qid == id:
                next(s for s in n['sources'] if s['ref'] == ref)['locator'] = locator
                changed.append('sources')
        texts = [o['reason'] for o in n['option_notes']]
        if len(texts) != len(set(texts)):
            raise SystemExit(f'{id}: option reasons still duplicated')
        note_records.append(dict(question_id=id, changed_fields=changed, changed_options=sorted(reasons),
                                 before=before, before_hash=digest(before), after_hash=digest(n),
                                 reason='정답 보기와 오답 보기가 같은 이유 문구를 공유해 보기별 설명 역할을 하지 못함',
                                 source_reads=SOURCE_READS[id]))
    for ref, (field, old, new) in SOURCE_URLS.items():
        source = data['sources'][ref]
        before = copy.deepcopy(source)
        if old not in source[field]:
            raise SystemExit(f'{ref}: unexpected {field}')
        source[field] = source[field].replace(old, new)
        source_records.append(dict(ref=ref, field=field, before=before, before_hash=digest(before),
                                   after_hash=digest(source),
                                   reason='인용한 commit이 옛 저장소 이름에서는 열리지 않음; 같은 commit을 가진 현재 저장소 이름으로 교체',
                                   verification='git ls-remote로 새 저장소 HEAD가 인용 commit과 같음을 확인하고 raw 파일 200 응답과 제목을 확인'))
    audit['post_review_amendments'] = dict(checked_on=CHECKED_ON, notes=note_records, sources=source_records,
                                           policy='보호 해시는 변경 전 내용을 계속 검증하고, 이 기록의 before/after 해시로만 현재 내용을 허용')
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(f'Amended {len(note_records)} explanations and {len(source_records)} source links')


if __name__ == '__main__':
    main()
