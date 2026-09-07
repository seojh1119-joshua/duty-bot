import os
import glob
import calendar
import datetime
import io
import base64
import re
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="숙직 근무표 대시보드",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"  # 컬럼 선택을 위해 사이드바 기본 열림
)

DATA_DIR = "./data"

# ---------------------------------------------------------
# 대한민국 주요 법정 공휴일 계산기
# ---------------------------------------------------------
def get_kr_holidays(year):
    fixed_holidays = {
        (1, 1): "신정",
        (3, 1): "삼일절",
        (5, 5): "어린이날",
        (6, 6): "현충일",
        (8, 15): "광복절",
        (10, 3): "개천절",
        (10, 9): "한글날",
        (12, 25): "성탄절",
    }
    
    holidays_dict = {}
    for (m, d), name in fixed_holidays.items():
        try:
            holidays_dict[datetime.date(year, m, d)] = name
        except ValueError:
            pass
            
    return holidays_dict


# ---------------------------------------------------------
# 이름 정제 함수 (숫자/코드 형태 제거 및 이름 추출)
# ---------------------------------------------------------
def clean_name(val):
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    if val_str in ["nan", "None", "0", "", "null"]:
        return ""
    return val_str


# 데이터가 사람이름인지 사번/코드 형태인지 판별하는 함수
def is_likely_code(series):
    clean_series = series.dropna().astype(str).str.strip()
    if len(clean_series) == 0:
        return False
    # 숫자만으로 이루어진 비율 체크
    numeric_ratio = clean_series.str.replace(r'\.0$', '', regex=True).str.isnumeric().mean()
    return numeric_ratio > 0.6


