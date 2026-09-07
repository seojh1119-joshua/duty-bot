import datetime
import calendar
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def update_dashboard(file_path, target_sheet_name):
    # 엑셀 워크북 로드
    wb = openpyxl.load_workbook(file_path)
    
    if target_sheet_name not in wb.sheetnames:
        print(f"오류: '{target_sheet_name}' 시트를 찾을 수 없습니다.")
        return

    target_ws = wb[target_sheet_name]

    # "대시보드" 시트 생성 또는 가져오기 (가장 앞에 위치)
    if "대시보드" in wb.sheetnames:
        dash_ws = wb["대시보드"]
        # 기존 내용 및 셀 병합 초기화
        dash_ws.delete_rows(1, dash_ws.max_row + 1)
        for range_ in list(dash_ws.merged_cells.ranges):
            dash_ws.unmerge_cells(str(range_))
    else:
        dash_ws = wb.create_sheet(title="대시보드", index=0)

    # 기본 디자인 스타일 정의
    font_title = Font(name="맑은 고딕", size=16, bold=True)
    font_header = Font(name="맑은 고딕", size=11, bold=True)
    font_date_bold = Font(name="맑은 고딕", size=10, bold=True)
    font_work = Font(name="맑은 고딕", size=9)
    font_gray = Font(name="맑은 고딕", size=9, color="A0A0A0")
    
    fill_title = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    fill_header = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    fill_date = PatternFill(start_color="FAFAFA", end_color="FAFAFA", fill_type="solid")
    fill_work = PatternFill(start_color="EBF5FF", end_color="EBF5FF", fill_type="solid")

    thin_border_side = Side(style='thin', color='CCCCCC')
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

    align_center = Alignment(horizontal='center', vertical='center')
    align_top_left = Alignment(horizontal='left', vertical='top')
    align_work = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # 1. 대시보드 제목 생성 (B2:H2 병합)
    dash_ws.merge_cells("B2:H2")
    title_cell = dash_ws["B2"]
    title_cell.value = f"{target_sheet_name} 근무 대시보드"
    title_cell.font = font_title
    title_cell.fill = fill_title
    title_cell.alignment = align_center

    # 2. 요일 헤더 생성 (B4:H4)
    headers = ["일", "월", "화", "수", "목", "금", "토"]
    for idx, header in enumerate(headers, start=2):
        cell = dash_ws.cell(row=4, column=idx)
        cell.value = header
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = thin_border
        
        # 주말 색상 포인트
        if idx == 2:
            cell.font = Font(name="맑은 고딕", size=11, bold=True, color="C00000") # 일요일 Red
        elif idx == 8:
            cell.font = Font(name="맑은 고딕", size=11, bold=True, color="0000C0") # 토요일 Blue

    # 3. 대상 시트 이름에서 연도/월 분석
    now = datetime.datetime.now()
    year_val = now.year
    month_val = now.month

    # 예: "2026-03" 또는 "3월" 파싱
    if "-" in target_sheet_name:
        parts = target_sheet_name.split("-")
        try:
            year_val = int(parts[0])
            month_val = int(parts[1])
        except ValueError:
            pass
    elif "월" in target_sheet_name:
        numbers = re.findall(r'\d+', target_sheet_name)
        if numbers:
            month_val = int(numbers[0])

    # 4. 대상 시트의 근무 데이터 읽기 (A열: 날짜, B열: 근무1, C열: 근무2)
    work_data = {}
    for row in target_ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        
        day_num = None
        date_val = row[0]

        # 날짜 형식 파싱 (숫자, datetime 객체, 문자열 대응)
        if isinstance(date_val, (int, float)):
            day_num = int(date_val)
        elif isinstance(date_val, (datetime.datetime, datetime.date)):
            day_num = date_val.day
        elif isinstance(date_val, str) and date_val.strip().isdigit():
            day_num = int(date_val.strip())

        if day_num:
            w1 = str(row[1]) if len(row) > 1 and row[1] is not None else ""
            w2 = str(row[2]) if len(row) > 2 and row[2] is not None else ""
            work_data[day_num] = (w1, w2)

    # 5. 해당 월의 달력 구조 계산
    # monthrange는 (첫번째 요일(0:월~6:일), 해당 월 총 일수) 반환
    first_weekday, total_days = calendar.monthrange(year_val, month_val)
    # 일요일 시작 기준으로 전환 (0:일~6:토)
    first_day_col = (first_weekday + 1) % 7 + 1 

    # 6. 달력 그리드 생성 및 데이터 작성 (최대 6주)
    day_counter = 1
    for i in range(6): # 주차
        for j in range(1, 8): # 1:일 ~ 7:토
            cur_row = 5 + (i * 2) # 날짜 행 (5, 7, 9...)
            cur_col = j + 1       # B열(2) ~ H열(8)

            date_cell = dash_ws.cell(row=cur_row, column=cur_col)
            work_cell = dash_ws.cell(row=cur_row + 1, column=cur_col)

            # 셀 테두리 설정
            date_cell.border = thin_border
            work_cell.border = thin_border

            # 달력 날짜 배치 조건
            if (i == 0 and j >= first_day_col) or (i > 0 and day_counter <= total_days):
                # 날짜 표시
                date_cell.value = f"{day_counter}일"
                date_cell.font = font_date_bold
                date_cell.fill = fill_date
                date_cell.alignment = align_top_left

                # 일요일/토요일 색상 적용
                if j == 1:
                    date_cell.font = Font(name="맑은 고딕", size=10, bold=True, color="C00000")
                elif j == 7:
                    date_cell.font = Font(name="맑은 고딕", size=10, bold=True, color="0000C0")

                # 근무1, 근무2 매핑 및 표시
                if day_counter in work_data:
                    w1, w2 = work_data[day_counter]
                    if w1 or w2:
                        work_cell.value = f"근무1: {w1}\n근무2: {w2}"
                        work_cell.font = font_work
                        work_cell.fill = fill_work
                        work_cell.alignment = align_work
                    else:
                        work_cell.value = "-"
                        work_cell.font = font_gray
                        work_cell.alignment = align_center
                else:
                    work_cell.value = "-"
                    work_cell.font = font_gray
                    work_cell.alignment = align_center

                day_counter += 1

        if day_counter > total_days:
            break

    # 7. 열 너비 및 행 높이 조절
    for col in ["B", "C", "D", "E", "F", "G", "H"]:
        dash_ws.column_dimensions[col].width = 18

    dash_ws.row_dimensions[2].height = 35 # 제목
    dash_ws.row_dimensions[4].height = 25 # 요일

    for i in range(6):
        dash_ws.row_dimensions[5 + (i * 2)].height = 20 # 날짜 행
        dash_ws.row_dimensions[6 + (i * 2)].height = 45 # 근무 데이터 행

    # 변경사항 저장
    wb.save(file_path)
    print(f"[{target_sheet_name}] 시트 기준 대시보드가 성공적으로 신규/갱신되었습니다.")

# ==========================================
# 실행 예시
# ==========================================
if __name__ == "__main__":
    # 엑셀 파일 경로와 대시보드로 만들 대상 시트 이름 지정
    excel_file = "근무표.xlsx"
    target_sheet = "2026-03"  # 또는 "3월"
    
    update_dashboard(excel_file, target_sheet)
