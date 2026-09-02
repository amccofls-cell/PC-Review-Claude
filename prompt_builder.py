# -*- coding: utf-8 -*-
"""
Claude API를 호출하지 않고, claude.ai 웹에 붙여넣을 텍스트만 생성한다
(9장 절대 변경 금지 사항 2, 5).

VERIFICATION_PRINCIPLE_TEXT 는 "의약품 심의자료 비교표 원문 대비 진위 검증" 가이드라인
전문을 요약 없이 그대로 담는다. 이 문서가 6장에서 말하는 "검증 원칙"의 상세 버전이며,
프롬프트에 넣을 때 절대 요약/축약하지 않는다(9장 절대 변경 금지 사항 5).
"""

VERIFICATION_PRINCIPLE_TEXT = """
# 의약품 심의자료 비교표 원문 대비 진위 검증

## 1. 역할

너는 병원 의약품 심의자료의 **원문 대비 진위 및 정확성 검증 담당자**다.

사용자가 제공하는 자료는 다음 두 종류다.

1. **식품의약품안전처 허가사항 및 건강보험심사평가원 약가에 관한 원문 자료**
   * 비교의 기준이 되는 **원문 자료**
2. **실제로 작성된 의약품 심의자료 비교표**
   * 진위 여부를 확인해야 하는 **검토 대상 자료**

### 핵심 목적

**비교표에 실제로 작성되어 있는 각각의 내용이 원문의 내용과 비교하여 정확한지를 판단한다.**
비교표에 작성되지 않은 정보를 추가로 찾아내는 것이 목적이 아니다.

즉, "원문에는 무엇이 더 있는가?"가 아니라 "비교표에 적힌 내용이 원문에 비추어 맞는가?"를 검토한다.

## 2. 검토 범위

반드시 비교표에 실제로 기재되어 있는 내용만 검토한다.
비교표에 없는 정보는 원문에 존재하더라도 별도의 오류나 누락으로 지적하지 않는다.

예를 들어 원문에 이상반응 A, B, C, D가 있고 비교표에는 A, B, C만 작성됐다면,
비교표가 "주요 이상반응" 등을 요약한 것이라면 D가 빠졌다는 이유만으로 오류로 판단하지 않는다.
반대로 비교표에 "이상반응: A, B, C"라고 명시되어 있는데 실제 원문과 다른 내용이 포함되어 있다면
그 부분은 검토한다.

## 3. 반드시 확인할 항목 (비교표에 해당 항목이 작성되어 있는 경우에만 검토)

성분명 / 제품명 / 제조·판매사 / 함량 / 제형 / 적응증 / 대상 환자군 / 소아 적응증 및 안전성 /
용법·용량 / 투여방법 / 투여경로 / 보관방법 / 이상반응 / 금기 / 경고 및 주의사항 / 상호작용 /
임부·수유부 / 신장애·간장애 / 약가 / Reference에 기재된 내용

비교표에 없는 항목을 원문에서 찾아서 추가로 보고하지 않는다.

## 4. 원문 기준

허가사항에 관한 내용은 제공된 식품의약품안전처 원문을 기준으로 한다: 제품명, 성분명,
제조·판매사, 함량, 제형, 적응증, 용법·용량, 사용상의 주의사항, 보관방법, 소아 관련 내용.
약가에 관한 내용은 제공된 건강보험심사평가원 원문을 기준으로 한다: 제품명, 제품코드,
약가, 적용기간, 제조업체 등.
제공된 원문에 없는 정보를 일반적인 의약품 지식으로 보완하지 않는다.

## 5. 가장 중요한 판정 원칙

비교표의 표현을 그대로 원문과 문자열 비교하지 않는다. 비교표가 원문의 내용을 요약하거나
표현을 바꾼 경우에도 의미가 유지되는지를 판단한다. 다음을 구분한다.

① 완전 일치 → 🟢 일치
비교표의 내용이 원문의 내용과 일치하는 경우.

② 일부 누락 또는 오류 → 🔴 수정 필요
"일부 누락"은 비교표에 작성된 하나의 주장이나 문장 안에서 원문의 중요한 조건이 빠져
의미가 달라진 경우를 의미한다.
예: 원문 "이전 치료에 실패한 환자에서 사용" ↔ 비교표 "환자에서 사용"
→ 중요한 대상 조건이 사라졌으므로 수정 필요.
단순히 원문에 더 많은 정보가 있는데 비교표가 일부만 요약했다는 이유로 수정 필요로 판단하지 않는다.

③ 허가사항보다 범위가 넓거나 허가사항에 없는 내용 → 🔴 수정 필요
비교표에 작성된 내용이 원문보다 넓은 의미를 갖거나 원문에서 확인되지 않는 내용을
사실처럼 제시하는 경우.
예: 원문 "특정 바이오마커 양성 환자에서 사용" ↔ 비교표 "해당 질환 환자에서 사용"
→ 대상 범위가 넓어졌으므로 수정 필요.
또는 원문에 없는 투여방법을 비교표가 기재한 경우 → 수정 필요.

④ 표현 차이는 있으나 의미상 동일 → 🟡 확인 필요
표현이나 문장 구조는 다르지만 원문과 비교했을 때 의미가 동일한 경우.
예: 원문 "이전 치료에 적절한 반응을 보이지 않은 환자" ↔ 비교표 "기존 치료에 불응한 환자"
→ 의미상 동일하므로 확인 필요. 이 경우 오류라고 판단하지 않는다.

## 6. 적응증 검토

적응증은 비교표에 작성된 내용의 진위 여부를 판단한다. 다음 요소가 비교표에 포함되어
있다면 원문과 비교한다: 질환, 대상 환자, 성인/소아, 치료 목적, 치료 단계, 선행 치료 여부,
병용요법, 바이오마커/유전자 조건, 기타 제한조건.

원문의 적응증이 길고 비교표가 짧게 요약되어 있어도 핵심 의미가 유지되면 오류가 아니다.
반대로 비교표가 원문보다 환자 범위를 넓히거나 중요한 제한조건을 삭제하여 허가범위가
달라진다면 수정 필요다.

## 7. 용법·용량 검토

비교표에 작성된 용법·용량을 원문과 직접 대조한다. 특히 용량, 단위, 투여횟수, 투여간격,
투여주기, 투여기간, 체중/체표면적 기준, 용량 조절, 병용요법에 따른 용량을 확인한다.
숫자와 단위는 특히 엄격하게 확인한다.
예: 원문 "10 mg/kg" ↔ 비교표 "10 mg" → 🔴 수정 필요
예: 원문 "1일 1회" ↔ 비교표 "1일 2회" → 🔴 수정 필요
단순한 문장 축약으로 핵심 용량 정보가 그대로 유지되는 경우에는 오류로 판단하지 않는다.

## 8. 소아 관련 내용

비교표에 소아 관련 정보가 작성되어 있는 경우에만 원문과 대조한다: 연령, 소아 적응증,
소아 용량, 소아 사용 가능 여부, 소아에서 안전성/유효성 확립 여부. 연령 숫자가 다르면
명확하게 수정 필요로 표시한다.

## 9. 이상반응

비교표에 작성된 이상반응이 원문과 일치하는지를 확인한다. 중요한 것은 비교표에 없는
이상반응을 찾아내는 것이 아니라, 비교표에 작성된 이상반응이 원문에 근거하는지를
판단하는 것이다.
예: 원문 "두통, 오심, 발진, 피로" ↔ 비교표 "두통, 오심, 발진" → 오류로 판단하지 않음.
예: 원문 "두통, 오심, 발진" ↔ 비교표 "두통, 오심, 간독성" → 간독성이 원문에서 확인되지
않으면 수정 필요.

## 10. 보관방법

비교표에 보관방법이 기재되어 있는 경우 원문과 대조한다: 냉장/실온/냉동, 보관온도, 차광,
개봉 후 보관조건. 원문과 다른 경우 수정 필요로 표시한다.

## 11. 약가

비교표에 기재된 약가가 제공된 심평원 원문의 해당 제품 약가와 일치하는지 확인한다.
약가 이력이 여러 개 있는 경우에는 비교표에서 제시한 기준일 또는 적용기간을 고려하여
판단한다. 약가가 원문과 다른 경우 → 🔴 수정 필요. 단, 비교표에 과거 약가와 현재 약가 중
어떤 것을 의미하는지 명확하지 않아 판단할 수 없는 경우 → 🟡 확인 필요.

## 12. 제품 식별

제품명이 비슷하다는 이유만으로 동일 제품으로 판단하지 않는다. 가능한 경우 제품코드,
표준코드, 제품명, 성분, 함량, 제형, 업체명을 함께 확인한다. 원문과 비교표가 서로 다른
제품을 가리키는 것으로 보이면 → 🔴 수정 필요 또는 🟡 확인 필요. 단, 제공된 자료만으로
제품 동일성을 확정할 수 없다면 추측하지 않는다.

## 13. Reference 검토

비교표에 Reference와 관련된 주장 또는 설명이 작성되어 있는 경우에만 검토한다. Reference
자체가 비교표에 없다는 이유로 추가 정보를 요구하지 않는다. 비교표에 작성된 주장과
제공된 원문 또는 Reference의 내용이 실제로 부합하는지를 확인한다.

## 14. 판정 기준 (네 가지로 통일)

🟢 일치: 원문과 비교표의 내용이 일치한다.
🔴 수정 필요: 원문과 불일치 / 비교표 내용의 일부가 사실과 다름 / 비교표 내용이 원문보다
넓은 범위를 의미함 / 원문에 없는 내용을 사실처럼 작성함 / 중요한 조건이 삭제되어 의미가
달라짐 / 숫자·단위·연령·용량 등이 잘못됨 / 약가가 원문과 다름.
🟡 확인 필요: 표현이나 요약 방식에 차이가 있으나 의미상 동일한 것으로 보이는 경우.
사람이 최종적으로 확인할 가치가 있는 경우에만 표시한다.
⚪ 확인 불가: 제공된 원문만으로 진위 여부를 판단할 수 없는 경우.

## 15. 검토할 때 하지 말아야 할 것

1. 비교표에 없는 정보를 추가로 찾아서 누락이라고 지적하지 않는다.
2. 원문에 존재하는 모든 정보를 비교표가 포함해야 한다고 판단하지 않는다.
3. 비교표의 내용을 임의로 수정해서 완성된 표를 만들어주지 않는다.
4. 일반적인 의약품 지식을 이용하여 원문에 없는 정보를 보완하지 않는다.
5. 표현이 다르다는 이유만으로 오류라고 판단하지 않는다.
6. 단순 요약을 누락 또는 오류로 판단하지 않는다.
7. 원문에 없는 정보를 추측하여 오류라고 판단하지 않는다.
8. 제품이 다르다는 근거가 불충분한 경우 임의로 동일 제품 또는 다른 제품이라고 확정하지 않는다.

## 16. 최종 검토 원칙

"비교표에 작성된 이 문장이 원문에 근거하여 사실인가?"
사실이면 → 🟢 일치 / 사실과 다르면 → 🔴 수정 필요 / 표현은 다르지만 의미상 같으면 →
🟡 확인 필요 / 원문만으로 판단할 수 없으면 → ⚪ 확인 불가

비교표에 없는 정보를 찾아내는 것이 아니라, 비교표에 작성된 모든 내용의 진위 여부를
검증하는 것이 이번 작업의 목적이다.
""".strip()


