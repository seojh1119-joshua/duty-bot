import calendar
import datetime
import gc
import glob
import io
import json
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
        "kakao_access_token": "",
        "current_user_name": "관리자",
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
    ("kakao_access_token", local_cfg.get("kakao_access_token", "")),
    ("current_user_name", local_cfg.get("current_user_name", "관리자")),
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
btn_hover_border = "#FFE300" if is_dark else "#CBD5E0"
sidebar_bg = "#181818" if is_dark else "#FFFFFF"
dialog_bg = "#1E1E1E" if is_dark else "#FFFFFF"
input_bg = "#272727" if is_dark else "#FFFFFF"
input_text = "#F5F5F5" if is_dark else "#1E1E1E"
box_bg = "#1E1E1E" if is_dark else "#FFFFFF"
primary_yellow = "#FFE300"

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
        background: linear-gradient(135deg, {primary_yellow}, #FFC107) !important;
        color: #1A1A1A !important;
        padding: 16px 18px !important;
        border-radius: 16px !important;
        margin-bottom: 16px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        box-shadow: 0 4px 12px rgba(255, 227, 0, 0.25);
    }}
    .today-card .today-title {{ font-size: 12px !important; font-weight: 800 !important; margin-bottom: 6px !important; color: #594D00 !important; text-transform: uppercase; letter-spacing: 0.5px; }}
    .today-card .today-content {{ font-size: 16px !important; font-weight: 800 !important; line-height: 1.4 !important; color: #1A1A1A !important; }}
    .today-card span {{ color: #1A1A1A !important; font-size: 17px !important; font-weight: 900 !important; text-decoration: underline; }}

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
        display: flex !important; 
        flex-direction: row !important; 
        flex-wrap: nowrap !important; 
        width: 100% !important; 
        gap: 3px !important; 
        margin: 0 !important; 
        padding: 0 !important;
    }}
    [data-testid="column"] {{
        width: 14.285% !important; 
        max-width: 14.285% !important; 
        min-width: 14.285% !important; 
        flex: 0 0 14.285% !important; 
        padding: 0px !important; 
        margin: 0 !important;
        box-sizing: border-box !important;
    }}
    div[data-testid="column"] .stButton > button {{
        min-height: 72px !important; 
        max-height: 96px !important; 
        padding: 4px 2px !important; 
        font-size: 10px !important; 
        border-radius: 10px !important;
        display: flex !important; 
        flex-direction: column !important; 
        justify-content: flex-start !important; 
        align-items: center !important; 
        line-height: 1.25 !important;
        width: 100% !important;
        box-sizing: border-box !important;
        background-color: {box_bg} !important;
        border: 1px solid {border_color} !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    div[data-testid="column"] .stButton > button:hover {{
        border-color: {primary_yellow} !important;
        box-shadow: 0 3px 8px rgba(0,0,0,0.08);
    }}
    .stButton > button span, .stButton > button p, .stButton > button div {{
        white-space: pre-wrap !important; word-wrap: break-word !important; word-break: break-all !important; overflow: hidden !important;
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
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

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
    return df[["날짜"] + [c for c in df.columns if c != "날짜"]], target_sheet, sheet_names, df_raw, file_bytes

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
    tab_s1, tab_s2, tab_s3 = st.tabs(["화면 설정", "순환 등록", "카카오 설정"])
    
    with tab_s1:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        new_view = st.radio("달력 표출 형식", ["🗓️ 가로형 Grid", "📄 세로형 리스트"], index=0 if st.session_state.auto_view_type == "🗓️ 가로형 Grid" else 1)
        new_th = st.radio("대시보드 테마", ["☀️ 화이트 테마", "🌙 블랙 테마"], index=0 if st.session_state.app_theme == "☀️ 화이트 테마" else 1)
        curr_user = st.text_input("현재 기기 사용자명 (내 이름)", value=st.session_state.current_user_name, placeholder="예: 관리자, 홍길동")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("화면 설정 적용", use_container_width=True, type="primary"):
            st.session_state.update({
                "auto_view_type": new_view, 
                "app_theme": new_th, 
                "current_user_name": curr_user,
                "show_settings_dialog": False
            })
            save_local_config("auto_view_type", new_view)
            save_local_config("app_theme", new_th)
            save_local_config("current_user_name", curr_user)
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
        k_token = st.text_input("카카오 사용자 액세스 토큰 (Access Token)", value=st.session_state.kakao_access_token, type="password", placeholder="REST API 키가 아닌 '사용자 액세스 토큰'을 입력하세요")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("토큰 저장", use_container_width=True, type="primary"):
            st.session_state.kakao_access_token = k_token
            save_local_config("kakao_access_token", k_token)
            st.session_state.show_settings_dialog = False
            st.success("✅ 카카오 액세스 토큰이 저장되었습니다.")
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

# 탭 구조 구성
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 달력", "✏️ 수정", "📊 통계", "💬 카카오톡", "🔍 원본"])

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

    sel_month = st.selectbox(
        "조회 월 선택", 
        avail_months, 
        index=avail_months.index(st.session_state.selected_month) if st.session_state.selected_month in avail_months else 0,
        label_visibility="collapsed"
    )
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
    target_df = df.copy() if sel_ed_m == "전체 기간" else df[df["년월"] == sel_ed_m].copy()

    edited_df = st.data_editor(target_df, num_rows="dynamic", key="editor_main", use_container_width=True)

    if st.button("변경사항 일괄 저장", use_container_width=True, type="primary"):
        m_df = edited_df.copy() if sel_ed_m == "전체 기간" else st.session_state.df.copy()
        if sel_ed_m != "전체 기간": m_df.update(edited_df)
            
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
# [탭 3] 통계 뷰 (버전 호환성 수정된 Alt 차트 반영)
# ---------------------------------------------------------
with tab3:
    st.subheader("근무자 월별 통계 및 근무 구분 분석")
    stat_ms = sorted(df["년월"].dropna().unique(), reverse=True)
    default_stat_idx = stat_ms.index(cur_ym) if cur_ym in stat_ms else 0
    
    sel_st_m = st.selectbox("통계 월 선택", ["전체 기간"] + stat_ms, index=default_stat_idx + 1 if cur_ym in stat_ms else 0)
    f_df = df.copy() if sel_st_m == "전체 기간" else df[df["년월"] == sel_st_m]
    
    def get_category_and_hours(row):
        wd = pd.to_datetime(row["날짜"]).weekday()
        if wd in [0, 1, 2, 3]:
            return "평일", 7
        elif wd == 4:
            return "금요일", 15
        elif wd == 5:
            return "토요일", 15
        else:
            return "일요일", 7

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
        
        # alt.SortField를 사용하여 최신 Altair 라이브러리 호환성 오류 해결
        chart = alt.Chart(agg_df).mark_bar().encode(
            x=alt.X('근무자:N', 
                    sort=alt.SortField(field='근무시간', op='sum', order='descending'), 
                    title='근무자',
                    axis=alt.Axis(labelAngle=0, labelOverlap=False)),
            y=alt.Y('근무시간:Q', title='총 근무시간 (시간)'),
            color=alt.Color('근무구분:N',
                            scale=alt.Scale(
                                domain=['평일', '금요일', '토요일', '일요일'],
                                range=['#EAB308', '#22C55E', '#3B82F6', '#EF4444']
                            ),
                            title='근무 구분'),
            tooltip=['근무자', '근무구분', '근무횟수', '근무시간']
        ).properties(
            height=340
        ).configure_legend(
            orient='bottom',
            direction='horizontal',
            title='근무 구분'
        )
        st.altair_chart(chart, use_container_width=True)
        
       st.subheader("📊 근무자별 숙직 통계 및 시각화")

# 데이터 존재 여부 확인 후 그래프렌더링
if "df_stats" in locals() and not df_stats.empty:
  # Altair 스택바 차트 구성
  chart = (
      alt.Chart(df_stats)
      .mark_bar()
      .encode(
          # X축: 근무자 이름 (총 근무 시간 순으로 정렬)
          x=alt.X(
              "근무자:N",
              sort=alt.EncodingSortField(
                  field="시간", op="sum", order="descending"
              ),
              title="근무자",
          ),
          # Y축: 총 근무 시간 (0~70시간으로 고정)
          y=alt.Y(
              "sum(시간):Q",
              scale=alt.Scale(domain=[0, 70]),
              title="총 근무 시간 (시간)",
          ),
          # 색상: 근무 유형별 구분 (평일, 금요일, 토요일, 일요일 등)
          color=alt.Color("근무유형:N", title="근무 유형"),
          tooltip=["근무자", "근무유형", "sum(시간)"],
      )
      .properties(height=400)
      .configure_axisX(labelAngle=0)  # X축 글자 겹침 방지 (가로 정렬)
      .configure_legend(
          orient="bottom", title=None
      )  # 범례를 하단으로 이동하고 제목 숨김 처리
  )

  # Streamlit에 차트 출력
  st.altair_chart(chart, use_container_width=True)
else:
  st.info("시각화할 통계 데이터가 존재하지 않습니다.")
# ---------------------------------------------------------
# [탭 4] 카카오톡 탭
# ---------------------------------------------------------
with tab4:
    st.subheader("💬 카카오톡 알림 및 근무자 연락처 관리")
    st.markdown("화면에서 직접 근무자 명단, 휴대폰 번호, 수신 동의 여부를 1열(세로형)로 입력하고 관리할 수 있습니다.")

    workers_db = load_workers_db()

    sub_k1, sub_k2 = st.tabs(["📋 근무자 정보 직접 입력 관리", "🚀 카카오 알림 발송"])

    with sub_k1:
        st.markdown("#### 근무자 연락처 및 수신 동의 편집기")
        st.markdown("아래 입력창에 근무자 이름, 휴대폰 번호, 수신 동의 여부를 세로(1열) 형식으로 입력하세요.")

        if "edit_workers_list" not in st.session_state:
            if workers_db:
                st.session_state.edit_workers_list = [dict(w) for w in workers_db]
            else:
                st.session_state.edit_workers_list = [{"name": "", "phone": "", "consent_agreed": True}]

        with st.form("dynamic_workers_form"):
            updated_workers = []
            for i, w_item in enumerate(st.session_state.edit_workers_list):
                st.markdown(f"**근무자 #{i+1}**")
                n_val = st.text_input(f"성명 (근무자 #{i+1})", value=w_item.get("name", ""), placeholder="이름 입력", key=f"dyn_name_{i}")
                p_val = st.text_input(f"휴대폰 번호 (근무자 #{i+1})", value=w_item.get("phone", ""), placeholder="01012345678", key=f"dyn_phone_{i}")
                c_val = st.checkbox(f"알림 수신 동의 여부 (근무자 #{i+1})", value=w_item.get("consent_agreed", True), key=f"dyn_consent_{i}")
                
                updated_workers.append({"name": n_val, "phone": p_val, "consent_agreed": c_val})
                st.divider()

            add_row_btn = st.form_submit_button("➕ 근무자 추가하기", use_container_width=True)
            save_db_btn = st.form_submit_button("💾 입력한 정보 최종 저장", type="primary", use_container_width=True)

            if add_row_btn:
                st.session_state.edit_workers_list = updated_workers + [{"name": "", "phone": "", "consent_agreed": True}]
                st.rerun()

            if save_db_btn:
                valid_db = [w for w in updated_workers if w["name"].strip()]
                save_workers_db(valid_db)
                st.session_state.edit_workers_list = valid_db
                st.success("✅ 근무자 연락처 및 수신 동의 정보가 성공적으로 저장되었습니다.")
                st.rerun()

    with sub_k2:
        st.markdown("#### 당일 근무 안내 알림 발송 및 옵션 설정")
        
        current_device_user = st.session_state.get("current_user_name", "관리자")
        st.info(f"현재 접속 중인 기기 사용자 (내): **{current_device_user}** (설정 메뉴에서 변경 가능)")

        target_send_date = st.date_input("알림 대상 일자", value=datetime.date.today(), key="kakao_target_send_date")
        target_str = target_send_date.strftime("%Y-%m-%d")

        matched_row = df[df["날짜"].dt.date == target_send_date]
        m_p1, m_p2 = "미지정", "미지정"
        if not matched_row.empty:
            r_info = matched_row.iloc[0]
            m_p1 = r_info.get("실제근무1", "미지정")
            m_p2 = r_info.get("실제근무2", "미지정")
            st.info(f"📌 **{target_str}** 근무표 당번 -> 1근무: **{m_p1}** | 2근무: **{m_p2}**")
        else:
            st.warning(f"⚠️ {target_str}에 해당하는 근무 정보가 없습니다.")

        send_option = st.radio(
            "발송 대상 옵션 선택", 
            ["모든 근무일 수신 (전체 수신 동의자 대상)", "내 근무일만 수신 (당일 근무자 중 동의한 대상자만)"]
        )

        access_token_input = st.text_input("카카오 사용자 액세스 토큰 (Access Token)", value=st.session_state.kakao_access_token, type="password", key="kakao_tab_token", placeholder="여기에 REST API 키가 아닌 '사용자 액세스 토큰'을 입력하세요")
        if access_token_input != st.session_state.kakao_access_token:
            st.session_state.kakao_access_token = access_token_input
            save_local_config("kakao_access_token", access_token_input)
            
        default_msg = f"[광주교도소 의료과 숙직 안내]\n일자: {target_str}\n- 1근무: {m_p1}\n- 2근무: {m_p2}"
        custom_msg = st.text_area("전송할 메시지 내용", value=default_msg)

        if st.button("📤 카카오톡 나에게 메시지 전송", type="primary", use_container_width=True):
            if access_token_input:
                url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
                headers = {"Authorization": f"Bearer {access_token_input}", "Content-Type": "application/x-www-form-urlencoded"}
                
                personalized_msg = f"[{current_device_user} 기기 알림]\n{custom_msg}"
                
                template = {
                    "object_type": "text",
                    "text": personalized_msg[:200],
                    "link": {"web_url": "", "mobile_web_url": ""},
                    "button_title": "일정 확인"
                }
                resp = requests.post(url, headers=headers, data={"template_object": json.dumps(template, ensure_ascii=False)})
                
                if resp.status_code == 200:
                    st.success(f"✅ [{current_device_user}] 카카오톡 '나에게 보내기' 전송 성공!")
                else:
                    try:
                        err_json = resp.json()
                        err_code = err_json.get("code")
                        err_msg = err_json.get("msg")
                        st.error(f"❌ 카카오 API 에러 발생 (HTTP {resp.status_code}, 코드: {err_code})\n- 내용: {err_msg}")
                    except:
                        st.error(f"❌ 전송 실패 (코드 {resp.status_code}): {resp.text}")
            else:
                st.warning("⚠️ 카카오 사용자 액세스 토큰이 입력되지 않았습니다. (REST API 키가 아닌 액세스 토큰을 입력해야 합니다)")

        st.divider()

        if st.button("🚀 조건별 동의 근무자에게 알림 일괄 발송", use_container_width=True):
            current_db = load_workers_db()
            consented_workers = [w for w in current_db if w.get("consent_agreed", False)]
            
            if send_option == "내 근무일만 수신 (당일 근무자 중 동의한 대상자만)":
                target_names = [str(m_p1).strip(), str(m_p2).strip()]
                final_targets = [w for w in consented_workers if w.get("name") in target_names]
            else:
                final_targets = consented_workers

            if not final_targets:
                st.warning("발송 조건에 부합하는 동의 근무자가 없습니다. (근무자 정보 관리 탭에서 이름을 등록하고 동의 체크를 확인하세요.)")
            else:
                target_names_str = ", ".join([f"{w['name']}({w['phone']})" for w in final_targets])
                st.info(f"📨 발송 대상자: **{target_names_str}** (총 {len(final_targets)}명)")
                
                if access_token_input:
                    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
                    headers = {"Authorization": f"Bearer {access_token_input}", "Content-Type": "application/x-www-form-urlencoded"}
                    template = {
                        "object_type": "text",
                        "text": f"[근무 안내 알림]\n{custom_msg}",
                        "link": {"web_url": "", "mobile_web_url": ""},
                        "button_title": "일정 확인"
                    }
                    resp = requests.post(url, headers=headers, data={"template_object": json.dumps(template, ensure_ascii=False)})
                    if resp.status_code == 200:
                        st.success(f"✅ 선택된 옵션에 따라 [{target_str}] 근무 안내 알림이 성공적으로 전송되었습니다!")
                    else:
                        try:
                            err_json = resp.json()
                            err_code = err_json.get("code")
                            err_msg = err_json.get("msg")
                            st.error(f"❌ 카카오 API 에러 발생 (HTTP {resp.status_code}, 코드: {err_code})\n- 내용: {err_msg}")
                        except:
                            st.error(f"❌ 알림 발송 실패 (코드 {resp.status_code}): {resp.text}")
                else:
                    st.error("카카오 사용자 액세스 토큰이 입력되지 않았습니다.")

# ---------------------------------------------------------
# [탭 5] 원본 데이터 뷰
# ---------------------------------------------------------
with tab5:
    st.subheader("시트 데이터 원본")
    st.dataframe(df, use_container_width=True)
