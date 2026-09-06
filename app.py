import calendar
import datetime
import pandas as pd
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="숙직 근무표 대시보드", layout="wide")

# ---------------------------------------------------------
# 1. 엑셀 스마트 로더 (헤더 위치 및 날짜 컬럼 자동 인식)
# ---------------------------------------------------------
def load_excel_smart(file):
    # 상단 10행 탐색 후 데이터 헤더 위치 결정
    df_raw = pd.read_excel(file, header=None, nrows=10)
    
    header_idx = 0
    for idx, row in df_raw.iterrows():
        row_str = row.astype(str).str.cat()
        if any(k in row_str for k in ["날짜", "일자", "근무일", "Date", "근무자"]):
            header_idx = idx
            break
            
    df = pd.read_excel(file, header=header_idx)
    df.columns = df.columns.astype(str).str.strip()
    
    # 날짜 컬럼 자동 인식
    date_col = None
    for col in df.columns:
        if any(k in col.lower() for k in ["날짜", "일자", "근무일", "date"]):
            date_col = col
            break
            
    if date_col:
        df.rename(columns={date_col: "날짜"}, inplace=True)
    else:
        df.rename(columns={df.columns[0]: "날짜"}, inplace=True)
        
    # 근무자 및 대직 컬럼 자동 정렬
    for target, alt in [("근무자1", "근무자"), ("근무자2", "근무자.1")]:
        if target not in df.columns:
            matching = [c for c in df.columns if target in c or alt in c]
            if matching:
                df.rename(columns={matching[0]: target}, inplace=True)
            else:
                df[target] = None
                
    for col in ["대직1", "대직2", "근무구분"]:
        if col not in df.columns:
            df[col] = None

    # 날짜 데이터 정제
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])
    
    # 실제근무자1, 2 자동 계산 (대직자 우선)
    df["실제근무1"] = df["대직1"].fillna("").replace("", None).combine_first(df["근무자1"]).fillna("미지정")
    df["실제근무2"] = df["대직2"].fillna("").replace("", None).combine_first(df["근무자2"]).fillna("미지정")
    
    if "근무구분" not in df.columns or df["근무구분"].isnull().all():
        df["근무구분"] = df["날짜"].dt.weekday.map(lambda x: "주말" if x >= 5 else "평일")

    return df

# 기본 샘플 데이터 생성
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
    df["실제근무1"] = df["대직1"].fillna("").replace("", None).combine_first(df["근무자1"])
    df["실제근무2"] = df["대직2"].fillna("").replace("", None).combine_first(df["근무자2"])
    return df

# 세션 상태 초기화
if "df" not in st.session_state:
    st.session_state.df = get_sample_data()

df = st.session_state.df

# ---------------------------------------------------------
# 사이드바: 파일 업로드
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 데이터 파일 관리")
    uploaded_file = st.file_uploader("엑셀(.xlsx) 파일 업로드", type=["xlsx"])
    
    if uploaded_file:
        try:
            parsed_df = load_excel_smart(uploaded_file)
            st.session_state.df = parsed_df
            st.success("✅ 엑셀 데이터가 정상 로드되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 파일 처리 오류: {e}")

# ---------------------------------------------------------
# 메인 화면 구성
# ---------------------------------------------------------
st.title("📋 숙직 근무표 통합 대시보드")

tab1, tab2, tab3 = st.tabs(["📅 달력 메인 화면", "✏️ 근무표 수정", "📊 근무 통계"])

today = datetime.date.today()

