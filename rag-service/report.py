"""Excel report generation (unchanged behaviour, extracted from main.py).

The ``POST /report`` contract is consumed by the frontend's export button and is
deliberately untouched: same request model, same two-sheet workbook.
"""

from __future__ import annotations

import io
from typing import Optional

from openpyxl import Workbook
from openpyxl.chart import AreaChart, BarChart, LineChart, PieChart, Reference
from openpyxl.utils import get_column_letter
from pydantic import BaseModel


class ChartConfig(BaseModel):
    type: str  # bar, line, pie, area
    title: str
    x: str
    y: str


class ReportRequest(BaseModel):
    columns: list[str]
    rows: list[list]
    chart: Optional[ChartConfig] = None
    title: Optional[str] = "Report"


CHART_BUILDERS = {
    "bar": BarChart,
    "line": LineChart,
    "pie": PieChart,
    "area": AreaChart,
}


def build_excel(req: ReportRequest) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"

    ws.append(req.columns)
    for row in req.rows:
        ws.append(row)

    for col_idx in range(1, len(req.columns) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            len(str(ws.cell(row=r, column=col_idx).value or ""))
            for r in range(1, len(req.rows) + 2)
        )
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    if req.chart and req.chart.type in CHART_BUILDERS:
        x_idx = None
        y_idx = None
        for i, col in enumerate(req.columns):
            if col == req.chart.x:
                x_idx = i + 1
            if col == req.chart.y:
                y_idx = i + 1

        if x_idx and y_idx:
            chart_cls = CHART_BUILDERS[req.chart.type]
            chart = chart_cls()
            chart.title = req.chart.title or req.title
            chart.width = 20
            chart.height = 12

            num_rows = len(req.rows)
            data_ref = Reference(ws, min_col=y_idx, min_row=1, max_row=num_rows + 1)
            cat_ref = Reference(ws, min_col=x_idx, min_row=2, max_row=num_rows + 1)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cat_ref)

            if req.chart.type != "pie":
                chart.x_axis.title = req.chart.x
                chart.y_axis.title = req.chart.y

            chart_ws = wb.create_sheet("Chart")
            chart_ws.add_chart(chart, "A1")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
