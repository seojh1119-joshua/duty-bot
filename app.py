import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="숙직 근무표 대시보드", layout="wide")

# 1. 데이터 로드 및 전처리 함수
@st.cache_data
def load_data():
    # 데이터 로드 예시 (실제 엑셀 로드 파일 경로 또는 session_state 적용)
    # df = pd.read_excel("duty_schedule.xlsx")
    
    # 예시 데이터 구조 생성
    data = {
        "날짜": pd.date_range(start="2026-09-01", periods=30, freq="D"),
        "근무구분": ["평일" if d.weekday() < 5 else "주말" for d in pd.date_range("2026-09-01", periods=30)],
        "근무자1": ["홍길동"] * 30,
        "근무자2": ["김철수"] * 30,
        "대직1": [None if i % 5 != 0 else "이대직" for i in range(30)],
        "대직2": [None] * 30,
    }
    df = pd.DataFrame(data)
    
    # 실제근무1, 실제근무2 계산 (대직이 있으면 대직자, 없으면 원래 근무자)
    df["날짜"] = pd.to_datetime(df["날짜"])
    df["실제근무1"] = df["대직1"].fillna("").replace("", None).combine_first(df["근무자1"])
    df["실제근무2"] = df["대직2"].fillna("").replace("", None).combine_first(df["근무자2"])
    
    return df

# 데이터 가져오기
if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

# ---------------------------------------------------------
# 사이드바: 파일 업로드
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 데이터 파일 관리")
    uploaded_file = st.file_uploader("엑셀(.xlsx) 파일 업로드", type=["xlsx"])
    if uploaded_file:
        raw_df = pd.read_excel(uploaded_file)
        raw_df["날짜"] = pd.to_datetime(raw_df["날짜"])
        raw_df["실제근무1"] = raw_df["대직1"].fillna("").replace("", None).combine_first(raw_df["근무자1"])
        raw_df["실제근무2"] = raw_df["대직2"].fillna("").replace("", None).combine_first(raw_df["근무자2"])
        st.session_state.df = raw_df
        st.success("파일이 성공적으로 로드되었습니다!")

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
st.title("📋 숙직 근무표 통합 대시보드")

tab1, tab2, tab3 = st.tabs(["📅 근무 일정 확인 (달력 메인)", "✏️ 근무표 수정", "📊 근무 통계"])

# 오늘 날짜 확인
today = datetime.date.today()

with tab1:
    st.subheader("📅 오늘 기준 숙직 근무 현황")
    
    # 1. 오늘 & 당주 근무자 하이라이트 카드로 표시
    today_df = df[df["날짜"].dt.date == today]
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📌 **오늘 날짜 ({today.strftime('%Y-%m-%d')}) 실제 근무자**")
        if not today_df.empty:
            p1 = today_df.iloc[0]["실제근무1"]
            p2 = today_df.iloc[0]["실제근무2"]
            st.markdown(f"### 👤 근무자1: **{p1}** | 👤 근무자2: **{p2}**")
        else:
            st.write("오늘 등록된 숙직 근무 정보가 없습니다.")
            
    with col2:
        # 월 선택 필터 (기본값: 오늘 날짜가 속한 년-월)
        df["년월"] = df["날짜"].dt.strftime("%Y-%m")
        available_months = sorted(df["년월"].unique())
        default_month_idx = available_months.index(today.strftime("%Y-%m")) if today.strftime("%Y-%m") in available_months else 0
        
        selected_month = st.selectbox("조회 월 선택", available_months, index=default_month_idx)

    st.markdown("---")
    
    # 2. 달력 형태(Grid/Chart) 시각화
    month_df = df[df["년월"] == selected_month].copy()
    month_df["일자"] = month_df["날짜"].dt.day
    month_df["요일"] = month_df["날짜"].dt.day_name()
    month_df["근무내용"] = month_df["실제근무1"] + ", " + month_df["실제근무2"]
    
    st.subheader(f"🗓️ {selected_month} 숙직 근무 달력")
    
    # Plotly 기반의 간트/타임라인 스타일 달력 뷰
    fig = px.timeline(
        month_df,
        x_start="날짜",
        x_end=month_df["날짜"] + pd.Timedelta(days=1),
        y="근무내용",
        color="근무구분",
        text="근무내용",
        title=f"{selected_month} 근무 현황 (오늘 포함)",
        labels={"근무내용": "실제근무자 1, 2"}
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_range=[month_df["날짜"].min(), month_df["날짜"].max()])
    st.plotly_chart(fig, use_container_width=True)
    
    # 테이블 형태 월간 달력 요약
    st.markdown("#### 📋 월간 실제 근무자 목록")
    display_df = month_df[["날짜", "근무구분", "근무자1", "근무자2", "대직1", "대직2", "실제근무1", "실제근무2"]]
    st.dataframe(
        display_df.style.highlight_between(
            left=pd.Timestamp(today), 
            right=pd.Timestamp(today), 
            subset=["날짜"], 
            color="#ffe0b2"
        ),
        use_container_width=True
    )

with tab2:
    st.subheader("✏️ 원본 데이터 직접 수정")
    st.caption("💡 셀 내용을 수정한 후 아래 [💾 변경사항 저장 및 반영] 버튼을 누르세요.")
    
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", key="data_editor")
    
    if st.button("💾 변경사항 저장 및 반영"):
        # 수정된 내용에서 실제근무1, 2 재계산
        edited_df["실제근무1"] = edited_df["대직1"].fillna("").replace("", None).combine_first(edited_df["근무자1"])
        edited_df["실제근무2"] = edited_df["대직2"].fillna("").replace("", None).combine_first(edited_df["근무자2"])
        
        st.session_state.df = edited_df
        st.success("변경사항이 성공적으로 저장되었습니다!")
        st.rerun()

with tab3:
    st.subheader("📊 근무 통계")
    st.write("실제 근무자 기준 개인별 숙직 횟수 통계입니다.")
    
    all_workers = pd.concat([df["실제근무1"], df["실제근무2"]]).value_counts().reset_index()
    all_workers.columns = ["근무자", "근무 횟수"]
    
    st.bar_chart(all_workers.set_index("근무자"))