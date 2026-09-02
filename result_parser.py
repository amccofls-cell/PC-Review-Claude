# -*- coding: utf-8 -*-
"""
사용자가 Claude 웹(claude.ai)에서 받은 답변을 붙여넣으면
마크다운 표 또는 JSON({"results":[...]}) 둘 다 지원해서 파싱한다.
파싱 실패 시 절대 추측해서 채우지 않고 "형식을 인식하지 못했습니다" + 원문 그대로 표시(8장).
"""
import json
import re

STATUS_COLOR = {
    "🟢 일치": "green", "일치": "green",
    "🔴 수정 필요": "red", "수정 필요": "red", "수정필요": "red",
    "🟡 확인 필요": "orange", "확인 필요": "orange", "확인필요": "orange",
    "⚪ 확인 불가": "gray", "확인 불가": "gray", "확인불가": "gray",
}


def _normalize_status(raw: str) -> str:
    raw = (raw or "").strip()
    for key in STATUS_COLOR:
        if key in raw:
            return key
    return raw


def parse_json_result(text: str):
    """{"results":[{"product":..,"field":..,"판단":..,"이유":..,"근거":..}, ...]} 형태 파싱 시도."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return None

    parsed = []
    for row in results:
        if not isinstance(row, dict):
            return None
        parsed.append({
            "product": row.get("product") or row.get("제품", ""),
            "field": row.get("field") or row.get("항목", ""),
            "status": _normalize_status(row.get("판단") or row.get("status", "")),
            "reason": row.get("이유") or row.get("reason", ""),
            "evidence": row.get("원문 근거") or row.get("evidence", ""),
        })
    return parsed if parsed else None


_MD_ROW_RE = re.compile(r"^\|(.+)\|\s*$")


def parse_markdown_table(text: str):
    """
    | 제품 | 항목 | 판단 | 이유 | 원문 근거 | 형태의 마크다운 표를 파싱.
    구분선(|---|---|...) 행은 스킵. 컬럼 수가 5개가 아니면 파싱 실패로 간주.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return None

    rows = []
    for ln in lines:
        m = _MD_ROW_RE.match(ln)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        # 구분선(---, :--- 등)은 스킵
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        rows.append(cells)

    if not rows:
        return None

    # 첫 행이 헤더인지 판단 (제품/항목/판단 등의 키워드 포함 여부)
    header = rows[0]
    header_keywords = {"제품", "항목", "판단", "이유", "근거"}
    is_header = any(any(k in c for k in header_keywords) for c in header)
    data_rows = rows[1:] if is_header else rows

    parsed = []
    for cells in data_rows:
        if len(cells) < 5:
            continue
        product, field, status, reason, evidence = cells[:5]
        parsed.append({
            "product": product,
            "field": field,
            "status": _normalize_status(status),
            "reason": reason,
            "evidence": evidence,
        })
    return parsed if parsed else None


def parse_claude_result(text: str) -> dict:
    """
    반환: {"ok": bool, "rows": [...] or None, "raw": text}
    ok=False면 화면에서 "형식을 인식하지 못했습니다 + 원문 그대로 표시" 처리해야 한다.
    """
    if not text or not text.strip():
        return {"ok": False, "rows": None, "raw": text}

    rows = parse_json_result(text.strip())
    if rows:
        return {"ok": True, "rows": rows, "raw": text}

    rows = parse_markdown_table(text)
    if rows:
        return {"ok": True, "rows": rows, "raw": text}

    return {"ok": False, "rows": None, "raw": text}
