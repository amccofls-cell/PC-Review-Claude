# -*- coding: utf-8 -*-
"""
의약품 심의자료 진위·오탈자 검증기 v4.0
- CSV 업로드 없음: 검색 → 즉시 API 조회
- Claude API 미호출: 프롬프트 텍스트만 생성해 claude.ai 웹에 붙여넣는 방식
"""
import streamlit as st

from modules import api_client, field_specs, matching
from modules.table_parsers import pptx_parser, xlsx_parser, paste_parser, normalize
from modules import rule_check, prompt_builder, result_parser

st.set_page_config(page_title="의약품 심의자료 검증기 v4.0", layout="wide")

# ---------------------------------------------------------------------------
# 세션 상태 초기화
# ---------------------------------------------------------------------------
def _init_state():
    defaults = {
        "selected_applicant": None,      # {"name":..., "mfds_detail":..., "hira":...}
        "selected_comparators": [],       # [{"name":..., "mfds_detail":..., "hira":...}, ...]
        "reference_data": {},             # {product_name: {"mfds": {...}, "hira": {...}}}
        "raw_grid": None,                 # 파싱 직후 원본 grid
        "orientation": None,              # "row" | "col"
        "entries": [],                    # 공통 스키마로 정규화된 비교표
        "rule_check_results": [],
        "claude_result_parsed": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


def get_service_keys():
    with st.sidebar:
        st.subheader("API 인증키")
        st.caption("공공데이터포털에서 발급받은 '디코딩된' 서비스키를 입력하세요. 세션 동안만 유지됩니다.")
        mfds_key = st.text_input("MFDS 서비스키", type="password", key="mfds_key_input")
        hira_key = st.text_input("HIRA 서비스키", type="password", key="hira_key_input")
    return mfds_key, hira_key


mfds_key, hira_key = get_service_keys()


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def _load_full_mfds_list(service_key: str):
    return api_client.fetch_all_mfds_products(service_key)


tab1, tab2, tab3 = st.tabs(["🔍 의약품 조회", "📋 비교표 입력", "🧾 검증 · Claude 자료"])

# ---------------------------------------------------------------------------
# 탭 1: 의약품 조회 — 검색 → 신청/비교 선택 → 즉시 MFDS+HIRA 조회
# ---------------------------------------------------------------------------
with tab1:
    st.markdown("MFDS 서비스키를 입력한 뒤 전체 목록을 한 번만 불러오면, 이후 검색은 매번 API를 "
                "호출하지 않고 불러온 목록 안에서 즉시(로컬) 필터링됩니다. CSV 업로드 단계는 없습니다.")

    full_list = st.session_state.get("mfds_full_list")
    results = []

    query = st.text_input("제품명/성분명 검색", key="drug_search_query",
                          disabled=not mfds_key,
                          help="전체 목록을 불러온 상태면 즉시(로컬) 검색, 아니면 그때그때 API로 검색합니다")

    if full_list:
        st.caption(f"✅ 전체 목록 {len(full_list)}건이 로드되어 있어 검색이 즉시 처리됩니다.")
        if query:
            q = query.strip()
            results = [
                r for r in full_list
                if q in (r.get("ITEM_NAME", "") or r.get("itemName", ""))
                or q in (r.get("ENTP_NAME", "") or r.get("entpName", ""))
                or q in (r.get("MAIN_ITEM_INGR", "") or "")
            ]
            st.session_state["search_results"] = results
    else:
        st.caption("전체 목록을 아직 안 불러오셨습니다 — 검색하면 그때그때 API로 조회합니다 "
                   "(느릴 수 있음). 자주 쓰실 거면 아래 '전체 목록 불러오기'를 눌러두세요.")
        if st.button("검색", key="btn_search_live") and query:
            try:
                with st.spinner("MFDS 목록 조회 중..."):
                    results = api_client.search_mfds_drugs(mfds_key, item_name=query)
                st.session_state["search_results"] = results
                if not results:
                    st.warning("검색 결과가 없습니다.")
            except api_client.ApiError as e:
                st.error(f"MFDS API 오류: {e}")
            except Exception as e:
                st.error(f"조회 중 오류 발생: {e}")

    st.divider()
    if not mfds_key:
        st.info("먼저 왼쪽 사이드바에 MFDS 서비스키를 입력하세요.")
    else:
        col_load, col_refresh = st.columns([3, 1])
        with col_load:
            if st.button("📥 전체 목록 불러오기 (검색을 자주 하실 거면 추천, 몇 분 걸림)", key="btn_load_full_list"):
                try:
                    with st.spinner("식약처 전체 목록을 불러오는 중입니다. 수만 건이라 몇 분 걸릴 수 있습니다..."):
                        loaded = _load_full_mfds_list(mfds_key)
                    st.session_state["mfds_full_list"] = loaded
                    st.success(f"{len(loaded)}건 불러왔습니다. 오늘은 다시 누르지 않아도 됩니다.")
                    st.rerun()
                except api_client.ApiError as e:
                    st.error(f"MFDS API 오류: {e}")
                except Exception as e:
                    st.error(f"조회 중 오류 발생: {e}")
        with col_refresh:
            if st.button("🔄 새로고침", key="btn_refresh_list",
                         help="목록이 오래됐거나 오류가 의심될 때만 누르세요"):
                _load_full_mfds_list.clear()
                st.session_state.pop("mfds_full_list", None)
                st.info("캐시를 비웠습니다.")
                st.rerun()

    results = st.session_state.get("search_results", [])
    if results:
        st.write(f"검색 결과 {len(results)}건")
        names = [f"{r.get('ITEM_NAME', r.get('itemName',''))} ({r.get('ENTP_NAME', r.get('entpName',''))})"
                 for r in results]

        col1, col2 = st.columns(2)
        with col1:
            applicant_idx = st.selectbox("신청의약품 선택 (1개)", options=range(len(names)),
                                          format_func=lambda i: names[i], key="applicant_select")
        with col2:
            comparator_idxs = st.multiselect("비교의약품 선택 (N개)", options=range(len(names)),
                                              format_func=lambda i: names[i], key="comparator_select")

        if st.button("선택 제품 즉시 조회 (MFDS + HIRA)", key="btn_fetch_selected"):
            if not mfds_key or not hira_key:
                st.error("MFDS/HIRA 서비스키를 모두 입력하세요.")
            else:
                def fetch_one(row):
                    name = row.get("ITEM_NAME", row.get("itemName", ""))
                    item_seq = row.get("ITEM_SEQ", row.get("itemSeq", ""))
                    try:
                        detail = api_client.get_mfds_detail(mfds_key, item_seq)
                        extra = field_specs.extract_extra_fields(detail)
                    except api_client.ApiError as e:
                        st.warning(f"{name} MFDS 상세조회 오류: {e}")
                        detail, extra = {}, {}

                    try:
                        hira_rows = api_client.search_hira_price(hira_key, item_name=name)
                    except api_client.ApiError as e:
                        st.warning(f"{name} HIRA 약가조회 오류: {e}")
                        hira_rows = []

                    # 8자리 코드 매칭으로 정확한 HIRA 행 선택 (제품명만으로 확정하지 않음)
                    bar_code = detail.get("BAR_CODE", "")
                    matched_hira = None
                    for hr in hira_rows:
                        if matching.is_same_product(hr.get("mdsCd", ""), bar_code):
                            matched_hira = hr
                            break

                    return {
                        "name": name,
                        "mfds_detail": detail,
                        "mfds_extra": extra,
                        "hira": matched_hira or (hira_rows[0] if hira_rows else {}),
                        "hira_candidates": hira_rows,
                        "code_matched": matched_hira is not None,
                    }

                with st.spinner("조회 중..."):
                    applicant = fetch_one(results[applicant_idx])
                    comparators = [fetch_one(results[i]) for i in comparator_idxs]

                st.session_state["selected_applicant"] = applicant
                st.session_state["selected_comparators"] = comparators

                ref_data = {applicant["name"]: {"mfds": applicant["mfds_extra"], "hira": applicant["hira"]}}
                for c in comparators:
                    ref_data[c["name"]] = {"mfds": c["mfds_extra"], "hira": c["hira"]}
                st.session_state["reference_data"] = ref_data
                st.success("조회 완료")

    if st.session_state["selected_applicant"]:
        st.divider()
        st.subheader("조회 결과")
        a = st.session_state["selected_applicant"]
        st.markdown(f"**신청의약품**: {a['name']}  "
                    f"{'✅ 코드매칭' if a['code_matched'] else '⚠️ 코드매칭 실패(제품명만 참고)'}")
        with st.expander("MFDS/HIRA 원문 보기"):
            st.json({"mfds_extra": a["mfds_extra"], "hira": a["hira"]})

        for c in st.session_state["selected_comparators"]:
            st.markdown(f"**비교의약품**: {c['name']}  "
                        f"{'✅ 코드매칭' if c['code_matched'] else '⚠️ 코드매칭 실패(제품명만 참고)'}")
            with st.expander(f"{c['name']} MFDS/HIRA 원문 보기"):
                st.json({"mfds_extra": c["mfds_extra"], "hira": c["hira"]})

# ---------------------------------------------------------------------------
# 탭 2: 비교표 입력 — PPTX / XLSX / 붙여넣기 + 구조 확인 화면 (7장)
# ---------------------------------------------------------------------------
with tab2:
    input_method = st.radio("입력 방식", ["붙여넣기 (권장, tab-구분)", "PPTX 업로드", "XLSX 업로드"],
                             key="input_method")

    grid = None
    slide_no = None

    if input_method.startswith("붙여넣기"):
        st.caption("Excel 등에서 표를 복사해 아래에 붙여넣으세요 (탭으로 구분된 표를 우선 지원합니다).")
        pasted = st.text_area("여기에 붙여넣기", height=200, key="paste_area")
        if pasted:
            parsed = paste_parser.parse_tab_separated(pasted)
            grid = parsed["grid"]
            if parsed["irregular"]:
                st.warning("행마다 열 개수가 달라 표 구조가 불안정합니다. PPT 표 복사 시 흔히 발생합니다. "
                           "아래 미리보기에서 표 방향을 반드시 확인하세요.")

    elif input_method == "PPTX 업로드":
        uploaded = st.file_uploader("PPTX 파일 업로드", type=["pptx"], key="pptx_uploader")
        if uploaded:
            tables = pptx_parser.parse_pptx_tables(uploaded)
            if not tables:
                st.warning("표를 찾지 못했습니다.")
            else:
                labels = [f"슬라이드 {t['slide']} - 표 {t['table_index']}" for t in tables]
                idx = st.selectbox("검증할 표 선택", options=range(len(tables)),
                                    format_func=lambda i: labels[i], key="pptx_table_select")
                grid = tables[idx]["grid"]
                slide_no = tables[idx]["slide"]

    else:  # XLSX
        uploaded = st.file_uploader("XLSX 파일 업로드", type=["xlsx"], key="xlsx_uploader")
        if uploaded:
            tables = xlsx_parser.parse_xlsx_tables(uploaded)
            if not tables:
                st.warning("표를 찾지 못했습니다.")
            else:
                labels = [t["sheet"] for t in tables]
                idx = st.selectbox("검증할 시트 선택", options=range(len(tables)),
                                    format_func=lambda i: labels[i], key="xlsx_table_select")
                grid = tables[idx]["grid"]

    if grid:
        st.session_state["raw_grid"] = grid
        st.divider()
        st.subheader("비교표 구조 확인 (필수)")
        guessed = normalize.guess_orientation(grid)

        default_idx = 0 if guessed == "row" else 1
        orientation_label = st.radio(
            "항목(성분명/효능효과 등)이 어느 방향으로 나열되어 있습니까?",
            ["1행이 항목명 (항목이 가로로 나열, 제품이 세로 나열)",
             "1열이 항목명 (항목이 세로로 나열, 제품이 가로 나열)"],
            index=default_idx if guessed in ("row", "col") else 0,
            key="orientation_radio",
        )
        orientation = "row" if orientation_label.startswith("1행") else "col"
        if guessed == "ambiguous":
            st.info("자동 추정이 애매해서 기본값을 표시했습니다. 아래 미리보기를 보고 방향을 직접 확인하세요.")

        st.markdown("**미리보기 (원본 grid)**")
        st.dataframe(grid, use_container_width=True)

        if st.button("이 방향으로 확정", key="btn_confirm_orientation"):
            entries = normalize.grid_to_common_schema(grid, orientation, slide=slide_no, table_index=1)
            st.session_state["entries"] = entries
            st.session_state["orientation"] = orientation
            st.success(f"{len(entries)}개 항목으로 정규화 완료. '🧾 검증 · Claude 자료' 탭으로 이동하세요.")

    if st.session_state["entries"]:
        with st.expander("현재 정규화된 비교표 항목 보기"):
            st.dataframe(st.session_state["entries"], use_container_width=True)

# ---------------------------------------------------------------------------
# 탭 3: 검증 · Claude 자료 생성 + 결과 재파싱
# ---------------------------------------------------------------------------
with tab3:
    entries = st.session_state["entries"]
    reference_data = st.session_state["reference_data"]
    applicant = st.session_state["selected_applicant"]
    comparators = st.session_state["selected_comparators"]

    if not entries:
        st.info("먼저 '📋 비교표 입력' 탭에서 비교표를 입력·확정하세요.")
    elif not applicant:
        st.info("먼저 '🔍 의약품 조회' 탭에서 신청/비교 의약품을 선택·조회하세요.")
    else:
        applicant_name = applicant["name"]
        comparator_names = [c["name"] for c in comparators]

        # --- 5장 규칙기반 1차 검증 ---
        st.subheader("Python 1차 규칙 검증 (숫자·단위·기본정보·약가만 기계적으로 확정)")
        reference_lookup = {}
        for product, ref in reference_data.items():
            field_values = {}
            for key, info in ref.get("mfds", {}).items():
                field_values[info.get("label", key)] = info.get("value", "")
            hira = ref.get("hira", {})
            if hira:
                field_values["약가"] = hira.get("gnlNm", "") or hira.get("appTot", "")
            reference_lookup[product] = field_values

        rule_results = rule_check.run_rule_checks(entries, reference_lookup)
        st.session_state["rule_check_results"] = rule_results

        status_order = {"수정필요": 0, "CLAUDE_확인필요": 1, "확인불가": 2, "일치": 3}
        rule_results_sorted = sorted(rule_results, key=lambda r: status_order.get(r["status"], 9))
        st.dataframe(rule_results_sorted, use_container_width=True)

        n_error = sum(1 for r in rule_results if r["status"] == "수정필요")
        n_claude = sum(1 for r in rule_results if r["status"] == "CLAUDE_확인필요")
        st.caption(f"🔴 자동 확정 수정필요 {n_error}건 · 🟡 Claude 확인 필요(서술형) {n_claude}건")

        st.divider()
        st.subheader("Claude 웹용 자료 생성 (이 앱은 Anthropic API를 호출하지 않습니다)")
        st.caption("아래에서 생성된 텍스트를 복사해 claude.ai 웹 채팅에 붙여넣고, 응답을 다시 이 페이지 하단에 붙여넣으세요.")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("[Claude용 전체 자료 생성]"):
                st.session_state["generated_prompt"] = prompt_builder.build_full_prompt(
                    entries, reference_data, applicant_name, comparator_names)
        with col_b:
            target_product = st.selectbox("제품 선택", options=[applicant_name] + comparator_names,
                                           key="product_scope_select")
            if st.button("[제품별 자료 생성]"):
                st.session_state["generated_prompt"] = prompt_builder.build_product_prompt(
                    entries, reference_data, applicant_name, comparator_names, target_product)
        with col_c:
            field_choice = st.selectbox("항목 선택", ["효능·효과/적응증", "용법·용량", "이상반응", "기본정보"],
                                         key="field_scope_select")
            field_kw_map = {
                "효능·효과/적응증": ["효능", "적응증"],
                "용법·용량": ["용법", "용량"],
                "이상반응": ["이상반응"],
                "기본정보": ["성분명", "제품명", "제조", "판매사", "제형", "함량"],
            }
            if st.button("[항목별 자료 생성]"):
                st.session_state["generated_prompt"] = prompt_builder.build_field_prompt(
                    entries, reference_data, applicant_name, comparator_names,
                    field_kw_map[field_choice])

        if st.session_state.get("generated_prompt"):
            st.text_area("생성된 프롬프트 (전체 선택 후 복사하세요)",
                         value=st.session_state["generated_prompt"], height=400,
                         key="generated_prompt_display")

        st.divider()
        st.subheader("Claude 검증 결과 붙여넣기")
        result_text = st.text_area("claude.ai 웹 응답을 여기에 붙여넣으세요 (마크다운 표 또는 JSON)",
                                    height=200, key="claude_result_input")
        if st.button("결과 파싱", key="btn_parse_result") and result_text:
            parsed = result_parser.parse_claude_result(result_text)
            st.session_state["claude_result_parsed"] = parsed

        parsed = st.session_state.get("claude_result_parsed")
        if parsed:
            if parsed["ok"]:
                st.success(f"{len(parsed['rows'])}건 파싱 완료")

                def _status_style(row):
                    color = result_parser.STATUS_COLOR.get(row["status"], "")
                    return [f"background-color: {color}20"] * len(row)

                st.dataframe(parsed["rows"], use_container_width=True)
            else:
                st.error("형식을 인식하지 못했습니다. 원문을 그대로 표시합니다.")
                st.text(parsed["raw"])
