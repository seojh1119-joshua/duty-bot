import os
import io
import glob
import datetime
import calendar
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import streamlit as st

# ==========================================
# 1. 대시보드 생성 함수
# ==========================================
def generate_dashboard_workbook(file_source, target_sheet_name):
    """
    file_source: 파일 경로(str) 또는 BytesIO 객체
    target_sheet_name: 대시보드를 생성할 기준 시트명
    """
    wb = openpyxl.load_workbook(file_source)
    
    if target_sheet_name not in wb.sheetnames:
        st.error(f"'{target_sheet_name}' 시트를 찾을 수 없습니다.")
        return None

    target_ws = wb[target_sheet_name]

    # "대시보드" 시트 생성 또는 초기화 (가장 앞에 배치)
    if "대시보드" in wb.sheetnames:
        dash_ws = wb["대시보드"]
        dash_ws.delete_rows(1, dash_ws.max_row + 1)
        for range_ in list(dash_ws.merged_cells.ranges):
            dash_ws.unmerge_cells(str(range_))
    else:
        dash_ws = wb.create_sheet(title="대시보드", index=0)

    # 서식 스타일 정의
    font_title = Font(name="맑은 고딕", size=16, bold=True)
    font_header = Font(name="맑은 고딕", size=11, bold=True)
    font_date_bold = Font(name="맑은 고딕", size=10, bold=True)
    font_work = Font(name="맑은 고딕", size=9)
    font_gray = Font(name="맑은 고딕", size=9, color="A0A0A0")
    
    fill_title = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    fill_header = PatternFill(start_color="F0F0F0", end_color="F0F0F0", fill_type="solid")
    fill_date = PatternFill(start_color="FAFAFA", end_color="FAFAFA", fill_type="solid")
    fill_work = PatternFill(start_color="EBF5FF", end_color="EBF5FF", fill_type="solid")

    thin_side = Side(style='thin', color='CCCCCC')
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    align_center = Alignment(horizontal='center', vertical='center')
    align_top_left = Alignment(horizontal='left', vertical='top')
    align_work = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # 1. 제목 생성 (B2:H2)
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
        if idx == 2:
            cell.font = Font(name="맑은 고딕", size=11, bold=True, color="C00000") # 일요일
        elif idx == 8:
            cell.font = Font(name="맑은 고딕", size=11, bold=True, color="0000C0") # 토요일

    # 3. 시트명에서 연도/월 분석
    now = datetime.datetime.now()
    year_val = now.year
    month_val = now.month

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

    # 4. 원본 데이터 읽기 (A열: 날짜, B열: 근무1, C열: 근무2)
    work_data = {}
    for row in target_ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        
        day_num = None
        date_val = row[0]

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

    # 5. 달력 구조 생성
    first_weekday, total_days = calendar.monthrange(year_val, month_val)
    first_day_col = (first_weekday + 1) % 7 + 1 

    day_counter = 1
    for i in range(6):
        for j in range(1, 8):
            cur_row = 5 + (i * 2)
            cur_col = j + 1

            date_cell = dash_ws.cell(row=cur_row, column=cur_col)
            work_cell = dash_ws.cell(row=cur_row + 1, column=cur_col)

            date_cell.border = thin_border
            work_cell.border = thin_border

            if (i == 0 and j >= first_day_col) or (i > 0 and day_counter <= total_days):
                date_cell.value = f"{day_counter}일"
                date_cell.font = font_date_bold
                date_cell.fill = fill_date
                date_cell.alignment = align_top_left

                if j == 1:
                    date_cell.font = Font(name="맑은 고딕", size=10, bold=True, color="C00000")
                elif j == 7:
                    date_cell.font = Font(name="맑은 고딕", size=10, bold=True, color="0000C0")

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

    # 6. 열/행 간격 조정
    for col in ["B", "C", "D", "E", "F", "G", "H"]:
        dash_ws.column_dimensions[col].width = 18

    dash_ws.row_dimensions[2].height = 35
    dash_ws.row_dimensions[4].height = 25

    for i in range(6):
        dash_ws.row_dimensions[5 + (i * 2)].height = 20
        dash_ws.row_dimensions[6 + (i * 2)].height = 45

    return wb


