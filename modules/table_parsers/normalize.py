# -*- coding: utf-8 -*-
"""
PPTX/XLSX/붙여넣기 세 경로 모두 여기서 공통 스키마로 합류한다.

공통 스키마 (명세서 4장):
{
  "slide": int|None,
  "table_index": int,
  "row": int,
  "column": int,
  "field": str,
  "product": str,
  "value": str,
}

known field/product 사전은 7장(비교표 구조 확인 화면)에서 방향 추정에 사용.
"""
KNOWN_FIELDS = [
    "성분명", "제품명", "제조사", "판매사", "제조/판매사", "함량", "제형",
    "효능효과", "효능·효과", "적응증", "용법용량", "용법·용량", "투여방법", "투여경로",
    "보관방법", "이상반응", "금기", "금기사항", "경고", "주의사항", "상호작용",
    "임부", "수유부", "소아", "고령자", "신장애", "간장애", "약가", "Reference", "참고문헌",
]


def guess_orientation(grid: list) -> str:
    """
    grid의 첫 번째 행과 첫 번째 열 중 어느 쪽이 '항목명'에 더 가까운지 known 사전과의
    겹침 정도로 추정. "row"면 1행이 항목 헤더(가로로 항목 나열), "col"이면 1열이 항목.
    확신이 낮으면 "ambiguous" 반환 -> 호출부에서 반드시 사용자에게 라디오로 물어야 한다(7장).
    """
    if not grid or not grid[0]:
        return "ambiguous"

    first_row = grid[0]
    first_col = [row[0] for row in grid if row]

    def score(cells):
        return sum(1 for c in cells if any(kw in c for kw in KNOWN_FIELDS))

    row_score = score(first_row)
    col_score = score(first_col)

    if row_score == col_score:
        return "ambiguous"
    return "row" if row_score > col_score else "col"


def grid_to_common_schema(grid: list, orientation: str, slide=None, table_index=1) -> list:
    """
    orientation="row": 1행=항목 헤더, 1열=제품명 헤더 (항목이 열 방향으로 나열)
    orientation="col": 1열=항목 헤더, 1행=제품명 헤더 (항목이 행 방향으로 나열)
    """
    if not grid:
        return []

    entries = []
    if orientation == "row":
        # grid[0][0]은 보통 빈칸/코너. field는 grid[0][c] (c>=1), product는 grid[r][0] (r>=1)
        fields = grid[0]
        for r in range(1, len(grid)):
            product = grid[r][0] if grid[r] else ""
            if not product:
                continue
            for c in range(1, len(grid[r])):
                field = fields[c] if c < len(fields) else f"열{c+1}"
                value = grid[r][c]
                if value == "":
                    continue
                entries.append({
                    "slide": slide, "table_index": table_index,
                    "row": r, "column": c,
                    "field": field, "product": product, "value": value,
                })
    else:  # "col"
        products = grid[0]
        for r in range(1, len(grid)):
            field = grid[r][0] if grid[r] else ""
            if not field:
                continue
            for c in range(1, len(grid[r])):
                product = products[c] if c < len(products) else f"열{c+1}"
                value = grid[r][c]
                if value == "":
                    continue
                entries.append({
                    "slide": slide, "table_index": table_index,
                    "row": r, "column": c,
                    "field": field, "product": product, "value": value,
                })

    return entries