# ---------------------------------------------------------
# 모바일 7열 5행 달력 CSS
# ---------------------------------------------------------
responsive_css = """
<style>
    .main .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 0.3rem !important;
        padding-right: 0.3rem !important;
    }
    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 3px;
        width: 100%;
    }
    .calendar-header {
        text-align: center;
        font-weight: bold;
        font-size: 13px;
        padding: 4px 0;
        background-color: #f0f2f6;
        border-radius: 4px;
    }
    .duty-card {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 6px;
        padding: 4px;
        min-height: 72px;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .duty-card-today {
        background-color: #FFF8E1 !important;
        border: 2px solid #FF9800 !important;
    }
    .duty-card-holiday {
        background-color: #FFF0F0;
        border: 1px solid #FFCDD2;
    }
    .day-num {
        font-weight: bold;
        font-size: 12px;
        color: #333333;
    }
    .day-num-red { color: #D32F2F !important; }
    .day-num-sat { color: #1976D2 !important; }
    .holiday-label {
        font-size: 9px;
        color: #D32F2F;
        font-weight: bold;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .worker-info {
        font-size: 11px;
        color: #222222;
        line-height: 1.25;
        margin-top: 2px;
    }
    @media (max-width: 768px) {
        .calendar-grid { gap: 2px; }
        .calendar-header { font-size: 10px; padding: 2px 0; }
        .duty-card { min-height: 58px !important; padding: 2px !important; border-radius: 4px; }
        .day-num { font-size: 10px !important; }
        .holiday-label { font-size: 8px !important; }
        .worker-info { font-size: 9px !important; line-height: 1.1 !important; }
    }
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)


# ---------------------------------------------------------
# data/ 폴더 자동 로더
# ---------------------------------------------------------
def get_data_folder_excel():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        return None, None

    excel_files = glob.glob(os.path.join(DATA_DIR, "*.xlsx")) + glob.glob(os.path.join(DATA_DIR, "*.xls"))
    if not excel_files:
        return None, None

    latest_file = max(excel_files, key=os.path.getmtime)
    with open(latest_file, "rb") as f:
        file_bytes = f.read()
    return file_bytes, os.path.basename(latest_file)


# ---------------------------------------------------------
# 스마트 파서 (숫자/코드 열 자동 필터링 적용)
# ---------------------------------------------------------
def parse_excel_smart(file_bytes, selected_sheet=None, override_cols=None):
    file_obj = io.BytesIO(file_bytes)
    excel_file = pd.ExcelFile(file_obj)
    sheet_names = excel_file.sheet_names

    target_sheet = selected_sheet
    if not target_sheet or target_sheet not in sheet_names:
        duty_sheets = [s for s in sheet_names if any(k in s for k in ["숙직", "근무", "당직", "일정"])]
        target_sheet = duty_sheets[0] if duty_sheets else sheet_names[0]

    df_raw = pd.read_excel(file_obj, sheet_name=target_sheet, header=None)

    # 헤더 행 탐색
    header_idx = 0
    for idx in range(min(25, len(df_raw))):
        row_values = [str(val).strip() for val in df_raw.iloc[idx].values]
        row_str = " ".join(row_values)
        if any(k in row_str for k in ["날짜", "일자", "근무일", "Date", "근무자", "성명", "이름", "담당", "주근", "야근"]):
            header_idx = idx
            break

    df = pd.read_excel(file_obj, sheet_name=target_sheet, header=header_idx)

    # 컬럼명 정제
    clean_cols = []
    for i, col in enumerate(df.columns):
        c_str = str(col).replace("\n", "").replace("\r", "").strip() if not str(col).startswith("Unnamed") else f"열_{i}"
        clean_cols.append(c_str)
    df.columns = clean_cols

    # 날짜 컬럼 자동 매핑
    date_col = next((c for c in df.columns if any(k in c.lower() for k in ["날짜", "일자", "근무일", "date"])), df.columns[0])
    df.rename(columns={date_col: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    all_cols = [c for c in df.columns if c != "날짜"]

    # 사용자가 수동 지정한 컬럼이 있으면 우선 적용
    p1_col = override_cols.get("p1") if override_cols else None
    p2_col = override_cols.get("p2") if override_cols else None
    sub1_col = override_cols.get("sub1") if override_cols else None
    sub2_col = override_cols.get("sub2") if override_cols else None

    # 자동 탐색 로직 (코드/숫자 열 자동 제외)
    if not p1_col:
        candidate_cols = []
        name_keywords = ["성명", "이름", "근무자", "숙직", "당직", "담당", "주근", "야근", "직원"]
        
        for c in all_cols:
            # 1. 키워드 일치 및 숫자 코드가 아닌 컬럼 우선
            if any(k in c for k in name_keywords) and "대직" not in c and "사번" not in c and "코드" not in c:
                if not is_likely_code(df[c]):
                    candidate_cols.append(c)

        # 키워드로 못 찾은 경우 숫자 코드가 아닌 일반 텍스트 열 선택
        if not candidate_cols:
            candidate_cols = [c for c in all_cols if not is_likely_code(df[c]) and "대직" not in c]

        p1_col = candidate_cols[0] if len(candidate_cols) > 0 else (all_cols[0] if all_cols else None)
        p2_col = candidate_cols[1] if len(candidate_cols) > 1 else None

    # 대직자 컬럼 자동 탐색
    if not sub1_col:
        sub_candidates = [c for c in all_cols if "대직" in c]
        sub1_col = sub_candidates[0] if len(sub_candidates) > 0 else None
        sub2_col = sub_candidates[1] if len(sub_candidates) > 1 else None

    df["근무자1"] = df[p1_col].apply(clean_name) if p1_col and p1_col in df.columns else ""
    df["근무자2"] = df[p2_col].apply(clean_name) if p2_col and p2_col in df.columns else ""
    df["대직1"] = df[sub1_col].apply(clean_name) if sub1_col and sub1_col in df.columns else ""
    df["대직2"] = df[sub2_col].apply(clean_name) if sub2_col and sub2_col in df.columns else ""

    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    # 대직 반영 실제 근무자
    df["실제근무1"] = df.apply(lambda r: r["대직1"] if r["대직1"] != "" else r["근무자1"], axis=1)
    df["실제근무2"] = df.apply(lambda r: r["대직2"] if r["대직2"] != "" else r["근무자2"], axis=1)

    df["실제근무1"] = df["실제근무1"].replace("", "미지정")
    df["실제근무2"] = df["실제근무2"].replace("", "미지정")

    return df, target_sheet, sheet_names, all_cols, {"p1": p1_col, "p2": p2_col, "sub1": sub1_col, "sub2": sub2_col}


def get_sample_df():
    today = datetime.date.today()
    start_date = today.replace(day=1)
    dates = pd.date_range(start=start_date, periods=35, freq="D")
    df = pd.DataFrame({
        "날짜": dates,
        "근무자1": ["김숙직"] * 35,
        "근무자2": ["이당직"] * 35,
        "대직1": ["박대직" if i % 5 == 0 else "" for i in range(35)],
        "대직2": [""] * 35,
    })
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")
    df["실제근무1"] = df.apply(lambda r: r["대직1"] if r["대직1"] != "" else r["근무자1"], axis=1)
    df["실제근무2"] = df.apply(lambda r: r["대직2"] if r["대직2"] != "" else r["근무자2"], axis=1)
    return df, ["근무자1", "근무자2", "대직1", "대직2"]


# ---------------------------------------------------------
# 세션 상태 및 data/ 폴더 자동 동기화
# ---------------------------------------------------------
if "excel_bytes" not in st.session_state or st.session_state.excel_bytes is None:
    file_bytes, file_name = get_data_folder_excel()
    if file_bytes:
        st.session_state.excel_bytes = file_bytes
        st.session_state.source_info = f"📂 `data/{file_name}` 자동 로드됨"
    else:
        st.session_state.excel_bytes = None
        st.session_state.source_info = "⚠️ `data/` 폴더에 엑셀 파일이 없어 샘플 표시 중"

if "selected_sheet" not in st.session_state:
    st.session_state.selected_sheet = None

if "override_cols" not in st.session_state:
    st.session_state.override_cols = {}

# 데이터 파싱 처리
if st.session_state.excel_bytes:
    try:
        df, used_sheet, sheet_list, raw_cols, auto_detected_cols = parse_excel_smart(
            st.session_state.excel_bytes, 
            st.session_state.selected_sheet,
            st.session_state.override_cols
        )
        st.session_state.df = df
        st.session_state.sheet_names = sheet_list
        st.session_state.selected_sheet = used_sheet
        st.session_state.raw_cols = raw_cols
        st.session_state.auto_detected_cols = auto_detected_cols
    except Exception as e:
        st.error(f"엑셀 로딩 오류: {e}")
        st.session_state.df, st.session_state.raw_cols = get_sample_df()
        st.session_state.auto_detected_cols = {}
else:
    st.session_state.df, st.session_state.raw_cols = get_sample_df()
    st.session_state.sheet_names = ["샘플"]
    st.session_state.auto_detected_cols = {}

# ---------------------------------------------------------
# 사이드바: 컬럼 수동 지정 옵션 (핵심 기능)
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 데이터 관리")
    st.caption(st.session_state.get("source_info", ""))

    uploaded_file = st.file_uploader("새 엑셀 파일 업로드", type=["xlsx", "xls"])
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        st.session_state.excel_bytes = bytes_data
        st.session_state.selected_sheet = None
        st.session_state.override_cols = {}
        st.session_state.source_info = f"📤 업로드됨: {uploaded_file.name}"

        os.makedirs(DATA_DIR, exist_ok=True)
        save_path = os.path.join(DATA_DIR, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(bytes_data)

        b64 = base64.b64encode(bytes_data).decode('utf-8')
        components.html(f"<script>localStorage.setItem('duty_excel_b64', '{b64}');</script>", height=0)
        st.rerun()

    if st.session_state.excel_bytes and len(st.session_state.sheet_names) > 1:
        st.subheader("📌 시트 변경")
        new_sheet = st.selectbox(
            "시트 선택", 
            st.session_state.sheet_names, 
            index=st.session_state.sheet_names.index(st.session_state.selected_sheet) if st.session_state.selected_sheet in st.session_state.sheet_names else 0
        )
        if new_sheet != st.session_state.selected_sheet:
            st.session_state.selected_sheet = new_sheet
            st.session_state.override_cols = {}
            st.rerun()

    # 🎯 코드가 대신 나올 때 사용자가 직접 이름 열을 지정할 수 있는 수동 선택 메뉴
    if "raw_cols" in st.session_state and st.session_state.raw_cols:
        st.markdown("---")
        st.subheader("🎯 근무자 이름 열 매핑")
        st.caption("달력에 이름 대신 코드가 나올 경우, 실제 **사람 이름**이 들어있는 열을 선택하세요.")

        cols_options = ["(자동 선택)"] + st.session_state.raw_cols
        
        curr_p1 = st.session_state.override_cols.get("p1") or st.session_state.auto_detected_cols.get("p1")
        curr_p2 = st.session_state.override_cols.get("p2") or st.session_state.auto_detected_cols.get("p2")

        p1_idx = cols_options.index(curr_p1) if curr_p1 in cols_options else 0
        p2_idx = cols_options.index(curr_p2) if curr_p2 in cols_options else 0

        selected_p1 = st.selectbox("👤 근무자 1 (이름 열)", cols_options, index=p1_idx)
        selected_p2 = st.selectbox("👤 근무자 2 (이름 열)", cols_options, index=p2_idx)

        new_p1 = None if selected_p1 == "(자동 선택)" else selected_p1
        new_p2 = None if selected_p2 == "(자동 선택)" else selected_p2

        if (new_p1 != st.session_state.override_cols.get("p1")) or (new_p2 != st.session_state.override_cols.get("p2")):
            st.session_state.override_cols["p1"] = new_p1
            st.session_state.override_cols["p2"] = new_p2
            st.rerun()

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
st.title("📋 숙직 근무표 대시보드")

df = st.session_state.df
today = datetime.date.today()

tab1, tab2, tab3 = st.tabs(["📅 달력 메인 화면", "🔍 데이터 상세 및 수정", "📊 근무 통계"])

# ---------------------------------------------------------
# TAB 1: 7열 5행 모바일 대응 달력 (일요일 시작)
# ---------------------------------------------------------
with tab1:
    available_months = sorted(df["년월"].dropna().unique())
    current_ym = today.strftime("%Y-%m")
    default_idx = available_months.index(current_ym) if current_ym in available_months else 0

    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.subheader(f"📌 오늘 ({today.strftime('%Y-%m-%d')}) 실제 근무")
        today_df = df[df["날짜"].dt.date == today]
        if not today_df.empty:
            p1 = today_df.iloc[0]["실제근무1"]
            p2 = today_df.iloc[0]["실제근무2"]
            st.markdown(f"#### 👤 **근무1:** `{p1}`  |  👤 **근무2:** `{p2}`")
        else:
            st.write("오늘 일자의 근무 정보가 없습니다.")

    with c2:
        selected_month = st.selectbox("🗓️ 조회 월 선택", available_months, index=default_idx)

    year, month = map(int, selected_month.split("-"))

    kr_holidays = get_kr_holidays(year)

    st.markdown("---")
    st.markdown(f"### 🗓️ {year}년 {month}월 숙직 달력")

    cal_obj = calendar.Calendar(firstweekday=6)
    cal = cal_obj.monthdayscalendar(year, month)

    month_df = df[df["년월"] == selected_month].copy()

    duty_map = {}
    for _, row in month_df.iterrows():
        d_day = row["날짜"].day
        duty_map[d_day] = {
            "p1": str(row["실제근무1"]),
            "p2": str(row["실제근무2"]),
            "date_obj": row["날짜"].date()
        }

    # 7열 헤더 (일~토 순서)
    days_header = ["일", "월", "화", "수", "목", "금", "토"]
    header_html = "<div class='calendar-grid'>"
    for idx, day_name in enumerate(days_header):
        color_style = "color:#D32F2F;" if idx == 0 else ("color:#1976D2;" if idx == 6 else "color:#333;")
        header_html += f"<div class='calendar-header' style='{color_style}'>{day_name}</div>"
    header_html += "</div>"
    st.markdown(header_html, unsafe_allow_html=True)

    grid_html = "<div class='calendar-grid' style='margin-top: 4px;'>"

    for week in cal:
        for i, day in enumerate(week):
            if day == 0:
                grid_html += "<div class='duty-card' style='background:transparent; border:none;'></div>"
            else:
                date_obj = datetime.date(year, month, day)
                duty_info = duty_map.get(day)
                is_today = (date_obj == today)

                holiday_name = kr_holidays.get(date_obj)
                is_sunday = (i == 0)
                is_saturday = (i == 6)
                is_holiday = bool(holiday_name) or is_sunday

                card_class = "duty-card"
                if is_today:
                    card_class += " duty-card-today"
                elif is_holiday:
                    card_class += " duty-card-holiday"

                day_num_class = "day-num"
                if is_holiday:
                    day_num_class += " day-num-red"
                elif is_saturday:
                    day_num_class += " day-num-sat"

                p1_name = duty_info['p1'] if duty_info else '-'
                p2_name = duty_info['p2'] if duty_info else '-'
                if len(p1_name) > 3: p1_name = p1_name[:3] + ".."
                if len(p2_name) > 3: p2_name = p2_name[:3] + ".."

                holiday_tag = f"<div class='holiday-label'>{holiday_name[:4]}</div>" if holiday_name else ""

                grid_html += f"""
                <div class="{card_class}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="{day_num_class}">{day}</span>
                        {holiday_tag}
                    </div>
                    <div class="worker-info">
                        1:{p1_name}<br>
                        2:{p2_name}
                    </div>
                </div>
                """

    grid_html += "</div>"
    st.markdown(grid_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📋 이달의 상세 근무 목록")
    st.dataframe(month_df, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: 데이터 수정
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 근무표 직접 수정 및 저장")
    st.caption("수정 후 아래 [저장] 버튼을 누르면 `data/` 폴더 내에 엑셀 파일로 저장됩니다.")

    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", key="editor")

    if st.button("💾 수정사항 저장"):
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df["년월"] = edited_df["날짜"].dt.strftime("%Y-%m")
        
        edited_df["근무자1"] = edited_df["근무자1"].apply(clean_name)
        edited_df["근무자2"] = edited_df["근무자2"].apply(clean_name)
        edited_df["대직1"] = edited_df["대직1"].apply(clean_name)
        edited_df["대직2"] = edited_df["대직2"].apply(clean_name)

        edited_df["실제근무1"] = edited_df.apply(lambda r: r["대직1"] if r["대직1"] != "" else r["근무자1"], axis=1)
        edited_df["실제근무2"] = edited_df.apply(lambda r: r["대직2"] if r["대직2"] != "" else r["근무자2"], axis=1)

        st.session_state.df = edited_df

        os.makedirs(DATA_DIR, exist_ok=True)
        save_path = os.path.join(DATA_DIR, "updated_duty_schedule.xlsx")
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            edited_df.to_excel(writer, index=False)

        st.success("🎉 수정된 데이터가 성공적으로 저장되었습니다!")
        st.rerun()

# ---------------------------------------------------------
# TAB 3: 근무 통계
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 근무자별 집계")
    w1 = df[["실제근무1"]].rename(columns={"실제근무1": "근무자"})
    w2 = df[["실제근무2"]].rename(columns={"실제근무2": "근무자"})
    all_workers = pd.concat([w1, w2])
    all_workers = all_workers[~all_workers["근무자"].isin(["미지정", "nan", "None", "", "-"])]

    if not all_workers.empty:
        counts = all_workers["근무자"].value_counts()
        st.bar_chart(counts)
    else:
        st.info("통계를 표시할 근무자 데이터가 없습니다.")
