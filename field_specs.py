# -*- coding: utf-8 -*-
"""
MFDS 상세조회 응답의 NB_DOC_DATA(허가사항 원문 XML/HTML 혼재 텍스트)를
title 키워드로 섹션 분리해서 필요한 항목만 뽑아내는 로직.

EXTRA_FIELD_SPECS:
  key: 내부에서 쓸 필드 키
  label: 화면/프롬프트 표시용 한글 라벨
  kind: "direct" (상세조회 응답의 최상위 필드를 그대로 사용)
        "section" (NB_DOC_DATA를 title 키워드로 찾아 그 섹션 본문을 추출)
  keywords: kind="section"일 때 title 매칭에 사용할 키워드 리스트(우선순위 순)
  source_field: kind="direct"일 때 원본 응답 필드명
"""
import re
from .utils import clean_markup

# 상세조회 원문에서 자주 쓰이는 섹션 제목 키워드.
# 실제 API 응답의 정확한 title 표기는 기관/버전에 따라 다를 수 있으므로
# 실사용 시 실제 응답 샘플로 keywords를 보정해야 한다.
EXTRA_FIELD_SPECS = [
    {"key": "efcy_qesitm", "label": "효능효과", "kind": "direct", "source_field": "EE_DOC_DATA"},
    {"key": "use_method_qesitm", "label": "용법용량", "kind": "direct", "source_field": "UD_DOC_DATA"},
    {"key": "atpn_warn_qesitm", "label": "경고", "kind": "section", "keywords": ["경고"]},
    {"key": "atpn_qesitm", "label": "일반적 주의사항", "kind": "section", "keywords": ["일반적", "주의사항"]},
    {"key": "intrc_qesitm", "label": "상호작용", "kind": "section", "keywords": ["상호작용"]},
    {"key": "se_qesitm", "label": "이상반응", "kind": "section", "keywords": ["이상반응", "부작용"]},
    {"key": "deposit_method_qesitm", "label": "보관방법", "kind": "section", "keywords": ["저장방법", "보관방법", "취급주의"]},
    {"key": "contraindication_qesitm", "label": "금기사항", "kind": "section", "keywords": ["다음 환자에는 투여하지", "금기"]},
    {"key": "elderly_qesitm", "label": "고령자투여", "kind": "section", "keywords": ["고령자에 대한 투여", "고령자투여"]},
    {"key": "pregnancy_qesitm", "label": "임부_수유부투여", "kind": "section", "keywords": ["임부", "수유부", "가임여성"]},
    {"key": "children_qesitm", "label": "소아_고령자투여", "kind": "section", "keywords": ["소아에 대한 투여", "소아투여"]},
    {"key": "overdose_qesitm", "label": "과량투여시의처치", "kind": "section", "keywords": ["과량투여"]},
    {"key": "handle_caution_qesitm", "label": "적용상의주의", "kind": "section", "keywords": ["적용상의 주의"]},
    {"key": "renal_hepatic_qesitm", "label": "신기능_간기능장애자투여", "kind": "section", "keywords": ["신장애", "간장애", "신기능", "간기능"]},
    {"key": "car_driving_qesitm", "label": "운전_기계조작능력영향", "kind": "section", "keywords": ["자동차", "기계조작"]},
    {"key": "interaction_food_qesitm", "label": "식품과의상호작용", "kind": "section", "keywords": ["식품"]},
    {"key": "abnormal_lab_qesitm", "label": "임상검사치이상", "kind": "section", "keywords": ["임상검사치"]},
    {"key": "dependency_qesitm", "label": "약물의존성", "kind": "section", "keywords": ["의존성", "남용"]},
    {"key": "other_caution_qesitm", "label": "기타주의사항", "kind": "section", "keywords": ["기타"]},
    {"key": "storage_condition_qesitm", "label": "저장조건상세", "kind": "section", "keywords": ["저장조건"]},
    {"key": "packaging_unit_qesitm", "label": "포장단위", "kind": "direct", "source_field": "PACK_UNIT"},
]


def _split_doc_sections(nb_doc_data: str):
    """
    NB_DOC_DATA 문자열을 <title>...</title><article>...</article> 유사 구조 또는
    'N. 제목' 패턴 기준으로 (title, body) 리스트로 분리.
    실제 응답이 XML 태그 구조라면 <title>/<article> 태그를 우선 사용하고,
    아니라면 숫자+마침표로 시작하는 줄바꿈 패턴으로 폴백한다.
    """
    if not nb_doc_data:
        return []

    sections = []
    # 1) XML 유사 구조 우선 시도
    tag_pattern = re.compile(
        r"<title>(.*?)</title>\s*<article>(.*?)</article>", re.DOTALL | re.IGNORECASE
    )
    matches = list(tag_pattern.finditer(nb_doc_data))
    if matches:
        for m in matches:
            title = clean_markup(m.group(1))
            body = clean_markup(m.group(2))
            sections.append((title, body))
        return sections

    # 2) 폴백: "숫자. 제목" 형태의 라인을 섹션 경계로 사용
    line_pattern = re.compile(r"(?:^|\n)\s*(\d{1,2}[.)]\s*[^\n]{2,40})\n", re.MULTILINE)
    idxs = [(m.start(1), m.group(1).strip()) for m in line_pattern.finditer(nb_doc_data)]
    if not idxs:
        # 섹션 구분이 전혀 안 되면 전체를 하나의 섹션으로 취급
        return [("전체", clean_markup(nb_doc_data))]

    for i, (pos, title) in enumerate(idxs):
        end = idxs[i + 1][0] if i + 1 < len(idxs) else len(nb_doc_data)
        body = nb_doc_data[pos + len(title):end]
        sections.append((title, clean_markup(body)))
    return sections


def parse_doc_sections(nb_doc_data: str) -> dict:
    """NB_DOC_DATA를 파싱해 title -> body 딕셔너리로 반환."""
    sections = _split_doc_sections(nb_doc_data)
    return {title: body for title, body in sections}


def extract_extra_fields(detail_response: dict) -> dict:
    """
    MFDS 상세조회(getDrugPrdtPrmsnDtlInq06) 응답 1건(dict)에서
    EXTRA_FIELD_SPECS에 정의된 항목들을 뽑아 {key: {"label":..., "value":...}} 형태로 반환.
    """
    result = {}
    nb_doc_data = detail_response.get("NB_DOC_DATA", "") or detail_response.get("nbDocData", "")
    sections = parse_doc_sections(nb_doc_data) if nb_doc_data else {}

    for spec in EXTRA_FIELD_SPECS:
        key = spec["key"]
        label = spec["label"]
        if spec["kind"] == "direct":
            raw = detail_response.get(spec["source_field"], "")
            value = clean_markup(raw)
        else:
            value = ""
            for title, body in sections.items():
                if any(kw in title for kw in spec["keywords"]):
                    value = body
                    break
        result[key] = {"label": label, "value": value}
    return result
