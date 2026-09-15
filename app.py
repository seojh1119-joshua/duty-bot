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

try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

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

st.set_page_config(
    page_title="광주교도소 의료과 숙직근무",
    page_icon="📋",
    layout="centered",
    initial_sidebar_state="expanded",
)

def load_local_config():
    default_config = {
        "auto_view_type": "🗓️ 9:16 가로형 프레임", 
        "app_theme": "☀️ 화이트 테마", 
        "kakao_access_token": "",
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
    ("uploader_key", 0), ("upload_success_msg", ""),
    ("active_tab_idx", 0)
]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.is_app_closed:
    st.title("👋 앱이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# 9:16 비율 싱글 프레임 및 모바일 최적화 CSS
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#0F172A" if is_dark else "#F8FAFC"
main_text_color = "#F8FAFC" if is_dark else "#0F172A"
card_bg = "#1E293B" if is_dark else "#FFFFFF"
border_color = "#334155" if is_dark else "#CBD5E1"
btn_bg = "#1E293B" if is_dark else "#FFFFFF"
btn_text = "#F8FAFC" if is_dark else "#0F172A"
btn_hover_bg = "#334155" if is_dark else "#F1F5F9"
btn_hover_border = "#60A5FA" if is_dark else "#2563EB"
sidebar_bg = "#0B0F19" if is_dark else "#F8FAFC"

responsive_css = f"""
<style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
    }}
    .main .block-container {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        padding: 0.2rem 0.5rem !important;
        max-width: 440px !important;
        margin: 0 auto !important;
        box-sizing: border-box !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        color: {main_text_color} !important;
    }}
    p, span, label, .stMarkdown, h1, h2, h3, h4 {{
        color: {main_text_color} !important;
    }}
    .phone-container {{
        background: {card_bg};
        border: 2px solid {border_color};
        border-radius: 20px;
        padding: 10px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        margin-bottom: 10px;
    }}
    .month-header-card {{
        background: { "linear-gradient(135deg, #1E293B 0%, #0F172A 100%)" if is_dark else "linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%)" };
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 4px 8px;
        margin-bottom: 6px;
        text-align: center;
    }}
    .month-header-card h2 {{
        margin: 0 !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        color: {"#60A5FA" if is_dark else "#1D4ED8"} !important;
    }}
    .today-card {{
        background: { "linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%)" if is_dark else "linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%)" };
        color: {"white" if is_dark else "#0F172A"};
        padding: 6px 10px;
        border-radius: 6px;
        border: 1px solid {border_color};
        margin-bottom: 6px;
        font-size: 11px;
    }}
    .today-card span {{
        color: {"#FDE047" if is_dark else "#1D4ED8"} !important;
        font-weight: bold;
    }}
    /* 9:16 프레임 내 달력 버튼 컴팩트 디자인 */
    .stButton > button {{
        width: 100% !important;
        height: 48px !important;
        min-height: 48px !important;
        padding: 1px !important;
        margin: 0px !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px !important;
        background-color: {btn_bg} !important;
        color: {btn_text} !important;
        font-size: 9px !important;
        line-height: 1.15 !important;
        font-weight: 500 !important;
        white-space: pre-wrap !important;
        word-break: break-all !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
    }}
    .stButton > button:hover {{
        border-color: {btn_hover_border} !important;
        background-color: {btn_hover_bg} !important;
    }}
    [data-testid="stHorizontalBlock"] {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: stretch !important;
        width: 100% !important;
        gap: 1.5px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    [data-testid="column"] {{
        min-width: 0 !important;
        padding: 0px !important;
        margin: 0 !important;
        flex: 1 1 14.285% !important;
    }}
    .table-container {{
        width: 100%;
        max-height: 400px;
        overflow: auto;
        border: 1px solid {border_color};
        border-radius: 8px;
    }}
    .sticky-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }}
    .sticky-table th, .sticky-table td {{
        padding: 6px 8px;
        border-bottom: 1px solid {border_color};
        text-align: center;
        white-space: nowrap;
    }}
    .sticky-table th {{
        background-color: {card_bg};
        position: sticky;
        top: 0;
        z-index: 3;
    }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# 데이터베이스 및 엑셀 영구 저장 유틸 함수
# ---------------------------------------------------------
def get_initial_excel_file():
    candidates = glob.glob(os.path.join("data", "*.xlsx")) + glob.glob(os.path.join("DATA", "*.xlsx")) + glob.glob("*.xlsx")
    valid_files = [f for f in candidates if not os.path.basename(f).startswith("~$")]
    if valid_files:
        return valid_files[0]
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", "숙직근무표.xlsx")

def update_excel_download_bytes(df):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        memos = st.session_state.get("memos", {})
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d)[:10], ""))
        
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
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d)[:10], ""))
        
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        if os.path.exists(file_path):
            try:
                with pd.ExcelWriter(file_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    save_df.to_excel(writer, index=False, sheet_name=sheet_name)
            except Exception:
                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                    save_df.to_excel(writer, index=False, sheet_name=sheet_name)
        else:
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                save_df.to_excel(writer, index=False, sheet_name=sheet_name)
                
        update_excel_download_bytes(df)
        return True
    except Exception as e:
        st.sidebar.warning(f"⚠️ 엑셀 저장 실패: {e}")
        return False

def save_app_state(df_target, sheet_name, memos_dict):
    try:
        os.makedirs("DATA", exist_ok=True)
        state_data = {
            "memos": memos_dict,
            "selected_sheet": sheet_name,
            "last_saved": str(datetime.datetime.now())
        }
        with open(PERSISTENCE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        save_to_excel_file(df_target, st.session_state.file_path, sheet_name)
    except Exception as e:
        st.sidebar.warning(f"⚠️ 앱 상태 저장 실패: {e}")

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
    
    # M열(13번째 열, 인덱스 12) 값 반영
    if len(df.columns) > 12:
        m_col_name = df.columns[12]
        df["M열구분"] = df[m_col_name].astype(str).str.strip().replace(["nan", "None", "nat", "NaT"], "")
    else:
        df["M열구분"] = ""

    base_cols = ["날짜", "근무자1", "대직1", "근무자2", "대직2", "실제근무1", "실제근무2", "M열구분"]
    other_cols = [c for c in df.columns if c not in base_cols and c != "년월"]
    ordered_cols = base_cols + other_cols + ["년월"]
    
    return df[ordered_cols], target_sheet, sheet_names, df_raw, file_bytes

initial_file = get_initial_excel_file()
if "file_path" not in st.session_state: st.session_state.file_path = initial_file

if "df" not in st.session_state:
    loaded_memos = {}
    if os.path.exists(PERSISTENCE_STATE_PATH):
        try:
            with open(PERSISTENCE_STATE_PATH, "r", encoding="utf-8") as f:
                saved_state = json.load(f)
                loaded_memos = saved_state.get("memos", {})
        except:
            pass

    if os.path.exists(initial_file):
        with open(initial_file, "rb") as f: 
            b_data = f.read()
        parsed_df, used_sheet, sheet_names, raw_df, _ = load_excel_smart(b_data)
        st.session_state.update({
            "file_bytes": b_data, "file_name": os.path.basename(initial_file),
            "df": parsed_df, "selected_sheet": used_sheet, "sheet_names": sheet_names, 
            "raw_df": raw_df, "memos": loaded_memos
        })
    else:
        dates = pd.date_range(start=datetime.date.today().replace(day=1), periods=60, freq="D")
        empty_df = pd.DataFrame({
            "날짜": dates, "근무자1": "미지정", "대직1": None, "근무자2": "미지정", "대직2": None,
            "실제근무1": "미지정", "실제근무2": "미지정", "M열구분": "", "년월": dates.strftime("%Y-%m")
        })
        st.session_state.update({
            "file_bytes": b"".encode(), "file_name": "숙직근무표.xlsx",
            "df": empty_df, "selected_sheet": "숙직근무자", "sheet_names": ["숙직근무자"], 
            "raw_df": empty_df, "memos": loaded_memos
        })
        save_to_excel_file(empty_df, initial_file, "숙직근무자")

update_excel_download_bytes(st.session_state.df)

# ---------------------------------------------------------
# 다이얼로그 모음
# ---------------------------------------------------------
@st.dialog("⚠️ 프로그램 종료 확인")
def confirm_exit_dialog():
    st.write("정말로 시스템을 종료하시겠습니까?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("취소", use_container_width=True, key="exit_cancel_btn"): 
            st.session_state.show_exit_dialog = False
            st.rerun()
    with c2:
        if st.button("종료", use_container_width=True, type="primary", key="exit_confirm_btn"):
            st.session_state.update({"show_exit_dialog": False, "is_app_closed": True})
            st.rerun()

@st.dialog("⚙️ 화면 및 순환근무 설정 관리")
def settings_dialog():
    tab_s1, tab_s2, tab_s3 = st.tabs(["화면 설정", "순환근무 등록", "카카오톡 연동"])
    
    with tab_s1:
        st.markdown("#### 📱 프레임 화면 설정")
        new_view = st.radio("달력 표출 형식", ["🗓️ 9:16 가로형 프레임", "📄 세로형 리스트"], index=0 if st.session_state.auto_view_type == "🗓️ 9:16 가로형 프레임" else 1, key="dlg_view_radio")
        new_th = st.radio("대시보드 테마", ["☀️ 화이트 테마", "🌙 블랙 테마"], index=0 if st.session_state.app_theme == "☀️ 화이트 테마" else 1, key="dlg_theme_radio")

        if st.button("화면 설정 적용", use_container_width=True, type="primary", key="dlg_apply_view_btn"):
            st.session_state.update({"auto_view_type": new_view, "app_theme": new_th, "show_settings_dialog": False})
            save_local_config("auto_view_type", new_view)
            save_local_config("app_theme", new_th)
            st.rerun()

    with tab_s2:
        st.markdown("#### 🔄 순환근무 패턴 자동 등록")
        cfg = load_local_config()
        try:
            default_start_date = datetime.datetime.strptime(cfg.get("batch_start_date", str(datetime.date.today())), "%Y-%m-%d").date()
        except:
            default_start_date = datetime.date.today()

        start_d = st.date_input("시작 날짜", value=default_start_date, key="batch_start_date_input")
        infinite_repeat = st.checkbox("연말까지 무한 순환", value=cfg.get("batch_infinite", False), key="batch_infinite_input")
        days_c = st.number_input("적용 일수", min_value=1, max_value=365, value=int(cfg.get("batch_days_c", 30)), disabled=infinite_repeat, key="batch_days_c_input")
        
        i1 = st.number_input("근무자1 주기 인원수", 1, 30, int(cfg.get("batch_i1", 3)), key="batch_i1_input")
        saved_w1 = cfg.get("batch_w1_names", ["", "", ""])
        w1_names = [st.text_input(f"1조 - 근무자 {i+1}", value=saved_w1[i] if i < len(saved_w1) else "", key=f"w1_{i}").strip() for i in range(int(i1))]
        
        i2 = st.number_input("근무자2 주기 인원수", 1, 30, int(cfg.get("batch_i2", 3)), key="batch_i2_input")
        saved_w2 = cfg.get("batch_w2_names", ["", "", ""])
        w2_names = [st.text_input(f"2조 - 근무자 {i+1}", value=saved_w2[i] if i < len(saved_w2) else "", key=f"w2_{i}").strip() for i in range(int(i2))]

        if st.button("🔄 순환근무 반영 및 저장", use_container_width=True, type="primary", key="dlg_apply_batch_btn"):
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
            delta_days = (datetime.date(start_d.year, 12, 31) - start_d).days + 1 if infinite_repeat else int(days_c)

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
            st.success("✅ 순환근무 패턴 반영 완료!")
            st.rerun()

    with tab_s3:
        st.markdown("#### 💬 카카오톡 개인 계정 연동")
        k_token = st.text_input("카카오 액세스 토큰", value=st.session_state.kakao_access_token, type="password", key="dlg_kakao_token_input")
        if st.button("토큰 저장", use_container_width=True, type="primary", key="dlg_save_token_btn"):
            st.session_state.kakao_access_token = k_token.strip()
            save_local_config("kakao_access_token", k_token.strip())
            st.session_state.show_settings_dialog = False
            st.success("✅ 토큰이 저장되었습니다.")
            st.rerun()

@st.dialog("✏️ 근무자 및 메모 수정")
def edit_worker_dialog(date_str, duty_info):
    st.markdown(f"### 🗓️ {date_str} 근무 관리")
    if duty_info is None or "idx" not in duty_info or duty_info["idx"] not in st.session_state.df.index:
        st.error("정보를 찾을 수 없습니다.")
        if st.button("닫기", use_container_width=True, key="edit_err_close_btn"):
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
        p1_s = st.selectbox("근무자1", worker_options, index=get_idx(curr_p1), key=f"f_p1_{date_str}")
        p1_c = st.text_input("근무자1 직접입력", value=curr_p1 if p1_s == "(직접 입력)" else "", key=f"f_p1c_{date_str}") if p1_s == "(직접 입력)" else ""
        sub1_s = st.selectbox("대직자1", worker_options, index=get_idx(curr_sub1), key=f"f_sub1_{date_str}")
        sub1_c = st.text_input("대직1 직접입력", value=curr_sub1 if sub1_s == "(직접 입력)" else "", key=f"f_sub1c_{date_str}") if sub1_s == "(직접 입력)" else ""

        p2_s = st.selectbox("근무자2", worker_options, index=get_idx(curr_p2), key=f"f_p2_{date_str}")
        p2_c = st.text_input("근무자2 직접입력", value=curr_p2 if p2_s == "(직접 입력)" else "", key=f"f_p2c_{date_str}") if p2_s == "(직접 입력)" else ""
        sub2_s = st.selectbox("대직자2", worker_options, index=get_idx(curr_sub2), key=f"f_sub2_{date_str}")
        sub2_c = st.text_input("대직2 직접입력", value=curr_sub2 if sub2_s == "(직접 입력)" else "", key=f"f_sub2c_{date_str}") if sub2_s == "(직접 입력)" else ""
        
        memo_in = st.text_area("일자별 메모", value=st.session_state.memos.get(date_str, ""), key=f"f_memo_{date_str}")
        
        submitted = st.form_submit_button("💾 저장 (엑셀 덮어쓰기)", use_container_width=True, type="primary")
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
        
        if memo_in.strip(): 
            st.session_state.memos[date_str] = memo_in.strip()
        else: 
            st.session_state.memos.pop(date_str, None)
        
        save_app_state(st.session_state.df, st.session_state.selected_sheet, st.session_state.memos)
        st.session_state.update({"editing_date": None, "editing_duty_info": None})
        st.success("✅ 엑셀 파일에 성공적으로 덮어쓰여졌습니다!")
        st.rerun()

    if closed:
        st.session_state.update({"editing_date": None, "editing_duty_info": None})
        st.rerun()

# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 파일 관리")
    if "file_name" in st.session_state: 
        st.info(f"📄 `{st.session_state.file_name}`")
    
    up_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"], key=f"file_uploader_{st.session_state.uploader_key}")
    if up_file:
        f_bytes = up_file.getvalue()
        save_p = os.path.join("data", up_file.name)
        with open(save_p, "wb") as f: 
            f.write(f_bytes)
        
        parsed_df, used_s, s_names, r_df, _ = load_excel_smart(f_bytes, "숙직근무자")
        st.session_state.update({
            "file_path": save_p, "file_bytes": f_bytes, "file_name": up_file.name,
            "df": parsed_df, "selected_sheet": used_s, "sheet_names": s_names, "raw_df": r_df,
            "upload_success_msg": "✅ 업로드 완료!"
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
    if st.button("🏠 달력 홈", use_container_width=True):
        st.session_state.active_tab_idx = 0
        st.rerun()
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

# 메인 상단 헤더
col_title, col_settings = st.columns([0.78, 0.22])
with col_title:
    st.title("광주교도소 의료과")
with col_settings:
    st.write("")
    if st.button("⚙️ 설정", use_container_width=True, type="secondary"):
        st.session_state.show_settings_dialog = True
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 달력", "✏️ 수정", "📊 통계", "💬 알림", "🔍 원본"])

with tab1:
    st.session_state.active_tab_idx = 0
    
    col_c1, col_c2 = st.columns([0.55, 0.45])
    with col_c1:
        avail_months = sorted(df["년월"].dropna().unique()) or [today.strftime("%Y-%m")]
        cur_ym = today.strftime("%Y-%m")
        if "selected_month" not in st.session_state or st.session_state.selected_month not in avail_months:
            st.session_state.selected_month = cur_ym if cur_ym in avail_months else avail_months[0]
        sel_month = st.selectbox("월 선택", avail_months, index=avail_months.index(st.session_state.selected_month) if st.session_state.selected_month in avail_months else 0, key="cal_month_sel")
        st.session_state.selected_month = sel_month
    with col_c2:
        view_mode_choice = st.radio("방식", ["🗓️ 가로", "📄 세로"], index=0 if st.session_state.auto_view_type == "🗓️ 9:16 가로형 프레임" else 1, horizontal=True, key="cal_mode_rad")
        st.session_state.auto_view_type = "🗓️ 9:16 가로형 프레임" if view_mode_choice == "🗓️ 가로" else "📄 세로형 리스트"

    today_df = df[df["날짜"].dt.date == today]
    if not today_df.empty:
        tr = today_df.iloc[0]
        sub1_t = str(tr.get("대직1", "")).strip() if pd.notnull(tr.get("대직1")) else ""
        sub2_t = str(tr.get("대직2", "")).strip() if pd.notnull(tr.get("대직2")) else ""
        p1 = f"{tr['실제근무1']}(대)" if sub1_t and sub1_t not in ["nan", "None", ""] else tr["실제근무1"]
        p2 = f"{tr['실제근무2']}(대)" if sub2_t and sub2_t not in ["nan", "None", ""] else tr["실제근무2"]
        memo_txt = f" | 📌 {st.session_state.memos.get(today.strftime('%Y-%m-%d'), '')}" if st.session_state.memos.get(today.strftime('%Y-%m-%d')) else ""
        st.markdown(f'<div class="today-card"><b>오늘 ({today.strftime("%m/%d")})</b> 1: <span>{p1}</span> | 2: <span>{p2}</span>{memo_txt}</div>', unsafe_allow_html=True)

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
                
            m_val = str(row.get("M열구분", "")).strip()
            if m_val in ["nan", "None", "NaT", "nat"]: m_val = ""
            duty_map[row["날짜"].day] = {"idx": i, "p1": p1_name, "p2": p2_name, "m_val": m_val}

        # 9:16 싱글 프레임 박스 내부 감싸기
        st.markdown('<div class="phone-container">', unsafe_allow_html=True)
        if st.session_state.auto_view_type == "📄 세로형 리스트":
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
            for d in range(1, num_days + 1):
                c_date = datetime.date(y, m, d)
                d_str = c_date.strftime("%Y-%m-%d")
                weekday_str = weekdays_kr[c_date.weekday()]
                info = duty_map.get(d, {"p1": "-", "p2": "-", "m_val": ""})
                
                is_today = (c_date == today)
                m_val = info["m_val"]
                t_str = f"🌟 [오늘] {d:02d}({weekday_str})" if is_today else (f"[{m_val}] {d:02d}({weekday_str})" if m_val else f"🗓️ {d:02d}({weekday_str})")
                memo_s = f" | 📌 {st.session_state.memos.get(d_str, '')}" if st.session_state.memos.get(d_str) else ""
                
                if st.button(f"{t_str} | 1:{info['p1']} 2:{info['p2']}{memo_s}", key=f"list_btn_{d_str}"):
                    st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(d)})
                    st.rerun()
        else:
            cols_h = st.columns(7)
            h_names = [("일", "#EF4444"), ("월", main_text_color), ("화", main_text_color), ("수", main_text_color), ("목", main_text_color), ("금", main_text_color), ("토", "#3B82F6")]
            for idx, (h_n, col_c) in enumerate(h_names):
                cols_h[idx].markdown(f"<div style='text-align: center; color: {col_c}; font-weight: 800; font-size: 10px; padding: 1px 0;'>{h_n}</div>", unsafe_allow_html=True)

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
                        info = duty_map.get(day_cnt, {"p1": "-", "p2": "-", "m_val": ""})
                        memo_val = st.session_state.memos.get(d_str, "").strip()
                        m_val = info.get("m_val", "")
                        
                        is_today = (c_date == today)
                        w_idx = c_date.weekday()
                        day_color = "#EF4444" if (w_idx == 6 or c_date in kr_holidays) else ("#3B82F6" if w_idx == 5 else main_text_color)

                        prefix = "🌟" if is_today else (f"[{m_val}]" if m_val else "")
                        t_header = f"{prefix}{day_cnt}"
                        
                        btn_txt = f"<span style='color:{day_color}; font-weight:bold;'>{t_header}</span>\n1:{info['p1']}\n2:{info['p2']}"
                        if memo_val: btn_txt += f"\n📌"

                        if g_cols[c].button(btn_txt, key=f"grid_btn_{d_str}"):
                            st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(day_cnt)})
                            st.rerun()
                        day_cnt += 1
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.session_state.active_tab_idx = 1
    st.subheader("전체 근무표 에디터")
    edit_ms = ["전체 기간"] + sorted(df["년월"].dropna().unique())
    sel_ed_m = st.selectbox("월", edit_ms, index=edit_ms.index(cur_ym) if cur_ym in edit_ms else 0)
    
    preferred_order = ["날짜", "근무자1", "대직1", "근무자2", "대직2", "실제근무1", "실제근무2", "M열구분"]
    display_cols = [c for c in preferred_order if c in df.columns]
    target_df = df[display_cols].copy() if sel_ed_m == "전체 기간" else df[df["년월"] == sel_ed_m][display_cols].copy()

    column_configs = {}
    if "날짜" in display_cols:
        column_configs["날짜"] = st.column_config.DateColumn("날짜", format="YYYY-MM-DD", disabled=True)

    edited_df = st.data_editor(target_df, num_rows="dynamic", key="editor_main_data_table", use_container_width=True, column_config=column_configs)

    if st.button("변경사항 저장", use_container_width=True, type="primary"):
        m_df = st.session_state.df.copy()
        if sel_ed_m == "전체 기간":
            for idx in edited_df.index:
                if idx in m_df.index:
                    for col in edited_df.columns:
                        if col != "날짜": m_df.loc[idx, col] = edited_df.loc[idx, col]
        else:
            sub_indices = m_df[m_df["년월"] == sel_ed_m].index
            for i, idx in enumerate(sub_indices):
                if i < len(edited_df):
                    ed_idx = edited_df.index[i]
                    for col in edited_df.columns:
                        if col != "날짜": m_df.loc[idx, col] = edited_df.loc[ed_idx, col]
            
        if "날짜" in m_df.columns:
            m_df["날짜"] = pd.to_datetime(m_df["날짜"], errors="coerce")
            m_df["년월"] = m_df["날짜"].dt.strftime("%Y-%m")
            
        p1, p2 = m_df["근무자1"].astype(str).str.strip(), m_df["근무자2"].astype(str).str.strip()
        sub1, sub2 = m_df["대직1"].astype(str).str.strip(), m_df["대직2"].astype(str).str.strip()
        m_df["실제근무1"] = sub1.replace(["", "nan", "None"], None).combine_first(p1).fillna("미지정")
        m_df["실제근무2"] = sub2.replace(["", "nan", "None"], None).combine_first(p2).fillna("미지정")
        
        st.session_state.df = m_df
        save_app_state(m_df, st.session_state.selected_sheet, st.session_state.memos)
        st.success("✅ 저장 완료!")
        st.rerun()

with tab3:
    st.session_state.active_tab_idx = 2
    st.subheader("통계 분석")
    stat_ms = sorted(df["년월"].dropna().unique(), reverse=True)
    sel_st_m = st.selectbox("통계 월", ["전체 기간"] + stat_ms, index=0)
    f_df = df.copy() if sel_st_m == "전체 기간" else df[df["년월"] == sel_st_m]
    
    cat_col = next((c for c in f_df.columns if "구분" in c and c != "년월" and c != "M열구분"), None)

    expanded_rows = []
    duty_dates = set()
    for _, r in f_df.iterrows():
        cat = str(r[cat_col]).strip() if cat_col and pd.notnull(r[cat_col]) and str(r[cat_col]).strip() not in ["", "nan", "None"] else "평일"
        hours = 7 if "평일" in cat or "주간" in cat else 15
        
        w1, w2 = str(r.get("실제근무1", "")).strip(), str(r.get("실제근무2", "")).strip()
        if w1 and w1 not in ["미지정", "nan", "None", ""]: expanded_rows.append({"근무자": w1, "근무구분": cat, "근무시간": hours, "횟수": 1})
        if w2 and w2 not in ["미지정", "nan", "None", ""]: expanded_rows.append({"근무자": w2, "근무구분": cat, "근무시간": hours, "횟수": 1})
        if (w1 or w2) and pd.notnull(r.get("날짜")): duty_dates.add(pd.to_datetime(r["날짜"]).date())

    if expanded_rows:
        exp_df = pd.DataFrame(expanded_rows)
        agg_df = exp_df.groupby(["근무자", "근무구분"]).agg(근무횟수=("횟수", "sum"), 근무시간=("근무시간", "sum")).reset_index()

        chart = alt.Chart(agg_df).mark_bar().encode(
            x=alt.X('근무자:N', sort=alt.EncodingSortField(field='근무시간', op='sum', order='descending')),
            y=alt.Y('근무시간:Q', title='시간'),
            color='근무구분:N',
            tooltip=['근무자', '근무구분', '근무횟수', '근무시간']
        ).properties(height=280).configure_legend(orient="bottom")
        st.altair_chart(chart, use_container_width=True)

with tab4:
    st.session_state.active_tab_idx = 3
    st.subheader("💬 카카오톡 알림 전송")
    target_send_date = st.date_input("알림 대상 일자", value=datetime.date.today())
    target_str = target_send_date.strftime("%Y-%m-%d")

    matched_row = df[df["날짜"].dt.date == target_send_date]
    m_p1, m_p2 = "미지정", "미지정"
    if not matched_row.empty:
        r_info = matched_row.iloc[0]
        m_p1, m_p2 = r_info.get("실제근무1", "미지정"), r_info.get("실제근무2", "미지정")
        st.info(f"📌 {target_str} -> 1근무: **{m_p1}** | 2근무: **{m_p2}**")

    default_kakao_msg = f"[광주교도소 의료과] {target_str} 숙직 안내\n- 1근무: {m_p1}\n- 2근무: {m_p2}"
    custom_kakao_msg = st.text_area("메시지 내용", value=default_kakao_msg, height=100)

    if st.button("📤 카카오톡 나에게 전송", type="primary", use_container_width=True):
        access_token = st.session_state.get("kakao_access_token", "").strip()
        if not access_token:
            st.warning("⚠️ [⚙️ 설정]에서 카카오 토큰을 먼저 입력해주세요.")
        else:
            url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
            payload = {"template_object": json.dumps({"object_type": "text", "text": custom_kakao_msg, "link": {"web_url": "https://developers.kakao.com", "mobile_web_url": "https://developers.kakao.com"}}, ensure_ascii=False)}
            try:
                resp = requests.post(url, headers=headers, data=payload, timeout=10)
                if resp.status_code in [200, 201]:
                    st.success("🎉 전송 성공!")
                else:
                    st.error(f"❌ 전송 실패: {resp.text}")
            except Exception as ex:
                st.error(f"❌ 오류: {ex}")

with tab5:
    st.session_state.active_tab_idx = 4
    st.subheader("원본 데이터")
    st.dataframe(df, use_container_width=True)
