# -*- coding: utf-8 -*-
"""
MFDS(식약처) 의약품 허가정보, HIRA(심평원) 약가정보 API 클라이언트.

주의: 이 환경(대화 중 코드 작성 단계)에서는 data.go.kr 계열 도메인으로의
실제 네트워크 호출을 테스트할 수 없다(허용 도메인 목록에 없음).
아래 구현은 공개된 API 스펙(공공데이터포털 "의약품 개요정보(e약은요)" /
"의약품 제품 허가정보" / "건강보험심사평가원_의약품 상한금액")을 기준으로 작성했으며,
실제 서비스키로 로컬 또는 Streamlit Cloud에서 1회 스모크 테스트가 필요하다.

- 서비스키는 코드에 하드코딩하지 않는다 (9장 절대 변경 금지 사항 9).
  st.secrets["MFDS_SERVICE_KEY"] / st.secrets["HIRA_SERVICE_KEY"] 를 우선 사용하고,
  없으면 st.text_input(type="password")로 입력받는다.
"""
import requests
from urllib.parse import unquote

MFDS_LIST_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"
# 상세조회(NB_DOC_DATA 등 허가사항 원문 포함) 엔드포인트는 미확인 상태입니다.
# data.go.kr 15095677 페이지에서 실제 미리보기로 확인한 값으로 교체해야 합니다.
MFDS_DETAIL_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq05"
HIRA_PRICE_URL = "https://apis.data.go.kr/B551182/dgamtCrtrInfoService1.2/getDgamtList"

DEFAULT_TIMEOUT = 15


class ApiError(Exception):
    """API가 HTTP 200이지만 resultCode(오류코드)가 정상이 아닌 경우를 명시적으로 드러내기 위한 예외."""
    pass


def _decode_key(service_key: str) -> str:
    """공공데이터포털 서비스키는 이미 URL-encoded 상태로 발급되는 경우가 많아 이중 인코딩을 방지."""
    if not service_key:
        return service_key
    return unquote(service_key)


def _request_xml_or_json(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)

    # data.go.kr은 오류 시에도 본문(XML/JSON)에 resultCode/resultMsg를 실어 보내는 경우가 많다.
    # HTTP 상태코드만 보고 raise_for_status()를 먼저 호출하면 그 본문을 못 보고 예외가 나버리므로,
    # 상태코드와 무관하게 먼저 본문 파싱을 시도해서 실제 사유를 노출한다.
    body_preview = resp.text.strip()[:500]
    ctype = resp.headers.get("Content-Type", "")

    try:
        if "json" in ctype or body_preview.startswith("{"):
            data = resp.json()
            header = (data.get("response", {}) or {}).get("header", {}) or data.get("header", {})
        else:
            import xmltodict
            data = xmltodict.parse(resp.text)
            header = (((data.get("response") or {}).get("header")) or {})
    except Exception:
        # 본문 자체가 JSON/XML이 아님 (예: 순수 HTML 오류 페이지) -> HTTP 상태코드 + 본문 일부를 그대로 노출
        raise ApiError(
            f"HTTP {resp.status_code} - 응답을 JSON/XML로 파싱하지 못함. "
            f"(url={resp.url}) 응답 본문 일부: {body_preview}"
        )

    result_code = str(header.get("resultCode", "" if resp.status_code >= 400 else "00"))
    # 정상 코드는 기관별로 "00" 또는 "0"인 경우가 있어 둘 다 허용
    if result_code not in ("00", "0"):
        result_msg = header.get("resultMsg", f"HTTP {resp.status_code} (본문에서 resultMsg를 찾지 못함)")
        raise ApiError(f"[{result_code}] {result_msg} (url={resp.url}) 응답 본문 일부: {body_preview}")

    if resp.status_code >= 400:
        raise ApiError(f"HTTP {resp.status_code} 오류 (url={resp.url}) 응답 본문 일부: {body_preview}")

    return data


