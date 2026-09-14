import calendar
imporimport calendar
import datetime
import gc
import glob
import io
import json
import os
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
# 시스템 CSS 적용
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#121212" if is_dark else "#F8F9FA"
main_text_color = "#E0E0E0" if is_dark else "#1A1A1A"
border_color = "#333333" if is_dark else "#E2E8F0"
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
        padding: 0.6rem 10px 1.2rem 10px !important;
        max-width: 520px !important;
        margin: 0 auto !important;
        box-sizing: border-box !important;
    }}

    h1 {{
        font-size: 22px !important;
        margin: 10px 0px 14px 0px !important;
        font-weight: 800 !important;
        color: {main_text_color} !important;
        text-align: center;
    }}

    .setting-box {{
        background-color: {box_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 16px !important;
        padding: 14px 16px !important;
        margin: 10px 0px 14px 0px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }}

    .today-card {{
        background: linear-gradient(135deg, {primary_blue}, #2563EB) !important;
        color: #FFFFFF !important;
        padding: 16px 18px !important;
        border-radius: 16px !important;
        margin-bottom: 16px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
    }}
    .today-card .today-title {{ font-size: 12px !important; font-weight: 800 !important; margin-bottom: 6px !important; color: #E0E7FF !important; text-transform: uppercase; letter-spacing: 0.5px; }}
    .today-card .today-content {{ font-size: 16px !important; font-weight: 800 !important; line-height: 1.4 !important; color: #FFFFFF !important; }}
    .today-card span {{ color: #FEF08A !important; font-size: 17px !important; font-weight: 900 !important; text-decoration: underline; }}

    .month-header-card {{
        background: {box_bg}; border: 1px solid {border_color}; border-radius: 14px; padding: 12px 16px; margin: 12px 0 14px 0; text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    }}
    .month-header-card h2 {{ margin: 0 !important; font-size: 17px !important; font-weight: 800 !important; color: {main_text_color} !important; }}

    [data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{ 
        background-color: {sidebar_bg} !important; color: {main_text_color} !important; 
    }}
    p, span, label, .stMarkdown, h2, h3, h4, h5, h6 {{ color: {main_text_color} !important; }}

    .stButton > button {{
        width: 100% !important; min-height: 40px !important;
        padding: 8px 10px !important; border: 1px solid {border_color} !important; border-radius: 12px !important;
        background-color: {btn_bg} !important; color: {btn_text} !important; font-size: 13px !important; font-weight: 800 !important; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        transition: all 0.2s ease;
    }}
    .stButton > button:hover {{ border-color: {btn_hover_border} !important; background-color: {btn_hover_bg} !important; transform: translateY(-1px); }}

    [data-testid="stHorizontalBlock"] {{
        display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; width: 100% !important; gap: 3px !important; margin: 0 !important; padding: 0 !important;
    }}
    [data-testid="column"] {{
        width: 14.285% !important; max-width: 14.285% !important; min-width: 14.285% !important; flex: 0 0 14.285% !important; padding: 0px !important; margin: 0 !important; box-sizing: border-box !important;
    }}
    div[data-testid="column"] .stButton > button {{
        min-height: 72px !important; max-height: 96px !important; padding: 4px 2px !important; font-size: 10px !important; border-radius: 10px !important;
        display: flex !important; flex-direction: column !important; justify-content: flex-start !important; align-items: center !important; line-height: 1.25 !important;
        width: 100% !important; box-sizing: border-box !important; background-color: {box_bg} !important; border: 1px solid {border_color} !important; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    div[data-testid="column"] .stButton > button:hover {{
        border-color: {primary_blue} !important; box-shadow: 0 3px 8px rgba(0,0,0,0.08);
    }}

    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important; color: {main_text_color} !important; width: 88vw !important; max-width: 380px !important;
        border-radius: 20px !important; padding: 16px 14px !important; border: 1px solid {border_color} !important; margin: auto !important;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
    }}
    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"] {{
        background-color: {input_bg} !important; color: {input_text} !important; border: 1px solid {border_color} !important; border-radius: 10px !important;
    }}
    [data-baseweb="tab-list"] {{
        width: 100% !important; display: flex !important; gap: 4px !important; background-color: {box_bg}; padding: 4px !important; border-radius: 14px; border: 1px solid {border_color};
    }}
    [data-baseweb="tab"] {{
        flex: 1 1 auto !important; padding: 8px 6px !important; font-size: 13px !important; font-weight: 800 !important; text-align: center !important; border-radius: 10px !important; justify-content: center !important;
    }}

    .table-container {{
        width: 100%; max-height: 450px; overflow-x: auto; overflow-y: auto; border: 1px solid {border_color}; border-radius: 12px; background-color: {box_bg}; margin-top: 10px;
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
# [탭 1] 달력 뷰
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
                
                if st.button(f"{t_str} | 1:{info['p1']} | 2:{info['p2']}{memo_s}", key=f"v_{d_str}"):
                    st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(d)})
                    st.rerun()
        else:
            cols_h = st.columns(7)
            h_names = [("일", "#EF4444"), ("월", main_text_color), ("화", main_text_color), ("수", main_text_color), ("목", main_text_color), ("금", main_text_color), ("토", "#3B82F6")]
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

                        if g_cols[c].button(btn_txt, key=f"g_{d_str}"):
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
            color=alt.Color('근무구분:N', scale=alt.Scale(domain=['평일', '금요일', '토요일', '일요일'], range=['#EAB308', '#22C55E', '#3B82F6', '#EF4444']), title='근무 구분'),
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
            <div style="display: flex; justify-content: space-around; background-color: {box_bg}; border: 1px solid {border_color}; border-radius: 12px; padding: 14px; margin-top: 12px; text-align: center;">
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
t datetime
import glob
import io
import json
import os
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# 대한민국 공휴일 라이브러리 예외 처리
try:
    import holidays

    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# DATA 및 data 기본 폴더 보장 생성
os.makedirs("DATA", exist_ok=True)
os.makedirs("data", exist_ok=True)

PERSISTENCE_STATE_PATH = os.path.join("DATA", "edited_duty_schedule.json")
CONFIG_PATH = os.path.join("DATA", "local_config.json")

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
# 1. 하드웨어/기기 개별 설정 저장 및 로드 함수 (웹 공유 방지)
# ---------------------------------------------------------
def load_local_config():
    default_config = {
        "auto_view_type": "🗓️ 가로형 Grid",
        "app_theme": "☀️ 화이트 테마",
        "kakao_api_key": "",
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_config.update(saved)
        except Exception:
            pass
    return default_config

def save_local_config(key, value):
    config = load_local_config()
    config[key] = value
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

local_cfg = load_local_config()

# 세션 상태 초기화
if "is_app_closed" not in st.session_state:
    st.session_state.is_app_closed = False

if "show_settings_dialog" not in st.session_state:
    st.session_state.show_settings_dialog = False

if "show_exit_dialog" not in st.session_state:
    st.session_state.show_exit_dialog = False

if "auto_view_type" not in st.session_state:
    st.session_state.auto_view_type = local_cfg["auto_view_type"]

if "app_theme" not in st.session_state:
    st.session_state.app_theme = local_cfg["app_theme"]

if "kakao_api_key" not in st.session_state:
    st.session_state.kakao_api_key = local_cfg["kakao_api_key"]

# 앱이 종료된 경우 화면 표시
if st.session_state.is_app_closed:
    st.title("👋 시스템이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# 동적 CSS (한 화면에 쏙 들어오는 한눈 핏 레이아웃)
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#0F172A" if is_dark else "#FFFFFF"
main_text_color = "#F8FAFC" if is_dark else "#0F172A"
card_bg = "#1E293B" if is_dark else "#F8FAFC"
border_color = "#334155" if is_dark else "#CBD5E1"
btn_bg = "#1E293B" if is_dark else "#FFFFFF"
btn_text = "#F8FAFC" if is_dark else "#0F172A"
btn_hover_bg = "#334155" if is_dark else "#F1F5F9"
btn_hover_border = "#60A5FA" if is_dark else "#2563EB"
sidebar_bg = "#0B0F19" if is_dark else "#F8FAFC"

dialog_bg = "#1E293B" if is_dark else "#FFFFFF"
input_bg = "#0F172A" if is_dark else "#FFFFFF"
input_text = "#F8FAFC" if is_dark else "#0F172A"

# 테마별 오늘 날짜 하이라이트 스타일 정의
today_highlight_bg = "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)" if is_dark else "linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%)"
today_highlight_text = "#FFFFFF" if is_dark else "#78350F"
today_highlight_border = "2px solid #F59E0B" if is_dark else "2px solid #D97706"

responsive_css = f"""
<style>
    /* 기본 바디 및 컨테이너 최적화 (한 화면 핏) */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        width: 100vw !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }}

    /* 여백 극소화 (스크롤 최소화 및 한 화면 표출) */
    .main .block-container {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        padding-left: 2px !important;
        padding-right: 2px !important;
        padding-top: 0.1rem !important;
        padding-bottom: 0.2rem !important;
        max-width: 100vw !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    h1 {{
        font-size: clamp(16px, 4vw, 24px) !important;
        margin-top: 0px !important;
        padding-top: 0px !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        color: {main_text_color} !important;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{
        color: {main_text_color} !important;
    }}

    p, span, label, .stMarkdown, h1, h2, h3, h4, h5, h6 {{
        color: {main_text_color} !important;
    }}

    .month-header-card {{
        background: { "linear-gradient(135deg, #1E293B 0%, #0F172A 100%)" if is_dark else "linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%)" };
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 3px 8px;
        margin-top: 1px;
        margin-bottom: 4px;
        text-align: center;
    }}
    .month-header-card h2 {{
        margin: 0 !important;
        font-size: clamp(14px, 3.2vw, 18px) !important;
        font-weight: 800 !important;
        color: {"#60A5FA" if is_dark else "#2563EB"} !important;
    }}

    .today-card {{
        background: { "linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%)" if is_dark else "linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%)" };
        color: {"white" if is_dark else "#0F172A"};
        padding: 4px 8px;
        border-radius: 6px;
        border: 1px solid {border_color};
        margin-bottom: 4px;
        width: 100%;
        box-sizing: border-box;
    }}
    
    .today-card span {{
        color: {"#FDE047" if is_dark else "#1D4ED8"} !important;
        font-weight: bold;
    }}

    /* 🚨 콤팩트 셀 버튼 높이 조절 (한 화면 한눈에 보기) */
    .stButton > button {{
        width: 100% !important;
        min-width: 0 !important;
        height: auto !important;
        min-height: 38px !important;
        padding: 2px 1px !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        background-color: {btn_bg} !important;
        color: {btn_text} !important;
        box-sizing: border-box !important;
        text-align: center !important;
        font-size: clamp(6.5px, 1.8vw, 10px) !important;
        font-weight: 500 !important;
        margin: 0 !important;
        white-space: pre-wrap !important;
        word-break: break-all !important;
        overflow-wrap: anywhere !important;
        line-height: 1.1 !important;
    }}

    .stButton > button:hover {{
        border-color: {btn_hover_border} !important;
        background-color: {btn_hover_bg} !important;
    }}

    /* 🚨 7개 컬럼 강제 가로 한 화면 정렬 */
    [data-testid="stHorizontalBlock"] {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        gap: 1px !important;
        margin: 0 !important;
    }}

    [data-testid="column"] {{
        width: 14.285% !important;
        max-width: 14.285% !important;
        min-width: 0 !important;
        flex: 1 1 14.285% !important;
        padding: 0px 0px !important;
        margin: 0 !important;
        box-sizing: border-box !important;
    }}

    [data-testid="stElementContainer"] {{
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }}

    /* 팝업 스타일 */
    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important;
        color: {main_text_color} !important;
        width: clamp(290px, 92vw, 600px) !important;
        max-width: 95vw !important;
        max-height: 88vh !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        overflow-y: auto !important;
        border: 1px solid {border_color} !important;
    }}

    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"] {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border-color: {border_color} !important;
    }}

    /* JS 히든 스와이프 버튼 은닉 */
    .swipe-hidden-container {{
        display: none !important;
        height: 0px !important;
        width: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
        position: absolute !important;
        left: -9999px !important;
    }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# 모바일 터치 스와이프 & 오늘 날짜 테마별 음영 처리 JS
# ---------------------------------------------------------
calendar_enhancer_js = f"""
<script>
(function() {{
    function enhanceCalendarUI() {{
        const doc = window.parent.document;
        if (!doc) return;

        // 1. 스와이프 히든 버튼 숨김
        const buttons = Array.from(doc.querySelectorAll('button'));
        buttons.forEach(btn => {{
            const txt = btn.innerText || '';
            if (txt.includes('HIDDEN_PREV') || txt.includes('HIDDEN_NEXT')) {{
                const container = btn.closest('[data-testid="stElementContainer"]');
                if (container) {{
                    container.style.setProperty('display', 'none', 'important');
                    container.style.setProperty('height', '0px', 'important');
                }}
            }}

            // 2. 오늘 날짜 테마별 개별 음영 및 스타일 적용
            if (txt.includes('🌟') || txt.includes('[오늘]')) {{
                btn.style.setProperty('background', '{today_highlight_bg}', 'important');
                btn.style.setProperty('color', '{today_highlight_text}', 'important');
                btn.style.setProperty('border', '{today_highlight_border}', 'important');
                btn.style.setProperty('font-weight', '800', 'important');
            }}
        }});

        // 3. 7개 컬럼 100% 폭 강제 밀착 (모바일 스크롤 방지)
        const horizBlocks = doc.querySelectorAll('[data-testid="stHorizontalBlock"]');
        horizBlocks.forEach(block => {{
            if (block.children.length === 7) {{
                block.style.setProperty('display', 'flex', 'important');
                block.style.setProperty('flex-direction', 'row', 'important');
                block.style.setProperty('flex-wrap', 'nowrap', 'important');
                block.style.setProperty('width', '100%', 'important');
                block.style.setProperty('max-width', '100%', 'important');
                block.style.setProperty('gap', '1px', 'important');

                Array.from(block.children).forEach(child => {{
                    child.style.setProperty('width', '14.285%', 'important');
                    child.style.setProperty('max-width', '14.285%', 'important');
                    child.style.setProperty('min-width', '0px', 'important');
                    child.style.setProperty('flex', '1 1 14.285%', 'important');
                    child.style.setProperty('padding', '0px', 'important');
                }});
            }}
        }});
    }}

    // 터치 스와이프 감지
    let touchstartX = 0, touchstartY = 0, touchendX = 0, touchendY = 0;
    function triggerMonthChange(dir) {{
        const doc = window.parent.document;
        const buttons = Array.from(doc.querySelectorAll('button'));
        const targetText = dir === 'next' ? 'HIDDEN_NEXT' : 'HIDDEN_PREV';
        const targetBtn = buttons.find(b => b.innerText && b.innerText.includes(targetText));
        if (targetBtn) targetBtn.click();
    }}

    function handleGesture() {{
        const diffX = touchendX - touchstartX;
        const diffY = touchendY - touchstartY;
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {{
            if (diffX < 0) triggerMonthChange('next');
            else triggerMonthChange('prev');
        }}
    }}

    const doc = window.parent.document;
    if (!doc._enhancerAttached) {{
        doc._enhancerAttached = true;
        doc.addEventListener('touchstart', function(e) {{
            touchstartX = e.changedTouches[0].screenX;
            touchstartY = e.changedTouches[0].screenY;
        }}, {{passive: true}});

        doc.addEventListener('touchend', function(e) {{
            touchendX = e.changedTouches[0].screenX;
            touchendY = e.changedTouches[0].screenY;
            handleGesture();
        }}, {{passive: true}});
    }}

    setInterval(enhanceCalendarUI, 200);
}})();
</script>
"""
components.html(calendar_enhancer_js, height=0, width=0)

# ---------------------------------------------------------
# 파일 탐색 및 저장 함수
# ---------------------------------------------------------
def get_initial_excel_file():
    candidates = (
        glob.glob(os.path.join("DATA", "*.xlsx"))
        + glob.glob(os.path.join("data", "*.xlsx"))
        + glob.glob("*.xlsx")
    )
    valid_files = [f for f in candidates if not os.path.basename(f).startswith("~$")]
    return valid_files[0] if valid_files else os.path.join("DATA", "숙직근무표.xlsx")


def save_to_excel_file(df, file_path):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")

        memos = st.session_state.get("memos", {})
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d), ""))

        if "날짜" in save_df.columns:
            cols = ["날짜"] + [c for c in save_df.columns if c != "날짜"]
            save_df = save_df[cols]

        save_df.to_excel(file_path, index=False)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            save_df.to_excel(writer, index=False)
        st.session_state.file_bytes = output.getvalue()
        return True
    except Exception as e:
        st.error(f"엑셀 파일 저장 중 오류가 발생했습니다: {e}")
        return False


def save_app_state(df, sheet_name, memos, batch_patterns=None):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")

        if batch_patterns is None:
            batch_patterns = st.session_state.get("batch_patterns", {})

        state_data = {
            "selected_sheet": sheet_name,
            "memos": memos,
            "batch_patterns": batch_patterns,
            "df_dict": save_df.to_dict(orient="records"),
        }
        with open(PERSISTENCE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

        target_path = st.session_state.get("file_path", get_initial_excel_file())
        save_to_excel_file(df, target_path)
    except Exception as e:
        st.error(f"상태 저장 중 오류가 발생했습니다: {e}")


def load_app_state():
    if os.path.exists(PERSISTENCE_STATE_PATH):
        try:
            with open(PERSISTENCE_STATE_PATH, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            df = pd.DataFrame(state_data["df_dict"])
            if "날짜" in df.columns:
                df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
                cols = ["날짜"] + [c for c in df.columns if c != "날짜"]
                df = df[cols]

            return (
                df,
                state_data.get("selected_sheet", "숙직근무자"),
                state_data.get("memos", {}),
                state_data.get("batch_patterns", {}),
            )
        except Exception:
            return None, None, None, None
    return None, None, None, None


# ---------------------------------------------------------
# 스마트 엑셀 파서
# ---------------------------------------------------------
def load_excel_smart(file_input, selected_sheet=None):
    if isinstance(file_input, bytes):
        file_bytes = file_input
    elif hasattr(file_input, "read"):
        file_bytes = file_input.read()
    else:
        with open(file_input, "rb") as f:
            file_bytes = f.read()

    file_obj = io.BytesIO(file_bytes)
    file_obj.seek(0)
    excel_file = pd.ExcelFile(file_obj)
    sheet_names = excel_file.sheet_names

    target_sheet = selected_sheet
    if not target_sheet or target_sheet not in sheet_names:
        p1 = [s for s in sheet_names if "숙직근무자" in s]
        if p1:
            target_sheet = p1[0]
        else:
            p2 = [
                s
                for s in sheet_names
                if any(k in s for k in ["숙직", "근무자", "근무", "달력", "야근"])
            ]
            target_sheet = p2[0] if p2 else sheet_names[0]

    file_obj.seek(0)
    df_raw = pd.read_excel(file_obj, sheet_name=target_sheet, header=None)

    header_idx = 0
    for idx in range(min(25, len(df_raw))):
        row_values = [str(val).strip() for val in df_raw.iloc[idx].values]
        row_str = " ".join(row_values)
        if any(
            k in row_str
            for k in ["날짜", "일자", "근무일", "Date", "근무자", "성명", "이름"]
        ):
            header_idx = idx
            break

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
        (
            col
            for col in df.columns
            if any(
                k in col.lower()
                for k in ["날짜", "일자", "근무일", "date", "일자/요일"]
            )
        ),
        df.columns[0],
    )
    df.rename(columns={date_col: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    duty_type_col = next(
        (
            c
            for c in df.columns
            if any(
                k in c
                for k in [
                    "근무구분_원본",
                    "근무구분",
                    "구분",
                    "근무유형",
                    "요일구분",
                    "요일",
                ]
            )
        ),
        None,
    )
    df["근무구분_원본"] = (
        df[duty_type_col].astype(str).str.strip() if duty_type_col else "평일"
    )

    cols = list(df.columns)
    p1_col = next(
        (
            c
            for c in cols
            if any(
                k in c
                for k in [
                    "근무자1",
                    "근무자 1",
                    "1근무",
                    "숙직1",
                    "당직1",
                    "성명",
                    "이름",
                ]
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
                k in c for k in ["근무자2", "근무자 2", "2근무", "숙직2", "당직2"]
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
        (c for c in cols if any(k in c for k in ["대직2", "대직자2", "대직 2"])),
        None,
    )

    df["근무자1"] = df[p1_col].astype(str).str.strip() if p1_col else "미지정"
    df["근무자2"] = df[p2_col].astype(str).str.strip() if p2_col else "미지정"
    df["대직1"] = df[sub1_col].astype(str).str.strip() if sub1_col else None
    df["대직2"] = df[sub2_col].astype(str).str.strip() if sub2_col else None
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    memo_col = next((c for c in cols if "메모" in c or "비고" in c), None)
    if memo_col:
        if "memos" not in st.session_state:
            st.session_state.memos = {}
        for _, r in df.iterrows():
            d_str = r["날짜"].strftime("%Y-%m-%d")
            m_val = str(r[memo_col]).strip()
            if m_val and m_val not in ["nan", "None"]:
                st.session_state.memos[d_str] = m_val

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

    reordered_cols = ["날짜"] + [c for c in df.columns if c != "날짜"]
    df = df[reordered_cols]
    return df, target_sheet, sheet_names, df_raw, file_bytes


def get_all_workers_list(df):
    worker_cols = ["근무자1", "근무자2", "대직1", "대직2", "실제근무1", "실제근무2"]
    names = set()
    for col in worker_cols:
        if col in df.columns:
            valid_names = df[col].dropna().astype(str).str.strip()
            for name in valid_names:
                if name and name not in ["미지정", "nan", "None", "NaN"]:
                    names.add(name)
    sorted_names = sorted(list(names))
    return ["(선택 안함)"] + sorted_names + ["(직접 입력)"]


# ---------------------------------------------------------
# 세션 상태 초기화 및 파일 로드
# ---------------------------------------------------------
initial_file = get_initial_excel_file()
if "file_path" not in st.session_state:
    st.session_state.file_path = initial_file

if "file_bytes" not in st.session_state and os.path.exists(initial_file):
    with open(initial_file, "rb") as f:
        st.session_state.file_bytes = f.read()
    st.session_state.file_name = os.path.basename(initial_file)

if "df" not in st.session_state:
    saved_df, saved_sheet, saved_memos, saved_patterns = load_app_state()

    if saved_df is not None:
        st.session_state.df = saved_df
        st.session_state.selected_sheet = saved_sheet
        st.session_state.memos = saved_memos if saved_memos else {}
        st.session_state.batch_patterns = saved_patterns if saved_patterns else {}
        if "file_bytes" in st.session_state:
            _, _, sheet_names, raw_df, _ = load_excel_smart(
                st.session_state.file_bytes, saved_sheet
            )
            st.session_state.sheet_names = sheet_names
            st.session_state.raw_df = raw_df
        else:
            st.session_state.sheet_names = [saved_sheet]
            st.session_state.raw_df = pd.DataFrame()
    elif "file_bytes" in st.session_state:
        parsed_df, used_sheet, sheet_names, raw_df, _ = load_excel_smart(
            st.session_state.file_bytes
        )
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
        if "memos" not in st.session_state:
            st.session_state.memos = {}
        st.session_state.batch_patterns = {}
    else:
        today_date = datetime.date.today()
        dates = pd.date_range(start=today_date.replace(day=1), periods=60, freq="D")
        sample_df = pd.DataFrame({
            "날짜": dates,
            "근무자1": ["우정수", "오기희", "이승헌", "유진수", "이원철"] * 12,
            "근무자2": ["정찬웅", "서진호", "장민우", "우정수", "오기희"] * 12,
            "대직1": [None] * 60,
            "대직2": [None] * 60,
        })
        sample_df["년월"] = sample_df["날짜"].dt.strftime("%Y-%m")
        sample_df["실제근무1"] = sample_df["근무자1"]
        sample_df["실제근무2"] = sample_df["근무자2"]
        cols = ["날짜"] + [c for c in sample_df.columns if c != "날짜"]
        sample_df = sample_df[cols]

        st.session_state.df = sample_df
        st.session_state.sheet_names = ["숙직근무자"]
        st.session_state.selected_sheet = "숙직근무자"
        st.session_state.raw_df = pd.DataFrame()
        st.session_state.memos = {}
        st.session_state.batch_patterns = {}

if "batch_patterns" not in st.session_state:
    st.session_state.batch_patterns = {}


# ---------------------------------------------------------
# 다이얼로그 정의
# ---------------------------------------------------------
@st.dialog("⚠️ 프로그램 종료 확인")
def confirm_exit_dialog():
    st.write("정말로 숙직 근무 관리 시스템을 종료하시겠습니까?")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("❌ 취소", use_container_width=True):
            st.session_state.show_exit_dialog = False
            st.rerun()
    with col_e2:
        if st.button("🔴 예 (종료)", use_container_width=True, type="primary"):
            st.session_state.show_exit_dialog = False
            st.session_state.is_app_closed = True
            st.rerun()


@st.dialog("⚙️ 대시보드 및 근무 관리 설정")
def settings_dialog():
    tab_s1, tab_s2, tab_s3 = st.tabs([
        "🎨 화면 및 테마 설정",
        "🔄 근무자 수동 반복등록",
        "💬 카카오 센더 기능",
    ])

    with tab_s1:
        st.markdown("**:blue[1. 달력 표시 방식 선택]**")
        new_view_type = st.radio(
            "달력 표출 형식",
            options=["🗓️ 가로형 Grid", "📄 세로형 리스트"],
            index=0 if st.session_state.auto_view_type == "🗓️ 가로형 Grid" else 1,
            key="cfg_view_type_radio",
        )

        st.markdown("---")
        st.markdown("**:blue[2. 테마 모드 선택]**")
        new_theme = st.radio(
            "대시보드 테마",
            options=["☀️ 화이트 테마", "🌙 블랙 테마"],
            index=0 if st.session_state.app_theme == "☀️ 화이트 테마" else 1,
            key="cfg_theme_radio",
        )

        if st.button("💾 화면 설정 적용하기", use_container_width=True, type="primary"):
            st.session_state.auto_view_type = new_view_type
            st.session_state.app_theme = new_theme
            save_local_config("auto_view_type", new_view_type)
            save_local_config("app_theme", new_theme)
            st.session_state.show_settings_dialog = False
            st.success("✅ 화면 설정이 저장되었습니다.")
            st.rerun()

    with tab_s2:
        st.markdown("📅 **입력된 근무자만 규칙적으로 순환 등록됩니다.**")
        today_default = datetime.date.today()
        saved_pat = st.session_state.get("batch_patterns", {})

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            start_date_input = st.date_input("시작 날짜", value=today_default, key="dlg_batch_start")
        with col_b2:
            total_days_count = st.number_input("적용 총 일수", min_value=1, max_value=180, value=30, step=1, key="dlg_batch_days")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown("**:blue[근무자 1 패턴]**")
            default_w1_int = saved_pat.get("interval1", 3)
            interval1 = st.number_input("주기(일)", min_value=1, max_value=30, value=int(default_w1_int), key="dlg_w1_int")
            default_w1_slots = saved_pat.get("w1_names", [])
            w1_names = [st.text_input(f"근무자1 순번 {i+1}", value=default_w1_slots[i] if i < len(default_w1_slots) else "", key=f"dlg_w1_{i}").strip() for i in range(int(interval1))]

        with col_p2:
            st.markdown("**:blue[근무자 2 패턴]**")
            default_w2_int = saved_pat.get("interval2", 3)
            interval2 = st.number_input("주기(일)", min_value=1, max_value=30, value=int(default_w2_int), key="dlg_w2_int")
            default_w2_slots = saved_pat.get("w2_names", [])
            w2_names = [st.text_input(f"근무자2 순번 {i+1}", value=default_w2_slots[i] if i < len(default_w2_slots) else "", key=f"dlg_w2_{i}").strip() for i in range(int(interval2))]

        if st.button("💾 반복 순서 저장 및 근무표 반영", use_container_width=True, type="primary"):
            st.session_state.batch_patterns = {
                "interval1": int(interval1),
                "w1_names": w1_names,
                "interval2": int(interval2),
                "w2_names": w2_names,
            }
            df = st.session_state.df
            current_date = start_date_input
            valid_w1 = [n for n in w1_names if n]
            valid_w2 = [n for n in w2_names if n]

            for i in range(int(total_days_count)):
                target_date_ts = pd.Timestamp(current_date)
                match_idx = df[df["날짜"] == target_date_ts].index
                if not match_idx.empty:
                    idx = match_idx[0]
                    if valid_w1:
                        assigned_w1 = valid_w1[i % len(valid_w1)]
                        df.at[idx, "근무자1"] = assigned_w1
                        if pd.isna(df.at[idx, "대직1"]) or str(df.at[idx, "대직1"]).strip() in ["", "nan", "None"]:
                            df.at[idx, "실제근무1"] = assigned_w1
                    if valid_w2:
                        assigned_w2 = valid_w2[i % len(valid_w2)]
                        df.at[idx, "근무자2"] = assigned_w2
                        if pd.isna(df.at[idx, "대직2"]) or str(df.at[idx, "대직2"]).strip() in ["", "nan", "None"]:
                            df.at[idx, "실제근무2"] = assigned_w2
                current_date += datetime.timedelta(days=1)

            st.session_state.df = df
            save_app_state(df, st.session_state.selected_sheet, st.session_state.memos, st.session_state.batch_patterns)
            st.session_state.show_settings_dialog = False
            st.success("✅ 순환 반복 패턴이 반영되었습니다.")
            st.rerun()

    with tab_s3:
        st.markdown("📱 **카카오톡 메시지 발송 설정**")
        kakao_key = st.text_input("카카오 REST API 키", value=st.session_state.kakao_api_key, type="password", key="kakao_key_input")
        if kakao_key != st.session_state.kakao_api_key:
            st.session_state.kakao_api_key = kakao_key
            save_local_config("kakao_api_key", kakao_key)

        send_date = st.date_input("발송 대상 근무 날짜", value=datetime.date.today(), key="kakao_send_date")
        send_date_ts = pd.Timestamp(send_date)
        match_row = st.session_state.df[st.session_state.df["날짜"] == send_date_ts]

        if not match_row.empty:
            r = match_row.iloc[0]
            p1 = r["실제근무1"]
            p2 = r["실제근무2"]
            memo = st.session_state.memos.get(send_date.strftime("%Y-%m-%d"), "없음")
            msg_content = f"📢 [{send_date.strftime('%Y-%m-%d')} 숙직근무 안내]\n- 근무자 1: {p1}\n- 근무자 2: {p2}\n- 메모: {memo}"
        else:
            msg_content = f"📢 [{send_date.strftime('%Y-%m-%d')} 숙직근무 안내]\n해당 날짜의 근무 정보가 없습니다."

        st.text_area("미리보기", value=msg_content, height=100)
        if st.button("💬 나에게 카카오톡 메시지 전송", use_container_width=True, type="primary"):
            if not kakao_key:
                st.warning("⚠️ API 키를 입력해주세요.")
            else:
                try:
                    headers = {"Authorization": f"Bearer {kakao_key}"}
                    payload = {"template_object": json.dumps({"object_type": "text", "text": msg_content, "link": {"web_url": "https://streamlit.io"}})}
                    res = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send", headers=headers, data=payload)
                    if res.status_code == 200:
                        st.success("✅ 전송 성공!")
                    else:
                        st.error(f"❌ 전송 실패 ({res.status_code}): {res.text}")
                except Exception as ex:
                    st.error(f"오류 발생: {ex}")


# ---------------------------------------------------------
# 근무자 수정 다이얼로그
# ---------------------------------------------------------
@st.dialog("✏️ 근무자 수정 및 메모 작성")
def edit_worker_dialog(date_str, duty_info):
    st.write(f"📅 **{date_str} 근무 정보 수정**")

    row_idx = duty_info["idx"]
    curr_row = st.session_state.df.loc[row_idx]
    worker_options = get_all_workers_list(st.session_state.df)

    val_p1 = str(curr_row.get("근무자1", "")) if pd.notnull(curr_row.get("근무자1")) else ""
    val_p2 = str(curr_row.get("근무자2", "")) if pd.notnull(curr_row.get("근무자2")) else ""
    val_sub1 = str(curr_row.get("대직1", "")) if pd.notnull(curr_row.get("대직1")) else ""
    val_sub2 = str(curr_row.get("대직2", "")) if pd.notnull(curr_row.get("대직2")) else ""

    val_p1 = "" if val_p1 in ["nan", "None"] else val_p1
    val_p2 = "" if val_p2 in ["nan", "None"] else val_p2
    val_sub1 = "" if val_sub1 in ["nan", "None"] else val_sub1
    val_sub2 = "" if val_sub2 in ["nan", "None"] else val_sub2

    current_memo = st.session_state.memos.get(date_str, "")

    def get_opt_idx(val):
        return (
            worker_options.index(val)
            if val in worker_options
            else (len(worker_options) - 1 if val else 0)
        )

    with st.form(key=f"dialog_form_{date_str}"):
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            st.markdown("**:blue[근무자 1 / 대직자 1]**")
            p1_sel = st.selectbox("근무자1 선택", options=worker_options, index=get_opt_idx(val_p1), key=f"p1_sel_{date_str}")
            p1_custom = st.text_input("근무자1 직접입력", value=val_p1 if p1_sel == "(직접 입력)" else "", key=f"p1_custom_{date_str}") if p1_sel == "(직접 입력)" else ""

            sub1_sel = st.selectbox("대직자1 선택", options=worker_options, index=get_opt_idx(val_sub1), key=f"sub1_sel_{date_str}")
            sub1_custom = st.text_input("대직자1 직접입력", value=val_sub1 if sub1_sel == "(직접 입력)" else "", key=f"sub1_custom_{date_str}") if sub1_sel == "(직접 입력)" else ""

        with col_f2:
            st.markdown("**:blue[근무자 2 / 대직자 2]**")
            p2_sel = st.selectbox("근무자2 선택", options=worker_options, index=get_opt_idx(val_p2), key=f"p2_sel_{date_str}")
            p2_custom = st.text_input("근무자2 직접입력", value=val_p2 if p2_sel == "(직접 입력)" else "", key=f"p2_custom_{date_str}") if p2_sel == "(직접 입력)" else ""

            sub2_sel = st.selectbox("대직자2 선택", options=worker_options, index=get_opt_idx(val_sub2), key=f"sub2_sel_{date_str}")
            sub2_custom = st.text_input("대직자2 직접입력", value=val_sub2 if sub2_sel == "(직접 입력)" else "", key=f"sub2_custom_{date_str}") if sub2_sel == "(직접 입력)" else ""

        st.divider()
        edit_memo = st.text_area("📌 날짜별 메모 (달력 표출)", value=current_memo, height=70, key=f"edit_memo_{date_str}")

        c_sub1, c_sub2 = st.columns([2, 1])
        with c_sub1:
            submitted = st.form_submit_button("💾 저장 및 반영", use_container_width=True)
        with c_sub2:
            close_dialog = st.form_submit_button("🚪 닫기", use_container_width=True)

        if submitted:
            final_p1 = p1_custom.strip() if p1_sel == "(직접 입력)" else ("" if p1_sel == "(선택 안함)" else p1_sel)
            final_p2 = p2_custom.strip() if p2_sel == "(직접 입력)" else ("" if p2_sel == "(선택 안함)" else p2_sel)
            final_sub1 = sub1_custom.strip() if sub1_sel == "(직접 입력)" else ("" if sub1_sel == "(선택 안함)" else sub1_sel)
            final_sub2 = sub2_custom.strip() if sub2_sel == "(직접 입력)" else ("" if sub2_sel == "(선택 안함)" else sub2_sel)

            st.session_state.df.at[row_idx, "근무자1"] = final_p1
            st.session_state.df.at[row_idx, "근무자2"] = final_p2
            st.session_state.df.at[row_idx, "대직1"] = final_sub1 if final_sub1 else None
            st.session_state.df.at[row_idx, "대직2"] = final_sub2 if final_sub2 else None

            st.session_state.df.at[row_idx, "실제근무1"] = final_sub1 if final_sub1 else final_p1
            st.session_state.df.at[row_idx, "실제근무2"] = final_sub2 if final_sub2 else final_p2
            st.session_state.memos[date_str] = edit_memo.strip()

            st.session_state.df["날짜"] = pd.to_datetime(st.session_state.df["날짜"], errors="coerce")
            st.session_state.df["년월"] = st.session_state.df["날짜"].dt.strftime("%Y-%m")
            st.session_state.df = st.session_state.df.sort_values(by="날짜").reset_index(drop=True)

            save_app_state(st.session_state.df, st.session_state.selected_sheet, st.session_state.memos, st.session_state.batch_patterns)
            st.success("✅ 저장되었습니다.")
            st.rerun()

        if close_dialog:
            st.rerun()


# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 근무표 파일 관리")
    if "file_name" in st.session_state:
        st.info(f"📄 파일: `{st.session_state.file_name}`")

    uploaded_file = st.file_uploader("새 엑셀 업로드", type=["xlsx"])
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        save_path = os.path.join("DATA", uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        parsed_df, used_sheet, sheet_names, raw_df, f_bytes = load_excel_smart(file_bytes)

        st.session_state.file_path = save_path
        st.session_state.file_bytes = f_bytes
        st.session_state.file_name = uploaded_file.name
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df

        save_app_state(parsed_df, used_sheet, st.session_state.get("memos", {}), st.session_state.get("batch_patterns", {}))
        st.success("✅ 파일 로드 완료")
        st.rerun()

    if "file_bytes" in st.session_state and st.session_state.file_bytes:
        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=st.session_state.file_bytes,
            file_name=st.session_state.get("file_name", "숙직근무표_수정본.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()
    if st.button("🔴 앱종료", use_container_width=True):
        st.session_state.show_exit_dialog = True
        st.rerun()

if st.session_state.show_settings_dialog:
    settings_dialog()

if st.session_state.show_exit_dialog:
    confirm_exit_dialog()

df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 화면 - 제목 및 설정 버튼 상단 배치
# ---------------------------------------------------------
col_title, col_settings = st.columns([0.82, 0.18])
with col_title:
    st.title("📋 숙직 근무 관리 대시보드")
with col_settings:
    st.write("")
    if st.button("⚙️ 설정", use_container_width=True, type="secondary", key="main_top_settings_btn"):
        st.session_state.show_settings_dialog = True
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs([
    "📅 달력 메인 화면",
    "✏️ 근무표 전체 수정",
    "📊 월별 근무 통계",
    "🔍 시트 데이터 점검",
])

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면
# ---------------------------------------------------------
with tab1:
    today_df = df[df["날짜"].dt.date == today]
    today_str = today.strftime("%Y년 %m월 %d일")

    if not today_df.empty:
        t_row = today_df.iloc[0]
        p1 = f"{t_row['실제근무1']}(대)" if pd.notnull(t_row.get("대직1")) and str(t_row.get("대직1")).strip() else t_row["실제근무1"]
        p2 = f"{t_row['실제근무2']}(대)" if pd.notnull(t_row.get("대직2")) and str(t_row.get("대직2")).strip() else t_row["실제근무2"]
        t_memo = st.session_state.memos.get(today.strftime("%Y-%m-%d"), "")
        memo_str = f" | 📌 {t_memo}" if t_memo else ""

        st.markdown(
            f"""
        <div class="today-card">
            <div style="font-size:11px; opacity:0.9;">🚨 오늘 근무자 ({today_str})</div>
            <div style="font-size:13px; font-weight:bold;">
                1: <span>{p1}</span> | 2: <span>{p2}</span>
                <span style="font-size:11px; font-weight:normal;">{memo_str}</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    available_months = sorted(df["년월"].dropna().unique())
    if not available_months:
        available_months = [today.strftime("%Y-%m")]

    current_ym = today.strftime("%Y-%m")

    if "selected_month" not in st.session_state or st.session_state.selected_month not in available_months:
        st.session_state.selected_month = current_ym if current_ym in available_months else available_months[0]

    if "calendar_month_select" not in st.session_state or st.session_state.calendar_month_select not in available_months:
        st.session_state.calendar_month_select = st.session_state.selected_month

    def on_month_change_select():
        st.session_state.selected_month = st.session_state.calendar_month_select

    def go_prev_month():
        curr_idx = available_months.index(st.session_state.selected_month)
        if curr_idx > 0:
            new_m = available_months[curr_idx - 1]
            st.session_state.selected_month = new_m
            st.session_state.calendar_month_select = new_m

    def go_next_month():
        curr_idx = available_months.index(st.session_state.selected_month)
        if curr_idx < len(available_months) - 1:
            new_m = available_months[curr_idx + 1]
            st.session_state.selected_month = new_m
            st.session_state.calendar_month_select = new_m

    st.markdown('<div class="swipe-hidden-container">', unsafe_allow_html=True)
    st.button("HIDDEN_PREV", key="btn_hidden_prev", on_click=go_prev_month)
    st.button("HIDDEN_NEXT", key="btn_hidden_next", on_click=go_next_month)
    st.markdown('</div>', unsafe_allow_html=True)

    selected_month = st.selectbox(
        "📅 조회 월 선택",
        available_months,
        key="calendar_month_select",
        on_change=on_month_change_select,
        label_visibility="collapsed",
    )
    st.session_state.selected_month = selected_month

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
        st.markdown(
            f"""
            <div class="month-header-card">
                <h2>🗓️ {year}년 {month}월 숙직 근무표</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        num_days = calendar.monthrange(year, month)[1]
        month_df = df[df["년월"] == selected_month].copy()

        duty_map = {}
        for idx_row, row in month_df.iterrows():
            d_day = row["날짜"].day
            d_date_str = row["날짜"].strftime("%Y-%m-%d")

            sub1_val = str(row["대직1"]).strip() if pd.notnull(row["대직1"]) else ""
            sub2_val = str(row["대직2"]).strip() if pd.notnull(row["대직2"]) else ""

            p1_display = str(row["실제근무1"])
            if sub1_val and sub1_val not in ["nan", "None", ""]:
                p1_display += "(대)"

            p2_display = str(row["실제근무2"])
            if sub2_val and sub2_val not in ["nan", "None", ""]:
                p2_display += "(대)"

            duty_map[d_day] = {
                "idx": idx_row,
                "date_str": d_date_str,
                "p1_display": p1_display,
                "p2_display": p2_display,
            }

        calendar_view_type = st.session_state.auto_view_type

        if calendar_view_type == "📄 세로형 리스트":
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
            for day in range(1, num_days + 1):
                curr_date = datetime.date(year, month, day)
                date_str = curr_date.strftime("%Y-%m-%d")
                weekday_idx = curr_date.weekday()
                weekday_str = weekdays_kr[weekday_idx]
                duty_info = duty_map.get(day)

                is_today = (curr_date == today)

                if is_today:
                    day_title = f"🌟 [오늘] {day:02d}일({weekday_str})"
                elif weekday_idx == 6 or curr_date in kr_holidays:
                    day_title = f"🔴 {day:02d}일({weekday_str})"
                elif weekday_idx == 5:
                    day_title = f"🔵 {day:02d}일({weekday_str})"
                else:
                    day_title = f"🗓️ {day:02d}일({weekday_str})"

                p1_txt = duty_info["p1_display"] if duty_info else "미지정"
                p2_txt = duty_info["p2_display"] if duty_info else "미지정"
                day_memo = st.session_state.memos.get(date_str, "")
                memo_display = f" | 📌 {day_memo}" if day_memo else ""

                btn_label = f"{day_title} | 1:{p1_txt} | 2:{p2_txt}{memo_display}"

                if st.button(btn_label, key=f"btn_v_card_{date_str}"):
                    if duty_info:
                        edit_worker_dialog(date_str, duty_info)
        else:
            # 🗓️ 모바일 세로 7열 한눈에 들어오는 가로 달력 레이아웃
            cols_header = st.columns(7)
            color_sun = "#FF6B6B" if is_dark else "#DC2626"
            color_sat = "#38BDF8" if is_dark else "#2563EB"
            color_weekday = "#F1F5F9" if is_dark else "#0F172A"

            headers = [
                ("일", color_sun), ("월", color_weekday), ("화", color_weekday),
                ("수", color_weekday), ("목", color_weekday), ("금", color_weekday), ("토", color_sat),
            ]

            for idx, (h_name, color) in enumerate(headers):
                cols_header[idx].markdown(
                    f"<div style='text-align: center; color: {color}; font-weight: bold; font-size: clamp(10px, 2.2vw, 13px); padding-bottom: 2px;'>{h_name}</div>",
                    unsafe_allow_html=True,
                )

            first_day_weekday = calendar.monthrange(year, month)[0]
            start_offset = (first_day_weekday + 1) % 7
            day_counter = 1
            total_cells = start_offset + num_days
            num_rows = (total_cells + 6) // 7

            for r in range(num_rows):
                grid_cols = st.columns(7)
                for c in range(7):
                    cell_index = r * 7 + c
                    if cell_index < start_offset or day_counter > num_days:
                        grid_cols[c].write("")
                    else:
                        curr_date = datetime.date(year, month, day_counter)
                        date_str = curr_date.strftime("%Y-%m-%d")
                        duty_info = duty_map.get(day_counter)

                        p1_txt = duty_info["p1_display"] if duty_info else "-"
                        p2_txt = duty_info["p2_display"] if duty_info else "-"
                        day_memo = st.session_state.memos.get(date_str, "")

                        is_today = (curr_date == today)
                        day_label = f"🌟{day_counter}일" if is_today else f"{day_counter}일"

                        cell_lines = [day_label, p1_txt, p2_txt]
                        if day_memo:
                            cell_lines.append(f"📌{day_memo}")

                        btn_text = "\n".join(cell_lines)

                        if grid_cols[c].button(btn_text, key=f"btn_grid_card_{date_str}"):
                            if duty_info:
                                edit_worker_dialog(date_str, duty_info)
                        day_counter += 1

# ---------------------------------------------------------
# TAB 2: 근무표 전체 수정
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 전체 근무표 수정")
    edit_months = ["전체 기간"] + sorted(df["년월"].dropna().unique())
    current_ym = today.strftime("%Y-%m")
    default_edit_idx = edit_months.index(current_ym) if current_ym in edit_months else 0

    col_ctrl1, col_ctrl2 = st.columns([1, 1])
    with col_ctrl1:
        selected_edit_month = st.selectbox("📅 근무 월 선택 검색", edit_months, index=default_edit_idx, key="edit_month_filter")

    target_editor_df = st.session_state.df.copy() if selected_edit_month == "전체 기간" else st.session_state.df[st.session_state.df["년월"] == selected_edit_month].copy()

    if "날짜" in target_editor_df.columns:
        cols = ["날짜"] + [c for c in target_editor_df.columns if c != "날짜"]
        target_editor_df = target_editor_df[cols]

    with col_ctrl2:
        st.write("")
        save_btn_clicked = st.button("💾 변경사항 적용 및 엑셀 저장", key="top_save_btn", use_container_width=True, type="primary")

    edited_df = st.data_editor(target_editor_df, num_rows="dynamic", key=f"data_editor_{selected_edit_month}", use_container_width=True)

    if save_btn_clicked:
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df = edited_df.dropna(subset=["날짜"]).copy()
        edited_df["년월"] = edited_df["날짜"].dt.strftime("%Y-%m")

        edited_df["실제근무1"] = edited_df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(edited_df["근무자1"]).fillna("미지정")
        edited_df["실제근무2"] = edited_df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(edited_df["근무자2"]).fillna("미지정")

        full_df = edited_df if selected_edit_month == "전체 기간" else pd.concat([st.session_state.df[st.session_state.df["년월"] != selected_edit_month], edited_df], ignore_index=True)
        full_df["날짜"] = pd.to_datetime(full_df["날짜"], errors="coerce")
        full_df["년월"] = full_df["날짜"].dt.strftime("%Y-%m")
        full_df = full_df.sort_values(by="날짜").reset_index(drop=True)
        
        cols = ["날짜"] + [c for c in full_df.columns if c != "날짜"]
        st.session_state.df = full_df[cols]

        save_app_state(st.session_state.df, st.session_state.selected_sheet, st.session_state.memos, st.session_state.batch_patterns)
        st.success("✅ 저장되었습니다.")
        st.rerun()

# ---------------------------------------------------------
# TAB 3: 월별 근무 통계
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 숙직근무자 월별 근무 통계")
    duty_stat_df = st.session_state.df.copy()
    available_stat_months = ["전체 기간"] + sorted(duty_stat_df["년월"].dropna().unique(), reverse=True)
    default_stat_idx = available_stat_months.index(current_ym) if current_ym in available_stat_months else 0

    stat_col1, stat_col2 = st.columns([1, 2])
    with stat_col1:
        selected_stat_month = st.selectbox("📅 통계조회 월선택", available_stat_months, index=default_stat_idx, key="stat_month_select")

    filtered_df = duty_stat_df.copy() if selected_stat_month == "전체 기간" else duty_stat_df[duty_stat_df["년월"] == selected_stat_month].copy()
    w1 = filtered_df[["실제근무1", "근무구분_원본"]].rename(columns={"실제근무1": "근무자", "근무구분_원본": "근무구분"})
    w2 = filtered_df[["실제근무2", "근무구분_원본"]].rename(columns={"실제근무2": "근무자", "근무구분_원본": "근무구분"})
    combined = pd.concat([w1, w2], ignore_index=True)
    combined["근무자"] = combined["근무자"].astype(str).str.strip()
    combined["근무구분"] = combined["근무구분"].astype(str).str.strip()
    combined = combined[combined["근무자"].notnull() & (~combined["근무자"].isin(["미지정", "nan", "None", "", "NaN"]))]

    if not combined.empty:
        stats_df = pd.crosstab(index=combined["근무자"], columns=combined["근무구분"], margins=False)
        sat_cnt = stats_df["토요일"] if "토요일" in stats_df.columns else 0
        sun_cnt = stats_df["일요일"] if "일요일" in stats_df.columns else 0
        stats_df["휴일근무 횟수"] = sat_cnt + sun_cnt

        hours_per_type = {"금요일": 15, "토요일": 15, "일요일": 7, "평일": 7}
        total_hours = pd.Series(0, index=stats_df.index)
        for col in stats_df.columns:
            if col in hours_per_type:
                total_hours += stats_df[col] * hours_per_type[col]
            elif col not in ["총 근무 횟수", "휴일근무 횟수"]:
                total_hours += stats_df[col] * 7

        stats_df["총 근무시간(h)"] = total_hours
        type_cols = [c for c in stats_df.columns if c not in ["총 근무 횟수", "휴일근무 횟수", "총 근무시간(h)"]]
        stats_df["총 근무 횟수"] = stats_df[type_cols].sum(axis=1)
        stats_df = stats_df[type_cols + ["휴일근무 횟수", "총 근무 횟수", "총 근무시간(h)"]].sort_values(by="총 근무시간(h)", ascending=False)

        m1, m2, m3 = st.columns(3)
        m1.metric("총 근무 인원", f"{len(stats_df)}명")
        m2.metric("총 근무건수 합계", f"{int(stats_df['총 근무 횟수'].sum())}건")
        m3.metric("총 근무시간 합계", f"{int(stats_df['총 근무시간(h)'].sum())}시간")
        st.markdown("---")
        st.dataframe(stats_df, use_container_width=True)
    else:
        st.info("조회할 근무 정보가 없습니다.")

# ---------------------------------------------------------
# TAB 4: 시트 데이터 점검
# ---------------------------------------------------------
with tab4:
    st.subheader("🔍 시트 데이터 원본 확인")
    st.dataframe(df, use_container_width=True)
