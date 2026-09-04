# -*- coding: utf-8 -*-
"""
의약품 심의자료 진위·오탈자 검증기 v4.0
- 1번 탭: 검증된 형식(검색→선택표→추가항목 체크→조회→상세/비교표/DUR)의 의약품 조회
- 2번 탭: PPTX/XLSX/붙여넣기 비교표 입력
- 3번 탭: 규칙기반 1차 검증 + Claude 웹용 자료 생성 (Claude API 미호출)
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from modules import mfds_hira_core as core
from modules import ui_table
from modules.table_parsers import pptx_parser, xlsx_parser, paste_parser, normalize
from modules import rule_check, prompt_builder, result_parser

st.set_page_config(page_title="의약품 심의자료 검증기 v4.0", page_icon="💊", layout="wide")
st.title("💊 의약품 심의자료 진위·오탈자 검증기 v4.0")

# ---------------------------------------------------------------------------
# 세션 상태 초기화
# ---------------------------------------------------------------------------
def _init_state():
    defaults = {
        "selection": [],          # 조회 대상으로 선택된 ITEM_SEQ 목록
        "last_result": None,       # 조회 결과 DataFrame (허가제품명/성분명/효능효과 등)
        "last_errors": [],
        "dur_indices": {},
        "raw_grid": None,
        "orientation": None,
        "entries": [],             # 비교표 공통 스키마
        "rule_check_results": [],
        "claude_result_parsed": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ---------------------------------------------------------------------------
# 사이드바: 인증키 + DUR 업로드
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("설정")
    st.caption("API 키는 코드에 저장하지 않습니다. 세션 동안만 유지됩니다.")
    mfds_key = st.text_input("식약처 인증키 (디코딩된 키)", type="password", key="mfds_key_input")
    hira_key = st.text_input("심평원 인증키 (디코딩된 키)", type="password", key="hira_key_input")

    if st.button("허가목록 캐시 새로고침"):
        st.cache_data.clear()
        for cache_path in (core.LIST_FILE, core.LIST_META_FILE, core.TEMP_FILE):
            if cache_path.exists():
                cache_path.unlink()
        st.rerun()
    st.caption("허가목록은 KST 기준 하루 1회만 자동 갱신합니다.")

    st.divider()
    st.markdown("**DUR 품목리스트 업로드** (선택)")
    st.caption("엑셀에 '제품코드'(또는 제품코드A/B, 약품코드) 열이 있어야 합니다.")
    for category in core.DUR_CATEGORIES:
        uploaded = st.file_uploader(category, type=["xlsx", "xls", "xlsb"], key=f"dur_upload_{category}")
        if uploaded is not None:
            try:
                dur_df, header_row, dur_index, code_columns = core.parse_dur_excel_cached(
                    uploaded.getvalue(), uploaded.name)
            except Exception as exc:
                st.error(f"[{category}] '{uploaded.name}' 읽기 실패: {exc}")
            else:
                if not code_columns:
                    st.warning(f"[{category}] '{uploaded.name}'에서 제품코드/약품코드 열을 찾지 못했습니다.")
                else:
                    st.session_state.dur_indices[category] = dur_index
                    st.success(f"[{category}] {len(dur_df):,}행, 매칭 제품코드 {len(dur_index):,}종 적용됨")

tab1, tab2, tab3 = st.tabs(["🔍 의약품 조회", "📋 비교표 입력", "🧾 검증 · Claude 자료"])

# ===========================================================================
# 탭 1: 의약품 조회 (검증된 형식 그대로)
# ===========================================================================
with tab1:
    cache_day = core.current_kst_date()
    cache_fresh = core.list_cache_is_fresh()
    if not cache_fresh and not mfds_key:
        st.warning("오늘 날짜의 허가목록 캐시가 없어 식약처 인증키가 필요합니다.")
        st.stop()
    if not hira_key:
        st.info("검색목록은 열 수 있지만, 약가·상세정보 조회에는 심평원 인증키가 필요합니다.")

    try:
        all_rows = core.load_permitted_drugs(mfds_key, str(core.DATA_DIR), cache_day)
    except Exception as exc:
        st.error(f"허가목록 수집에 실패했습니다: {exc}")
        st.exception(exc)
        st.stop()

    normal_rows = [row for row in all_rows if row.get("CANCEL_NAME") == "정상"]
    by_seq = {row.get("ITEM_SEQ", ""): row for row in normal_rows}
    st.success(f"정상 품목 {len(normal_rows):,}건 준비 완료")

    st.subheader("1. 의약품 검색")
    query = st.text_input("의약품명 또는 제약사명", placeholder="예: 타이레놀, 한미약품", key="drug_search_query")
    matches = []
    if query.strip():
        q = query.strip().casefold()
        matches = [row for row in normal_rows
                  if q in row.get("ITEM_NAME", "").casefold() or q in row.get("ENTP_NAME", "").casefold()][:200]
        st.caption(f"검색결과 {len(matches)}건 표시 (최대 200건)")

    if matches:
        search_df = pd.DataFrame([
            {"의약품명": row.get("ITEM_NAME", ""), "제약사": row.get("ENTP_NAME", ""), "품목코드": row.get("ITEM_SEQ", "")}
            for row in matches
        ])
        search_event = st.dataframe(
            search_df, use_container_width=True, hide_index=True,
            height=min(520, 36 + len(search_df) * 35),
            selection_mode="multi-row", on_select="rerun",
            key=f"search_results_table_{query.strip().casefold()}",
        )
        search_selected_seqs = [
            str(search_df.iloc[index]["품목코드"])
            for index in search_event.selection.rows
            if 0 <= index < len(search_df)
        ]
        st.caption(f"검색 결과에서 선택한 품목: **{len(search_selected_seqs)}건**")
        if st.button("선택한 검색 결과를 조회 목록에 추가", disabled=not search_selected_seqs, key="add_search_selection"):
            for seq in search_selected_seqs:
                if seq and seq not in st.session_state.selection:
                    st.session_state.selection.append(seq)
            st.rerun()

    st.subheader("2. 조회할 품목")
    selected_rows = [by_seq[seq] for seq in st.session_state.selection if seq in by_seq]
    if selected_rows:
        selected_df = pd.DataFrame([
            {"의약품명": row.get("ITEM_NAME", ""), "제약사": row.get("ENTP_NAME", ""), "품목코드": row.get("ITEM_SEQ", "")}
            for row in selected_rows
        ])
        st.caption("아래 표에서 제거할 행을 선택한 뒤 버튼을 누르세요.")
        selected_event = st.dataframe(
            selected_df, use_container_width=True, hide_index=True,
            height=min(360, 36 + len(selected_df) * 35),
            selection_mode="multi-row", on_select="rerun", key="selected_items_table",
        )
        if st.button("선택한 품목 제거", disabled=not selected_event.selection.rows):
            remove_seq = {str(selected_df.iloc[index]["품목코드"]) for index in selected_event.selection.rows}
            st.session_state.selection = [seq for seq in st.session_state.selection if seq not in remove_seq]
            st.rerun()
    else:
        st.info("1번 검색 결과 표에서 조회할 행을 클릭하세요.")
    st.write(f"현재 선택된 품목: **{len(st.session_state.selection)}건**")

    st.subheader("3. 추가 조회 항목")
    if "preset_new_drug_intro" not in st.session_state:
        st.session_state.preset_new_drug_intro = all(
            st.session_state.get(f"extra_{key}", False) for key in core.NEW_DRUG_PRESET_KEYS)
    if "preset_new_drug_intro_prev" not in st.session_state:
        st.session_state.preset_new_drug_intro_prev = st.session_state.preset_new_drug_intro

    st.checkbox(
        "[신약 도입 준비]", key="preset_new_drug_intro",
        help="영문 제품명, ATC 코드, 포장단위, 주성분 영문명, 원료약품 및 분량, 유효기간, 성상, "
            "전문·일반의약품 구분, 보관정보, 보관 및 취급상의 주의사항을 한 번에 선택/해제합니다.",
    )
    if st.session_state.preset_new_drug_intro != st.session_state.preset_new_drug_intro_prev:
        for preset_key in core.NEW_DRUG_PRESET_KEYS:
            st.session_state[f"extra_{preset_key}"] = st.session_state.preset_new_drug_intro
        st.session_state.preset_new_drug_intro_prev = st.session_state.preset_new_drug_intro
        st.rerun()

    selected_extras = []
    extra_columns = st.columns(3)
    for index, key in enumerate(core.EXTRA_FIELD_ORDER):
        with extra_columns[index % 3]:
            if st.checkbox(core.EXTRA_FIELD_LABELS[key], key=f"extra_{key}"):
                selected_extras.append(key)

    summary_view = st.checkbox(
        "요약 버전으로 보기",
        help="새로운 의학적 판단을 생성하지 않고, 원문에서 앞부분과 문장 단위 내용을 발췌해 짧게 표시합니다.",
    )

    if st.button("선택한 품목 조회", type="primary",
                key="btn_lookup_selected",
                disabled=not st.session_state.selection or not (mfds_key and hira_key)):
        selected_rows = [by_seq[seq] for seq in st.session_state.selection if seq in by_seq]
        with st.spinner("식약처 상세정보와 심평원 약가를 조회하는 중입니다…"):
            result_df, errors = core.lookup_selected(selected_rows, mfds_key, hira_key, selected_extras)
        st.session_state.last_result = result_df
        st.session_state.last_errors = errors
        st.rerun()

    if st.session_state.last_result is not None:
        st.subheader("조회 결과")
        result_df = st.session_state.last_result
        filtered_result_df = result_df
        result_tab, comparison_tab, dur_tab = st.tabs(["상세 결과", "여러 약품 비교표", "DUR 확인"])

        with result_tab:
            transpose_view = st.checkbox(
                "행/열 전환", key="result_transpose", value=True,
                help="켜면 약 하나가 세로줄 하나가 되고, 화면 폭에 맞춰 각 약의 너비가 자동 조절됩니다.",
            )
            displayed_df = core.make_display_df(filtered_result_df, summary_view=summary_view,
                                                transpose_view=transpose_view)
            if summary_view:
                st.caption("요약 버전: 원문에서 문장 단위로 발췌한 표시용 요약입니다. 임상적 판단을 대신하지 않습니다.")
            ui_table.render_resizable_wrapped_table(displayed_df, show_index=transpose_view,
                                                     height=720, table_key="detail")
            csv_bytes = displayed_df.to_csv(index=transpose_view, encoding="utf-8-sig").encode("utf-8-sig")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_suffix = "_행열전환" if transpose_view else ""
            st.download_button("결과 CSV 다운로드", data=csv_bytes,
                              file_name=f"의약품조회결과_{timestamp}{csv_suffix}.csv", mime="text/csv")

        with comparison_tab:
            if len(filtered_result_df) < 2:
                st.info("두 품목 이상 조회하면 비교표가 표시됩니다.")
            else:
                comparison_df = core.make_comparison_df(
                    core.make_summary_df(filtered_result_df) if summary_view else filtered_result_df)
                st.caption("행은 조회 항목, 열은 의약품입니다. 헤더 경계를 드래그해 너비를 조절할 수 있습니다.")
                ui_table.render_resizable_wrapped_table(comparison_df, show_index=True,
                                                         height=760, table_key="comparison")
                comparison_csv = comparison_df.to_csv(index=True, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button("비교표 CSV 다운로드", data=comparison_csv,
                                  file_name=f"의약품비교표_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                  mime="text/csv")

        with dur_tab:
            if not st.session_state.dur_indices:
                st.info("사이드바의 'DUR 품목리스트 업로드'에서 먼저 엑셀을 올려주세요.")
            else:
                if st.button("선택한 품목 DUR 확인", key="run_dur_check"):
                    dur_call_counter = {"hira": 0, "mfds": 0}
                    dur_errors = []
                    dur_cache_detail = core.load_json_cache(core.CACHE_DETAIL_FILE)
                    with st.spinner("DUR(병용금기 등) 확인 중입니다…"):
                        dur_result_df = core.check_dur(
                            selected_rows, mfds_key, st.session_state.dur_indices,
                            dur_cache_detail, dur_call_counter, dur_errors,
                        )
                    core.save_json_cache(core.CACHE_DETAIL_FILE, dur_cache_detail)
                    st.session_state.dur_result = dur_result_df
                    st.session_state.dur_errors = dur_errors
                if "dur_result" in st.session_state:
                    dur_result_df = st.session_state.dur_result
                    if dur_result_df.empty:
                        st.success("선택한 품목 중 업로드된 DUR 리스트에 해당하는 품목이 없습니다.")
                    else:
                        st.dataframe(dur_result_df, use_container_width=True, hide_index=True)
                        dur_csv = dur_result_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                        st.download_button("DUR 확인 결과 CSV 다운로드", data=dur_csv,
                                          file_name=f"DUR확인결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                          mime="text/csv")
                    if st.session_state.get("dur_errors"):
                        with st.expander(f"DUR 확인 중 경고/오류 {len(st.session_state.dur_errors)}건"):
                            for error in st.session_state.dur_errors:
                                st.warning(error)

        if st.session_state.last_errors:
            with st.expander(f"API 경고/오류 {len(st.session_state.last_errors)}건"):
                for error in st.session_state.last_errors:
                    st.warning(error)

# ===========================================================================
# 탭 2: 비교표 입력 — PPTX / XLSX / 붙여넣기 + 구조 확인 화면
# ===========================================================================
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
                st.warning("행마다 열 개수가 달라 표 구조가 불안정합니다. 아래 미리보기에서 표 방향을 반드시 확인하세요.")

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

# ===========================================================================
# 탭 3: 검증 · Claude 자료 생성 + 결과 재파싱
# ===========================================================================
with tab3:
    entries = st.session_state["entries"]
    result_df = st.session_state.get("last_result")

    if not entries:
        st.info("먼저 '📋 비교표 입력' 탭에서 비교표를 입력·확정하세요.")
    elif result_df is None or result_df.empty:
        st.info("먼저 '🔍 의약품 조회' 탭에서 신청/비교 의약품을 조회하세요.")
    else:
        product_names = result_df["허가제품명"].tolist()

        # 비교표에 실제로 쓰인 제품(컬럼) 라벨들 — 예: "신청의약품","비교의약품1","비교의약품2","비교의약품3"
        table_roles = sorted({e.get("product", "") for e in entries if e.get("product")})

        st.subheader("역할 구성 — 함량별 여러 품목을 하나의 역할로 묶기")
        st.caption("비교표에서 쓰인 제품 라벨마다, 조회 결과 중 해당하는 품목(함량별로 여러 개면 전부)을 선택하세요. "
                   "예: '신청의약품' 역할에 나르코설하정 100/200/300마이크로그램 3개를 모두 선택.")

        role_to_products = {}
        for role in table_roles:
            # 라벨과 이름이 비슷한 조회결과를 기본 선택값으로 추정 (완전 일치 아니어도 괜찮음, 사용자가 직접 조정)
            guess = [p for p in product_names if any(tok in p for tok in role.replace("비교의약품", "").split() if tok)]
            selected = st.multiselect(
                f"「{role}」에 매핑할 조회 결과", options=product_names,
                default=[p for p in product_names if p in guess] if guess else [],
                key=f"role_map_{role}",
            )
            role_to_products[role] = selected

        applicant_name = st.selectbox("이 중 '신청의약품' 역할은 어느 것입니까?", options=table_roles,
                                      key="applicant_role_select")
        comparator_names = [r for r in table_roles if r != applicant_name]

        unmapped = [role for role, prods in role_to_products.items() if not prods]
        if unmapped:
            st.warning(f"아직 조회 결과가 매핑되지 않은 역할: {', '.join(unmapped)} — 매핑 안 하면 그 역할은 "
                      "'확인불가'로 처리됩니다.")

        # 여러 품목이 매핑된 역할은 값들을 합쳐서(중복은 제거) 하나의 참조자료로 구성.
        # 예: 함량이 달라 값이 다르면 각각 다 보존되고, 효능효과처럼 강도와 무관하게 동일한 텍스트는 중복 제거됨.
        def _merge_field_values(rows, col):
            seen = []
            for row in rows:
                value = str(row.get(col, "") or "").strip()
                if value and value not in seen:
                    seen.append(value)
            return "; ".join(seen)

        reference_data = {}
        reference_lookup = {}
        for role, prods in role_to_products.items():
            matched_rows = [row for _, row in result_df.iterrows() if row["허가제품명"] in prods]
            if not matched_rows:
                reference_data[role] = {"mfds": {}, "hira": {}}
                reference_lookup[role] = {}
                continue
            mfds_fields = {}
            flat = {}
            for col in result_df.columns:
                if col in ("허가제품명", "약가"):
                    continue
                merged = _merge_field_values(matched_rows, col)
                mfds_fields[col] = {"label": col, "value": merged}
                flat[col] = merged
            price_merged = _merge_field_values(matched_rows, "약가")
            # 제품명 자체는 함량별로 다 달라야 의미가 있으므로 원본 그대로 나열
            product_names_merged = _merge_field_values(matched_rows, "허가제품명")
            mfds_fields["해당 품목(함량별)"] = {"label": "해당 품목(함량별)", "value": product_names_merged}
            flat["허가제품명"] = product_names_merged
            reference_data[role] = {"mfds": mfds_fields, "hira": {"약가": price_merged}}
            flat["약가"] = price_merged
            reference_lookup[role] = flat

        st.divider()
        st.subheader("Python 1차 규칙 검증 (숫자·단위·기본정보·약가만 기계적으로 확정)")
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

        col_x, col_y, col_z = st.columns(3)
        with col_x:
            if st.button("[Claude용 전체 자료 생성]"):
                st.session_state["generated_prompt"] = prompt_builder.build_full_prompt(
                    entries, reference_data, applicant_name, comparator_names)
        with col_y:
            target_product = st.selectbox("제품 선택", options=[applicant_name] + comparator_names,
                                         key="product_scope_select")
            if st.button("[제품별 자료 생성]"):
                st.session_state["generated_prompt"] = prompt_builder.build_product_prompt(
                    entries, reference_data, applicant_name, comparator_names, target_product)
        with col_z:
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
                st.dataframe(parsed["rows"], use_container_width=True)
            else:
                st.error("형식을 인식하지 못했습니다. 원문을 그대로 표시합니다.")
                st.text(parsed["raw"])
