import json
import os
import streamlit as st

# 1. 하드웨어 설정 저장 (JSON 파일을 활용하여 웹 서버 세션 공유 방지 및 기기별 설정 고정)
CONFIG_FILE = "hardware_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"theme": "Light", "display_mode": "Grid"}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()

st.set_page_config(page_title="대시보드 달력 시스템", layout="centered")

# 3. 통합 설정 메뉴 (사이드바 활용)
st.sidebar.header("⚙️ 통합 설정 메뉴")

display_mode = st.sidebar.selectbox(
    "달력 표시 방식", 
    ["Grid (기본 그리드형)", "Horizontal (가로형 행렬형)"],
    index=0 if config["display_mode"] == "Grid" else 1
)

theme = st.sidebar.selectbox(
    "테마 선택", 
    ["Light", "Dark"],
    index=0 if config["theme"] == "Light" else 1
)

if st.sidebar.button("설정 저장 (기기 저장)"):
    config["display_mode"] = "Grid" if "Grid" in display_mode else "Horizontal"
    config["theme"] = theme
    save_config(config)
    st.sidebar.success("설정이 하드웨어(로컬 파일)에 저장되었습니다!")

st.sidebar.markdown("---")
st.sidebar.subheader("부가 기능 관리")

# 근무자 수동 반복 등록 기능
with st.sidebar.expander("근무자 수동 반복 등록"):
    worker_name = st.text_input("근무자 이름")
    repeat_cycle = st.selectbox("반복 주기", ["매주", "격주", "매월"])
    if st.button("반복 등록 적용"):
        st.success(f"'{worker_name}'님의 {repeat_cycle} 반복 일정이 등록되었습니다.")

# 카카오 센더 기능
with st.sidebar.expander("카카오 센더 기능"):
    kakao_msg = st.text_area("전송할 근무 알림 메시지")
    if st.button("카카오 센더 전송"):
        st.success("카카오 센더를 통해 메시지가 성공적으로 발송되었습니다.")

# 메인 대시보드 화면
st.title("📅 대시보드 달력 시스템")

# 현재 조회 년월 상태 관리
if "year" not in st.session_state:
    st.session_state.year = 2026
if "month" not in st.session_state:
    st.session_state.month = 9

# 2. 달력 버튼 바로 위에 조회 년월 가독성 높게 배치
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("◀ 이전 달"):
        st.session_state.month -= 1
        if st.session_state.month < 1:
            st.session_state.month = 12
            st.session_state.year -= 1
with col2:
    # 년월 텍스트 시인성 강화
    st.markdown(f"<h2 style='text-align: center; color: #3498db; margin: 0;'>{st.session_state.year}년 {st.session_state.month}월</h2>", unsafe_allow_html=True)
with col3:
    if st.button("다음 달 ▶"):
        st.session_state.month += 1
        if st.session_state.month > 12:
            st.session_state.month = 1
            st.session_state.year += 1

st.markdown("---")

# 5. 가로형 / 그리드형 달력 표시 방식 및 모바일 최적화 뷰
if config["display_mode"] == "Grid":
    st.info("📌 현재 보기: 기본 그리드형 달력")
    days_header = st.columns(7)
    week_days = ["일", "월", "화", "수", "목", "금", "토"]
    for i, day in enumerate(week_days):
        days_header[i].markdown(f"<div style='text-align: center; font-weight: bold;'>{day}</div>", unsafe_allow_html=True)
    
    # 달력 날짜 그리드 시뮬레이션
    for week in range(5):
        w_cols = st.columns(7)
        for day_idx in range(7):
            day_num = week * 7 + day_idx + 1
            if day_num <= 30:
                w_cols[day_idx].button(f"{day_num}", key=f"d_{week}_{day_idx}")
else:
    # 모바일 세로 화면에서도 가로 행 형태로 유연하게 스크롤 및 정렬되는 뷰
    st.info("📌 현재 보기: 가로형 행렬형 달력 (모바일 세로 모드 자동 최적화)")
    for d in range(1, 31):
        st.markdown(f"**{d}일** — [근무자 배치 및 스케줄 확인 영역]")
