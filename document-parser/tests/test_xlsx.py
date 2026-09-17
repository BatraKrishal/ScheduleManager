import io
import openpyxl
import pytest
from app.models.canonical import ActivityStatus
from app.parsers.xlsx_parser import XlsxParser

def make_sample_excel() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Schedule"
    ws.append(["Activity ID", "Activity Name", "WBS", "Status", "Start", "Finish", "Duration", "% Complete"])
    ws.append(["A100", "Site Survey", "Engineering", "Completed", "2024-01-01", "2024-01-05", 5, 100])
    ws.append(["A200", "Piping Layout", "Engineering", "Not Started", "2024-01-06", "2024-01-20", 14, 0])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

def test_parse_valid_xlsx():
    content = make_sample_excel()
    parser = XlsxParser()
    result = parser.parse(content, "sample.xlsx")

    assert result.project.project_code == "sample"
    assert len(result.wbs) == 1
    assert result.wbs[0].code == "Engineering"

    assert len(result.activities) == 2
    assert result.activities[0].activity_code == "A100"
    assert result.activities[0].status == ActivityStatus.COMPLETED
    assert result.activities[1].activity_code == "A200"
    assert result.activities[1].status == ActivityStatus.NOT_STARTED
