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
        "auto_view_type": "🗓️ 이미지형 달력",
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
    ("auto_view_type", local_cfg["auto_view_type"]), ("app_theme", local_cfg["app_theme"]),
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
# 시스템 CSS 적용
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#FFFFFF" if not is_dark else "#121212"
main_text_color = "#1A1A1A" if not is_dark else "#E0E0E0"
border_color = "#E0E0E0" if not is_dark else "#333333"
btn_bg = "#FFFFFF" if not is_dark else "#1E1E1E"
btn_text = "#2D3748" if not is_dark else "#E0E0E0"
sidebar_bg = "#FFFFFF" if not is_dark else "#181818"
box_bg = "#FFFFFF" if not is_dark else "#1E1E1E"
primary_blue = "#3B82F6"
table_header_bg = "#EDF2F7" if not is_dark else "#2C2C2C"

responsive_css = f"""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    [data-testid="stSidebarNav"] {{ z-index: 100000 !important; }}
    [data-testid="collapsedControl"] {{ z-index: 99999 !important; top: 5px !important; }}
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        font-family: Pretendard, -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    .main .block-container {{
        background-color: {theme_bg} !important;
        padding: 1rem 1rem 2rem 1rem !important;
        max-width: 700px !important;
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
    
    .cal-duty-text {{
        font-size: 11px !important; font-weight: 700 !important; line-height: 1.3 !important;
        text-align: center; color: {main_text_color} !important; margin: 1px 0;
    }}
    .cal-memo-text {{
        font-size: 10px !important; font-weight: 700 !important; color: #D97706 !important;
        text-align: center; margin-top: 3px; line-height: 1.2;
    }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# 파일 유틸 및 로더 함수 (안전하게 수정됨)
# ---------------------------------------------------------
def get_initial_excel_file():
    candidates = glob.glob(os.path.join("DATA", "*.xlsx")) + glob.glob(os.path.join("data", "*.xlsx")) + glob.glob("*.xlsx")
    valid_files = [f for f in candidates if not os.path.basename(f).startswith("~$")]
    return valid_files[0] if valid_files else os.path.join("data", "숙직근무표.xlsx")

def update_excel_download_bytes(df):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        
        memos = st.session_state.get("memos", {})
        memo_list = []
        for _, row in save_df.iterrows():
            d_str = pd.to_datetime(row["날짜"]).strftime('%Y-%m-%d')
            if d_str in memos:
                memo_list.append(memos[d_str])
            else:
                val = row.get("메모", "")
                memo_list.append("" if pd.isna(val) else val)
        save_df["메모"] = memo_list
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            save_df.to_excel(writer, index=False, sheet_name="숙직근무자")
        st.session_state.file_bytes = output.getvalue()
    except Exception as e:
        st.sidebar.warning(f"⚠️ 다운로드 데이터 생성 실패: {e}")

def save_to_excel_file(df, file_path, sheet_name="숙직근무자"):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        
        memos = st.session_state.get("memos", {})
        memo_list = []
        for _, row in save_df.iterrows():
            d_str = pd.to_datetime(row["날짜"]).strftime('%Y-%m-%d')
            if d_str in memos:
                memo_list.append(memos[d_str])
            else:
                val = row.get("메모", "")
                memo_list.append("" if pd.isna(val) else val)
        save_df["메모"] = memo_list

        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            save_df.to_excel(writer, index=False, sheet_name=sheet_name)
        update_excel_download_bytes(save_df)
    except Exception as e:
        st.sidebar.warning(f"⚠️ 파일 저장 실패: {e}")