def _get_items(data: dict) -> list:
    """공공데이터포털 표준 응답에서 items 리스트만 안전하게 추출. 0건이어도 빈 리스트를 반환(freeze 방지)."""
    body = (((data.get("response") or {}).get("body")) or data.get("body") or {})
    items = body.get("items") or {}
    if isinstance(items, dict):
        item = items.get("item")
        if item is None:
            return []
        return item if isinstance(item, list) else [item]
    if isinstance(items, list):
        return items
    return []


def fetch_all_mfds_products(service_key: str, num_of_rows: int = 100, max_pages: int = 400,
                             progress_callback=None) -> list:
    """
    식약처 의약품 제품 허가정보 '전체' 목록을 여러 페이지에 걸쳐 가져온다.
    item_name 없이 호출하므로 전체 허가 의약품(수만 건)이 대상이라 시간이 걸릴 수 있다.
    하루 1회 정도만 호출하고, 이후 검색은 이 결과를 세션에 캐시해서 로컬에서 필터링하는
    용도로 쓰기 위한 함수다 (매 검색마다 API를 다시 호출하지 않기 위함).

    progress_callback(page, total_fetched)을 넘기면 페이지마다 호출되어 진행상황을 알릴 수 있다.
    """
    key = _decode_key(service_key)
    all_items = []
    for page in range(1, max_pages + 1):
        params = {
            "serviceKey": key,
            "type": "json",
            "pageNo": page,
            "numOfRows": num_of_rows,
        }
        data = _request_xml_or_json(MFDS_LIST_URL, params)
        items = _get_items(data)
        if not items:
            break
        all_items.extend(items)
        if progress_callback:
            progress_callback(page, len(all_items))
        if len(items) < num_of_rows:
            break
    return all_items


def search_mfds_drugs(service_key: str, item_name: str = "", entp_name: str = "",
                       page_no: int = 1, num_of_rows: int = 50, max_pages: int = 20) -> list:
    """
    MFDS 의약품 제품 허가정보 목록 조회.
    totalCount가 0/누락으로 잘못 파싱돼도 무한루프에 빠지지 않도록 max_pages로 상한을 둔다.
    """
    key = _decode_key(service_key)
    all_items = []
    for page in range(page_no, page_no + max_pages):
        params = {
            "serviceKey": key,
            "type": "json",
            "pageNo": page,
            "numOfRows": num_of_rows,
        }
        if item_name:
            params["item_name"] = item_name
        if entp_name:
            params["entp_name"] = entp_name

        data = _request_xml_or_json(MFDS_LIST_URL, params)
        items = _get_items(data)
        if not items:
            break
        all_items.extend(items)
        if len(items) < num_of_rows:
            break
    return all_items


def get_mfds_detail(service_key: str, item_seq: str) -> dict:
    """MFDS 의약품 상세조회(허가사항 원문 NB_DOC_DATA 포함)."""
    key = _decode_key(service_key)
    params = {
        "serviceKey": key,
        "type": "json",
        "item_seq": item_seq,
    }
    data = _request_xml_or_json(MFDS_DETAIL_URL, params)
    items = _get_items(data)
    return items[0] if items else {}


def search_hira_price(service_key: str, item_name: str = "", mds_cd: str = "",
                       page_no: int = 1, num_of_rows: int = 50, max_pages: int = 20) -> list:
    """
    HIRA 약가(상한금액) 조회. payTpNm != '삭제' 인 건만 유효한 것으로 필터링.
    """
    key = _decode_key(service_key)
    all_items = []
    for page in range(page_no, page_no + max_pages):
        params = {
            "serviceKey": key,
            "type": "json",
            "pageNo": page,
            "numOfRows": num_of_rows,
        }
        if item_name:
            params["itmNm"] = item_name
        if mds_cd:
            params["mdsCd"] = mds_cd

        data = _request_xml_or_json(HIRA_PRICE_URL, params)
        items = _get_items(data)
        if not items:
            break
        all_items.extend(items)
        if len(items) < num_of_rows:
            break

    return [row for row in all_items if row.get("payTpNm") != "삭제"]
