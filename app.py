import calendar
import datetime
import re
import pandas as pd
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="숙직 근무표 대시보드", layout="wide")


# ---------------------------------------------------------
# 1. 고도화된 엑셀 스마트 로더 (숙직근무자 시트 자동 인식)
# ---------------------------------------------------------
def load_excel_smart(file, selected_sheet=None):
    excel_file = pd.ExcelFile(file)
    sheet_names = excel_file.sheet_names

    # 1. 대상 시트 자동 찾기 ('숙직' 키워드 포함 시트 우선, 없으면 첫 번째 시트)
    target_sheet = selected_sheet
    if not target_sheet:
        duty_sheets = [s for s in sheet_names if "숙직" in s or "근무" in s]
        target_sheet = duty_sheets[0] if duty_sheets else sheet_names[0]

    # 시트 전체를 헤더 없이 일단 읽어옴 (최대 30행 스캔)
    df_raw = pd.read_excel(file, sheet_name=target_sheet, header=None)

    # 2. 날짜 데이터가 실제로 시작되는 표 헤더 위치 탐색
    header_idx = None
    for idx in range(min(25, len(df_raw))):
        row_values = [str(val).strip() for val in df_raw.iloc[idx].values]
        row_str = " ".join(row_values)

        # 날짜/일자 및 근무자 관련 핵심 키워드 체크
        if any(
            k in row_str for k in ["날짜", "일자", "근무일", "Date", "근무자"]
        ):
            header_idx = idx
            break

    if header_idx is None:
        header_idx = 0

    # 헤더 위치 기준으로 데이터 다시 읽기
    df = pd.read_excel(file, sheet_name=target_sheet, header=header_idx)

    # 컬럼명 정제 (줄바꿈 제거, 공백 제거, Unnamed 제거)
    clean_cols = []
    for i, col in enumerate(df.columns):
        c_str = (
            str(col)
            .replace("\n", "")
            .replace("\r", "")
            .strip()
            if not str(col).startswith("Unnamed")
            else f"열_{i}"
        )
        clean_cols.append(c_str)
    df.columns = clean_cols

    # 3. 날짜 컬럼 자동 인식
    date_col = None
    for col in df.columns:
        if any(
            k in col.lower()
            for k in ["날짜", "일자", "근무일", "date", "일자/요일"]
        ):
            date_col = col
            break

    if date_col:
        df.rename(columns={date_col: "날짜"}, inplace=True)
    else:
        # 첫 번째 열이 날짜일 가능성이 높음
        df.rename(columns={df.columns[0]: "날짜"}, inplace=True)

    # 날짜 데이터 정제 (숫자만 있거나 문자가 섞인 날짜도 파싱)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    # 4. 근무자 및 대직 컬럼 유연하게 정기 매핑
    # (예: 근무자1, 1근무자, 숙직1, 당직1, 대직자1 등 모두 대응)
    cols = list(df.columns)

    p1_col = next(
        (
            c
            for c in cols
            if any(
                k in c
                for k in ["근무자1", "근무자 1", "1근무", "숙직1", "당직1"]
            )
            and "대직" not in c
        ),
        None,
    )
    p2_col = next(
        (
            c
            for c in cols
            if any(
                k in c
                for k in ["근무자2", "근무자 2", "2근무", "숙직2", "당직2"]
            )
            and "대직" not in c
        ),
        None,
    )

    sub1_col = next(
        (
            c
            for c in cols
            if any(k in c for k in ["대직1", "대직자1", "대직 1", "대직자"])
        ),
        None,
    )
    sub2_col = next(
        (
            c
            for c in cols
            if any(k in c for k in ["대직2", "대직자2", "대직 2"])
        ),
        None,
    )

    # 매핑 적용
    if p1_col:
        df.rename(columns={p1_col: "근무자1"}, inplace=True)
    else:
        if "근무자1" not in df.columns:
            df["근무자1"] = "미지정"

    if p2_col:
        df.rename(columns={p2_col: "근무자2"}, inplace=True)
    else:
        if "근무자2" not in df.columns:
            df["근무자2"] = "미지정"

    if sub1_col:
        df.rename(columns={sub1_col: "대직1"}, inplace=True)
    else:
        if "대직1" not in df.columns:
            df["대직1"] = None

    if sub2_col:
        df.rename(columns={sub2_col: "대직2"}, inplace=True)
    else:
        if "대직2" not in df.columns:
            df["대직2"] = None

    # 근무구분(평일/주말) 컬럼
    type_col = next(
        (
            c
            for c in cols
            if any(k in c for k in ["구분", "근무구분", "요일", "비고"])
        ),
        None,
    )
    if type_col and type_col != "날짜":
        df.rename(columns={type_col: "근무구분"}, inplace=True)
    else:
        df["근무구분"] = df["날짜"].dt.weekday.map(
            lambda x: "주말" if x >= 5 else "평일"
        )

    # 5. 데이터 정돈 및 실제근무자 산출
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    # 대직자가 입력되어 있으면 대직자 우선 적용
    df["실제근무1"] = (
        df["대직1"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace(["", "nan", "None"], None)
        .combine_first(df["근무자1"])
        .fillna("미지정")
    )

    df["실제근무2"] = (
        df["대직2"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace(["", "nan", "None"], None)
        .combine_first(df["근무자2"])
        .fillna("미지정")
    )

    return df, target_sheet, sheet_names


# 샘플 데이터 생성
@st.cache_data
def get_sample_data():
    today = datetime.date.today()
    start_date = today.replace(day=1)
    dates = pd.date_range(start=start_date, periods=35, freq="D")

    df = pd.DataFrame({
        "날짜": dates,
        "근무구분": ["평일" if d.weekday() < 5 else "주말" for d in dates],
        "근무자1": ["홍길동"] * 35,
        "근무자2": ["김철수"] * 35,
        "대직1": [None if i % 4 != 0 else "이대직" for i in range(35)],
        "대직2": [None] * 35,
    })
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")
    df["실제근무1"] = (
        df["대직1"].fillna("").replace("", None).combine_first(df["근무자1"])
    )
    df["실제근무2"] = (
        df["대직2"].fillna("").replace("", None).combine_first(df["근무자2"])
    )
    return df


# 세션 상태 초기화
if "df" not in st.session_state:
    st.session_state.df = get_sample_data()

df = st.session_state.df

# ---------------------------------------------------------
# 사이드바: 파일 업로드 및 시트 선택
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 데이터 파일 관리")
    uploaded_file = st.file_uploader("엑셀(.xlsx) 파일 업로드", type=["xlsx"])

    if uploaded_file:
        try:
            excel_file = pd.ExcelFile(uploaded_file)
            sheets = excel_file.sheet_names

            # 시트 선택 옵션 제공
            selected_sheet = st.selectbox(
                "📌 불러올 시트 선택",
                sheets,
                index=0,
                help="'숙직' 관련 시트가 자동으로 선택됩니다.",
            )

            if st.button("🔄 선택한 시트 로드"):
                parsed_df, used_sheet, _ = load_excel_smart(
                    uploaded_file, selected_sheet
                )
                st.session_state.df = parsed_df
                st.success(
                    f"✅ '{used_sheet}' 시트 데이터가 성공적으로 로드되었습니다!"
                )
                st.rerun()

        except Exception as e:
            st.error(f"❌ 파일 처리 오류: {e}")

# ---------------------------------------------------------
# 메인 화면 구성
# ---------------------------------------------------------
st.title("📋 숙직 근무표 통합 대시보드")

tab1, tab2, tab3 = st.tabs(
    ["📅 달력 메인 화면", "✏️ 근무표 수정", "📊 근무 통계"]
)

today = datetime.date.today()

with tab1:
    st.subheader("📅 오늘 기준 숙직 근무 현황")

    today_df = df[df["날짜"].dt.date == today]

    col_card1, col_card2 = st.columns(2)
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

        selected_month = st.selectbox(
            "조회 월 선택", available_months, index=default_idx
        )

    st.markdown("---")

    # 월간 달력 형태 출력 (7열 그리드 레이아웃)
    st.subheader(f"🗓️ {selected_month} 숙직 근무 달력")

    year, month = map(int, selected_month.split("-"))
    cal = calendar.monthcalendar(year, month)

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

    # 요일 헤더 표시
    days_header = ["월", "화", "수", "목", "금", "토", "일"]
    cols = st.columns(7)
    for idx, day_name in enumerate(days_header):
        header_color = "🔴" if idx == 6 else ("🔵" if idx == 5 else "⚪")
        cols[idx].markdown(
            f"**{header_color} {day_name}**", unsafe_allow_html=True
        )

    # 주별/일별 달력 그리드 생성
    for week in cal:
        week_cols = st.columns(7)
        for i, day in enumerate(week):
            with week_cols[i]:
                if day != 0:
                    duty_info = duty_map.get(day)

                    is_today = (
                        duty_info and duty_info["date_obj"] == today
                    )
                    bg_color = "#FFF3E0" if is_today else "#F9F9F9"
                    border_color = "#FF9800" if is_today else "#E0E0E0"

                    p1_text = duty_info["p1"] if duty_info else "-"
                    p2_text = duty_info["p2"] if duty_info else "-"

                    card_html = f"""
                    <div style="
                        background-color: {bg_color};
                        border: 2px solid {border_color};
                        border-radius: 8px;
                        padding: 8px;
                        margin-bottom: 8px;
                        min-height: 95px;
                    ">
                        <div style="font-weight: bold; font-size: 14px; color: {'#D32F2F' if i == 6 else ('#1976D2' if i == 5 else '#333')};">
                            {day}일 {'(오늘)' if is_today else ''}
                        </div>
                        <div style="font-size: 12px; margin-top: 4px; color: #333;">
                            <b>1:</b> {p1_text}<br>
                            <b>2:</b> {p2_text}
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div style='min-height: 95px;'></div>",
                        unsafe_allow_html=True,
                    )

    st.markdown("---")

    # 상세 데이터 목록
    st.markdown("#### 📋 상세 근무 목록")
    display_cols = [
        c
        for c in [
            "날짜",
            "근무구분",
            "근무자1",
            "근무자2",
            "대직1",
            "대직2",
            "실제근무1",
            "실제근무2",
        ]
        if c in month_df.columns
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

with tab2:
    st.subheader("✏️ 원본 데이터 직접 수정")
    st.caption(
        "💡 대직 정보를 입력하면 `실제근무1`, `실제근무2`가 자동으로 반영됩니다."
    )

    edited_df = st.data_editor(
        st.session_state.df, num_rows="dynamic", key="data_editor"
    )

    if st.button("💾 변경사항 저장 및 반영"):
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df["년월"] = edited_df["날짜"].dt.strftime("%Y-%m")
        edited_df["실제근무1"] = (
            edited_df["대직1"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자1"])
        )
        edited_df["실제근무2"] = (
            edited_df["대직2"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자2"])
        )
        st.session_state.df = edited_df
        st.success("변경사항이 성공적으로 저장되었습니다!")
        st.rerun()

with tab3:
    st.subheader("📊 근무 통계")

    st.markdown("#### 👤 개인별 총 근무 횟수")
    workers_s1 = df[["실제근무1", "근무구분"]].rename(
        columns={"실제근무1": "근무자"}
    )
    workers_s2 = df[["실제근무2", "근무구분"]].rename(
        columns={"실제근무2": "근무자"}
    )
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
