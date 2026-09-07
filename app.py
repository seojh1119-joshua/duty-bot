import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
import datetime

# 1. 워크북 생성 및 시트 설정
wb = openpyxl.Workbook()

ws_cal = wb.active
ws_cal.title = "월간 근무 달력"
ws_data = wb.create_sheet(title="근무자 및 유형")

# 2. 색상 및 스타일 정의
COLOR_HEADER_BG = "1F4E78"    # 다크 블루 (헤더)
COLOR_HEADER_TEXT = "FFFFFF"
COLOR_ACCENT = "2F5597"
COLOR_TODAY_BG = "FFF2CC"    # 오늘 날짜 하이라이트
COLOR_CARD_BG = "F2F4F8"
COLOR_BORDER = "D9D9D9"

font_title = Font(name="Calibri", size=18, bold=True, color="1F4E78")
font_subtitle = Font(name="Calibri", size=11, italic=True, color="595959")
font_header = Font(name="Calibri", size=11, bold=True, color=COLOR_HEADER_TEXT)
font_day_num = Font(name="Calibri", size=11, bold=True, color="2F5597")
font_day_num_sun = Font(name="Calibri", size=11, bold=True, color="C00000")
font_day_num_sat = Font(name="Calibri", size=11, bold=True, color="0070C0")
font_work = Font(name="Calibri", size=10, bold=True, color="000000")
font_memo = Font(name="Calibri", size=9, color="595959")

fill_header = PatternFill(start_color=COLOR_HEADER_BG, end_color=COLOR_HEADER_BG, fill_type="solid")
fill_accent_header = PatternFill(start_color=COLOR_ACCENT, end_color=COLOR_ACCENT, fill_type="solid")
fill_card = PatternFill(start_color=COLOR_CARD_BG, end_color=COLOR_CARD_BG, fill_type="solid")
fill_today_card = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

thin_border_side = Side(border_style="thin", color=COLOR_BORDER)
border_cell = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
border_card = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

align_center = Alignment(horizontal="center", vertical="center")
align_right = Alignment(horizontal="right", vertical="center")

# 3. 데이터 시트 작성 (기본 목록 저장용)
ws_data['A1'] = "근무자 목록"
ws_data['A1'].font = Font(bold=True)
workers = ["김철수", "이영희", "박민수", "정수진", "최동현", "강서연", "조현우"]
for idx, name in enumerate(workers, start=2):
    ws_data[f'A{idx}'] = name

# 4. 메인 달력 시트 레이아웃 구성
ws_cal.views.sheetView[0].showGridLines = True

# 타이틀 및 안내 문구
ws_cal['A1'] = "월간 근무 관리 달력 (2026년 9월)"
ws_cal['A1'].font = font_title
ws_cal['A2'] = "※ 달력 각 날짜의 입력란에 이름과 메모를 직접 입력하여 즉각 수정할 수 있습니다."
ws_cal['A2'].font = font_subtitle

# --- 상단 [오늘의 근무자] 자동 요약 대시보드 ---
ws_cal.merge_cells("A4:B4")
ws_cal['A4'] = "📅 TODAY (오늘의 날짜)"
ws_cal['A4'].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
ws_cal['A4'].fill = fill_accent_header
ws_cal['A4'].alignment = align_center

ws_cal.merge_cells("A5:B6")
ws_cal['A5'] = "=TODAY()"
ws_cal['A5'].font = Font(name="Calibri", size=14, bold=True, color="1F4E78")
ws_cal['A5'].alignment = align_center
ws_cal['A5'].fill = fill_today_card
ws_cal['A5'].number_format = "yyyy-mm-dd (ddd)"

ws_cal.merge_cells("C4:E4")
ws_cal['C4'] = "👤 오늘 근무자 (자동 갱신)"
ws_cal['C4'].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
ws_cal['C4'].fill = fill_accent_header
ws_cal['C4'].alignment = align_center

# 오늘 날짜 위치를 찾아 근무자를 자동 표시하는 엑셀 수식
ws_cal.merge_cells("C5:E6")
ws_cal['C5'] = '=IFERROR(INDIRECT(ADDRESS(MAX(IF(B9:H25=TODAY(), ROW(B9:H25)+1, 1)), MAX(IF(B9:H25=TODAY(), COLUMN(B9:H25), 1)))), "오늘 일정 없음")'
ws_cal['C5'].font = Font(name="Calibri", size=13, bold=True, color="1F4E78")
ws_cal['C5'].alignment = align_center
ws_cal['C5'].fill = fill_card

ws_cal.merge_cells("F4:H4")
ws_cal['F4'] = "📝 오늘 주요 메모 / 전달사항"
ws_cal['F4'].font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
ws_cal['F4'].fill = fill_accent_header
ws_cal['F4'].alignment = align_center

# 오늘 날짜 위치의 메모를 자동 표시하는 수식
ws_cal.merge_cells("F5:H6")
ws_cal['F5'] = '=IFERROR(INDIRECT(ADDRESS(MAX(IF(B9:H25=TODAY(), ROW(B9:H25)+2, 1)), MAX(IF(B9:H25=TODAY(), COLUMN(B9:H25), 1)))), "-")'
ws_cal['F5'].font = Font(name="Calibri", size=11, color="333333")
ws_cal['F5'].alignment = align_center
ws_cal['F5'].fill = fill_card

for r in range(4, 7):
    for c in range(1, 9):
        ws_cal.cell(row=r, column=c).border = border_card

