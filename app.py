import os
import calendar
import datetime
import gc
import glob
import io
import json
import hmac
import hashlib
import uuid
import requests
import pandas as pd
import streamlit as st
from pathlib import Path

# 대한민국 공휴일 라이브러리 예외 처리
try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# ---------------------------------------------------------
# 자동 메모리 및 로그 정제 함수
# ---------------------------------------------------------
def cleanup_memory_and_logs():
    if "memos" in st.session_state and isinstance(st.session_state.memos, dict):
        st.session_state.memos = {k: v for k, v in st.session_state.memos.items() if v and str(v).strip()}
    gc.collect()

cleanup_memory_and_logs()

os.makedirs("DATA", exist_ok=True)
os.makedirs("data", exist_ok=True)

CONFIG_PATH = os.path.join("DATA", "local_config.json")
PERSISTENCE_STATE_PATH = os.path.join("DATA", "edited_duty_schedule.json")

# ---------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="광주교도소 의료과 숙직근무",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

def load_local_config():
    default_config = {
        "auto_view_type": "🗓️ 이미지형 달력",
        "app_theme": "☀️ 화이트 테마", 
        "sms_api_key": "",
        "sms_api_secret": "",
        "sms_sender_phone": "",
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_config.update(saved)
        except Exception:
            pass
    return default_config

local_cfg = load_local_config()

for k, v in [
    ("is_app_closed", False),
    ("auto_view_type", local_cfg["auto_view_type"]),
    ("app_theme", local_cfg["app_theme"]),
    ("memos", {}),
]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.is_app_closed:
    st.title("👋 앱이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# 데이터 로드 함수
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def load_data():
    candidates = glob.glob(os.path.join("DATA", "*.xlsx")) + glob.glob(os.path.join("data", "*.xlsx")) + glob.glob("*.xlsx")
    valid_files = [f for f in candidates if not os.path.basename(f).startswith("~$")]
    file_path = valid_files[0] if valid_files else os.path.join("data", "숙직근무표.xlsx")
    
    if os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path)
            return df, file_path
        except Exception:
            pass
    
    # 기본 더미 데이터 생성 (파일이 없을 경우)
    dates = [pd.Timestamp.today().normalize() + pd.Timedelta(days=i) for i in range(30)]
    df = pd.DataFrame({
        "날짜": dates,
        "숙직자1": ["당직자A"] * 30,
        "숙직자2": ["당직자B"] * 30,
        "메모": [""] * 30
    })
    return df, file_path

df, current_file_path = load_data()

# 저장된 메모 불러오기
if os.path.exists(PERSISTENCE_STATE_PATH):
    try:
        with open(PERSISTENCE_STATE_PATH, "r", encoding="utf-8") as f:
            saved_memos = json.load(f)
            if isinstance(saved_memos, dict):
                st.session_state.memos.update(saved_memos)
    except Exception:
        pass

# ---------------------------------------------------------
# 시스템 CSS 스타일 적용
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"
theme_bg = "#FFFFFF" if not is_dark else "#121212"
main_text_color = "#1A1A1A" if not is_dark else "#E0E0E0"
border_color = "#E0E0E0" if not is_dark else "#333333"
box_bg = "#FFFFFF" if not is_dark else "#1E1E1E"
primary_blue = "#3B82F6"
table_header_bg = "#EDF2F7" if not is_dark else "#2C2C2C"

responsive_css = f"""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        font-family: Pretendard, -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    .main .block-container {{
        background-color: {theme_bg} !important;
        padding: 1rem 1rem 2rem 1rem !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    }}

    h1 {{
        font-size: 24px !important; margin: 10px 0px 20px 0px !important; font-weight: 800 !important;
        color: {main_text_color} !important; text-align: center;
        border-bottom: 3px solid {primary_blue} !important; padding-bottom: 10px !important;
    }}

    .cal-container {{ display: flex; flex-direction: column; width: 100%; border: 1px solid {border_color}; }}
    .cal-week-row {{ display: flex; border-bottom: 1px solid {border_color}; }}
    .cal-week-row:last-child {{ border-bottom: none; }}
    .cal-day-cell {{
        flex: 1; min-height: 100px; padding: 4px; border-right: 1px solid {border_color};
        display: flex; flex-direction: column; box-sizing: border-box; position: relative;
        background-color: {box_bg};
    }}
    .cal-day-cell:last-child {{ border-right: none; }}
    
    .cal-header-cell {{
        text-align: center; font-weight: 800; font-size: 12px; padding: 6px 0;
        border-bottom: 2px solid {main_text_color}; background-color: {table_header_bg};
    }}
    
    .cal-day-number {{
        font-size: 13px; font-weight: 900; text-align: right; display: block; margin-bottom: 2px;
    }}
    
    .text-sun {{ color: #EF4444 !important; }}
    .text-sat {{ color: #3B82F6 !important; }}
    .cal-header-cell.text-sun {{ background-color: #FEF2F2 !important; }}
    .cal-header-cell.text-sat {{ background-color: #EFF6FF !important; }}

    .cal-day-cell.is-today {{ background-color: #EFF6FF !important; border: 2px solid {primary_blue}; }}
    .cal-day-cell.is-today .cal-day-number {{ color: {primary_blue}; }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# 메인 UI 구성
# ---------------------------------------------------------
st.title("📋 광주교도소 의료과 숙직근무")

# 사이드바 메뉴
st.sidebar.header("⚙️ 메뉴 및 설정")
view_type = st.sidebar.radio(
    "보기 방식 선택", 
    ["🗓️ 이미지형 달력", "📋 표 형식", "✏️ 근무표 편집 및 메모"],
    index=0
)

# 1. 이미지형 달력 보기
if view_type == "🗓️ 이미지형 달력":
    col_y, col_m = st.sidebar.columns(2)
    today = datetime.date.today()
    year = col_y.selectbox("연도", range(2025, 2030), index=(today.year - 2025))
    month = col_m.selectbox("월", range(1, 13), index=(today.month - 1))
    
    st.markdown(f"<div style='text-align:center; font-size:20px; font-weight:800; margin:10px 0 20px 0;'>{year}년 {month}월 숙직 근무표</div>", unsafe_allow_html=True)
    
    cal = calendar.monthcalendar(year, month)
    
    # 날짜별 데이터 딕셔너리 매핑
    df_lookup = {}
    if "날짜" in df.columns:
        for _, r in df.iterrows():
            try:
                d_key = pd.to_datetime(r["날짜"]).strftime("%Y-%m-%d")
                df_lookup[d_key] = {
                    "w1": r.get("숙직자1", ""),
                    "w2": r.get("숙직자2", ""),
                    "memo": st.session_state.memos.get(d_key, r.get("메모", ""))
                }
            except Exception:
                pass

    html_content = '<div class="cal-container">'
    weekdays = [("일", "text-sun"), ("월", ""), ("화", ""), ("수", ""), ("목", ""), ("금", ""), ("토", "text-sat")]
    
    html_content += '<div class="cal-week-row">'
    for day_name, css_class in weekdays:
        html_content += f'<div class="cal-header-cell {css_class}" style="flex:1;">{day_name}</div>'
    html_content += '</div>'
    
    for week in cal:
        html_content += '<div class="cal-week-row">'
        for i, day in enumerate(week):
            if day == 0:
                html_content += '<div class="cal-day-cell" style="background-color: transparent;"></div>'
            else:
                d_str = f"{year}-{month:02d}-{day:02d}"
                d_obj = datetime.date(year, month, day)
                is_today = (d_obj == today)
                
                day_class = "is-today" if is_today else ""
                text_color_class = "text-sun" if i == 0 else ("text-sat" if i == 6 else "")
                
                duty_info = df_lookup.get(d_str, {"w1": "", "w2": "", "memo": ""})
                w1 = duty_info["w1"]
                w2 = duty_info["w2"]
                memo = duty_info["memo"]
                
                html_content += f'<div class="cal-day-cell {day_class}">'
                html_content += f'<span class="cal-day-number {text_color_class}">{day}</span>'
                if w1 or w2:
                    html_content += f'<div style="font-size:11px; font-weight:700; text-align:center; margin-top:4px; line-height:1.3;"><b>{w1}</b><br>{w2}</div>'
                if memo and str(memo).strip():
                    html_content += f'<div style="font-size:10px; font-weight:700; color:#D97706; text-align:center; margin-top:3px;">📌 {memo}</div>'
                html_content += '</div>'
        html_content += '</div>'
    html_content += '</div>'
    
    st.markdown(html_content, unsafe_allow_html=True)

# 2. 표 형식 보기
elif view_type == "📋 표 형식":
    st.subheader("📋 전체 숙직표 목록")
    if "날짜" in df.columns:
        display_df = df.copy()
        display_df["날짜"] = pd.to_datetime(display_df["날짜"]).dt.strftime("%Y-%m-%d")
        
        # 메모 실시간 반영
        memo_list = []
        for _, row in display_df.iterrows():
            d_str = row["날짜"]
            if d_str in st.session_state.memos:
                memo_list.append(st.session_state.memos[d_str])
            else:
                val = row.get("메모", "")
                memo_list.append("" if pd.isna(val) else val)
        display_df["메모"] = memo_list

        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("표시할 데이터가 없습니다.")

# 3. 근무표 편집 및 메모 관리
else:
    st.subheader("✏️ 날짜별 메모 및 관리")
    st.info("특정 날짜를 선택하여 메모를 추가하거나 수정할 수 있습니다.")
    
    selected_date = st.date_input("수정할 날짜 선택", datetime.date.today())
    d_str = selected_date.strftime("%Y-%m-%d")
    
    current_memo = st.session_state.memos.get(d_str, "")
    new_memo = st.text_input("해당일 메모 입력", value=current_memo)
    
    if st.button("메모 저장하기", type="primary"):
        st.session_state.memos[d_str] = new_memo
        with open(PERSISTENCE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(st.session_state.memos, f, ensure_ascii=False, indent=2)
        st.success(f"[{d_str}] 메모가 성공적으로 저장되었습니다!")
        st.rerun()
