import calendar
import datetime
import gc
import glob
import io
import json
import hmac
import hashlib
import uuid
import os
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
        "auto_view_type": "🗓️ 가로형 Grid", 
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
    ("editing_date", None), ("editing_duty_info", None),
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
# 카카오뱅크 스타일 디자인 시스템 CSS 적용
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#171717" if is_dark else "#F5F5F5"
main_text_color = "#F5F5F5" if is_dark else "#1E1E1E"
border_color = "#343434" if is_dark else "#ECECEC"
btn_bg = "#242424" if is_dark else "#FFFFFF"
btn_text = "#F5F5F5" if is_dark else "#1E1E1E"
btn_hover_bg = "#343434" if is_dark else "#FAFAFA"
btn_hover_border = "#FFE300" if is_dark else "#FFE300"
sidebar_bg = "#1E1E1E" if is_dark else "#FFFFFF"
dialog_bg = "#242424" if is_dark else "#FFFFFF"
input_bg = "#242424" if is_dark else "#FFFFFF"
input_text = "#F5F5F5" if is_dark else "#1E1E1E"
box_bg = "#242424" if is_dark else "#FFFFFF"
primary_yellow = "#FFE300"
table_header_bg = "#2C2C2C" if is_dark else "#ECECEC"

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
        padding: 0.8rem 12px 1.5rem 12px !important;
        max-width: 520px !important;
        margin: 0 auto !important;
        box-sizing: border-box !important;
    }}

    h1 {{
        font-size: 22px !important;
        margin: 12px 0px 16px 0px !important;
        font-weight: 800 !important;
        color: {main_text_color} !important;
        text-align: center;
        letter-spacing: -0.03em;
    }}

    .setting-box {{
        background-color: {box_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 18px !important;
        padding: 16px 18px !important;
        margin: 10px 0px 14px 0px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }}

    .today-card {{
        background: {primary_yellow} !important;
        color: #1E1E1E !important;
        padding: 18px 20px !important;
        border-radius: 18px !important;
        margin-bottom: 16px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        box-shadow: 0 8px 24px rgba(255, 227, 0, 0.25);
    }}
    .today-card .today-title {{ font-size: 12px !important; font-weight: 800 !important; margin-bottom: 6px !important; color: #5C5200 !important; text-transform: uppercase; letter-spacing: -0.02em; }}
    .today-card .today-content {{ font-size: 16px !important; font-weight: 800 !important; line-height: 1.4 !important; color: #1E1E1E !important; }}
    .today-card span {{ color: #1E1E1E !important; font-size: 17px !important; font-weight: 900 !important; text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 3px; }}

    .month-header-card {{
        background: {box_bg}; border: 1px solid {border_color}; border-radius: 16px; padding: 14px 18px; margin: 12px 0 14px 0; text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }}
    .month-header-card h2 {{ margin: 0 !important; font-size: 17px !important; font-weight: 800 !important; color: {main_text_color} !important; }}

    [data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{ 
        background-color: {sidebar_bg} !important; color: {main_text_color} !important; 
    }}
    p, span, label, .stMarkdown, h2, h3, h4, h5, h6 {{ color: {main_text_color} !important; }}

    .stButton > button {{
        width: 100% !important; min-height: 44px !important;
        padding: 10px 14px !important; border: 1px solid {border_color} !important; border-radius: 14px !important;
        background-color: {btn_bg} !important; color: {btn_text} !important; font-size: 14px !important; font-weight: 800 !important; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        transition: all 0.15s ease;
    }}
    .stButton > button:hover {{ border-color: {btn_hover_border} !important; background-color: {btn_hover_bg} !important; transform: translateY(-1px); }}

    [data-testid="stHorizontalBlock"] {{
        display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; width: 100% !important; gap: 4px !important; margin: 0 !important; padding: 0 !important;
    }}
    [data-testid="column"] {{
        width: 14.285% !important; max-width: 14.285% !important; min-width: 14.285% !important; flex: 0 0 14.285% !important; padding: 0px !important; margin: 0 !important; box-sizing: border-box !important;
    }}
    div[data-testid="column"] .stButton > button {{
        min-height: 76px !important; max-height: 98px !important; padding: 6px 2px !important; font-size: 11px !important; border-radius: 12px !important;
        display: flex !important; flex-direction: column !important; justify-content: flex-start !important; align-items: center !important; line-height: 1.25 !important;
        width: 100% !important; box-sizing: border-box !important; background-color: {box_bg} !important; border: 1px solid {border_color} !important; box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }}
    div[data-testid="column"] .stButton > button:hover {{
        border-color: {primary_yellow} !important; box-shadow: 0 4px 12px rgba(255,227,0,0.2);
    }}

    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important; color: {main_text_color} !important; width: 88vw !important; max-width: 380px !important;
        border-radius: 20px !important; padding: 18px 16px !important; border: 1px solid {border_color} !important; margin: auto !important;
        box-shadow: 0 12px 30px rgba(0,0,0,0.2);
    }}
    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"] {{
        background-color: {input_bg} !important; color: {input_text} !important; border: 1px solid {border_color} !important; border-radius: 12px !important;
    }}
    [data-baseweb="tab-list"] {{
        width: 100% !important; display: flex !important; gap: 6px !important; background-color: {box_bg}; padding: 6px !important; border-radius: 16px; border: 1px solid {border_color};
    }}
    [data-baseweb="tab"] {{
        flex: 1 1 auto !important; padding: 9px 8px !important; font-size: 13px !important; font-weight: 800 !important; text-align: center !important; border-radius: 12px !important; justify-content: center !important;
    }}

    .table-container {{
        width: 100%; max-height: 450px; overflow-x: auto; overflow-y: auto; border: 1px solid {border_color}; border-radius: 14px; background-color: {box_bg}; margin-top: 10px;
    }}
    .sticky-table {{
        width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; white-space: nowrap;
    }}
    .sticky-table th, .sticky-table td {{
        padding: 10px 12px; border-bottom: 1px solid {border_color}; border-right: 1px solid {border_color};
    }}
    .sticky-table th {{
        background-color: {table_header_bg}; font-weight: 800; position: sticky; top: 0; z-index: 3;
    }}
    .sticky-table th:nth-child(1), .sticky-table td:nth-child(1) {{
        position: sticky; left: 0; z-index: 2; background-color: {box_bg}; width: 90px; min-width: 90px;
    }}
    .sticky-table th:nth-child(1) {{ z-index: 4; background-color: {table_header_bg}; }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# Solapi (CoolSMS) 인증 헤더 생성 유틸 함수
# ---------------------------------------------------------
def get_solapi_auth_headers(api_key, api_secret):
    date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    salt = uuid.uuid4().hex
    data = date + salt
    signature = hmac.new(api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()
    auth = f"HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}"
    return {"Authorization": auth, "Content-Type": "application/json; charset=utf-8"}

# ---------------------------------------------------------
# 파일 유틸 및 저장 함수
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
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d), ""))
        
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
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d), ""))
        
        if os.path.exists(file_path):
            with pd.ExcelWriter(file_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                save_df.to_excel(writer, index=False, sheet_name=sheet_name)
        else:
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                save_df.to_excel(writer, index=False, sheet_name=sheet_name)
                
        update_excel_download_bytes(df)
        return True
    except Exception as e:
        st.sidebar.warning(f"⚠️ 엑셀 저장 실패: {e}")
        return False

def save_app_state(df, sheet_name, memos):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        state_data = {"selected_sheet": sheet_name, "memos": memos, "df_dict": save_df.to_dict(orient="records")}
        with open(PERSISTENCE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        save_to_excel_file(df, st.session_state.get("file_path", get_initial_excel_file()), sheet_name)
    except Exception as e:
        st.sidebar.warning(f"⚠️ 상태 저장 실패: {e}")

def load_excel_smart(file_input, selected_sheet=None):
    file_bytes = file_input if isinstance(file_input, bytes) else (file_input.read() if hasattr(file_input, "read") else open(file_input, "rb").read())
    file_obj = io.BytesIO(file_bytes)
    excel_file = pd.ExcelFile(file_obj)
    sheet_names = excel_file.sheet_names

    target_sheet = selected_sheet if selected_sheet and selected_sheet in sheet_names else (next((s for s in sheet_names if "숙직근무자" in s), sheet_names[0]))
    
    file_obj.seek(0)
    df_raw = pd.read_excel(file_obj, sheet_name=target_sheet, header=None)
    header_idx = 0
    for idx in range(min(20, len(df_raw))):
        if any(k in " ".join([str(v) for v in df_raw.iloc[idx].values]) for k in ["날짜", "일자", "근무일", "성명"]):
            header_idx = idx
            break

    file_obj.seek(0)
    df = pd.read_excel(file_obj, sheet_name=target_sheet, header=header_idx)
    df.columns = [str(col).strip() if not str(col).startswith("Unnamed") else f"열_{i}" for i, col in enumerate(df.columns)]
    
    date_col = next((c for c in df.columns if any(k in c.lower() for k in ["날짜", "일자", "date"])), df.columns[0])
    df.rename(columns={date_col: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    p1_col = next((c for c in df.columns if any(k in c for k in ["근무자1", "1근무", "숙직1", "성명"]) and "대직" not in c), None)
    p2_col = next((c for c in df.columns if any(k in c for k in ["근무자2", "2근무", "숙직2"]) and "대직" not in c), None)
    sub1_col = next((c for c in df.columns if any(k in c for k in ["대직1", "대직자1"])), None)
    sub2_col = next((c for c in df.columns if any(k in c for k in ["대직2", "대직자2"])), None)

    df["근무자1"] = df[p1_col].astype(str).str.strip() if p1_col else "미지정"
    df["근무자2"] = df[p2_col].astype(str).str.strip() if p2_col else "미지정"
    df["대직1"] = df[sub1_col].astype(str).str.strip() if sub1_col else None
    df["대직2"] = df[sub2_col].astype(str).str.strip() if sub2_col else None
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    df["실제근무1"] = df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(df["근무자1"]).fillna("미지정")
    df["실제근무2"] = df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(df["근무자2"]).fillna("미지정")
    
    base_cols = ["날짜", "근무자1", "대직1", "근무자2", "대직2", "실제근무1", "실제근무2"]
    other_cols = [c for c in df.columns if c not in base_cols and c != "년월"]
    ordered_cols = base_cols + other_cols + ["년월"]
    
    return df[ordered_cols], target_sheet, sheet_names, df_raw, file_bytes

initial_file = get_initial_excel_file()
if "file_path" not in st.session_state: st.session_state.file_path = initial_file
if "file_bytes" not in st.session_state and os.path.exists(initial_file):
    with open(initial_file, "rb") as f: st.session_state.file_bytes = f.read()
    st.session_state.file_name = os.path.basename(initial_file)

if "df" not in st.session_state:
    parsed_df, used_sheet, sheet_names, raw_df, _ = load_excel_smart(st.session_state.file_bytes)
    st.session_state.update({"df": parsed_df, "selected_sheet": used_sheet, "sheet_names": sheet_names, "raw_df": raw_df, "memos": {}})

def load_workers_db():
    if WORKERS_DB_FILE.exists():
        try:
            return json.loads(WORKERS_DB_FILE.read_text(encoding="utf-8"))
        except:
            return []
    return []

def save_workers_db(workers):
    WORKERS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKERS_DB_FILE.write_text(json.dumps(workers, ensure_ascii=False, indent=2))

update_excel_download_bytes(st.session_state.df)

# ---------------------------------------------------------
# 다이얼로그 모음
# ---------------------------------------------------------
@st.dialog("⚠️ 프로그램 종료 확인")
def confirm_exit_dialog():
    st.write("정말로 시스템을 종료하시겠습니까?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("취소", use_container_width=True): 
            st.session_state.show_exit_dialog = False
            st.rerun()
    with c2:
        if st.button("종료", use_container_width=True, type="primary"):
            st.session_state.update({"show_exit_dialog": False, "is_app_closed": True})
            st.rerun()

@st.dialog("⚙️ 화면 및 설정 관리")
def settings_dialog():
    tab_s1, tab_s2, tab_s3 = st.tabs(["화면 설정", "순환 등록", "SMS 연동 설정"])
    
    with tab_s1:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        new_view = st.radio("달력 표출 형식", ["🗓️ 가로형 Grid", "📄 세로형 리스트"], index=0 if st.session_state.auto_view_type == "🗓️ 가로형 Grid" else 1)
        new_th = st.radio("대시보드 테마", ["☀️ 화이트 테마", "🌙 블랙 테마"], index=0 if st.session_state.app_theme == "☀️ 화이트 테마" else 1)
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("화면 설정 적용", use_container_width=True, type="primary"):
            st.session_state.update({
                "auto_view_type": new_view, "app_theme": new_th, "show_settings_dialog": False
            })
            save_local_config("auto_view_type", new_view)
            save_local_config("app_theme", new_th)
            st.rerun()

    with tab_s2:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        st.markdown("#### 🔄 순환 등록 설정")
        
        cfg = load_local_config()
        try:
            default_start_date = datetime.datetime.strptime(cfg.get("batch_start_date", str(datetime.date.today())), "%Y-%m-%d").date()
        except:
            default_start_date = datetime.date.today()

        start_d = st.date_input("시작 날짜", value=default_start_date, key="batch_start_date_input")
        infinite_repeat = st.checkbox("무한 순환", value=cfg.get("batch_infinite", False), key="batch_infinite_input")
        days_c = st.number_input("적용 일수", min_value=1, max_value=365, value=int(cfg.get("batch_days_c", 30)), disabled=infinite_repeat, key="batch_days_c_input")
        
        i1 = st.number_input("근무자1 주기", 1, 30, int(cfg.get("batch_i1", 3)), key="batch_i1_input")
        saved_w1 = cfg.get("batch_w1_names", ["", "", ""])
        w1_names = [st.text_input(f"1-{i+1}", value=saved_w1[i] if i < len(saved_w1) else "", key=f"w1_{i}").strip() for i in range(int(i1))]
        
        i2 = st.number_input("근무자2 주기", 1, 30, int(cfg.get("batch_i2", 3)), key="batch_i2_input")
        saved_w2 = cfg.get("batch_w2_names", ["", "", ""])
        w2_names = [st.text_input(f"2-{i+1}", value=saved_w2[i] if i < len(saved_w2) else "", key=f"w2_{i}").strip() for i in range(int(i2))]
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("🔄 순환 패턴 반영", use_container_width=True, type="primary"):
            save_local_config("batch_start_date", str(start_d))
            save_local_config("batch_infinite", infinite_repeat)
            save_local_config("batch_days_c", int(days_c))
            save_local_config("batch_i1", int(i1))
            save_local_config("batch_w1_names", w1_names)
            save_local_config("batch_i2", int(i2))
            save_local_config("batch_w2_names", w2_names)

            df_cur = st.session_state.df
            cur_d = start_d
            v1, v2 = [n for n in w1_names if n], [n for n in w2_names if n]
            
            if infinite_repeat:
                target_end_date = datetime.date(start_d.year, 12, 31)
                delta_days = (target_end_date - start_d).days + 1
            else:
                delta_days = int(days_c)

            for i in range(delta_days):
                idx_m = df_cur[df_cur["날짜"].dt.date == cur_d].index
                if not idx_m.empty:
                    idx = idx_m[0]
                    if v1: 
                        df_cur.loc[idx, "근무자1"] = v1[i % len(v1)]
                        df_cur.loc[idx, "대직1"] = None
                        df_cur.loc[idx, "실제근무1"] = v1[i % len(v1)]
                    if v2: 
                        df_cur.loc[idx, "근무자2"] = v2[i % len(v2)]
                        df_cur.loc[idx, "대직2"] = None
                        df_cur.loc[idx, "실제근무2"] = v2[i % len(v2)]
                cur_d += datetime.timedelta(days=1)
                
            st.session_state.df = df_cur
            save_app_state(df_cur, st.session_state.selected_sheet, st.session_state.memos)
            st.session_state.show_settings_dialog = False
            st.success("✅ 순환 패턴이 성공적으로 반영되었습니다!")
            st.rerun()

    with tab_s3:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        s_key = st.text_input("SMS API 키 (API Key)", value=st.session_state.sms_api_key, type="password", placeholder="Solapi/CoolSMS API Key")
        s_sec = st.text_input("SMS API 시크릿 (API Secret)", value=st.session_state.sms_api_secret, type="password", placeholder="Solapi/CoolSMS API Secret")
        s_phone = st.text_input("발신자 대표 번호", value=st.session_state.sms_sender_phone, placeholder="0200000000 (등록된 발신번호)")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("SMS 설정 저장", use_container_width=True, type="primary"):
            st.session_state.sms_api_key = s_key
            st.session_state.sms_api_secret = s_sec
            st.session_state.sms_sender_phone = s_phone
            save_local_config("sms_api_key", s_key)
            save_local_config("sms_api_secret", s_sec)
            save_local_config("sms_sender_phone", s_phone)
            st.session_state.show_settings_dialog = False
            st.success("✅ 문자(SMS) API 설정이 저장되었습니다.")
            st.rerun()

@st.dialog("✏️ 근무자 및 메모 수정")
def edit_worker_dialog(date_str, duty_info):
    st.markdown(f"### {date_str} 근무 관리")
    if duty_info is None or "idx" not in duty_info or duty_info["idx"] not in st.session_state.df.index:
        st.error("해당 날짜의 정보를 찾을 수 없습니다.")
        if st.button("닫기", use_container_width=True):
            st.session_state.update({"editing_date": None, "editing_duty_info": None})
            st.rerun()
        return

    row_idx = duty_info["idx"]
    curr_row = st.session_state.df.loc[row_idx]
    
    all_workers = set()
    for col in ["근무자1", "근무자2", "대직1", "대직2"]:
        if col in st.session_state.df.columns:
            for v in st.session_state.df[col].dropna().unique():
                v_str = str(v).strip()
                if v_str and v_str not in ["미지정", "nan", "None"]:
                    all_workers.add(v_str)

    worker_options = ["(선택 안함)"] + sorted(all_workers) + ["(직접 입력)"]
    
    def get_idx(val):
        if not val or pd.isna(val) or str(val).strip() in ["nan", "None", "미지정"]: return 0
        val_str = str(val).strip()
        return worker_options.index(val_str) if val_str in worker_options else len(worker_options) - 1

    curr_p1 = str(curr_row.get("근무자1", "")).strip() if pd.notnull(curr_row.get("근무자1")) else ""
    curr_p2 = str(curr_row.get("근무자2", "")).strip() if pd.notnull(curr_row.get("근무자2")) else ""
    curr_sub1 = str(curr_row.get("대직1", "")).strip() if pd.notnull(curr_row.get("대직1")) else ""
    curr_sub2 = str(curr_row.get("대직2", "")).strip() if pd.notnull(curr_row.get("대직2")) else ""

    with st.form(f"form_{date_str}"):
        p1_s = st.selectbox("근무자1", worker_options, index=get_idx(curr_p1))
        p1_c = st.text_input("직접입력1", value=curr_p1 if p1_s == "(직접 입력)" else "") if p1_s == "(직접 입력)" else ""
        sub1_s = st.selectbox("대직자1", worker_options, index=get_idx(curr_sub1))
        sub1_c = st.text_input("대직1 직접입력", value=curr_sub1 if sub1_s == "(직접 입력)" else "") if sub1_s == "(직접 입력)" else ""

        p2_s = st.selectbox("근무자2", worker_options, index=get_idx(curr_p2))
        p2_c = st.text_input("직접입력2", value=curr_p2 if p2_s == "(직접 입력)" else "") if p2_s == "(직접 입력)" else ""
        sub2_s = st.selectbox("대직자2", worker_options, index=get_idx(curr_sub2))
        sub2_c = st.text_input("대직2 직접입력", value=curr_sub2 if sub2_s == "(직접 입력)" else "") if sub2_s == "(직접 입력)" else ""
        
        memo_in = st.text_area("메모", value=st.session_state.memos.get(date_str, ""))
        
        submitted = st.form_submit_button("💾 저장", use_container_width=True, type="primary")
        closed = st.form_submit_button("❌ 닫기", use_container_width=True)

    if submitted:
        f_p1 = p1_c if p1_s == "(직접 입력)" else ("" if p1_s == "(선택 안함)" else p1_s)
        f_p2 = p2_c if p2_s == "(직접 입력)" else ("" if p2_s == "(선택 안함)" else p2_s)
        f_sub1 = sub1_c if sub1_s == "(직접 입력)" else ("" if sub1_s == "(선택 안함)" else sub1_s)
        f_sub2 = sub2_c if sub2_s == "(직접 입력)" else ("" if sub2_s == "(선택 안함)" else sub2_s)
        
        st.session_state.df.loc[row_idx, ["근무자1", "근무자2", "대직1", "대직2"]] = [
            f_p1 if f_p1 else "미지정", f_p2 if f_p2 else "미지정", f_sub1 if f_sub1 else None, f_sub2 if f_sub2 else None
        ]
        st.session_state.df.loc[row_idx, "실제근무1"] = f_sub1 if f_sub1 else (f_p1 if f_p1 else "미지정")
        st.session_state.df.loc[row_idx, "실제근무2"] = f_sub2 if f_sub2 else (f_p2 if f_p2 else "미지정")
        
        if memo_in.strip(): st.session_state.memos[date_str] = memo_in.strip()
        else: st.session_state.memos.pop(date_str, None)
        
        save_app_state(st.session_state.df, st.session_state.selected_sheet, st.session_state.memos)
        st.session_state.update({"editing_date": None, "editing_duty_info": None})
        st.rerun()

    if closed:
        st.session_state.update({"editing_date": None, "editing_duty_info": None})
        st.rerun()

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 파일 관리")
    if "file_name" in st.session_state: st.info(f"📄 `{st.session_state.file_name}`")
    
    up_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"], key=f"file_uploader_{st.session_state.uploader_key}")
    if up_file:
        f_bytes = up_file.getvalue()
        save_p = os.path.join("data", up_file.name)
        with open(save_p, "wb") as f: f.write(f_bytes)
        
        parsed_df, used_s, s_names, r_df, _ = load_excel_smart(f_bytes, "숙직근무자")
        st.session_state.update({
            "file_path": save_p, "file_bytes": f_bytes, "file_name": up_file.name,
            "df": parsed_df, "selected_sheet": used_s, "sheet_names": s_names, "raw_df": r_df,
            "upload_success_msg": "✅ 파일 업로드 완료!"
        })
        save_app_state(parsed_df, used_s, st.session_state.memos)
        st.session_state.uploader_key += 1
        st.rerun()

    if st.session_state.get("upload_success_msg"):
        st.success(st.session_state.upload_success_msg)
        st.session_state.upload_success_msg = ""

    if "file_bytes" in st.session_state:
        st.download_button("📥 엑셀 다운로드", data=st.session_state.file_bytes, file_name="숙직근무표_수정본.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.divider()
    if st.button("🔴 앱 종료", use_container_width=True):
        st.session_state.show_exit_dialog = True
        st.rerun()

if st.session_state.show_exit_dialog: 
    confirm_exit_dialog()
elif st.session_state.show_settings_dialog: 
    settings_dialog()
elif st.session_state.editing_date and st.session_state.editing_duty_info: 
    edit_worker_dialog(st.session_state.editing_date, st.session_state.editing_duty_info)

df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
st.title("광주교도소 의료과 숙직근무")

st.markdown('<div class="setting-box">', unsafe_allow_html=True)
if st.button("⚙️ 화면 및 설정 관리 열기", use_container_width=True):
    st.session_state.show_settings_dialog = True
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 달력", "✏️ 수정", "📊 통계", "💬 문자통보", "🔍 원본"])

# ---------------------------------------------------------
# [탭 1] 달력 뷰 (오류 수정 반영 부분)
# ---------------------------------------------------------
with tab1:
    today_df = df[df["날짜"].dt.date == today]
    if not today_df.empty:
        tr = today_df.iloc[0]
        sub1_t = str(tr.get("대직1", "")).strip() if pd.notnull(tr.get("대직1")) else ""
        sub2_t = str(tr.get("대직2", "")).strip() if pd.notnull(tr.get("대직2")) else ""
        
        p1 = f"{tr['실제근무1']}(대)" if sub1_t and sub1_t not in ["nan", "None", ""] else tr["실제근무1"]
        p2 = f"{tr['실제근무2']}(대)" if sub2_t and sub2_t not in ["nan", "None", ""] else tr["실제근무2"]
        memo_txt = f" | 📌 {st.session_state.memos.get(today.strftime('%Y-%m-%d'), '')}" if st.session_state.memos.get(today.strftime('%Y-%m-%d')) else ""
        st.markdown(f'<div class="today-card"><div class="today-title">오늘 근무 안내 ({today.strftime("%m월 %d일")})</div><div class="today-content">1: <span>{p1}</span> | 2: <span>{p2}</span>{memo_txt}</div></div>', unsafe_allow_html=True)

    avail_months = sorted(df["년월"].dropna().unique()) or [today.strftime("%Y-%m")]
    cur_ym = today.strftime("%Y-%m")
    
    if "selected_month" not in st.session_state or st.session_state.selected_month not in avail_months:
        st.session_state.selected_month = cur_ym if cur_ym in avail_months else avail_months[0]

    sel_month = st.selectbox("조회 월 선택", avail_months, index=avail_months.index(st.session_state.selected_month) if st.session_state.selected_month in avail_months else 0, label_visibility="collapsed")
    st.session_state.selected_month = sel_month

    if sel_month in avail_months:
        y, m = map(int, sel_month.split("-"))
        st.markdown(f'<div class="month-header-card"><h2>📅 {y}년 {m}월 근무표</h2></div>', unsafe_allow_html=True)
        
        num_days = calendar.monthrange(y, m)[1]
        m_df = df[df["년월"] == sel_month]
        
        duty_map = {}
        for i, row in m_df.iterrows():
            p1_name = str(row.get("실제근무1", "미지정")).strip()
            p2_name = str(row.get("실제근무2", "미지정")).strip()
            sub1_val = str(row.get("대직1", "")).strip() if pd.notnull(row.get("대직1")) else ""
            sub2_val = str(row.get("대직2", "")).strip() if pd.notnull(row.get("대직2")) else ""
            
            if sub1_val and sub1_val not in ["nan", "None", ""]: p1_name = f"{p1_name}(대)"
            if sub2_val and sub2_val not in ["nan", "None", ""]: p2_name = f"{p2_name}(대)"
                
            duty_map[row["날짜"].day] = {"idx": i, "p1": p1_name, "p2": p2_name}

        if st.session_state.auto_view_type == "📄 세로형 리스트":
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
            for d in range(1, num_days + 1):
                c_date = datetime.date(y, m, d)
                d_str = c_date.strftime("%Y-%m-%d")
                weekday_idx = c_date.weekday()
                weekday_str = weekdays_kr[weekday_idx]
                info = duty_map.get(d, {"p1": "-", "p2": "-"})
                
                is_today = (c_date == today)
                if is_today: t_str = f"🌟 [오늘] {d:02d}일({weekday_str})"
                elif weekday_idx == 6 or c_date in kr_holidays: t_str = f"🔴 {d:02d}일({weekday_str})"
                elif weekday_idx == 5: t_str = f"🔵 {d:02d}일({weekday_str})"
                else: t_str = f"🗓️ {d:02d}일({weekday_str})"
                    
                memo_s = f" | 📌 {st.session_state.memos.get(d_str, '')}" if st.session_state.memos.get(d_str) else ""
                
                # 오류 수정: 고유한 식별 키 부여 (v_YYYY-MM-DD 형식)
                if st.button(f"{t_str} | 1:{info['p1']} | 2:{info['p2']}{memo_s}", key=f"v_list_btn_{d_str}"):
                    st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(d)})
                    st.rerun()
        else:
            cols_h = st.columns(7)
            h_names = [("일", "#FF3838"), ("월", main_text_color), ("화", main_text_color), ("수", main_text_color), ("목", main_text_color), ("금", main_text_color), ("토", "#2563EB")]
            for idx, (h_n, col_c) in enumerate(h_names):
                cols_h[idx].markdown(f"<div style='text-align: center; color: {col_c}; font-weight: 800; font-size: 12px; padding: 4px 0;'>{h_n}</div>", unsafe_allow_html=True)

            offset = (calendar.monthrange(y, m)[0] + 1) % 7
            day_cnt = 1
            for r in range((offset + num_days + 6) // 7):
                g_cols = st.columns(7)
                for c in range(7):
                    if (r * 7 + c) < offset or day_cnt > num_days:
                        g_cols[c].write("")
                    else:
                        c_date = datetime.date(y, m, day_cnt)
                        d_str = c_date.strftime("%Y-%m-%d")
                        info = duty_map.get(day_cnt, {"p1": "-", "p2": "-"})
                        memo_s = "📌" if st.session_state.memos.get(d_str) else ""
                        
                        is_today = (c_date == today)
                        if is_today: day_prefix = "🌟"
                        elif c == 0 or c_date in kr_holidays: day_prefix = "🔴"
                        elif c == 6: day_prefix = "🔵"
                        else: day_prefix = ""
                            
                        t_str = f"{day_prefix}{day_cnt}" if day_prefix else str(day_cnt)
                        btn_txt = f"{t_str}\n{info['p1']}\n{info['p2']}"
                        if memo_s: btn_txt += f" {memo_s}"

                        # 오류 수정: 달력 Grid의 버튼마다 연-월-일을 포함한 완벽히 고유한 키(g_grid_btn_YYYY-MM-DD)를 할당하여 클릭 오류 원천 차단
                        if g_cols[c].button(btn_txt, key=f"g_grid_btn_{d_str}"):
                            st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(day_cnt)})
                            st.rerun()
                        day_cnt += 1

# ---------------------------------------------------------
# [탭 2] 수정 뷰
# ---------------------------------------------------------
with tab2:
    st.subheader("전체 근무표 에디터 수정")
    edit_ms = ["전체 기간"] + sorted(df["년월"].dropna().unique())
    sel_ed_m = st.selectbox("월 선택", edit_ms, index=edit_ms.index(cur_ym) if cur_ym in edit_ms else 0)
    
    valid_cols = [c for c in df.columns if c and not str(c).startswith("열_") and not str(c).startswith("Unnamed")]
    
    preferred_order = ["날짜", "근무자1", "대직1", "근무자2", "대직2", "실제근무1", "실제근무2"]
    display_cols = [c for c in preferred_order if c in df.columns]
    for c in valid_cols:
        if c not in display_cols and c != "년월":
            display_cols.append(c)

    target_df = df[display_cols].copy() if sel_ed_m == "전체 기간" else df[df["년월"] == sel_ed_m][display_cols].copy()

    column_config = {
        "날짜": st.column_config.DateColumn("날짜", format="YYYY-MM-DD", pinned=True, disabled=False)
    }

    edited_df = st.data_editor(target_df, num_rows="dynamic", key="editor_main", use_container_width=True, column_config=column_config)

    if st.button("변경사항 일괄 저장", use_container_width=True, type="primary"):
        m_df = st.session_state.df.copy()
        
        if sel_ed_m == "전체 기간":
            for idx in edited_df.index:
                if idx in m_df.index:
                    for col in edited_df.columns:
                        m_df.loc[idx, col] = edited_df.loc[idx, col]
        else:
            sub_indices = m_df[m_df["년월"] == sel_ed_m].index
            for i, idx in enumerate(sub_indices):
                if i < len(edited_df):
                    ed_idx = edited_df.index[i]
                    for col in edited_df.columns:
                        m_df.loc[idx, col] = edited_df.loc[ed_idx, col]
            
        if "날짜" in m_df.columns:
            m_df["날짜"] = pd.to_datetime(m_df["날짜"], errors="coerce")
            m_df["년월"] = m_df["날짜"].dt.strftime("%Y-%m")
            
        p1 = m_df["근무자1"].astype(str).str.strip() if "근무자1" in m_df.columns else "미지정"
        p2 = m_df["근무자2"].astype(str).str.strip() if "근무자2" in m_df.columns else "미지정"
        sub1 = m_df["대직1"].astype(str).str.strip() if "대직1" in m_df.columns else ""
        sub2 = m_df["대직2"].astype(str).str.strip() if "대직2" in m_df.columns else ""
        
        m_df["실제근무1"] = sub1.replace(["", "nan", "None"], None).combine_first(p1).fillna("미지정")
        m_df["실제근무2"] = sub2.replace(["", "nan", "None"], None).combine_first(p2).fillna("미지정")
        
        st.session_state.df = m_df
        save_app_state(m_df, st.session_state.selected_sheet, st.session_state.memos)
        st.success("✅ 변경사항이 저장되었습니다.")
        st.rerun()

# ---------------------------------------------------------
# [탭 3] 통계 뷰
# ---------------------------------------------------------
with tab3:
    st.subheader("근무자 월별 통계 및 근무 구분 분석")
    stat_ms = sorted(df["년월"].dropna().unique(), reverse=True)
    default_stat_idx = stat_ms.index(cur_ym) if cur_ym in stat_ms else 0
    
    sel_st_m = st.selectbox("통계 월 선택", ["전체 기간"] + stat_ms, index=default_stat_idx + 1 if cur_ym in stat_ms else 0)
    f_df = df.copy() if sel_st_m == "전체 기간" else df[df["년월"] == sel_st_m]
    
    def get_category_and_hours(row):
        c_date = pd.to_datetime(row["날짜"])
        wd = c_date.weekday()
        
        if "근무구분" in row and pd.notnull(row["근무구분"]):
            cat_val = str(row["근무구분"]).strip()
            if "평일" in cat_val: return "평일", 7
            elif "금요일" in cat_val: return "금요일", 15
            elif "토요일" in cat_val: return "토요일", 15
            elif "일요일" in cat_val or "공휴일" in cat_val: return "일요일", 7

        if wd in [0, 1, 2, 3]: return "평일", 7
        elif wd == 4: return "금요일", 15
        elif wd == 5: return "토요일", 15
        else: return "일요일", 7

    expanded_rows = []
    for _, r in f_df.iterrows():
        cat, hours = get_category_and_hours(r)
        w1 = str(r.get("실제근무1", "")).strip()
        w2 = str(r.get("실제근무2", "")).strip()
        
        if w1 and w1 not in ["미지정", "nan", "None", ""]:
            expanded_rows.append({"근무자": w1, "근무구분": cat, "근무시간": hours, "횟수": 1})
        if w2 and w2 not in ["미지정", "nan", "None", ""]:
            expanded_rows.append({"근무자": w2, "근무구분": cat, "근무시간": hours, "횟수": 1})

    if expanded_rows:
        exp_df = pd.DataFrame(expanded_rows)
        
        agg_df = exp_df.groupby(["근무자", "근무구분"]).agg(
            근무횟수=("횟수", "sum"), 
            근무시간=("근무시간", "sum")
        ).reset_index()
        
        st.markdown("### 📈 근무시간 비율 그래프 (구분별 스택바)")
        
        chart = alt.Chart(agg_df).mark_bar().encode(
            x=alt.X('근무자:N', sort=alt.EncodingSortField(field='근무시간', op='sum', order='descending'), title='근무자', axis=alt.Axis(labelAngle=-45, labelOverlap=False)),
            y=alt.Y('근무시간:Q', title='총 근무시간 (시간)'),
            color=alt.Color('근무구분:N', scale=alt.Scale(domain=['평일', '금요일', '토요일', '일요일'], range=['#FFE300', '#22C55E', '#3B82F6', '#FF3838']), title='근무 구분'),
            tooltip=['근무자', '근무구분', '근무횟수', '근무시간']
        ).properties(height=380).configure_legend(orient="bottom", title=None)
        
        st.altair_chart(chart, use_container_width=True)
        
        st.markdown("### 📊 근무자별 상세 통계표 (구분별 횟수 및 시간)")
        
        pivot_count = exp_df.pivot_table(index="근무자", columns="근무구분", values="횟수", aggfunc="sum", fill_value=0)
        pivot_hours = exp_df.pivot_table(index="근무자", columns="근무구분", values="근무시간", aggfunc="sum", fill_value=0)
        
        categories = ["평일", "금요일", "토요일", "일요일"]
        for cat in categories:
            if cat not in pivot_count.columns: pivot_count[cat] = 0
            if cat not in pivot_hours.columns: pivot_hours[cat] = 0
        pivot_count = pivot_count[categories]
        pivot_hours = pivot_hours[categories]
        
        summary_table = pd.DataFrame({
            "평일(회/시)": [f"{int(c)}회 / {int(h)}시간" for c, h in zip(pivot_count["평일"], pivot_hours["평일"])],
            "금요일(회/시)": [f"{int(c)}회 / {int(h)}시간" for c, h in zip(pivot_count["금요일"], pivot_hours["금요일"])],
            "토요일(회/시)": [f"{int(c)}회 / {int(h)}시간" for c, h in zip(pivot_count["토요일"], pivot_hours["토요일"])],
            "일요일(회/시)": [f"{int(c)}회 / {int(h)}시간" for c, h in zip(pivot_count["일요일"], pivot_hours["일요일"])],
            "총 근무횟수": pivot_count.sum(axis=1).astype(int),
            "총 근무시간": pivot_hours.sum(axis=1).astype(int)
        })
        summary_table = summary_table.sort_values(by="총 근무시간", ascending=False).reset_index()
        summary_table.index = range(1, len(summary_table) + 1)
        summary_table.insert(0, "번호", summary_table.index)
        
        html_table = f"""
        <div class="table-container">
            <table class="sticky-table">
                <thead>
                    <tr>{"".join([f"<th>{col}</th>" for col in summary_table.columns])}</tr>
                </thead>
                <tbody>
        """
        for _, row in summary_table.iterrows():
            html_table += "<tr>" + "".join([f"<td>{val}</td>" for val in row]) + "</tr>"
        html_table += "</tbody></table></div>"
        st.markdown(html_table, unsafe_allow_html=True)

        total_workers_count = len(summary_table)
        total_duty_days = len(f_df)
        total_duty_hours = int(summary_table["총 근무시간"].sum())

        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-around; background-color: {box_bg}; border: 1px solid {border_color}; border-radius: 16px; padding: 16px; margin-top: 14px; text-align: center;">
                <div>
                    <div style="font-size: 11px; font-weight: 700; color: #888; margin-bottom: 4px;">👥 총 근무자 명수</div>
                    <div style="font-size: 16px; font-weight: 900; color: {main_text_color};">{total_workers_count} 명</div>
                </div>
                <div style="border-right: 1px solid {border_color};"></div>
                <div>
                    <div style="font-size: 11px; font-weight: 700; color: #888; margin-bottom: 4px;">📅 총 근무일수</div>
                    <div style="font-size: 16px; font-weight: 900; color: {main_text_color};">{total_duty_days} 일</div>
                </div>
                <div style="border-right: 1px solid {border_color};"></div>
                <div>
                    <div style="font-size: 11px; font-weight: 700; color: #888; margin-bottom: 4px;">⏱️ 총 근무시간</div>
                    <div style="font-size: 16px; font-weight: 900; color: {main_text_color};">{total_duty_hours} 시간</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.info("통계 데이터가 없습니다.")

# ---------------------------------------------------------
# [탭 4] 문자 통보 탭
# ---------------------------------------------------------
with tab4:
    st.subheader("💬 실제 근무자 문자(SMS) 자동 통보 시스템")
    st.markdown("""
    > 💡 **안내**: 등록된 연락처 DB를 기반으로 Solapi/CoolSMS API를 통해 근무자에게 SMS를 발송합니다.
    """)

    workers_db = load_workers_db()

    sub_k1, sub_k2 = st.tabs(["🚀 당일 근무자 문자(SMS) 발송", "📋 근무자 연락처 관리"])

    with sub_k1:
        st.markdown("#### 선택 일자 근무자 문자 통보 발송")
        
        target_send_date = st.date_input("알림 대상 일자 선택", value=datetime.date.today(), key="sms_target_send_date")
        target_str = target_send_date.strftime("%Y-%m-%d")

        matched_row = df[df["날짜"].dt.date == target_send_date]
        m_p1, m_p2 = "미지정", "미지정"
        if not matched_row.empty:
            r_info = matched_row.iloc[0]
            m_p1 = r_info.get("실제근무1", "미지정")
            m_p2 = r_info.get("실제근무2", "미지정")
            st.info(f"📌 **{target_str}** 근무자 확인 -> 1근무: **{m_p1}** | 2근무: **{m_p2}**")
        else:
            st.warning(f"⚠️ {target_str}에 해당하는 근무 정보가 없습니다.")

        default_sms_msg = f"[광주교도소 의료과] {target_str} 숙직 근무 안내\n- 1근무: {m_p1}\n- 2근무: {m_p2}\n지정된 시간에 근무에 임해주시기 바랍니다."
        custom_sms_msg = st.text_area("발송할 문자 내용 작성", value=default_sms_msg)

        phone_map = {w["name"].strip(): w for w in workers_db}
        
        w1_info = phone_map.get(m_p1)
        w2_info = phone_map.get(m_p2)

        if w1_info and w1_info.get("phone"):
            st.success(f"1근무자 **{m_p1}** 연락처 등록됨 (발송 가능)")
        else:
            st.warning(f"1근무자 **{m_p1}**의 연락처가 등록되어 있지 않습니다.")

        if w2_info and w2_info.get("phone"):
            st.success(f"2근무자 **{m_p2}** 연락처 등록됨 (발송 가능)")
        else:
            st.warning(f"2근무자 **{m_p2}**의 연락처가 등록되어 있지 않습니다.")

        if st.button("📤 실제 근무자들에게 문자(SMS) 일괄 통보 전송", type="primary", use_container_width=True):
            api_key = st.session_state.get("sms_api_key", "").strip()
            api_secret = st.session_state.get("sms_api_secret", "").strip()
            sender_ph = st.session_state.get("sms_sender_phone", "").replace("-", "").strip()

            if not api_key or not api_secret or not sender_ph:
                st.warning("⚠️ [설정 관리] ➔ [SMS 연동 설정] 탭에서 SMS API 키, 시크릿, 발신자 번호를 모두 입력해주세요.")
            else:
                success_count = 0
                targets_to_send = [w1_info, w2_info]
                url = "https://api.solapi.com/messages/v4/send"
                headers = get_solapi_auth_headers(api_key, api_secret)
                
                for t_info in targets_to_send:
                    if t_info and t_info.get("phone") and t_info.get("consent_agreed", True):
                        opt = t_info.get("sms_option", "매일 근무 상관없이 받기")
                        if opt == "받지 않기":
                            continue
                        if opt == "내 근무에만 받기" and t_info["name"] not in [m_p1, m_p2]:
                            continue
                            
                        dest_phone = t_info["phone"].replace("-", "").strip()
                        payload = {
                            "message": {
                                "to": dest_phone,
                                "from": sender_ph,
                                "text": custom_sms_msg
                            }
                        }
                        try:
                            resp = requests.post(url, headers=headers, json=payload, timeout=10)
                            res_data = resp.json()
                            if resp.status_code in [200, 201]:
                                success_count += 1
                                st.success(f"✅ [{t_info['name']}] 님에게 전송 성공!")
                            else:
                                st.error(f"❌ [{t_info['name']}] 전송 실패 (코드 {resp.status_code}): {res_data}")
                        except Exception as ex:
                            st.error(f"전송 중 네트워크 오류 발생 ({t_info['name']}): {ex}")

                if success_count > 0:
                    st.success(f"🎉 총 {success_count}명의 근무자에게 문자(SMS) 통보가 성공적으로 발송되었습니다!")
                else:
                    st.info("ℹ️ 발송 대상이 없거나 유효 연락처가 등록되지 않았습니다.")

        st.divider()
        st.markdown("#### ⚡ 직접 즉시 개별 발송")
        consent_workers = [w["name"] for w in workers_db if w.get("consent_agreed", True)]
        
        with st.form("direct_instant_sms_form"):
            selected_direct_worker = st.selectbox("수신 동의한 근무자 선택", consent_workers if consent_workers else ["등록된 동의 근무자 없음"])
            direct_msg_input = st.text_area("즉시 발송할 메시지 내용 (수정 가능)", value=default_sms_msg)
            
            submitted_direct = st.form_submit_button("🚀 즉시 발송 전송하기", type="primary", use_container_width=True)
            if submitted_direct:
                if not consent_workers:
                    st.warning("⚠️ 수신 동의된 근무자가 존재하지 않습니다.")
                else:
                    target_w_obj = next((w for w in workers_db if w["name"] == selected_direct_worker), None)
                    api_key = st.session_state.get("sms_api_key", "").strip()
                    api_secret = st.session_state.get("sms_api_secret", "").strip()
                    sender_ph = st.session_state.get("sms_sender_phone", "").replace("-", "").strip()

                    if not api_key or not api_secret or not sender_ph:
                        st.warning("⚠️ [설정 관리] ➔ [SMS 연동 설정]에서 API 키와 발신번호를 설정해주세요.")
                    elif target_w_obj and target_w_obj.get("phone"):
                        dest_phone = target_w_obj["phone"].replace("-", "").strip()
                        url = "https://api.solapi.com/messages/v4/send"
                        headers = get_solapi_auth_headers(api_key, api_secret)
                        payload = {
                            "message": {
                                "to": dest_phone,
                                "from": sender_ph,
                                "text": direct_msg_input
                            }
                        }
                        try:
                            resp = requests.post(url, headers=headers, json=payload, timeout=10)
                            res_data = resp.json()
                            if resp.status_code in [200, 201]:
                                st.success(f"✅ [{selected_direct_worker}] 님에게 즉시 메시지 전송이 완료되었습니다! (전화번호: {dest_phone})")
                            else:
                                st.error(f"❌ 전송 실패 (코드 {resp.status_code}): {res_data}")
                        except Exception as ex:
                            st.error(f"전송 실패: {ex}")
                    else:
                        st.warning("⚠️ 선택한 근무자의 유효한 전화번호를 찾을 수 없습니다.")

    with sub_k2:
        st.markdown("#### 근무자 연락처 및 수신 동의 등록부")
        
        with st.form("single_worker_add_form", clear_on_submit=True):
            new_name = st.text_input("성명")
            new_phone = st.text_input("휴대전화번호 (- 제외 또는 포함)")
            new_consent = st.checkbox("문자 수신 동의 여부", value=True)
            
            sms_option = st.selectbox(
                "문자 발송 옵션 설정", 
                ["매일 근무 상관없이 받기", "내 근무에만 받기", "받지 않기"],
                index=0
            )

            submitted_single = st.form_submit_button("💾 근무자 정보 등록", type="primary", use_container_width=True)
            if submitted_single:
                if not new_name.strip() or not new_phone.strip():
                    st.warning("⚠️ 성명과 휴대전화번호를 모두 입력해주세요.")
                else:
                    workers_db.append({
                        "name": new_name.strip(),
                        "phone": new_phone.strip(),
                        "consent_agreed": new_consent,
                        "sms_option": sms_option
                    })
                    save_workers_db(workers_db)
                    st.success(f"✅ [{new_name.strip()}] 님의 연락처가 등록되었습니다.")
                    st.rerun()

        st.divider()
        st.markdown("#### 📄 등록된 근무자 연락처 리스트")
        if workers_db:
            def mask_phone(phone_str):
                p_clean = phone_str.replace("-", "").strip()
                if len(p_clean) >= 10:
                    return f"{p_clean[:3]}-****-{p_clean[7:]}"
                return "***-****-***"

            worker_display_data = []
            for w in workers_db:
                masked_num = mask_phone(w.get('phone', ''))
                consent_txt = "동의" if w.get('consent_agreed', True) else "거부"
                opt_txt = w.get('sms_option', '매일 근무 상관없이 받기')
                worker_display_data.append({
                    "성명": w.get('name'),
                    "전화번호": masked_num,
                    "수신동의": consent_txt,
                    "발송옵션": opt_txt
                })
            
            df_workers_view = pd.DataFrame(worker_display_data)
            st.dataframe(df_workers_view, use_container_width=True, hide_index=True)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            with st.form("delete_worker_form"):
                del_target = st.selectbox("삭제할 근무자 선택", [w['name'] for w in workers_db])
                if st.form_submit_button("선택한 근무자 삭제", use_container_width=True):
                    updated_db = [w for w in workers_db if w['name'] != del_target]
                    save_workers_db(updated_db)
                    st.success(f"✅ [{del_target}] 님의 정보가 삭제되었습니다.")
                    st.rerun()
        else:
            st.info("등록된 근무자 연락처가 없습니다.")

# ---------------------------------------------------------
# [탭 5] 원본 데이터 뷰
# ---------------------------------------------------------
with tab5:
    st.subheader("시트 데이터 원본")
    st.dataframe(df, use_container_width=True)