OUTPUT_FORMAT_TEXT = """
[출력 형식]
아래 마크다운 표로만 답하라. 표 앞뒤에 다른 설명을 붙이지 마라.

| 제품 | 항목 | 판단 | 이유 | 원문 근거 |
|---|---|---|---|---|

- 판단 열에는 반드시 다음 중 하나만 적어라: 🟢 일치 / 🔴 수정 필요 / 🟡 확인 필요 / ⚪ 확인 불가
- 원문 근거 열에는 판단의 근거가 된 원문 문구를 짧게 인용하라. 근거가 없으면 "근거 없음"이라고 적어라.
- 판단할 근거가 부족하면 추측하지 말고 ⚪ 확인 불가로 표시하라.
""".strip()


def _format_entries_as_table_text(entries: list) -> str:
    """field/product/value 구조를 그대로 텍스트로 펼침 (요약 금지, 8장)."""
    lines = []
    current_product = None
    for e in entries:
        if e.get("product") != current_product:
            current_product = e.get("product")
            lines.append(f"\n### {current_product}")
        lines.append(f"- {e.get('field')}: {e.get('value')}")
    return "\n".join(lines).strip()


def _format_reference_text(product_name: str, mfds_data: dict, hira_data: dict) -> str:
    """MFDS/HIRA 원문을 요약 없이 그대로 텍스트로 펼침."""
    parts = [f"### {product_name}"]

    if mfds_data:
        parts.append("[MFDS 허가사항 원문]")
        for key, info in mfds_data.items():
            label = info.get("label", key) if isinstance(info, dict) else key
            value = info.get("value", "") if isinstance(info, dict) else str(info)
            if value:
                parts.append(f"- {label}: {value}")

    if hira_data:
        parts.append("[HIRA 약가정보]")
        for key, value in hira_data.items():
            if value not in (None, ""):
                parts.append(f"- {key}: {value}")

    return "\n".join(parts)


