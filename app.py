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

# ---------------------------------------------------------
# 자동 메모리 및 로그 정제 함수
# ---------------------------------------------------------
def cleanup_memory_and_logs():
    """불필요한 세션 로그 정제 및 메모리 가비지 컬렉션 실행"""
    if "memos" in st.session_state and isinstance(st.session_state.memos, dict):
        st.session_state.memos = {k: v for k, v in st.session_state.memos.items() if v and str(v).strip()}
    gc.collect()

cleanup_memory_and_logs()

os.makedirs("DATA", exist_ok=True)
os.makedirs("data", exist_ok=True)

PERSISTENCE_STATE_PATH = os.path.join("DATA", "edited_duty_schedule.json")
CONFIG_PATH = os.path.join("DATA", "local_config.json")

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
    default_config = {"auto_view_type": "🗓️ 가로형 Grid", "app_theme": "☀️ 화이트 테마", "kakao_api_key": ""}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                default_config.update(json.load(f))
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

# 세션 상태 초기화
for k, v in [
    ("is_app_closed", False), ("show_settings_dialog", False), ("show_exit_dialog", False),
    ("editing_date", None), ("editing_duty_info", None),
    ("auto_view_type", local_cfg["auto_view_type"]), ("app_theme", local_cfg["app_theme"]),
    ("kakao_api_key", local_cfg["kakao_api_key"]), ("batch_patterns", {})
]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.is_app_closed:
    st.title("👋 앱이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# 닌텐도 디자인 시스템 기반 동적 CSS 및 모바일 맞춤 스타일
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

# 닌텐도 토큰 색상 매핑 (nintendo-dark.md 기반)
theme_bg = "#1A1A1A" if is_dark else "#FFFFFF"
main_text_color = "#FFFFFF" if is_dark else "#1A1A1A"
border_color = "#3A3A3A" if is_dark else "#F0F0F0"
btn_bg = "#2D2D2D" if is_dark else "#FAFAFA"
btn_text = "#FFFFFF" if is_dark else "#1A1A1A"
btn_hover_bg = "#3A3A3A" if is_dark else "#F0F0F0"
btn_hover_border = "#FF606A" if is_dark else "#E60012"
sidebar_bg = "#161618" if is_dark else "#FAFAFA"
dialog_bg = "#2D2D2D" if is_dark else "#FFFFFF"
input_bg = "#2D2D2D" if is_dark else "#FAFAFA"
input_text = "#FFFFFF" if is_dark else "#1A1A1A"
box_bg = "#2D2D2D" if is_dark else "#FAFAFA"
primary_accent = "#FF606A" if is_dark else "#E60012"

today_highlight_bg = "linear-gradient(135deg, #FF3644 0%, #C90010 100%)" if is_dark else "linear-gradient(135deg, #FFE9EA 0%, #FFC4C7 100%)"
today_highlight_text = "#FFFFFF" if is_dark else "#8C000A"
today_highlight_border = "2px solid #FF606A" if is_dark else "2px solid #E60012"

responsive_css = f"""
<style>
    [data-testid="stSidebarNav"] {{ z-index: 100000 !important; }}
    [data-testid="collapsedControl"] {{ z-index: 99999 !important; top: 5px !important; }}
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
        -webkit-tap-highlight-color: transparent !important;
        font-family: 'Nintendo Std', 'Arial Rounded MT Bold', 'Pretendard', sans-serif !important;
    }}

    .main .block-container {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        padding: 0.2rem 2px 0.1rem 2px !important;
        max-width: 100vw !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    h1 {{
        font-size: clamp(26px, 6.5vw, 36px) !important;
        margin: 10px 0px 20px 0px !important;
        padding: 4px 0px !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        text-align: center !important;
        color: {primary_accent} !important;
        letter-spacing: -0.02em !important;
    }}

    .setting-box {{
        background-color: {box_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 20px !important;
        padding: 12px 16px !important;
        margin: 14px 0px 18px 0px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.40) !important;
    }}

    .today-card {{
        background: { "linear-gradient(135deg, #2D2D2D 0%, #1A1A1A 100%)" if is_dark else "linear-gradient(135deg, #FAFAFA 0%, #F0F0F0 100%)" } !important;
        color: {main_text_color} !important;
        padding: 14px 16px !important;
        border-radius: 20px !important;
        border: 2px solid {primary_accent} !important;
        margin-bottom: 16px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        box-shadow: 0 6px 18px rgba(230,0,18,0.2) !important;
    }}
    .today-card .today-title {{ 
        font-size: clamp(16px, 4.5vw, 20px) !important; 
        font-weight: 700 !important; 
        margin-bottom: 6px !important;
        color: {primary_accent} !important;
    }}
    .today-card .today-content {{ 
        font-size: clamp(17px, 5vw, 23px) !important; 
        font-weight: 700 !important; 
        line-height: 1.4 !important;
    }}
    .today-card span {{ 
        color: {primary_accent} !important; 
        font-size: clamp(18px, 5.2vw, 24px) !important;
        font-weight: 700 !important; 
    }}

    .month-header-card {{
        background: { "linear-gradient(135deg, #2D2D2D 0%, #1A1A1A 100%)" if is_dark else "linear-gradient(135deg, #FAFAFA 0%, #F0F0F0 100%)" };
        border: 1px solid {border_color}; border-radius: 14px; padding: 8px 10px; margin: 6px 0 10px 0; text-align: center;
    }}
    .month-header-card h2 {{ 
        margin: 0 !important; 
        font-size: clamp(20px, 5.5vw, 28px) !important; 
        font-weight: 700 !important; 
        color: {primary_accent} !important; 
    }}

    [data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{ background-color: {sidebar_bg} !important; color: {main_text_color} !important; }}
    p, span, label, .stMarkdown, h2, h3, h4, h5, h6 {{ color: {main_text_color} !important; }}

    .stButton > button {{
        width: 100% !important; min-width: 0 !important; height: auto !important; min-height: 38px !important;
        padding: 8px 12px !important; border: 1.5px solid {border_color} !important; border-radius: 14px !important;
        background-color: {btn_bg} !important; color: {btn_text} !important; box-sizing: border-box !important;
        text-align: center !important; font-size: 14px !important; font-weight: 700 !important; margin: 0 !important;
        cursor: pointer !important; transition: transform 150ms ease, box-shadow 150ms ease !important;
    }}

    [data-testid="stHorizontalBlock"] {{
        display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
        width: 100% !important; max-width: 100vw !important; min-width: 0 !important; gap: 2px !important; margin: 0 !important; padding: 0 !important; box-sizing: border-box !important;
    }}
    [data-testid="column"] {{
        width: 14.285% !important; max-width: 14.285% !important; min-width: 0 !important;
        flex: 1 1 14.285% !important; padding: 0px !important; margin: 0 !important; box-sizing: border-box !important;
    }}

    div[data-testid="column"] .stButton > button {{
        min-height: clamp(140px, 28vw, 220px) !important;
        max-height: 280px !important;
        padding: 4px 2px !important;
        border-radius: 14px !important;
        font-size: clamp(9px, 2.5vw, 12px) !important;
        color: { main_text_color } !important;
        overflow: hidden !important;
        flex-shrink: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: center !important;
        width: 100% !important;
    }}

    .stButton > button span, .stButton > button p, .stButton > button div {{
        white-space: pre-wrap !important; word-wrap: break-word !important; word-break: break-all !important;
        overflow-wrap: anywhere !important; text-overflow: clip !important; overflow: hidden !important; line-height: 1.25 !important;
        pointer-events: none !important;
    }}
    .stButton > button:hover {{ border-color: {btn_hover_border} !important; background-color: {btn_hover_bg} !important; transform: translateY(-1px); }}

    [data-testid="stElementContainer"] {{ width: 100% !important; margin: 0 !important; padding: 0 !important; }}

    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important; color: {main_text_color} !important;
        width: 94vw !important; max-width: 480px !important; max-height: 90vh !important;
        border-radius: 20px !important; padding: 16px 12px !important; overflow-y: auto !important;
        border: 2px solid {primary_accent} !important; margin: auto !important; position: fixed !important;
        top: 50% !important; left: 50% !important; transform: translate(-50%, -50%) !important;
        box-sizing: border-box !important;
        box-shadow: 0 20px 48px rgba(0,0,0,0.60) !important;
    }}

    [data-testid="stDialog"] [data-testid="stForm"] {{
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"] {{
        gap: 8px !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    [data-testid="stDialog"] [data-testid="column"] {{
        width: 50% !important;
        max-width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 0 !important;
        padding: 0 2px !important;
        box-sizing: border-box !important;
    }}

    [data-testid="stDialog"] input, 
    [data-testid="stDialog"] select, 
    [data-testid="stDialog"] textarea,
    [data-testid="stDialog"] [data-baseweb="select"],
    [data-testid="stDialog"] div[role="combobox"],
    [data-testid="stDialog"] [data-testid="stTextInput"],
    [data-testid="stDialog"] [data-testid="stSelectbox"],
    [data-testid="stDialog"] [data-testid="stTextArea"] {{
        width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
        border-radius: 14px !important;
    }}

    [data-testid="stDialog"] label {{
        font-size: clamp(12px, 3.2vw, 14px) !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
        white-space: nowrap !important;
    }}

    [data-testid="stDialog"] .stButton > button {{
        min-height: 42px !important;
        font-size: clamp(13px, 3.6vw, 15px) !important;
        padding: 6px 8px !important;
        border-radius: 9999px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        background-color: {primary_accent} !important;
        color: #FFFFFF !important;
        border: none !important;
    }}

    @media screen and (max-width: 600px) {{
        [data-testid="stDialog"] > div:first-child {{
            width: 95vw !important;
            padding: 12px 10px !important;
        }}
        [data-testid="stDialog"] [data-testid="stForm"] > [data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
        }}
        [data-testid="stDialog"] [data-testid="stForm"] > [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
            width: 100% !important;
            max-width: 100% !important;
            flex: 1 1 100% !important;
        }}
        [data-testid="stDialog"] [data-testid="stForm"] [data-testid="stHorizontalBlock"]:last-child {{
            flex-direction: row !important;
        }}
        [data-testid="stDialog"] [data-testid="stForm"] [data-testid="stHorizontalBlock"]:last-child > [data-testid="column"] {{
            width: 50% !important;
            max-width: 50% !important;
            flex: 1 1 50% !important;
        }}
    }}

    [data-baseweb="tab-list"] {{
        width: 100% !important;
        display: flex !important;
        gap: 4px !important;
        padding: 0 !important;
    }}
    [data-baseweb="tab"] {{
        flex: 1 1 auto !important;
        padding: 10px 6px !important;
        font-size: clamp(11px, 3.2vw, 15px) !important;
        font-weight: 700 !important;
        text-align: center !important;
        justify-content: center !important;
        min-width: 0 !important;
        border-radius: 14px 14px 0 0 !important;
    }}

    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"], input[type="date"] {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border: 1.5px solid {border_color} !important;
        border-radius: 14px !important;
        font-weight: 600 !important;
        max-width: 100% !important;
    }}
    [data-baseweb="input"] input {{
        color: {input_text} !important;
        -webkit-text-fill-color: {input_text} !important;
    }}

    .swipe-hidden-container {{ display: none !important; position: absolute !important; left: -9999px !important; }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# 브라우저 스크립트
# ---------------------------------------------------------
calendar_enhancer_js_template = """
<script>
(function() {
    const doc = window.parent.document;
    if (!doc) return;

    if (!window.history.state || !window.history.state.calendarApp) {
        window.history.pushState({ calendarApp: true, view: 'main' }, '', window.location.href);
    }

    window.addEventListener('popstate', function(event) {
        const dialogs = doc.querySelectorAll('[data-testid="stDialog"]');
        if (dialogs.length > 0) {
            const closeButtons = Array.from(doc.querySelectorAll('button')).filter(b => {
                const txt = (b.innerText || '').trim();
                return txt.includes('🚪 닫기') || txt.includes('❌ 취소') || txt.includes('닫기');
            });
            if (closeButtons.length > 0) {
                closeButtons[0].click();
                window.history.pushState({ calendarApp: true }, '', window.location.href);
                return;
            }
        }

        const tabs = Array.from(doc.querySelectorAll('[data-baseweb="tab"]'));
        if (tabs.length > 0) {
            const activeTab = doc.querySelector('[data-baseweb="tab"][aria-selected="true"]');
            if (activeTab && activeTab !== tabs[0]) {
                tabs[0].click();
                window.history.pushState({ calendarApp: true }, '', window.location.href);
                return;
            }
        }

        window.history.pushState({ calendarApp: true }, '', window.location.href);
    });

    function preventUnwantedKeyboard() {
        const selectInputs = doc.querySelectorAll('[data-baseweb="select"] input');
        selectInputs.forEach(el => {
            if (!el.hasAttribute('data-kb-handled')) {
                el.setAttribute('data-kb-handled', 'true');
                el.setAttribute('inputmode', 'none');
                el.setAttribute('readonly', 'readonly');
            }
        });
        const selects = doc.querySelectorAll('select');
        selects.forEach(el => {
            el.setAttribute('inputmode', 'none');
        });
    }

    function enhanceCalendarUI() {
        preventUnwantedKeyboard();
        const buttons = Array.from(doc.querySelectorAll('button'));
        buttons.forEach(btn => {
            const txt = btn.innerText || '';
            if (txt.includes('HIDDEN_PREV') || txt.includes('HIDDEN_NEXT')) {
                const container = btn.closest('[data-testid="stElementContainer"]');
                if (container) { container.style.setProperty('display', 'none', 'important'); }
            }
            if (txt.includes('🌟') || txt.includes('[오늘]')) {
                btn.style.setProperty('background', '___BG___', 'important');
                btn.style.setProperty('color', '___TEXT___', 'important');
                btn.style.setProperty('border', '___BORDER___', 'important');
                btn.style.setProperty('font-weight', '700', 'important');
            }
        });
    }

    let touchstartX = 0, touchstartY = 0;
    
    function triggerMonthChange(dir) {
        const buttons = Array.from(doc.querySelectorAll('button'));
        const targetText = dir === 'next' ? 'HIDDEN_NEXT' : 'HIDDEN_PREV';
        const targetBtn = buttons.find(b => b.innerText && b.innerText.includes(targetText));
        if (targetBtn) targetBtn.click();
    }

    if (!doc._swipeAttached) {
        doc._swipeAttached = true;
        
        doc.addEventListener('touchstart', function(e) {
            if (e.changedTouches && e.changedTouches.length > 0) {
                touchstartX = e.changedTouches[0].clientX;
                touchstartY = e.changedTouches[0].clientY;
            }
        }, {passive: true});

        doc.addEventListener('touchend', function(e) {
            if (!e.changedTouches || e.changedTouches.length === 0) return;
            let diffX = e.changedTouches[0].clientX - touchstartX;
            let diffY = e.changedTouches[0].clientY - touchstartY;
            
            if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 40) {
                if (diffX < 0) {
                    triggerMonthChange('next');
                } else {
                    triggerMonthChange('prev');
                }
            }
        }, {passive: true});
    }

    setInterval(enhanceCalendarUI, 250);
})();
</script>
"""

calendar_enhancer_js = (
    calendar_enhancer_js_template
    .replace('___BG___', today_highlight_bg)
    .replace('___TEXT___', today_highlight_text)
    .replace('___BORDER___', today_highlight_border)
)

components.html(calendar_enhancer_js, height=0, width=0)

# ---------------------------------------------------------
# 공통 엑셀 및 데이터 유틸함수
# ---------------------------------------------------------
def get_initial_excel_file():
    candidates = glob.glob(os.path.join("DATA", "*.xlsx")) + glob.glob(os.path.join("data", "*.xlsx")) + glob.glob("*.xlsx")
    valid_files = [f for f in candidates if not os.path.basename(f).startswith("~$")]
    return valid_files[0] if valid_files else os.path.join("DATA", "숙직근무표.xlsx")

def update_excel_download_bytes(df):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        memos = st.session_state.get("memos", {})
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d), ""))
        if "날짜" in save_df.columns:
            save_df = save_df[["날짜"] + [c for c in save_df.columns if c != "날짜"]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            save_df.to_excel(writer, index=False)
        st.session_state.file_bytes = output.getvalue()
    except Exception as e:
        st.sidebar.warning(f"⚠️ 엑셀 다운로드 데이터 생성 실패: {e}")

def save_to_excel_file(df, file_path):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        memos = st.session_state.get("memos", {})
        save_df["메모"] = save_df["날짜"].map(lambda d: memos.get(str(d), ""))
        save_df.to_excel(file_path, index=False)
        update_excel_download_bytes(df)
        return True
    except Exception as e:
        st.sidebar.warning(f"⚠️ 엑셀 파일 저장 실패: {e}")
        return False

def save_app_state(df, sheet_name, memos, batch_patterns=None):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")
        if batch_patterns is None:
            batch_patterns = st.session_state.get("batch_patterns", {})

        state_data = {"selected_sheet": sheet_name, "memos": memos, "batch_patterns": batch_patterns, "df_dict": save_df.to_dict(orient="records")}
        with open(PERSISTENCE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        save_to_excel_file(df, st.session_state.get("file_path", get_initial_excel_file()))
    except Exception as e:
        st.sidebar.warning(f"⚠️ 상태 저장 실패: {e}")

def load_app_state():
    if os.path.exists(PERSISTENCE_STATE_PATH):
        try:
            with open(PERSISTENCE_STATE_PATH, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            df = pd.DataFrame(state_data["df_dict"])
            if "날짜" in df.columns:
                df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
                df = df[["날짜"] + [c for c in df.columns if c != "날짜"]]
                
            if "근무자1" not in df.columns: df["근무자1"] = "미지정"
            if "근무자2" not in df.columns: df["근무자2"] = "미지정"
            if "대직1" not in df.columns: df["대직1"] = None
            if "대직2" not in df.columns: df["대직2"] = None
            if "근무구분_원본" not in df.columns: df["근무구분_원본"] = "평일"
            if "년월" not in df.columns and "날짜" in df.columns:
                df["년월"] = df["날짜"].dt.strftime("%Y-%m")
            if "실제근무1" not in df.columns:
                df["실제근무1"] = df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(df["근무자1"]).fillna("미지정")
            if "실제근무2" not in df.columns:
                df["실제근무2"] = df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(df["근무자2"]).fillna("미지정")
                
            return df, state_data.get("selected_sheet", "숙직근무자"), state_data.get("memos", {}), state_data.get("batch_patterns", {})
        except Exception as e:
            st.sidebar.warning(f"⚠️ 저장된 상태 불러오기 실패: {e}")
    return None, None, None, None

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

    duty_type_col = next((c for c in df.columns if any(k in c for k in ["근무구분", "구분", "요일구분"])), None)
    df["근무구분_원본"] = df[duty_type_col].astype(str).str.strip() if duty_type_col else "평일"

    p1_col = next((c for c in df.columns if any(k in c for k in ["근무자1", "1근무", "숙직1", "성명"]) and "대직" not in c), None)
    p2_col = next((c for c in df.columns if any(k in c for k in ["근무자2", "2근무", "숙직2"]) and "대직" not in c), None)
    sub1_col = next((c for c in df.columns if any(k in c for k in ["대직1", "대직자1"])), None)
    sub2_col = next((c for c in df.columns if any(k in c for k in ["대직2", "대직자2"])), None)

    df["근무자1"] = df[p1_col].astype(str).str.strip() if p1_col else "미지정"
    df["근무자2"] = df[p2_col].astype(str).str.strip() if p2_col else "미지정"
    df["대직1"] = df[sub1_col].astype(str).str.strip() if sub1_col else None
    df["대직2"] = df[sub2_col].astype(str).str.strip() if sub2_col else None
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    memo_col = next((c for c in df.columns if "메모" in c or "비고" in c), None)
    if memo_col:
        if "memos" not in st.session_state: st.session_state.memos = {}
        for _, r in df.iterrows():
            m_val = str(r[memo_col]).strip()
            if m_val and m_val not in ["nan", "None"]:
                st.session_state.memos[r["날짜"].strftime("%Y-%m-%d")] = m_val

    df["실제근무1"] = df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(df["근무자1"]).fillna("미지정")
    df["실제근무2"] = df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None).combine_first(df["근무자2"]).fillna("미지정")
    return df[["날짜"] + [c for c in df.columns if c != "날짜"]], target_sheet, sheet_names, df_raw, file_bytes

initial_file = get_initial_excel_file()
if "file_path" not in st.session_state: st.session_state.file_path = initial_file
if "file_bytes" not in st.session_state and os.path.exists(initial_file):
    with open(initial_file, "rb") as f: st.session_state.file_bytes = f.read()
    st.session_state.file_name = os.path.basename(initial_file)

if "df" not in st.session_state:
    saved_df, saved_sheet, saved_memos, saved_patterns = load_app_state()
    if saved_df is not None:
        st.session_state.update({"df": saved_df, "selected_sheet": saved_sheet, "memos": saved_memos or {}, "batch_patterns": saved_patterns or {}})
        _, _, st.session_state.sheet_names, st.session_state.raw_df, _ = load_excel_smart(st.session_state.file_bytes, saved_sheet)
    elif "file_bytes" in st.session_state:
        parsed_df, used_sheet, sheet_names, raw_df, _ = load_excel_smart(st.session_state.file_bytes)
        st.session_state.update({"df": parsed_df, "selected_sheet": used_sheet, "sheet_names": sheet_names, "raw_df": raw_df, "memos": {}, "batch_patterns": {}})
    else:
        today_d = datetime.date.today()
        sample_df = pd.DataFrame({"날짜": pd.date_range(start=today_d.replace(day=1), periods=60, freq="D"), "근무자1": ["우정수", "오기희"] * 30, "근무자2": ["정찬웅", "서진호"] * 30})
        sample_df["년월"] = sample_df["날짜"].dt.strftime("%Y-%m")
        sample_df["실제근무1"], sample_df["실제근무2"] = sample_df["근무자1"], sample_df["근무자2"]
        sample_df["대직1"], sample_df["대직2"] = None, None
        sample_df["근무구분_원본"] = "평일"
        st.session_state.update({"df": sample_df, "sheet_names": ["숙직근무자"], "selected_sheet": "숙직근무자", "raw_df": pd.DataFrame(), "memos": {}, "batch_patterns": {}})

update_excel_download_bytes(st.session_state.df)

# ---------------------------------------------------------
# 다이얼로그 정의
# ---------------------------------------------------------
@st.dialog("⚠️ 프로그램 종료 확인")
def confirm_exit_dialog():
    st.write("정말로 시스템을 종료하시겠습니까?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ 취소", use_container_width=True): 
            st.session_state.show_exit_dialog = False
            st.rerun()
    with c2:
        if st.button("🔴 예 (종료)", use_container_width=True, type="primary"):
            st.session_state.update({"show_exit_dialog": False, "is_app_closed": True})
            st.rerun()

@st.dialog("⚙️ 대시보드 및 근무 관리 설정")
def settings_dialog():
    tab_s1, tab_s2, tab_s3 = st.tabs(["🎨 화면 설정", "🔄 순환등록", "💬 카카오"])
    with tab_s1:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        st.markdown("### 📱 화면 표시 설정")
        new_view = st.radio("달력 표출 형식", ["🗓️ 가로형 Grid", "📄 세로형 리스트"], index=0 if st.session_state.auto_view_type == "🗓️ 가로형 Grid" else 1)
        new_th = st.radio("대시보드 테마", ["☀️ 화이트 테마", "🌙 블랙 테마"], index=0 if st.session_state.app_theme == "☀️ 화이트 테마" else 1)
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("💾 화면 설정 적용", use_container_width=True, type="primary"):
            st.session_state.update({"auto_view_type": new_view, "app_theme": new_th, "show_settings_dialog": False})
            save_local_config("auto_view_type", new_view)
            save_local_config("app_theme", new_th)
            st.rerun()

    with tab_s2:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        st.markdown("📅 **입력된 근무자만 규칙적으로 순환 등록됩니다.**")
        start_d = st.date_input("시작 날짜", value=datetime.date.today())
        
        infinite_repeat = st.checkbox("♾️ 시작일부터 월말까지 순환 적용", value=True)
        days_c = st.number_input("적용 일수", min_value=1, max_value=365, value=30, disabled=infinite_repeat)
        
        c1, c2 = st.columns(2)
        with c1:
            i1 = st.number_input("근무자1 주기", 1, 30, 3)
            w1_names = [st.text_input(f"1-{i+1}", key=f"w1_{i}").strip() for i in range(int(i1))]
        with c2:
            i2 = st.number_input("근무자2 주기", 1, 30, 3)
            w2_names = [st.text_input(f"2-{i+1}", key=f"w2_{i}").strip() for i in range(int(i2))]
        st.markdown('</div>', unsafe_allow_html=True)
            
        if st.button("💾 순환 패턴 반영", use_container_width=True, type="primary"):
            df_cur = st.session_state.df
            cur_d = start_d
            v1, v2 = [n for n in w1_names if n], [n for n in w2_names if n]
            
            if infinite_repeat:
                last_day_of_month = calendar.monthrange(start_d.year, start_d.month)[1]
                target_end_date = datetime.date(start_d.year, start_d.month, last_day_of_month)
                delta_days = (target_end_date - start_d).days + 1
            else:
                delta_days = int(days_c)

            for i in range(delta_days):
                idx_m = df_cur[df_cur["날짜"] == pd.Timestamp(cur_d)].index
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
            st.rerun()

    with tab_s3:
        st.markdown('<div class="setting-box">', unsafe_allow_html=True)
        k_key = st.text_input("카카오 REST API 키", value=st.session_state.kakao_api_key, type="password")
        if k_key != st.session_state.kakao_api_key:
            st.session_state.kakao_api_key = k_key
            save_local_config("kakao_api_key", k_key)
        s_date = st.date_input("발송 대상 날짜", value=datetime.date.today())
        row_m = st.session_state.df[st.session_state.df["날짜"] == pd.Timestamp(s_date)]
        msg = f"📢 [{s_date} 숙직안내]\n- 1: {row_m.iloc[0]['실제근무1'] if not row_m.empty else '-'}\n- 2: {row_m.iloc[0]['실제근무2'] if not row_m.empty else '-'}"
        st.text_area("미리보기", value=msg)
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("💬 나에게 카카오톡 전송", use_container_width=True, type="primary"):
            if k_key:
                res = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send", headers={"Authorization": f"Bearer {k_key}"}, data={"template_object": json.dumps({"object_type": "text", "text": msg})})
                st.success("✅ 전송 성공!" if res.status_code == 200 else f"❌ 전송 실패: {res.text}")
            else:
                st.warning("API 키를 입력해주세요.")

@st.dialog("✏️ 근무자 및 메모 수정")
def edit_worker_dialog(date_str, duty_info):
    st.markdown(f"### 📅 {date_str} 근무 수정")
    
    if duty_info is None or "idx" not in duty_info or duty_info["idx"] not in st.session_state.df.index:
        st.error("해당 날짜의 근무 정보 위치를 찾을 수 없습니다.")
        if st.button("🚪 닫기", use_container_width=True):
            st.session_state.update({"editing_date": None, "editing_duty_info": None})
            st.rerun()
        return

    row_idx = duty_info["idx"]
    curr_row = st.session_state.df.loc[row_idx]
    
    all_workers = set()
    for col in ["근무자1", "근무자2", "대직1", "대직2"]:
        if col in st.session_state.df.columns:
            vals = st.session_state.df[col].dropna().unique()
            for v in vals:
                v_str = str(v).strip()
                if v_str and v_str not in ["미지정", "nan", "None"]:
                    all_workers.add(v_str)

    worker_options = ["(선택 안함)"] + sorted(all_workers) + ["(직접 입력)"]
    
    def get_idx(val):
        if not val or pd.isna(val):
            return 0
        val_str = str(val).strip()
        if not val_str or val_str in ["nan", "None", "미지정"]:
            return 0
        if val_str in worker_options:
            return worker_options.index(val_str)
        return len(worker_options) - 1

    curr_p1 = str(curr_row.get("근무자1", "")).strip() if pd.notnull(curr_row.get("근무자1")) else ""
    curr_p2 = str(curr_row.get("근무자2", "")).strip() if pd.notnull(curr_row.get("근무자2")) else ""
    curr_sub1 = str(curr_row.get("대직1", "")).strip() if pd.notnull(curr_row.get("대직1")) else ""
    curr_sub2 = str(curr_row.get("대직2", "")).strip() if pd.notnull(curr_row.get("대직2")) else ""

    with st.form(f"form_{date_str}"):
        c1, c2 = st.columns(2)
        with c1:
            p1_s = st.selectbox("근무자1", worker_options, index=get_idx(curr_p1), key=f"p1_s_{date_str}")
            p1_c = st.text_input("직접입력1", value=curr_p1 if p1_s == "(직접 입력)" else "", key=f"p1_c_{date_str}") if p1_s == "(직접 입력)" else ""

            sub1_s = st.selectbox("대직자1", worker_options, index=get_idx(curr_sub1), key=f"sub1_s_{date_str}")
            sub1_c = st.text_input("대직1 직접입력", value=curr_sub1 if sub1_s == "(직접 입력)" else "", key=f"sub1_c_{date_str}") if sub1_s == "(직접 입력)" else ""

        with c2:
            p2_s = st.selectbox("근무자2", worker_options, index=get_idx(curr_p2), key=f"p2_s_{date_str}")
            p2_c = st.text_input("직접입력2", value=curr_p2 if p2_s == "(직접 입력)" else "", key=f"p2_c_{date_str}") if p2_s == "(직접 입력)" else ""

            sub2_s = st.selectbox("대직자2", worker_options, index=get_idx(curr_sub2), key=f"sub2_s_{date_str}")
            sub2_c = st.text_input("대직2 직접입력", value=curr_sub2 if sub2_s == "(직접 입력)" else "", key=f"sub2_c_{date_str}") if sub2_s == "(직접 입력)" else ""
        
        memo_in = st.text_area("📌 메모", value=st.session_state.memos.get(date_str, ""), key=f"memo_{date_str}")
        
        col_sub1, col_sub2 = st.columns(2)
        with col_sub1:
            submitted = st.form_submit_button("💾 저장", use_container_width=True)
        with col_sub2:
            closed = st.form_submit_button("🚪 닫기", use_container_width=True)

        if submitted:
            f_p1 = p1_c if p1_s == "(직접 입력)" else ("" if p1_s == "(선택 안함)" else p1_s)
            f_p2 = p2_c if p2_s == "(직접 입력)" else ("" if p2_s == "(선택 안함)" else p2_s)
            f_sub1 = sub1_c if sub1_s == "(직접 입력)" else ("" if sub1_s == "(선택 안함)" else sub1_s)
            f_sub2 = sub2_c if sub2_s == "(직접 입력)" else ("" if sub2_s == "(선택 안함)" else sub2_s)
            
            st.session_state.df.loc[row_idx, ["근무자1", "근무자2", "대직1", "대직2"]] = [
                f_p1 if f_p1 else "미지정", 
                f_p2 if f_p2 else "미지정", 
                f_sub1 if f_sub1 else None, 
                f_sub2 if f_sub2 else None
            ]
            st.session_state.df.loc[row_idx, "실제근무1"] = f_sub1 if f_sub1 else (f_p1 if f_p1 else "미지정")
            st.session_state.df.loc[row_idx, "실제근무2"] = f_sub2 if f_sub2 else (f_p2 if f_p2 else "미지정")
            
            if memo_in.strip():
                st.session_state.memos[date_str] = memo_in.strip()
            else:
                st.session_state.memos.pop(date_str, None)
            
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
    st.header("📂 근무표 파일 관리")
    if "file_name" in st.session_state: st.info(f"📄 `{st.session_state.file_name}`")
    
    up_file = st.file_uploader("새 엑셀 업로드", type=["xlsx"])
    if up_file:
        f_bytes = up_file.getvalue()
        save_p = os.path.join("DATA", up_file.name)
        with open(save_p, "wb") as f: f.write(f_bytes)
        parsed_df, used_s, s_names, r_df, _ = load_excel_smart(f_bytes)
        st.session_state.update({"file_path": save_p, "file_bytes": f_bytes, "file_name": up_file.name, "df": parsed_df, "selected_sheet": used_s, "sheet_names": s_names, "raw_df": r_df})
        save_app_state(parsed_df, used_s, st.session_state.memos)
        st.rerun()

    if "file_bytes" in st.session_state:
        st.download_button("📥 엑셀 다운로드", data=st.session_state.file_bytes, file_name="숙직근무표_수정본.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    st.divider()
    if st.button("🔴 앱종료", use_container_width=True):
        st.session_state.show_exit_dialog = True
        st.rerun()

if st.session_state.show_exit_dialog: confirm_exit_dialog()
elif st.session_state.show_settings_dialog: settings_dialog()
elif st.session_state.editing_date and st.session_state.editing_duty_info: edit_worker_dialog(st.session_state.editing_date, st.session_state.editing_duty_info)

df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
st.title("📋 광주교도소 의료과 숙직근무")

st.markdown('<div class="setting-box">', unsafe_allow_html=True)
if st.button("⚙️ 대시보드 및 설정 관리 열기", use_container_width=True, type="secondary"):
    st.session_state.show_settings_dialog = True
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📅 달력", "✏️ 수정", "📊 통계", "🔍 원본"])

with tab1:
    today_df = df[df["날짜"].dt.date == today]
    if not today_df.empty:
        tr = today_df.iloc[0]
        sub1_t = str(tr.get("대직1", "")).strip() if pd.notnull(tr.get("대직1")) else ""
        sub2_t = str(tr.get("대직2", "")).strip() if pd.notnull(tr.get("대직2")) else ""
        
        p1 = f"{tr['실제근무1']}(대)" if sub1_t and sub1_t not in ["nan", "None", ""] else tr["실제근무1"]
        p2 = f"{tr['실제근무2']}(대)" if sub2_t and sub2_t not in ["nan", "None", ""] else tr["실제근무2"]
        memo_txt = f" | 📌 {st.session_state.memos.get(today.strftime('%Y-%m-%d'), '')}" if st.session_state.memos.get(today.strftime('%Y-%m-%d')) else ""
        st.markdown(f'<div class="today-card"><div class="today-title">🚨 오늘 근무자 ({today.strftime("%m월 %d일")})</div><div class="today-content">1: <span>{p1}</span> | 2: <span>{p2}</span>{memo_txt}</div></div>', unsafe_allow_html=True)

    avail_months = sorted(df["년월"].dropna().unique()) or [today.strftime("%Y-%m")]
    cur_ym = today.strftime("%Y-%m")
    if "selected_month" not in st.session_state or st.session_state.selected_month not in avail_months:
        st.session_state.selected_month = cur_ym if cur_ym in avail_months else avail_months[0]
    if "calendar_month_select" not in st.session_state:
        st.session_state.calendar_month_select = st.session_state.selected_month

    def go_month(direction):
        idx = avail_months.index(st.session_state.selected_month)
        if direction == 'prev' and idx > 0:
            st.session_state.selected_month = avail_months[idx - 1]
        elif direction == 'next' and idx < len(avail_months) - 1:
            st.session_state.selected_month = avail_months[idx + 1]
        st.session_state.calendar_month_select = st.session_state.selected_month

    st.markdown('<div class="swipe-hidden-container">', unsafe_allow_html=True)
    st.button("HIDDEN_PREV", on_click=go_month, args=('prev',))
    st.button("HIDDEN_NEXT", on_click=go_month, args=('next',))
    st.markdown('</div>', unsafe_allow_html=True)

    sel_month = st.selectbox("📅 조회 월 선택", avail_months, key="calendar_month_select", on_change=lambda: st.session_state.update({"selected_month": st.session_state.calendar_month_select}), label_visibility="collapsed")
    st.session_state.selected_month = sel_month

    if sel_month in avail_months:
        y, m = map(int, sel_month.split("-"))
        st.markdown(f'<div class="month-header-card"><h2>🗓️ {y}년 {m}월 숙직 근무표</h2></div>', unsafe_allow_html=True)
        
        num_days = calendar.monthrange(y, m)[1]
        m_df = df[df["년월"] == sel_month]
        
        duty_map = {}
        for i, row in m_df.iterrows():
            p1_name = str(row.get("실제근무1", "미지정")).strip()
            p2_name = str(row.get("실제근무2", "미지정")).strip()
            
            sub1_val = str(row.get("대직1", "")).strip() if pd.notnull(row.get("대직1")) else ""
            sub2_val = str(row.get("대직2", "")).strip() if pd.notnull(row.get("대직2")) else ""
            
            if sub1_val and sub1_val not in ["nan", "None", ""]:
                p1_name = f"{p1_name}(대)"
            if sub2_val and sub2_val not in ["nan", "None", ""]:
                p2_name = f"{p2_name}(대)"
                
            duty_map[row["날짜"].day] = {
                "idx": i,
                "p1": p1_name,
                "p2": p2_name
            }

        if st.session_state.auto_view_type == "📄 세로형 리스트":
            for d in range(1, num_days + 1):
                c_date = datetime.date(y, m, d)
                d_str = c_date.strftime("%Y-%m-%d")
                t_str = f"🌟 [오늘] {d:02d}일" if c_date == today else f"{d:02d}일"
                info = duty_map.get(d, {"p1": "-", "p2": "-"})
                memo_s = f" | 📌 {st.session_state.memos.get(d_str, '')}" if st.session_state.memos.get(d_str) else ""
                
                if st.button(f"{t_str} | 1:{info['p1']} | 2:{info['p2']}{memo_s}", key=f"v_{d_str}"):
                    st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(d)})
                    st.rerun()
        else:
            cols_h = st.columns(7)
            h_names = [
                ("일", "#FF606A" if is_dark else "#E60012"), 
                ("월", main_text_color), 
                ("화", main_text_color), 
                ("수", main_text_color), 
                ("목", main_text_color), 
                ("금", main_text_color), 
                ("토", "#69A9FF" if is_dark else "#1565D8")
            ]
            for idx, (h_n, col_c) in enumerate(h_names):
                cols_h[idx].markdown(f"<div style='text-align: center; color: {col_c}; font-weight: 700; font-size: clamp(11px, 3.2vw, 15px); padding: 4px 0; background: rgba(128,128,128,0.1); border-radius: 8px; border: 1px solid {border_color};'>{h_n}</div>", unsafe_allow_html=True)

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
                        memo_s = f"📌{st.session_state.memos.get(d_str, '')}" if st.session_state.memos.get(d_str) else ""
                        
                        btn_txt = f"🌟{day_cnt}일\n{info['p1']}\n{info['p2']}" if c_date == today else f"{day_cnt}일\n{info['p1']}\n{info['p2']}"
                        if memo_s: btn_txt += f"\n{memo_s}"

                        if g_cols[c].button(btn_txt, key=f"g_{d_str}"):
                            st.session_state.update({"editing_date": d_str, "editing_duty_info": duty_map.get(day_cnt)})
                            st.rerun()
                        day_cnt += 1

with tab2:
    st.subheader("✏️ 전체 근무표 수정")
    edit_ms = ["전체 기간"] + sorted(df["년월"].dropna().unique())
    sel_ed_m = st.selectbox("📅 월 선택", edit_ms, index=edit_ms.index(cur_ym) if cur_ym in edit_ms else 0)
    target_df = df.copy() if sel_ed_m == "전체 기간" else df[df["년월"] == sel_ed_m].copy()

    edited_df = st.data_editor(target_df, num_rows="dynamic", key="editor_main", use_container_width=True)

    if st.button("💾 변경사항 일괄 저장", use_container_width=True, type="primary"):
        if sel_ed_m == "전체 기간":
            m_df = edited_df.copy()
        else:
            m_df = st.session_state.df.copy()
            m_df.update(edited_df)
            
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

with tab3:
    st.subheader("📊 숙직근무자 월별 통계")
    stat_ms = ["전체 기간"] + sorted(df["년월"].dropna().unique(), reverse=True)
    sel_st_m = st.selectbox("📅 통계 월선택", stat_ms)
    f_df = df.copy() if sel_st_m == "전체 기간" else df[df["년월"] == sel_st_m]
    
    comb = pd.concat([
        f_df[["실제근무1", "근무구분_원본"]].rename(columns={"실제근무1": "근무자", "근무구분_원본": "구분"}),
        f_df[["실제근무2", "근무구분_원본"]].rename(columns={"실제근무2": "근무자", "근무구분_원본": "구분"})
    ], ignore_index=True)
    comb = comb[comb["근무자"].notnull() & (~comb["근무자"].isin(["미지정", "nan", "None", ""]))]

    if not comb.empty:
        stats = pd.crosstab(comb["근무자"], comb["구분"])
        stats["총 근무 횟수"] = stats.sum(axis=1)
        st.dataframe(stats.sort_values(by="총 근무 횟수", ascending=False), use_container_width=True)
    else:
        st.info("통계 데이터가 없습니다.")

with tab4:
    st.subheader("🔍 시트 데이터 원본 확인")
    st.dataframe(df, use_container_width=True)