with tab1:
    st.subheader("📅 오늘 기준 숙직 근무 현황")
    
    # 1. 상단 카드 (오늘 날짜 실제 근무자)
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
        df["년월"] = df["날짜"].dt.strftime("%Y-%m")
        available_months = sorted(df["년월"].unique())
        
        current_ym = today.strftime("%Y-%m")
        default_idx = available_months.index(current_ym) if current_ym in available_months else 0
        
        selected_month = st.selectbox("조회 월 선택", available_months, index=default_idx)

    st.markdown("---")
    
    # 2. 월간 달력 형태 출력 (7열 그리드 레이아웃)
    st.subheader(f"🗓️ {selected_month} 숙직 근무 달력")
    
    # 선택 월 연/월 추출
    year, month = map(int, selected_month.split("-"))
    cal = calendar.monthcalendar(year, month)
    
    # 월 데이터 사전 매핑 (날짜 -> 데이터)
    month_df = df[df["년월"] == selected_month].copy()
    duty_map = {}
    for _, row in month_df.iterrows():
        d_day = row["날짜"].day
        duty_map[d_day] = {
            "p1": row["실제근무1"],
            "p2": row["실제근무2"],
            "type": row["근무구분"],
            "date_obj": row["날짜"].date()
        }

    # 요일 헤더 표시
    days_header = ["월", "화", "수", "목", "금", "토", "일"]
    cols = st.columns(7)
    for idx, day_name in enumerate(days_header):
        header_color = "🔴" if idx == 6 else ("🔵" if idx == 5 else "⚪")
        cols[idx].markdown(f"**{header_color} {day_name}**", unsafe_allow_html=True)

    # 주별/일별 달력 그리드 생성
    for week in cal:
        week_cols = st.columns(7)
        for i, day in enumerate(week):
            with week_cols[i]:
                if day != 0:
                    duty_info = duty_map.get(day)
                    
                    # 오늘 날짜 및 스타일 설정
                    is_today = (duty_info and duty_info["date_obj"] == today)
                    bg_color = "#FFF3E0" if is_today else "#F5F5F5"
                    border_color = "#FF9800" if is_today else "#E0E0E0"
                    
                    p1_text = duty_info['p1'] if duty_info else '-'
                    p2_text = duty_info['p2'] if duty_info else '-'
                    
                    # 달력 카드 HTML
                    card_html = f"""
                    <div style="
                        background-color: {bg_color};
                        border: 2px solid {border_color};
                        border-radius: 8px;
                        padding: 8px;
                        margin-bottom: 8px;
                        min-height: 90px;
                    ">
                        <div style="font-weight: bold; font-size: 14px; color: {'#D32F2F' if i >= 5 else '#333'};">
                            {day}일 {'(오늘)' if is_today else ''}
                        </div>
                        <div style="font-size: 12px; margin-top: 4px; color: #1565C0;">
                            <b>1:</b> {p1_text}<br>
                            <b>2:</b> {p2_text}
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                else:
                    st.markdown("<div style='min-height: 90px;'></div>", unsafe_allow_html=True)

    st.markdown("---")
    
    # 3. 데이터 테이블 요약
    st.markdown("#### 📋 상세 근무 목록")
    display_cols = [c for c in ["날짜", "근무구분", "근무자1", "근무자2", "대직1", "대직2", "실제근무1", "실제근무2"] if c in month_df.columns]
    
    st.dataframe(
        month_df[display_cols].style.highlight_between(
            left=pd.Timestamp(today), 
            right=pd.Timestamp(today), 
            subset=["날짜"], 
            color="#FFE0B2"
        ),
        use_container_width=True
    )

with tab2:
    st.subheader("✏️ 원본 데이터 직접 수정")
    st.caption("💡 대직 정보를 입력하면 `실제근무1`, `실제근무2`가 자동으로 반영됩니다.")
    
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", key="data_editor")
    
    if st.button("💾 변경사항 저장 및 반영"):
        edited_df["실제근무1"] = edited_df["대직1"].fillna("").replace("", None).combine_first(edited_df["근무자1"])
        edited_df["실제근무2"] = edited_df["대직2"].fillna("").replace("", None).combine_first(edited_df["근무자2"])
        st.session_state.df = edited_df
        st.success("변경사항이 성공적으로 저장되었습니다!")
        st.rerun()

with tab3:
    st.subheader("📊 근무 통계")
    all_workers = pd.concat([df["실제근무1"], df["실제근무2"]]).value_counts().reset_index()
    all_workers.columns = ["근무자", "근무 횟수"]
    st.bar_chart(all_workers.set_index("근무자"))