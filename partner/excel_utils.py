"""
Tiện ích xuất file Excel (.xlsx) với định dạng đẹp, cột tự co giãn.
"""
from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


def create_excel_response(filename, headers, rows, sheet_title="Sheet1"):
    """
    Tạo HttpResponse chứa file Excel (.xlsx) với:
    - Header đậm, nền xanh, chữ trắng
    - Cột tự co giãn theo nội dung
    - Border mỏng cho tất cả ô

    Args:
        filename: Tên file khi tải về (VD: "bao_cao.xlsx")
        headers: List tên cột (VD: ['Tên', 'Địa chỉ', 'Doanh thu'])
        rows: List các list dữ liệu (VD: [['Sân A', '123 ABC', 100000], ...])
        sheet_title: Tên sheet

    Returns:
        HttpResponse chứa file xlsx
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    # ── Style cho header ──
    header_font = Font(name='Arial', bold=True, size=12, color='000000')
    header_fill = PatternFill(start_color='BDD7EE', end_color='BDD7EE', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # ── Style cho data ──
    data_font = Font(name='Arial', size=11)
    data_alignment = Alignment(vertical='center', wrap_text=False)

    # ── Border chung ──
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    # ── Ghi header bằng append (cách chuẩn nhất) ──
    ws.append(headers)

    # ── Áp dụng style cho header row ──
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # ── Đặt chiều cao header row ──
    ws.row_dimensions[1].height = 30

    # ── Ghi dữ liệu ──
    for row_data in rows:
        ws.append(row_data)

    # ── Áp dụng style cho data rows ──
    for row_idx in range(2, len(rows) + 2):
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.alignment = data_alignment
            cell.border = thin_border

    # ── Auto-fit column width ──
    for col_idx in range(1, len(headers) + 1):
        max_length = 0
        column_letter = get_column_letter(col_idx)

        for row_idx in range(1, len(rows) + 2):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value is not None:
                cell_length = len(str(cell.value))
                if cell_length > max_length:
                    max_length = cell_length

        # Thêm padding, tối thiểu 12, tối đa 50
        adjusted_width = min(max(max_length + 4, 12), 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # ── Freeze header row ──
    ws.freeze_panes = 'A2'

    # ── Tạo response ──
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