# --- 요일 헤더 생성 ---
days = ["일 (Sun)", "월 (Mon)", "화 (Tue)", "수 (Wed)", "목 (Thu)", "금 (Fri)", "토 (Sat)"]
for col_idx, day_name in enumerate(days, start=2): # B ~ H열
    cell = ws_cal.cell(row=8, column=col_idx)
    cell.value = day_name
    cell.font = font_header
    cell.fill = fill_header
    cell.alignment = align_center

ws_cal.row_dimensions[8].height = 25

# --- 달력 본문 격자 생성 ---
current_row = 9
start_col = 4 # 2026년 9월 1일 화요일 (D열)

# 샘플 데이터 (이름 및 메모)
sample_schedule = {
    1: ("김철수 (주간)", "장비 점검일"),
    2: ("이영희 (야간)", "야간 안전순찰"),
    3: ("박민수 (주간)", "정기 회의"),
    4: ("정수진 (주간)", "월차 점검"),
    5: ("최동현 (비번)", "휴무"),
    6: ("강서연 (휴무)", "-"),
    7: ("김철수 (주간)", "재고 조사"),
    8: ("이영희 (주간)", "오늘의 근무자 자동 표시"),
    9: ("박민수 (야간)", "야간 근무"),
    10: ("정수진 (주간)", "외부 미팅"),
    11: ("최동현 (주간)", "시설 보수"),
    12: ("조현우 (주간)", "주말 당직"),
    13: ("강서연 (휴무)", "-"),
    14: ("김철수 (주간)", "주간 보고"),
    15: ("이영희 (야간)", "시스템 업데이트"),
    16: ("박민수 (주간)", "안전 교육"),
    17: ("정수진 (주간)", "거래처 방문"),
    18: ("최동현 (주간)", "주간 점검"),
    19: ("조현우 (비번)", "-"),
    20: ("강서연 (휴무)", "-"),
    21: ("김철수 (주간)", "장비 납품"),
    22: ("이영희 (주간)", "청소 점검"),
    23: ("박민수 (야간)", "야간 대기"),
    24: ("정수진 (주간)", "월간 평가"),
    25: ("최동현 (주간)", "주말 대비"),
    26: ("조현우 (주간)", "주말 당직"),
    27: ("강서연 (휴무)", "-"),
    28: ("김철수 (주간)", "월말 마감"),
    29: ("이영희 (주간)", "월말 보고"),
    30: ("박민수 (야간)", "야간 점검")
}

col_idx = start_col
day_count = 1

while day_count <= 30:
    date_val = datetime.date(2026, 9, day_count)
    
    r_date = current_row
    r_name = current_row + 1
    r_memo = current_row + 2
    
    cell_date = ws_cal.cell(row=r_date, column=col_idx)
    cell_name = ws_cal.cell(row=r_name, column=col_idx)
    cell_memo = ws_cal.cell(row=r_memo, column=col_idx)
    
    cell_date.value = date_val
    cell_date.number_format = "yyyy-mm-dd"
    
    # 즉각적인 수정이 가능한 셀 값 입력
    if day_count in sample_schedule:
        cell_name.value = sample_schedule[day_count][0]
        cell_memo.value = sample_schedule[day_count][1]
    
    cell_date.alignment = align_right
    if col_idx == 2:
        cell_date.font = font_day_num_sun
    elif col_idx == 8:
        cell_date.font = font_day_num_sat
    else:
        cell_date.font = font_day_num
    
    cell_name.font = font_work
    cell_name.alignment = align_center
    
    cell_memo.font = font_memo
    cell_memo.alignment = align_center
    
    fill_day_bg = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    if col_idx == 2:
        fill_day_bg = PatternFill(start_color="FFF2F2", end_color="FFF2F2", fill_type="solid")
    elif col_idx == 8:
        fill_day_bg = PatternFill(start_color="F2F7FA", end_color="F2F7FA", fill_type="solid")
        
    cell_date.fill = fill_day_bg
    cell_name.fill = fill_day_bg
    cell_memo.fill = fill_day_bg
    
    cell_date.border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side)
    cell_name.border = Border(left=thin_border_side, right=thin_border_side)
    cell_memo.border = Border(left=thin_border_side, right=thin_border_side, bottom=thin_border_side)
    
    day_count += 1
    col_idx += 1
    if col_idx > 8:
        col_idx = 2
        ws_cal.row_dimensions[current_row].height = 20
        ws_cal.row_dimensions[current_row+1].height = 24
        ws_cal.row_dimensions[current_row+2].height = 20
        ws_cal.row_dimensions[current_row+3].height = 8 # 주간 간격
        current_row += 4

ws_cal.row_dimensions[current_row].height = 20
ws_cal.row_dimensions[current_row+1].height = 24
ws_cal.row_dimensions[current_row+2].height = 20

# 9월 이전 빈 칸 테두리 채우기
for col in [2, 3]:
    for r in range(9, 12):
        c = ws_cal.cell(row=r, column=col)
        c.fill = PatternFill(start_color="FAFAFA", end_color="FAFAFA", fill_type="solid")
        c.border = border_cell

# 열 너비 조정
ws_cal.column_dimensions['A'].width = 3
for col_letter in ['B', 'C', 'D', 'E', 'F', 'G', 'H']:
    ws_cal.column_dimensions[col_letter].width = 18

# 오늘 날짜 조건부 서식 강조
today_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
for r in [9, 13, 17, 21, 25]:
    for c in range(2, 9):
        ws_cal.conditional_formatting.add(
            f"{get_column_letter(c)}{r}:{get_column_letter(c)}{r+2}",
            CellIsRule(operator='equal', formula=['TODAY()'], stopIfTrue=False, fill=today_fill)
        )

# 5. 파일 저장
file_path = "2026_Monthly_Work_Calendar.xlsx"
wb.save(file_path)
