# -*- coding: utf-8 -*-
"""
제품 식별: HIRA mdsCd 앞 8자리 <-> MFDS BAR_CODE의 4~11번째 8자리 매칭.
제품명만으로 동일 제품이라 확정하지 않는다 (9장 절대 변경 금지 사항 6).
"""
import re


def _digits_only(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def mdscd_key8(mds_cd: str) -> str:
    """HIRA mdsCd(제품코드) 앞 8자리 추출."""
    d = _digits_only(mds_cd)
    return d[:8] if len(d) >= 8 else ""


def barcode_key8(bar_code: str) -> str:
    """MFDS BAR_CODE(표준코드, 보통 13자리 GS1)의 4~11번째(0-index 3:11) 8자리 추출."""
    d = _digits_only(bar_code)
    return d[3:11] if len(d) >= 11 else ""


def is_same_product(mds_cd: str, bar_code: str) -> bool:
    """8자리 코드가 모두 존재하고 일치할 때만 동일 제품으로 판단."""
    k1 = mdscd_key8(mds_cd)
    k2 = barcode_key8(bar_code)
    if not k1 or not k2:
        return False
    return k1 == k2


def match_products(hira_rows: list, mfds_rows: list,
                    hira_code_field="mdsCd", mfds_code_field="BAR_CODE"):
    """
    HIRA 행 리스트와 MFDS 행 리스트를 8자리 코드로 매칭.
    반환: [{"hira": hira_row, "mfds": mfds_row}, ...] (매칭된 것만)
    매칭 실패한 항목은 별도로 unmatched_hira / unmatched_mfds 로 함께 반환한다.
    """
    mfds_index = {}
    for row in mfds_rows:
        k = barcode_key8(row.get(mfds_code_field, ""))
        if k:
            mfds_index.setdefault(k, []).append(row)

    matched, unmatched_hira = [], []
    matched_mfds_ids = set()
    for hrow in hira_rows:
        k = mdscd_key8(hrow.get(hira_code_field, ""))
        candidates = mfds_index.get(k, []) if k else []
        if candidates:
            for mrow in candidates:
                matched.append({"hira": hrow, "mfds": mrow})
                matched_mfds_ids.add(id(mrow))
        else:
            unmatched_hira.append(hrow)

    unmatched_mfds = [r for r in mfds_rows if id(r) not in matched_mfds_ids]
    return {"matched": matched, "unmatched_hira": unmatched_hira, "unmatched_mfds": unmatched_mfds}