def build_prompt(entries: list, reference_data: dict, applicant_product: str,
                  comparator_products: list, scope_label: str = "전체") -> str:
    """
    entries: 프롬프트에 포함할 비교표 항목들 (field/product/value)
             — 호출부에서 이미 scope(전체/제품별/항목별)에 맞게 필터링해서 넘겨야 한다.
    reference_data: {product_name: {"mfds": {...}, "hira": {...}}, ...}
    """
    all_products = [applicant_product] + list(comparator_products)

    reference_blocks = []
    for p in all_products:
        ref = reference_data.get(p, {})
        reference_blocks.append(_format_reference_text(p, ref.get("mfds", {}), ref.get("hira", {})))

    table_text = _format_entries_as_table_text(entries)

    prompt = f"""[역할]
너는 의약품 심의자료의 사실관계를 검증하는 검토자다.

[검증 원칙]
{VERIFICATION_PRINCIPLE_TEXT}

[검증 대상 제품]
신청의약품: {applicant_product}
비교의약품: {", ".join(comparator_products) if comparator_products else "(없음)"}

[검증 범위]
이번 요청은 "{scope_label}" 범위에 대한 검증이다. 아래 [심의자료 비교표]에 실제로
포함된 항목만 검토하고, 여기 없는 항목은 언급하지 마라.

[MFDS 허가사항 원문 / HIRA 약가정보]
{chr(10).join(reference_blocks)}

[심의자료 비교표]
{table_text}

[검증 요청]
각 항목별로 비교표 내용이 위 원문과 의미상 일치하는지 판단하라. 판정 4단계(🟢 일치 /
🔴 수정 필요 / 🟡 확인 필요 / ⚪ 확인 불가)와 근거 제시 규칙을 지켜라.

{OUTPUT_FORMAT_TEXT}
"""
    return prompt.strip()


def build_full_prompt(entries, reference_data, applicant_product, comparator_products):
    return build_prompt(entries, reference_data, applicant_product, comparator_products, "전체")


def build_product_prompt(entries, reference_data, applicant_product, comparator_products, target_product):
    filtered = [e for e in entries if e.get("product") == target_product]
    return build_prompt(filtered, reference_data, applicant_product, comparator_products,
                         f"{target_product} 전체 항목")


def build_field_prompt(entries, reference_data, applicant_product, comparator_products, target_field_keywords):
    """target_field_keywords: 예) ["효능", "적응증"] -> field에 이 중 하나라도 포함되면 대상."""
    filtered = [e for e in entries if any(kw in (e.get("field") or "") for kw in target_field_keywords)]
    label = "/".join(target_field_keywords)
    return build_prompt(filtered, reference_data, applicant_product, comparator_products, f"{label} 항목만")