# ==========================================
# 2. Streamlit 메인 UI 로직
# ==========================================
st.set_page_config(page_title="근무 대시보드 생성기", layout="wide")
st.title("📅 근무표 대시보드 자동 생성기")

# 기본 경로 및 폴더 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# data 폴더가 없으면 자동 생성
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# data/ 폴더 안의 모든 엑셀 파일 탐색 (.xlsx, .xls)
excel_files_in_data = glob.glob(os.path.join(DATA_DIR, "*.xlsx")) + glob.glob(os.path.join(DATA_DIR, "*.xls"))

# 임시 파일(~$ 시작) 제외
excel_files_in_data = [f for f in excel_files_in_data if not os.path.basename(f).startswith("~$")]

# 사이드바: 파일 및 시트 선택
st.sidebar.header("📁 파일 및 옵션 설정")

# 웹 화면에서 직관적으로 새 파일을 올릴 수 있는 업로더
uploaded_file = st.sidebar.file_uploader(
    "새로운 엑셀 파일로 갱신하려면 업로드하세요", 
    type=["xlsx", "xls"]
)

file_to_process = None
source_name = ""

# 파일 탐색 및 자동 매핑 우선순위 지정
if uploaded_file is not None:
    file_to_process = uploaded_file
    source_name = f"웹에서 업로드한 파일: {uploaded_file.name}"
    st.sidebar.success("새 엑셀 파일이 업로드되었습니다!")

elif excel_files_in_data:
    # data/ 폴더에 엑셀 파일이 하나 이상 있을 때: 가장 최근에 수정된 파일 선택
    latest_file = max(excel_files_in_data, key=os.path.getmtime)
    file_to_process = latest_file
    file_basename = os.path.basename(latest_file)
    source_name = f"data/ 폴더 감지 파일: {file_basename}"
    st.sidebar.info(f"`data/` 폴더에서 `{file_basename}` 파일을 자동으로 로드했습니다.")

else:
    st.error("`data/` 폴더 내에 엑셀 파일이 존재하지 않고, 웹 업로드된 파일도 없습니다.")
    st.info("GitHub의 `data/` 폴더에 임의의 엑셀 파일(.xlsx)을 넣어두시거나, 왼쪽 사이드바에서 파일을 직접 업로드해 주세요.")

# 파일 로드가 정상적으로 준비된 경우
if file_to_process is not None:
    st.caption(f"📌 **현재 적용 기준:** {source_name}")
    
    try:
        # 시트 목록 읽기
        temp_wb = openpyxl.load_workbook(file_to_process, read_only=True)
        all_sheets = [s for s in temp_wb.sheetnames if s != "대시보드"]
        
        if not all_sheets:
            st.warning("엑셀 파일에 근무 데이터 시트가 존재하지 않습니다.")
        else:
            selected_sheet = st.sidebar.selectbox("대시보드를 생성할 시트를 선택하세요", all_sheets)

            if st.button("🚀 선택한 시트로 대시보드 생성/갱신"):
                # 파일 포인터 초기화 (업로드 파일 대응)
                if hasattr(file_to_process, "seek"):
                    file_to_process.seek(0)
                
                # 대시보드 포함된 워크북 생성
                updated_wb = generate_dashboard_workbook(file_to_process, selected_sheet)

                if updated_wb:
                    st.success(f"'{selected_sheet}' 시트 기준 대시보드가 정상적으로 작성되었습니다!")

                    # 메모리 스트림에 파일 저장 후 다운로드 제공
                    output_stream = io.BytesIO()
                    updated_wb.save(output_stream)
                    output_stream.seek(0)

                    st.download_button(
                        label="📥 대시보드가 반영된 엑셀 파일 다운로드",
                        data=output_stream,
                        file_name=f"근무대시보드_{selected_sheet}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {e}")
