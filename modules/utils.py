# -*- coding: utf-8 -*-
"""
공통 유틸 함수
- format_price: 약가 숫자 포맷팅
- clean_whitespace: 공백/개행 정리
- clean_markup: HTML 태그, 마크업 잔재 제거
- normalize_company_name: (주)/주식회사 표기 차이 무시하고 비교하기 위한 정규화
- normalize_product_core: 제품명에서 함량/제형 표기 잡음 제거(기본 비교용)
"""
import re
import html


def format_price(value) -> str:
    """숫자/문자열 약가를 '12,345원' 형태로 포맷팅. 변환 불가 시 원본 문자열 반환."""
    if value is None:
        return ""
    s = str(value).strip()
    if s == "":
        return ""
    # 이미 콤마/원 등이 섞여 있으면 숫자만 추출
    digits = re.sub(r"[^\d.\-]", "", s)
    if digits == "" or digits in ("-", "."):
        return s
    try:
        num = float(digits)
        if num.is_integer():
            return f"{int(num):,}원"
        return f"{num:,.2f}원"
    except ValueError:
        return s


def clean_whitespace(text: str) -> str:
    """연속 공백/개행/탭을 단일 공백으로 정리하고 앞뒤 공백 제거."""
    if text is None:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


_TAG_RE = re.compile(r"<[^>]+>")


def clean_markup(text: str) -> str:
    """HTML 태그 제거 + 엔티티 디코딩 + 공백 정리 (NB_DOC_DATA 등 XML/HTML 섞인 원문 정리용)."""
    if text is None:
        return ""
    text = html.unescape(str(text))
    text = _TAG_RE.sub(" ", text)
    return clean_whitespace(text)


_COMPANY_NOISE = [
    "주식회사", "(주)", "㈜", "유한회사", "(유)", "합자회사", "(합)",
    "Co.,Ltd.", "Co., Ltd.", "Co.,Ltd", "Corp.", "corporation",
]


def normalize_company_name(name: str) -> str:
    """회사명 표기 차이((주), 주식회사 등)를 무시하기 위한 정규화."""
    if not name:
        return ""
    s = clean_whitespace(name)
    for noise in _COMPANY_NOISE:
        s = s.replace(noise, "")
    s = re.sub(r"\s+", "", s)  # 공백 전부 제거 후 비교
    return s.strip().lower()


def normalize_text_for_compare(text: str) -> str:
    """서술형 텍스트를 완전 문자열비교용으로 느슨하게 정규화(공백/구두점 정도만)."""
    if not text:
        return ""
    s = clean_whitespace(text)
    s = re.sub(r"[ㆍ·,\.]", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


_UNIT_TOKEN_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg/kg/day|mg/kg|mg/m2|mg/m²|mcg/kg|μg|mcg|mg|g|kg|"
    r"mL|ml|L|IU|units?|%|mEq|mmol|정|캡슐|앰플|바이알|회|일|주|개월|년|시간|분)",
    re.IGNORECASE,
)


def extract_number_unit_tokens(text: str):
    """텍스트에서 '숫자+단위' 토큰을 전부 추출. [(value:str, unit:str), ...] 반환."""
    if not text:
        return []
    s = clean_whitespace(text)
    return [(m.group(1), m.group(2)) for m in _UNIT_TOKEN_RE.finditer(s)]
