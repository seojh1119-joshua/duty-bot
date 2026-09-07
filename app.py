import calendar
import datetime
import io
import os
import glob
import pandas as pd
import streamlit as st

# 대한민국 공휴일 라이브러리
try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# ---------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="숙직 근무표 대시보드",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# CSS 스타일링 (달력 카드 디자인 및 가독성 개선)
# ---------------------------------------------------------
responsive_css = """
<style>
    .main .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    .duty-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 6px;
        margin-bottom: 8px;
        min-height: 110px;
        background-color: #FFFFFF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .duty-card-header {
        font-weight: bold;
        font-size: 13px;
        padding: 2px 4px;
        border-radius: 4px;
        margin-bottom: 4px;
    }
    .duty-worker-info {
        font-size: 12px;
        color: #1E293B;
        line-height: 1.4;
        margin-bottom: 4px;
    }
    .duty-card-memo {
        margin-top: 4px;
        padding: 3px 5px;
        background-color: #FEF3C7;
        border-left: 3px solid #F59E0B;
        font-size: 11px;
        color: #92400E;
        border-radius: 2px;
        word-break: break-all;
    }
    .stButton > button {
        width: 100% !important;
        font-size: 10px !important;
        padding: 1px 2px !important;
        min-height: 22px !important;
        height: 22px !important;
        margin-top: 2px !important;
    }
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

DEFAULT_FILE_PATH = os.path.join("data", "duty_schedule.xlsx")

# ---------------------------------------------------------
# 엑셀 스마트 로더 (숙직근무자 시트 우선)
# ---------------------------------------------------------
def load_excel_smart(file_source, selected_sheet=None):
    if isinstance(file_source, bytes):
        file_obj = io.BytesIO(file_source)
    else:
        file_obj = file_source

    excel_file = pd.ExcelFile(file_obj)
    sheet_names = excel_file.sheet_names

    target_sheet = selected_sheet
    if not target_sheet or target_sheet not in sheet_names:
        priority_sheets = [s for s in sheet_names if "숙직근무자" in s or "숙직" in s or "의료과" in s or "야근" in s]
        target_sheet = priority_sheets[0] if priority_sheets else sheet_names[0]

    if isinstance(file_source, bytes):
        file_obj.seek(0)

    df_raw = pd.read_excel(file_obj, sheet_name=target_sheet, header=None)

    header_idx = None
    for idx in range(min(25, len(df_raw))):
        row_values = [str(val).strip() for val in df_raw.iloc[idx].values]
        row_str = " ".join(row_values)
        if any(k in row_str for k in ["날짜", "일자", "근무일", "Date", "근무자", "성명", "이름"]):
            header_idx = idx
            break

    if header_idx is None:
        header_idx = 0

    if isinstance(file_source, bytes):
        file_obj.seek(0)

    df = pd.read_excel(file_obj, sheet_name=target_sheet, header=header_idx)

    clean_cols = []
    for i, col in enumerate(df.columns):
        c_str = (
            str(col).replace("\n", "").replace("\r", "").strip()
            if not str(col).startswith("Unnamed")
            else f"열_{i}"
        )
        clean_cols.append(c_str)
    df.columns = clean_cols

    date_col = next(
        (col for col in df.columns if any(k in col.lower() for k in ["날짜", "일자", "근무일", "date", "일자/요일"])),
        df.columns[0]
    )
    df.rename(columns={date_col: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    duty_type_col = next(
        (c for c in df.columns if any(k in c for k in ["근무구분_원본", "근무구분", "구분", "근무유형", "요일구분", "요일"])), 
        None
    )
    if duty_type_col:
        df["근무구분_원본"] = df[duty_type_col].astype(str).str.strip()
    else:
        df["근무구분_원본"] = "평일"

    cols = list(df.columns)
    p1_col = next((c for c in cols if any(k in c for k in ["근무자1", "근무자 1", "1근무", "숙직1", "당직1", "성명", "이름"]) and "대직" not in c), None)
    p2_col = next((c for c in cols if any(k in c for k in ["근무자2", "근무자 2", "2근무", "숙직2", "당직2"]) and "대직" not in c), None)
    sub1_col = next((c for c in cols if any(k in c for k in ["대직1", "대직자1", "대직 1", "대직자"])), None)
    sub2_col = next((c for c in cols if any(k in c for k in ["대직2", "대직자2", "대직 2"])), None)

    df["근무자1"] = df[p1_col].astype(str).str.strip() if p1_col else "미지정"
    df["근무자2"] = df[p2_col].astype(str).str.strip() if p2_col else "미지정"
    df["대직1"] = df[sub1_col].astype(str).str.strip() if sub1_col else None
    df["대직2"] = df[sub2_col].astype(str).str.strip() if sub2_col else None

    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    df["실제근무1"] = (
        df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
        .combine_first(df["근무자1"]).fillna("미지정")
    )
    df["실제근무2"] = (
        df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
        .combine_first(df["근무자2"]).fillna("미지정")
    )

    return df, target_sheet, sheet_names, df_raw


def save_to_excel_file(df, sheet_name):
    """수정사항 엑셀 저장"""
    save_path = st.session_state.get("file_path", DEFAULT_FILE_PATH)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    save_df = df.copy()
    save_df["날짜"] = save_df["날짜"].dt.strftime("%Y-%m-%d")

    if os.path.exists(save_path):
        try:
            with pd.ExcelWriter(save_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                save_df.to_excel(writer, sheet_name=sheet_name, index=False)
        except Exception:
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                save_df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
            save_df.to_excel(writer, sheet_name=sheet_name, index=False)


# ---------------------------------------------------------
# 세션 상태 초기화 및 데이터 로드
# ---------------------------------------------------------
if "file_path" not in st.session_state:
    if os.path.exists("data"):
        files = glob.glob(os.path.join("data", "*.xlsx"))
        st.session_state.file_path = files[0] if files else DEFAULT_FILE_PATH
    else:
        st.session_state.file_path = DEFAULT_FILE_PATH

if "memos" not in st.session_state:
    st.session_state.memos = {}

if "df" not in st.session_state:
    if os.path.exists(st.session_state.file_path):
        parsed_df, used_sheet, sheet_names, raw_df = load_excel_smart(st.session_state.file_path)
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
    else:
        today = datetime.date.today()
        dates = pd.date_range(start=today.replace(day=1), periods=60, freq="D")
        sample_df = pd.DataFrame({
            "날짜": dates,
            "근무구분_원본": ["평일", "금요일", "토요일", "일요일", "평일"] * 12,
            "근무자1": ["서진호", "김철수", "이영희", "박민수", "정수진"] * 12,
            "근무자2": ["김철수", "이영희", "박민수", "정수진", "서진호"] * 12,
            "대직1": [None] * 60,
            "대직2": [None] * 60,
        })
        sample_df["년월"] = sample_df["날짜"].dt.strftime("%Y-%m")
        sample_df["실제근무1"] = sample_df["근무자1"]
        sample_df["실제근무2"] = sample_df["근무자2"]

        st.session_state.df = sample_df
        st.session_state.sheet_names = ["숙직근무자"]
        st.session_state.selected_sheet = "숙직근무자"
        st.session_state.raw_df = pd.DataFrame()
        save_to_excel_file(sample_df, st.session_state.selected_sheet)


# ---------------------------------------------------------
# 근무자 수정 및 메모 입력 팝업 모달
# ---------------------------------------------------------
@st.dialog("✏️ 근무자 수정 및 메모 작성")
def edit_worker_dialog(date_str, duty_info):
    st.write(f"📅 **{date_str} 상세 정보 입력**")

    current_memo = st.session_state.memos.get(date_str, "")

    with st.form(key=f"dialog_form_{date_str}"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            edit_p1 = st.text_input("근무자1", value=duty_info["p1_orig"])
            edit_sub1 = st.text_input("대직자1", value=duty_info["sub1"])
        with col_f2:
            edit_p2 = st.text_input("근무자2", value=duty_info["p2_orig"])
            edit_sub2 = st.text_input("대직자2", value=duty_info["sub2"])

        st.divider()
        edit_memo = st.text_area("📌 날짜별 메모 (달력에 바로 표시됨)", value=current_memo, height=80)

        submitted = st.form_submit_button("💾 저장하기", use_container_width=True)

        if submitted:
            row_idx = duty_info["idx"]
            st.session_state.df.at[row_idx, "근무자1"] = edit_p1.strip()
            st.session_state.df.at[row_idx, "근무자2"] = edit_p2.strip()
            st.session_state.df.at[row_idx, "대직1"] = edit_sub1.strip() if edit_sub1.strip() else None
            st.session_state.df.at[row_idx, "대직2"] = edit_sub2.strip() if edit_sub2.strip() else None

            st.session_state.df.at[row_idx, "실제근무1"] = edit_sub1.strip() if edit_sub1.strip() else edit_p1.strip()
            st.session_state.df.at[row_idx, "실제근무2"] = edit_sub2.strip() if edit_sub2.strip() else edit_p2.strip()

            st.session_state.memos[date_str] = edit_memo.strip()

            save_to_excel_file(st.session_state.df, st.session_state.selected_sheet)
            st.success("✅ 저장되었습니다!")
            st.rerun()


# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 파일 및 시트 설정")
    uploaded_file = st.file_uploader("새 엑셀 파일 업로드", type=["xlsx"])

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        with open(st.session_state.file_path, "wb") as f:
            f.write(file_bytes)

        parsed_df, used_sheet, sheet_names, raw_df = load_excel_smart(file_bytes)
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
        st.success("✅ 업로드 완료!")
        st.rerun()

    if "sheet_names" in st.session_state:
        sheets = st.session_state.sheet_names
        curr_idx = sheets.index(st.session_state.selected_sheet) if st.session_state.selected_sheet in sheets else 0

        selected_s = st.selectbox("📌 시트 선택", sheets, index=curr_idx)
        if selected_s != st.session_state.selected_sheet:
            st.session_state.selected_sheet = selected_s
            parsed_df, used_sheet, _, raw_df = load_excel_smart(st.session_state.file_path, selected_s)
            st.session_state.df = parsed_df
            st.session_state.raw_df = raw_df
            st.rerun()

df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 탭 구성
# ---------------------------------------------------------
st.title("📋 야근/숙직 근무 현황 및 통계")

tab1, tab_sheet, tab2, tab3 = st.tabs([
    "📅 달력 메인 화면",
    "📊 시트 데이터 점검",
    "✏️ 근무표 전체 수정",
    "📊 숙직근무자 월별 근무 통계",
])

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면
# ---------------------------------------------------------
with tab1:
    st.subheader("📅 근무 달력")

    available_months = sorted(df["년월"].dropna().unique())
    current_ym = today.strftime("%Y-%m")
    default_idx = available_months.index(current_ym) if current_ym in available_months else 0

    selected_month = st.selectbox("조회 월 선택", available_months, index=default_idx) if available_months else current_ym

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)
        month_df = df[df["년월"] == selected_month].copy()

        duty_map = {}
        for idx_row, row in month_df.iterrows():
            d_day = row["날짜"].day
            duty_map[d_day] = {
                "idx": idx_row,
                "p1_orig": str(row["근무자1"]),
                "p2_orig": str(row["근무자2"]),
                "sub1": str(row["대직1"]) if pd.notnull(row["대직1"]) else "",
                "sub2": str(row["대직2"]) if pd.notnull(row["대직2"]) else "",
                "p1_real": str(row["실제근무1"]),
                "p2_real": str(row["실제근무2"]),
            }

        cols = st.columns(7)
        for idx, day_name in enumerate(["일", "월", "화", "수", "목", "금", "토"]):
            cols[idx].markdown(f"**{'🔴' if idx==0 else ('🔵' if idx==6 else '⚪')} {day_name}**")

        for week in month_days:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                with week_cols[i]:
                    if day != 0:
                        curr_date = datetime.date(year, month, day)
                        date_str = curr_date.strftime("%Y-%m-%d")
                        duty_info = duty_map.get(day)

                        is_today = (curr_date == today)
                        is_holiday = kr_holidays.get(curr_date) is not None or i == 0

                        bg_header = "#FFD54F" if is_today else ("#FFCDD2" if is_holiday else ("#BBDEFB" if i == 6 else "#E0E0E0"))
                        
                        card_html = f"<div class='duty-card'>"
                        card_html += f"<div class='duty-card-header' style='background-color:{bg_header};'>{day}일</div>"

                        if duty_info:
                            p1_txt = duty_info['p1_real'] + ("(대)" if duty_info['sub1'] else "")
                            p2_txt = duty_info['p2_real'] + ("(대)" if duty_info['sub2'] else "")
                            card_html += f"<div class='duty-worker-info'>👤 {p1_txt}<br>👤 {p2_txt}</div>"

                        day_memo = st.session_state.memos.get(date_str, "")
                        if day_memo:
                            card_html += f"<div class='duty-card-memo'>📌 {day_memo}</div>"

                        card_html += "</div>"
                        st.markdown(card_html, unsafe_allow_html=True)

                        if duty_info:
                            if st.button("✏️ 수정", key=f"btn_{date_str}"):
                                edit_worker_dialog(date_str, duty_info)

# ---------------------------------------------------------
# TAB 2: 데이터 점검
# ---------------------------------------------------------
with tab_sheet:
    st.subheader(f"🔍 [{st.session_state.selected_sheet}] 시트 데이터 확인")
    st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: 근무표 전체 수정
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 전체 근무표 수정")
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", key="data_editor")

    if st.button("💾 전체 변경사항 저장"):
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df = edited_df.dropna(subset=["날짜"]).copy()
        
        edited_df["근무구분_원본"] = edited_df["근무구분_원본"].astype(str).str.strip()
        edited_df["년월"] = edited_df["날짜"].dt.strftime("%Y-%m")

        edited_df["실제근무1"] = (
            edited_df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자1"]).fillna("미지정")
        )
        edited_df["실제근무2"] = (
            edited_df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자2"]).fillna("미지정")
        )

        st.session_state.df = edited_df
        save_to_excel_file(edited_df, st.session_state.selected_sheet)
        st.success("✅ 성공적으로 저장되었습니다.")
        st.rerun()

# ---------------------------------------------------------
# TAB 4: 월별 근무 통계 (범위 제한 차트 및 근무시간 산출표)
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 숙직근무자 월별 근무 통계")
    st.caption("📌 **근무 시간 산출 기준:** 금요일 15시간, 토요일 15시간, 일요일 7시간, 평일 7시간 | **휴일근무 횟수:** 토요일 + 일요일 근무 횟수")

    duty_stat_df = st.session_state.df.copy()

    available_stat_months = ["전체 기간"] + sorted(duty_stat_df["년월"].dropna().unique(), reverse=True)
    curr_ym = today.strftime("%Y-%m")
    default_stat_idx = available_stat_months.index(curr_ym) if curr_ym in available_stat_months else 0

    col_s1, _ = st.columns([1, 2])
    with col_s1:
        selected_stat_month = st.selectbox(
            "📅 통계 조회 월 선택",
            available_stat_months,
            index=default_stat_idx,
            key="stat_month_select"
        )

    filtered_df = duty_stat_df.copy() if selected_stat_month == "전체 기간" else duty_stat_df[duty_stat_df["년월"] == selected_stat_month].copy()

    # 근무자1, 근무자2 결합
    w1 = filtered_df[["실제근무1", "근무구분_원본"]].rename(columns={"실제근무1": "근무자", "근무구분_원본": "근무구분"})
    w2 = filtered_df[["실제근무2", "근무구분_원본"]].rename(columns={"실제근무2": "근무자", "근무구분_원본": "근무구분"})
    
    combined = pd.concat([w1, w2], ignore_index=True)
    combined["근무자"] = combined["근무자"].astype(str).str.strip()
    combined["근무구분"] = combined["근무구분"].astype(str).str.strip()
    
    # 예외/미지정 근무자 제외
    combined = combined[
        combined["근무자"].notnull() & 
        (~combined["근무자"].isin(["미지정", "nan", "None", "", "NaN"])) &
        (~combined["근무구분"].isin(["nan", "None", "", "NaN"]))
    ]

    if not combined.empty:
        # 피벗 테이블 생성: 근무자별 근무구분 문자열 개수 카운트
        stats_df = pd.crosstab(index=combined["근무자"], columns=combined["근무구분"], margins=False)
        
        # 1. 휴일근무 횟수 계산 (토요일 + 일요일 근무 횟수)
        sat_cnt = stats_df["토요일"] if "토요일" in stats_df.columns else 0
        sun_cnt = stats_df["일요일"] if "일요일" in stats_df.columns else 0
        stats_df["휴일근무 횟수"] = sat_cnt + sun_cnt

        # 2. 근무시간 계산 (금: 15h, 토: 15h, 일: 7h, 평일/기타: 7h)
        hours_per_type = {
            "금요일": 15,
            "토요일": 15,
            "일요일": 7,
            "평일": 7
        }

        total_hours = pd.Series(0, index=stats_df.index)
        for col in stats_df.columns:
            if col in hours_per_type:
                total_hours += stats_df[col] * hours_per_type[col]
            elif col not in ["총 근무 횟수", "휴일근무 횟수"]:
                total_hours += stats_df[col] * 7

        stats_df["총 근무시간(h)"] = total_hours

        # 3. 총 근무 횟수 연산
        type_cols = [c for c in stats_df.columns if c not in ["총 근무 횟수", "휴일근무 횟수", "총 근무시간(h)"]]
        stats_df["총 근무 횟수"] = stats_df[type_cols].sum(axis=1)

        # 열 정렬 및 근무시간 내림차순 정렬
        ordered_cols = type_cols + ["휴일근무 횟수", "총 근무 횟수", "총 근무시간(h)"]
        stats_df = stats_df[ordered_cols].sort_values(by="총 근무시간(h)", ascending=False)

        # 요약 메트릭 카드
        m1, m2, m3 = st.columns(3)
        m1.metric("총 근무 인원", f"{len(stats_df)}명")
        m2.metric("총 근무건수 합계", f"{int(stats_df['총 근무 횟수'].sum())}건")
        m3.metric("총 근무시간 합계", f"{int(stats_df['총 근무시간(h)'].sum())}시간")

        st.markdown("---")

        # ---------------------------------------------------------
        # 1. 차트 범위 제한 섹션
        # ---------------------------------------------------------
        st.markdown(f"#### 📊 [{selected_stat_month}] 근무자별 총 근무시간 비교 차트")
        
        max_workers = len(stats_df)
        default_limit = min(10, max_workers)
        
        top_n = st.slider(
            "차트에 표시할 상위 근무자 수 제한", 
            min_value=1, 
            max_value=max_workers, 
            value=default_limit,
            help="근무시간이 많은 상위 N명의 근무자만 차트에 표시합니다."
        )
        
        chart_df = stats_df.head(top_n)[["총 근무시간(h)"]]
        st.bar_chart(chart_df)

        st.markdown("---")

        # ---------------------------------------------------------
        # 2. 근무시간 산출 상세 집계표 (합계 Row 포함)
        # ---------------------------------------------------------
        st.markdown(f"#### 📋 [{selected_stat_month}] 근무시간 산출 상세 집계표")
        
        display_df = stats_df.copy()
        
        # 합계(Total) 행 계산 및 추가
        total_row = display_df.sum(axis=0)
        total_row.name = "합계"
        display_df = pd.concat([display_df, pd.DataFrame(total_row).T])

        st.dataframe(display_df, use_container_width=True, height=500)

    else:
        st.info("조회할 근무 정보가 존재하지 않습니다.")
