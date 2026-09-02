# -*- coding: utf-8 -*-
"""
5장 Python 1차 규칙 검증.
기계적으로 100% 확실한 것만 자동 판정하고, 서술형 항목은 절대 확정하지 않는다
(9장 절대 변경 금지 사항 4). 서술형은 status="CLAUDE_확인필요"로만 표시하고
8장 프롬프트 생성 대상 목록에 그대로 흘려보낸다.
"""
import re
from .utils import (
    normalize_company_name, normalize_text_for_compare,
    extract_number_unit_tokens, format_price,
)

BASIC_INFO_FIELDS = {"제품명", "성분명", "제조사", "판매사", "제조/판매사", "제형"}
NUMERIC_FIELDS_HINT = {"함량", "용법용량", "용법·용량", "용량", "투여횟수", "투여기간", "투여간격"}
PRICE_FIELDS = {"약가", "상한금액", "보험약가"}


def classify_field(field_name: str) -> str:
    if not field_name:
        return "descriptive"
    f = field_name.strip()
    if any(k in f for k in BASIC_INFO_FIELDS):
        # 제형/제품명 등은 숫자를 포함하는 경우가 거의 없어 기본정보로 분류
        return "basic_info"
    if any(k in f for k in PRICE_FIELDS):
        return "price"
    if any(k in f for k in NUMERIC_FIELDS_HINT):
        return "numeric"
    return "descriptive"


def check_basic_info(compare_value: str, reference_value: str) -> dict:
    """제품명/성분명/제조판매사/제형: 정규화 후 비교. 회사명 표기 차이는 무시."""
    if not reference_value:
        return {"status": "확인불가", "detail": "원문(MFDS/HIRA)에서 해당 항목을 찾지 못함"}

    a = normalize_company_name(compare_value)
    b = normalize_company_name(reference_value)
    if a and a == b:
        return {"status": "일치", "detail": ""}

    a2 = normalize_text_for_compare(compare_value)
    b2 = normalize_text_for_compare(reference_value)
    if a2 == b2:
        return {"status": "일치", "detail": ""}

    return {
        "status": "수정필요",
        "detail": f"비교표: '{compare_value}' / 원문: '{reference_value}' — 불일치",
    }


def check_numeric(compare_value: str, reference_value: str) -> dict:
    """숫자+단위 토큰을 추출해 정확히 비교. 단위가 다르거나 값이 다르면 즉시 수정필요."""
    if not reference_value:
        return {"status": "확인불가", "detail": "원문에서 해당 수치 항목을 찾지 못함"}

    tok_a = extract_number_unit_tokens(compare_value)
    tok_b = extract_number_unit_tokens(reference_value)

    if not tok_a:
        # 숫자/단위 토큰이 없는 서술형 표현이면 규칙기반으로 확정하지 않고 Claude로 위임
        return {"status": "CLAUDE_확인필요", "detail": "수치 토큰을 추출하지 못해 의미 비교가 필요함"}

    def norm(tok_list):
        return sorted((v.rstrip("0").rstrip(".") if "." in v else v, u.lower()) for v, u in tok_list)

    if norm(tok_a) == norm(tok_b):
        return {"status": "일치", "detail": ""}

    return {
        "status": "수정필요",
        "detail": f"비교표 수치: {tok_a} / 원문 수치: {tok_b} — 값 또는 단위 불일치",
    }


def calc_price_diff(applicant_price, comparator_min_price):
    """
    (신청의약품가격 - 비교의약품 최저가) / 비교의약품 최저가 × 100
    반환: {"percent": float, "direction": "상승"|"하락"|"동일", "color": "red"|"blue"|"gray"}
    """
    try:
        a = float(re.sub(r"[^\d.\-]", "", str(applicant_price)))
        b = float(re.sub(r"[^\d.\-]", "", str(comparator_min_price)))
    except (ValueError, TypeError):
        return {"percent": None, "direction": None, "color": None,
                "detail": "약가 숫자를 파싱할 수 없음"}

    if b == 0:
        return {"percent": None, "direction": None, "color": None, "detail": "비교의약품 최저가가 0"}

    percent = (a - b) / b * 100
    if percent > 0:
        direction, color = "상승", "red"
    elif percent < 0:
        direction, color = "하락", "blue"
    else:
        direction, color = "동일", "gray"

    return {
        "percent": round(percent, 2),
        "direction": direction,
        "color": color,
        "detail": f"{format_price(a)} vs 최저 {format_price(b)} ({direction} {abs(round(percent,2))}%)",
    }


def run_rule_checks(entries: list, reference_lookup: dict) -> list:
    """
    entries: normalize.grid_to_common_schema()의 결과 (field/product/value 포함)
    reference_lookup: {product_name: {field_name: reference_value, ...}, ...}
                       (호출부에서 MFDS 상세+HIRA 약가를 field 라벨 기준으로 미리 매핑해서 넘겨줌)

    반환: entries에 "status"/"detail"/"field_category" 를 덧붙인 리스트.
    서술형(descriptive)은 여기서 절대 일치/불일치를 확정하지 않는다.
    """
    results = []
    for entry in entries:
        field = entry.get("field", "")
        product = entry.get("product", "")
        value = entry.get("value", "")
        category = classify_field(field)
        ref_map = reference_lookup.get(product, {})
        reference_value = ref_map.get(field, "")

        if category == "basic_info":
            check = check_basic_info(value, reference_value)
        elif category == "numeric":
            check = check_numeric(value, reference_value)
        elif category == "price":
            # 약가는 그리드상 단일 값이라 여기서는 원문 약가와의 단순 비교만 수행.
            # 신청/비교의약품 간 비율 계산(calc_price_diff)은 화면단에서 별도 카드로 표시.
            check = check_basic_info(format_price(value), format_price(reference_value)) \
                if reference_value else {"status": "확인불가", "detail": "원문 약가를 찾지 못함"}
        else:
            check = {"status": "CLAUDE_확인필요", "detail": "서술형 항목 — 규칙기반으로 확정하지 않음"}

        results.append({**entry, "field_category": category, **check})
    return results
