# -*- coding: utf-8 -*-
"""
붙여넣기 입력 파싱.

P0(반드시 확실히 동작해야 함): tab-구분 plain text 파싱.
  - Excel 등에서 표를 복사하면 대부분 탭으로 셀이 구분되고 줄바꿈으로 행이 구분된다.
  - PPT 표를 복사하면 탭 구분이 깨지는 경우가 있어, 이 경우 grid의 열 개수가
    행마다 들쭉날쭉하게 나오는데 이를 감지해서 "구조가 불안정합니다" 경고를 반환한다.

보조: HTML clipboard(`text/html`)의 <table>을 rowspan/colspan 점유행렬 방식으로 파싱.
  - Streamlit 쪽에서 st.components.v1.html로 paste 이벤트를 잡아 clipboardData.getData('text/html')를
    hidden textarea(st.session_state)로 넘겨준 뒤, 이 함수에 그 HTML 문자열을 전달하면 된다.
"""
from bs4 import BeautifulSoup
from ..utils import clean_whitespace


def parse_tab_separated(text: str) -> dict:
    """
    반환: {"grid": [[...],...], "irregular": bool, "col_counts": [int,...]}
    irregular=True면 행별 열 개수가 서로 달라 구조 확인 화면에서 사용자에게
    표 방향(행=항목/열=제품 등)을 반드시 확인시켜야 한다.
    """
    if not text:
        return {"grid": [], "irregular": False, "col_counts": []}

    lines = [ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip() != ""]
    grid = [[clean_whitespace(cell) for cell in line.split("\t")] for line in lines]
    col_counts = [len(row) for row in grid]
    irregular = len(set(col_counts)) > 1 if col_counts else False

    if irregular:
        max_cols = max(col_counts)
        grid = [row + [""] * (max_cols - len(row)) for row in grid]

    return {"grid": grid, "irregular": irregular, "col_counts": col_counts}


def parse_html_table(html_text: str) -> dict:
    """
    HTML <table> 하나를 rowspan/colspan을 고려한 점유행렬 방식으로 grid로 변환.
    여러 <table>이 있으면 첫 번째 표만 사용(다중 표 지원이 필요하면 호출부에서
    soup.find_all('table')로 순회하며 이 로직을 재사용할 것).
    """
    soup = BeautifulSoup(html_text or "", "html.parser")
    table = soup.find("table")
    if table is None:
        return {"grid": [], "merge_map": []}

    rows = table.find_all("tr")
    # 1차 패스: 최대 열 수 계산을 위해 점유행렬을 동적으로 확장
    occupied = {}  # (r, c) -> True
    grid_rows = []
    max_cols = 0

    for r_idx, tr in enumerate(rows):
        cells = tr.find_all(["td", "th"])
        c_idx = 0
        row_values = {}
        for cell in cells:
            while occupied.get((r_idx, c_idx)):
                c_idx += 1
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            text = clean_whitespace(cell.get_text(separator=" "))

            for rr in range(r_idx, r_idx + rowspan):
                for cc in range(c_idx, c_idx + colspan):
                    if (rr, cc) == (r_idx, c_idx):
                        row_values[cc] = text
                    occupied[(rr, cc)] = True
            c_idx += colspan
            max_cols = max(max_cols, c_idx)
        grid_rows.append(row_values)

    grid = []
    merge_map = []
    for r_idx, row_values in enumerate(grid_rows):
        row = []
        merge_row = []
        for c in range(max_cols):
            if c in row_values:
                row.append(row_values[c])
                merge_row.append(False)
            else:
                # 이 위치가 병합에 흡수된 셀인지, 아니면 원래 표에 없던 빈칸인지는
                # occupied 여부로 구분 가능하나 grid 상에서는 빈 문자열로 통일 처리
                row.append("")
                merge_row.append(occupied.get((r_idx, c), False))
        grid.append(row)
        merge_map.append(merge_row)

    return {"grid": grid, "merge_map": merge_map}
