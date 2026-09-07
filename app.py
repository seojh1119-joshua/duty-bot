import calendar
import datetime
import io
import os
import glob
import pandas as pd
import streamlit as st

# 대한민국 공휴일 라이브러리 (미설치 시 예외 처리)
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
# 반응형 CSS (PC/모바일 대응 및 공휴일/일요일 스타일링)
# ---------------------------------------------------------
responsive_css = """
<style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    .duty-card {
        border-radius: 8px;
        padding: 6px 8px;
        margin-bottom: 6px;
        min-height: 85px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .duty-card-title {
        font-weight: bold;
        font-size: 13px;
        border-bottom: 1px solid rgba(0,0,0,0.08);
        padding-bottom: 3px;
        margin-bottom: 4px;
    }
    .duty-card-text {
        font-size: 11px;
        color: #2c3e50;
        line-height: 1.4;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.25rem;
            padding-right: 0.25rem;
        }
        .duty-card {
            min-height: 70px !important;
            padding: 4px !important;
        }
        .duty-card-title {
            font-size: 10px !important;
        }
        .duty-card-text {
            font-size: 9px !important;
        }
    }
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)


# ---------------------------------------------------------
# 1. 스마트 엑셀 로더 함수
# ---------------------------------------------------------
def load_excel_smart(file_bytes, selected_sheet=None):
    file_obj = io.BytesIO(file_bytes)
    
    file_obj.seek(0)
    excel_file = pd.ExcelFile(file_obj)
    sheet_names = excel_file.sheet_names

    target_sheet = selected_sheet
    if not target_sheet or target_sheet not in sheet_names:
        duty_sheets = [s for s in sheet_names if "숙직" in s or "근무" in s]
        target_sheet = duty_sheets[0] if duty_sheets else sheet_names[0]

    file_obj.seek(0)
    df_raw = pd.read_excel(file_obj, sheet_name=target_sheet, header=None)

    header_idx = None
    for idx in range(min(25, len(df_raw))):
        row_values = [str(val).strip() for val in df_raw.iloc[idx].values]
        row_str = " ".join(row_values)
        if any(k in row_str for k in ["날짜", "일자", "근무일", "Date", "근무자"]):
            header_idx = idx
            break

    if header_idx is None:
        header_idx = 0

    file_obj.seek(0)
    df = pd.read_excel(file_obj, sheet_name=target_sheet, header=header_idx)

    # 컬럼 정제
    clean_cols = []
    for i, col in enumerate(df.columns):
        c_str = (
            str(col).replace("\n", "").replace("\r", "").strip()
            if not str(col).startswith("Unnamed")
            else f"열_{i}"
        )
        clean_cols.append(c_str)
    df.columns = clean_cols

    # 날짜 컬럼 자동 인식
    date_col = next(
        (col for col in df.columns if any(k in col.lower() for k in ["날짜", "일자", "근무일", "date", "일자/요일"])),
        df.columns[0]
    )
    df.rename(columns={date_col: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    # 근무자 매핑
    cols = list(df.columns)
    p1_col = next((c for c in cols if any(k in c for k in ["근무자1", "근무자 1", "1근무", "숙직1", "당직1"]) and "대직" not in c), None)
    p2_col = next((c for c in cols if any(k in c for k in ["근무자2", "근무자 2", "2근무", "숙직2", "당직2"]) and "대직" not in c), None)
    sub1_col = next((c for c in cols if any(k in c for k in ["대직1", "대직자1", "대직 1", "대직자"])), None)
    sub2_col = next((c for c in cols if any(k in c for k in ["대직2", "대직자2", "대직 2"])), None)

    df["근무자1"] = df[p1_col] if p1_col else "미지정"
    df["근무자2"] = df[p2_col] if p2_col else "미지정"
    df["대직1"] = df[sub1_col] if sub1_col else None
    df["대직2"] = df[sub2_col] if sub2_col else None

    type_col = next((c for c in cols if any(k in c for k in ["구분", "근무구분", "요일", "비고"])), None)
    if type_col and type_col != "날짜":
        df.rename(columns={type_col: "근무구분"}, inplace=True)
    else:
        df["근무구분"] = df["날짜"].dt.weekday.map(lambda x: "주말" if x in [5, 6] else "평일")

    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    # 대직자 적용 로직
    df["실제근무1"] = (
        df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
        .combine_first(df["근무자1"]).fillna("미지정")
    )
    df["실제근무2"] = (
        df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
        .combine_first(df["근무자2"]).fillna("미지정")
    )

    return df, target_sheet, sheet_names, df_raw


# ---------------------------------------------------------
# data/ 폴더 기본 엑셀 로드 함수
# ---------------------------------------------------------
def get_default_excel_bytes():
    data_dir = "data"
    if os.path.exists(data_dir):
        files = glob.glob(os.path.join(data_dir, "*.xlsx"))
        if files:
            with open(files[0], "rb") as f:
                return f.read()
    return None


# ---------------------------------------------------------
# 세션 상태(Session State) 유지 관리 (새로고침 시 초기화 방지)
# ---------------------------------------------------------
if "excel_bytes" not in st.session_state:
    st.session_state.excel_bytes = get_default_excel_bytes()

if "selected_sheet" not in st.session_state:
    st.session_state.selected_sheet = None

# 초기 데이터 로드
if st.session_state.excel_bytes is not None and "df" not in st.session_state:
    try:
        parsed_df, used_sheet, sheet_names, raw_df = load_excel_smart(st.session_state.excel_bytes)
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
    except Exception:
        pass

# 기본 샘플 데이터 Fallback
if "df" not in st.session_state:
    today = datetime.date.today()
    dates = pd.date_range(start=today.replace(day=1), periods=35, freq="D")
    sample_df = pd.DataFrame({
        "날짜": dates,
        "근무구분": ["주말" if d.weekday() in [5, 6] else "평일" for d in dates],
        "근무자1": ["홍길동"] * 35,
        "근무자2": ["김철수"] * 35,
        "대직1": [None if i % 5 != 0 else "이대직" for i in range(35)],
        "대직2": [None] * 35,
    })
    sample_df["년월"] = sample_df["날짜"].dt.strftime("%Y-%m")
    sample_df["실제근무1"] = sample_df["대직1"].fillna("").replace("", None).combine_first(sample_df["근무자1"])
    sample_df["실제근무2"] = sample_df["대직2"].fillna("").replace("", None).combine_first(sample_df["근무자2"])
    
    st.session_state.df = sample_df
    st.session_state.sheet_names = ["샘플시트"]
    st.session_state.raw_df = pd.DataFrame()


# ---------------------------------------------------------
# 사이드바: 파일 및 시트 관리
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 파일 및 시트 관리")
    uploaded_file = st.file_uploader(
        "새로운 엑셀(.xlsx) 파일 업로드", type=["xlsx"]
    )

    # 새로운 파일 선택 시 세션 저장소 업데이트
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        if file_bytes != st.session_state.excel_bytes:
            st.session_state.excel_bytes = file_bytes
            st.session_state.selected_sheet = None
            
            parsed_df, used_sheet, sheet_names, raw_df = load_excel_smart(file_bytes)
            st.session_state.df = parsed_df
            st.session_state.selected_sheet = used_sheet
            st.session_state.sheet_names = sheet_names
            st.session_state.raw_df = raw_df
            st.success("✅ 파일이 성공적으로 갱신되었습니다!")
            st.rerun()

    # 시트 선택 드롭다운
    if st.session_state.excel_bytes is not None and "sheet_names" in st.session_state:
        sheets = st.session_state.sheet_names
        curr_idx = sheets.index(st.session_state.selected_sheet) if st.session_state.selected_sheet in sheets else 0
        
        selected_s = st.selectbox(
            "📌 불러올 시트 선택",
            sheets,
            index=curr_idx,
            key="sheet_selector",
        )

        if selected_s != st.session_state.selected_sheet:
            st.session_state.selected_sheet = selected_s
            parsed_df, used_sheet, _, raw_df = load_excel_smart(
                st.session_state.excel_bytes, selected_s
            )
            st.session_state.df = parsed_df
            st.session_state.raw_df = raw_df
            st.rerun()

        st.caption(f"🟢 현재 사용 중: **[{st.session_state.selected_sheet}]** 시트")
    else:
        st.info("💡 `data/` 폴더 내 엑셀이 없거나 업로드된 파일이 없어 샘플 데이터를 표시 중입니다.")

df = st.session_state.df

# ---------------------------------------------------------
# 메인 화면 구성 (탭)
# ---------------------------------------------------------
st.title("📋 숙직 근무표 통합 대시보드")

tab1, tab_sheet, tab2, tab3 = st.tabs([
    "📅 달력 메인 화면",
    "📊 시트 데이터 점검",
    "✏️ 근무표 수정",
    "📊 근무 통계",
])

today = datetime.date.today()

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면 (일요일 시작 7열 5행 달력)
# ---------------------------------------------------------
with tab1:
    st.subheader("📅 오늘 기준 숙직 근무 현황")

    today_df = df[df["날짜"].dt.date == today]

    col_card1, col_card2 = st.columns([1.2, 1])
    with col_card1:
        st.info(f"📌 **오늘 날짜 ({today.strftime('%Y-%m-%d')}) 실제 근무자**")
        if not today_df.empty:
            p1 = today_df.iloc[0]["실제근무1"]
            p2 = today_df.iloc[0]["실제근무2"]
            st.markdown(f"### 👤 근무1: **{p1}** | 👤 근무2: **{p2}**")
        else:
            st.write("오늘 등록된 숙직 정보가 없습니다.")

    with col_card2:
        available_months = sorted(df["년월"].dropna().unique())
        current_ym = today.strftime("%Y-%m")
        default_idx = (
            available_months.index(current_ym)
            if current_ym in available_months
            else 0
        )

        selected_month = (
            st.selectbox("조회 월 선택", available_months, index=default_idx)
            if available_months
            else current_ym
        )

    st.markdown("---")

    st.subheader(f"🗓️ {selected_month} 숙직 근무 달력")

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
        
        # 일요일 시작(firstweekday=6) 달력 객체 생성
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)

        month_df = df[df["년월"] == selected_month].copy()
        duty_map = {}
        for _, row in month_df.iterrows():
            d_day = row["날짜"].day
            duty_map[d_day] = {
                "p1": row["실제근무1"],
                "p2": row["실제근무2"],
                "type": row["근무구분"],
                "date_obj": row["날짜"].date(),
            }

        # 일요일부터 시작하는 요일 헤더
        days_header = ["일", "월", "화", "수", "목", "금", "토"]
        cols = st.columns(7)
        for idx, day_name in enumerate(days_header):
            header_color = "🔴" if idx == 0 else ("🔵" if idx == 6 else "⚪")
            cols[idx].markdown(f"**{header_color} {day_name}**", unsafe_allow_html=True)

        # 7열 달력 주차별 렌더링
        for week in month_days:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                with week_cols[i]:
                    if day != 0:
                        curr_date = datetime.date(year, month, day)
                        duty_info = duty_map.get(day)
                        
                        is_today = (curr_date == today)
                        is_sunday = (i == 0)
                        is_saturday = (i == 6)
                        
                        # 대한민국 공휴일 체크
                        holiday_name = kr_holidays.get(curr_date)
                        is_holiday = holiday_name is not None

                        # 카드 배경 및 테두리 색상
                        if is_today:
                            bg_color = "#FFF3E0"
                            border_color = "#FF9800"
                        elif is_holiday or is_sunday:
                            bg_color = "#FFEBEE"
                            border_color = "#FFCDD2"
                        elif is_saturday:
                            bg_color = "#E3F2FD"
                            border_color = "#BBDEFB"
                        else:
                            bg_color = "#F9F9F9"
                            border_color = "#E0E0E0"

                        # 타이틀 텍스트 색상
                        if is_holiday or is_sunday:
                            title_color = "#D32F2F"
                        elif is_saturday:
                            title_color = "#1976D2"
                        else:
                            title_color = "#333333"

                        p1_text = duty_info["p1"] if duty_info else "-"
                        p2_text = duty_info["p2"] if duty_info else "-"
                        
                        title_label = f"{day}일"
                        if is_today:
                            title_label += " (오늘)"
                        elif is_holiday:
                            title_label += f" ({holiday_name})"

                        card_html = f"""
                        <div class="duty-card" style="
                            background-color: {bg_color};
                            border: 1.5px solid {border_color};
                        ">
                            <div class="duty-card-title" style="color: {title_color};">
                                {title_label}
                            </div>
                            <div class="duty-card-text">
                                <b>근무1:</b> {p1_text}<br>
                                <b>근무2:</b> {p2_text}
                            </div>
                        </div>
                        """
                        st.markdown(card_html, unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='min-height: 85px;'></div>", unsafe_allow_html=True)

        st.markdown("---")

        # 상세 목록
        st.markdown("#### 📋 상세 근무 목록")
        display_cols = [
            c for c in [
                "날짜", "근무구분", "근무자1", "근무자2",
                "대직1", "대직2", "실제근무1", "실제근무2"
            ] if c in month_df.columns
        ]

        st.dataframe(
            month_df[display_cols].style.highlight_between(
                left=pd.Timestamp(today),
                right=pd.Timestamp(today),
                subset=["날짜"],
                color="#FFE0B2",
            ),
            use_container_width=True,
        )

# ---------------------------------------------------------
# TAB 2: 시트 데이터 점검
# ---------------------------------------------------------
with tab_sheet:
    current_s = st.session_state.selected_sheet or "기본"
    st.subheader(f"🔍 시트 데이터 분석: [{current_s}]")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 등록 데이터(행)", f"{len(df)}건")
    m2.metric("인식된 컬럼 수", f"{len(df.columns)}개")
    m3.metric(
        "근무자1 지정률",
        f"{(df['근무자1'] != '미지정').mean() * 100:.1f}%" if "근무자1" in df.columns else "0%",
    )
    m4.metric(
        "대직 발생 수",
        f"{df['대직1'].notnull().sum() + df['대직2'].notnull().sum()}건"
        if "대직1" in df.columns and "대직2" in df.columns else "0건",
    )

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### ⚙️ 자동 인식 및 정제된 데이터")
        st.dataframe(df, height=350, use_container_width=True)

    with col_b:
        st.markdown("#### 📄 원본 시트 데이터 구조 (상단)")
        if not st.session_state.raw_df.empty:
            st.dataframe(
                st.session_state.raw_df.head(15),
                height=350,
                use_container_width=True,
            )
        else:
            st.info("원본 원천 데이터가 없습니다.")

# ---------------------------------------------------------
# TAB 3: 근무표 직접 수정
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 원본 데이터 직접 수정")
    st.caption("💡 대직 정보를 입력하면 `실제근무1`, `실제근무2`가 자동으로 반영됩니다.")

    edited_df = st.data_editor(
        st.session_state.df, num_rows="dynamic", key="data_editor"
    )

    if st.button("💾 변경사항 저장 및 반영"):
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df = edited_df.dropna(subset=["날짜"]).copy()
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
        st.success("변경사항이 성공적으로 저장되었습니다!")
        st.rerun()

# ---------------------------------------------------------
# TAB 4: 근무 통계
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 근무 통계")

    st.markdown("#### 👤 개인별 총 근무 횟수 (평일 / 주말)")
    workers_s1 = df[["실제근무1", "근무구분"]].rename(columns={"실제근무1": "근무자"})
    workers_s2 = df[["실제근무2", "근무구분"]].rename(columns={"실제근무2": "근무자"})
    all_workers_df = pd.concat([workers_s1, workers_s2])
    all_workers_df = all_workers_df[
        all_workers_df["근무자"].notnull()
        & (~all_workers_df["근무자"].isin(["미지정", "nan", "None"]))
    ]

    if not all_workers_df.empty:
        stats_df = (
            all_workers_df.groupby(["근무자", "근무구분"])
            .size()
            .unstack(fill_value=0)
        )
        st.bar_chart(stats_df)
    else:
        st.info("통계를 산출할 근무자 데이터가 존재하지 않습니다.")
