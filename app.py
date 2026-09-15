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
import streamlit.components.v1 as components
import altair as alt
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

PERSISTENCE_STATE_PATH = os.path.join("DATA", "edited_duty_schedule.json")
CONFIG_PATH = os.path.join("DATA", "local_config.json")
WORKERS_DB_FILE = Path("data/workers_db.json")

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
        "auto_view_type": "🗓️ 가로형 Grid", # 기본값 유지하나 코드 내에서 이미지형으로 강제 변환 예정
        "app_theme": "☀️ 화이트 테마", 
        "sms_api_key": "",
        "sms_api_secret": "",
        "sms_sender_phone": "",
        "batch_start_date": str(datetime.date.today()),
        "batch_infinite": False,
        "batch_days_c": 30,
        "batch_i1": 3,
        "batch_w1_names": ["", "", ""],
        "batch_i2": 3,
        "batch_w2_names": ["", "", ""]
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_config.update(saved)
        except Exception as e:
            st.sidebar.warning(f"⚠️ 설정 로드 실패: {e}")
    return default_config

def save_local_config(key, value):
    config = load_local_config()
    config[key] = value
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.sidebar.warning(f"⚠️ 설정 저장 실패: {e}")

local_cfg = load_local_config()

for k, v in [
    ("is_app_closed", False), ("show_settings_dialog", False), ("show_exit_dialog", False),
    ("auto_view_type", "🗓️ 이미지형 달력"), # 강제 초기화
    ("app_theme", local_cfg["app_theme"]),
    ("sms_api_key", local_cfg.get("sms_api_key", "")),
    ("sms_api_secret", local_cfg.get("sms_api_secret", "")),
    ("sms_sender_phone", local_cfg.get("sms_sender_phone", "")),
    ("uploader_key", 0), ("upload_success_msg", "")
]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.is_app_closed:
    st.title("👋 앱이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# 시스템 CSS 및 자바스크립트 적용
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#121212" if is_dark else "#FFFFFF" # 배경 흰색 고정
main_text_color = "#E0E0E0" if is_dark else "#1A1A1A"
border_color = "#333333" if is_dark else "#E0E0E0"
btn_bg = "#1E1E1E" if is_dark else "#FFFFFF"
btn_text = "#E0E0E0" if is_dark else "#2D3748"
btn_hover_bg = "#2C2C2C" if is_dark else "#EDF2F7"
btn_hover_border = "#3B82F6" if is_dark else "#CBD5E0"
sidebar_bg = "#181818" if is_dark else "#FFFFFF"
dialog_bg = "#1E1E1E" if is_dark else "#FFFFFF"
input_bg = "#272727" if is_dark else "#FFFFFF"
input_text = "#F5F5F5" if is_dark else "#1E1E1E"
box_bg = "#1E1E1E" if is_dark else "#FFFFFF"
primary_blue = "#3B82F6"
table_header_bg = "#2C2C2C" if is_dark else "#EDF2F7"

responsive_css = f"""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    [data-testid="stSidebarNav"] {{ z-index: 100000 !important; }}
    [data-testid="collapsedControl"] {{ z-index: 99999 !important; top: 5px !important; }}
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        font-family: Pretendard, -apple-system, BlinkMacSystemFont, sans-serif !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }}

    .main .block-container {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        padding: 1rem 1rem 2rem 1rem !important; /* 패딩 조정 */
        max-width: 700px !important;
        margin: 0 auto !important;
        box-sizing: border-box !important;
    }}

    h1 {{
        font-size: 24px !important;
        margin: 10px 0px 20px 0px !important;
        font-weight: 800 !important;
        color: {main_text_color} !important;
        text-align: center;
        border-bottom: 3px solid {primary_blue} !important;
        padding-bottom: 10px !important;
    }}

    .setting-box {{
        background-color: {box_bg} !important;
        border: 1px solid {primary_blue} !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        margin: 8px 0px 12px 0px !important;
    }}

    .today-card {{
        background: linear-gradient(135deg, {primary_blue}, #2563EB) !important;
        color: #FFFFFF !important;
        padding: 16px 20px !important;
        border-radius: 16px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
    }}
    .today-card .today-title {{ font-size: 14px !important; font-weight: 800 !important; margin-bottom: 6px !important; color: #E0E7FF !important; }}
    .today-card .today-content {{ font-size: 18px !important; font-weight: 800 !important; line-height: 1.4 !important; }}
    .today-card span {{ color: #FEF08A !important; font-weight: 900 !important; }}

    .month-header {{
        font-size: 20px !important; font-weight: 800 !important; color: {main_text_color} !important;
        text-align: center; margin: 10px 0 20px 0 !important;
    }}

    /* 이미지형 달력 스타일 */
    .cal-week-row {{
        display: flex; border-bottom: 1px solid {border_color};
    }}
    .cal-week-row:first-child {{
        border-top: 2px solid {main_text_color}; /* 최상단 굵은 선 */
    }}
    .cal-day-cell {{
        flex: 1; min-height: 80px; padding: 4px; border-right: 1px solid {border_color};
        display: flex; flex-direction: column; box-sizing: border-box;
        position: relative;
    }}
    .cal-day-cell:last-child {{ border-right: none; }}
    
    /* 주말/공휴일 헤더 셀 배경색 */
    .cal-header-cell {{
        text-align: center; font-weight: 800; font-size: 13px; padding: 6px 0;
        border-bottom: 2px solid {main_text_color};
    }}
    
    .cal-day-number {{
        font-size: 14px; font-weight: 900; text-align: right; margin-bottom: 4px;
        display: block;
    }}
    /* 오늘 날짜 표시 */
    .cal-day-cell.is-today {{
        background-color: #EFF6FF !important; border: 2px solid {primary_blue};
        border-radius: 8px; margin: -1px; /* 테두리 침범 방지 */
    }}
    .cal-day-cell.is-today .cal-day-number {{ color: {primary_blue}; }}

    /* 근무자 텍스트 */
    .cal-duty-text {{
        font-size: 11px !important; font-weight: 600 !important; line-height: 1.3 !important;
        text-align: center; margin-top: auto; margin-bottom: auto;
        color: {main_text_color} !important;
    }}
    /* 대직 표시 (괄호) */
    .cal-sub-text {{ color: #666 !important; }}
    /* 메모 텍스트 (추석연휴 등) */
    .cal-memo-text {{
        font-size: 10px !important; font-weight: 700 !important; color: #D97706 !important;
        text-align: center; margin-top: 2px;
    }}

    /* 색상 정의 */
    .text-sun {{ color: #EF4444 !important; }} /* 일요일/공휴일 빨강 */
    .text-sat {{ color: #3B82F6 !important; }} /* 토요일 파랑 */
    .bg-sun-header {{ background-color: #FEF2F2 !important; }}
    .bg-sat-header {{ background-color: #EFF6FF !important; }}

    [data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{ 
        background-color: {sidebar_bg} !important; color: {main_text_color} !important; 
    }}
    p, span, label, .stMarkdown, h2, h3, h4, h5, h6 {{ color: {main_text_color} !important; }}

    .stButton > button {{
        width: 100% !important; min-height: 38px !important;
        padding: 6px 10px !important; border: 1px solid {border_color} !important; border-radius: 10px !important;
        background-color: {btn_bg} !important; color: {btn_text} !important; font-size: 13px !important; font-weight: 800 !important; 
        transition: all 0.2s ease;
    }}
    .stButton > button:hover {{ border-color: {btn_hover_border} !important; background-color: {btn_hover_bg} !important; transform: translateY(-1px); }}

    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important; color: {main_text_color} !important;
        border-radius: 18px !important; padding: 16px 14px !important; border: 1px solid {border_color} !important;
    }}
    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"] {{
        background-color: {input_bg} !important; color: {input_text} !important; border: 1px solid {border_color} !important; border-radius: 10px !important;
    }}
    [data-baseweb="tab-list"] {{
        width: 100% !important; display: flex !important; gap: 3px !important;
        background-color: #F3F4F6 !important; padding: 3px !important; border-radius: 12px !important;
    }}
    [data-baseweb="tab"] {{
        flex: 1 1 auto !important; padding: 6px 4px !important; font-size: 12px !important; font-weight: 800 !important;
        text-align: center !important; border-radius: 8px !important; color: #4B5563 !important;
    }}
    [data-baseweb="tab[aria-selected=\"true\"]"] {{ background-color: #FFFFFF !important; color: {primary_blue} !important; }}

    .table-container {{
        width: 100%; max-height: 480px; overflow-x: auto; overflow-y: auto; border: 1px solid {border_color}; border-radius: 12px; background-color: {box_bg}; margin-top: 10px;
    }}
    .sticky-table {{
        width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; white-space: nowrap;
    }}
    .sticky-table th, .sticky-table td {{
        padding: 6px 8px; border-bottom: 1px solid {border_color}; border-right: 1px solid {border_color};
    }}
    .sticky-table th {{
        background-color: {table_header_bg}; font-weight: 800; position: sticky; top: 0; z-index: 3;
    }}
    .sticky-table th:nth
