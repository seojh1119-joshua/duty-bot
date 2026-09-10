import calendar
import datetime
import glob
import io
import json
import os
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

os.makedirs("DATA", exist_ok=True)
os.makedirs("data", exist_ok=True)

PERSISTENCE_STATE_PATH = os.path.join("DATA", "edited_duty_schedule.json")
CONFIG_PATH = os.path.join("DATA", "local_config.json")

# ---------------------------------------------------------
# 페이지 기본 설정[cite: 1]
# ---------------------------------------------------------
st.set_page_config(
    page_title="광주교도소 의료과 숙직근무",
    page_icon="",
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

# 세션 상태 초기화[cite: 1]
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
# 동적 CSS 및 모바일 최적화 스타일 (세로폭 2배 확대 및 7열 가로폭 최적화)
# ---------------------------------------------------------
is_dark = st.session_state.app_theme == "🌙 블랙 테마"

theme_bg = "#0F172A" if is_dark else "#FFFFFF"
main_text_color = "#F8FAFC" if is_dark else "#0F172A"
border_color = "#334155" if is_dark else "#CBD5E1"
btn_bg = "#1E293B" if is_dark else "#FFFFFF"
btn_text = "#F8FAFC" if is_dark else "#0F172A"
btn_hover_bg = "#334155" if is_dark else "#F1F5F9"
btn_hover_border = "#60A5FA" if is_dark else "#2563EB"
sidebar_bg = "#0B0F19" if is_dark else "#F8FAFC"
dialog_bg = "#1E293B" if is_dark else "#FFFFFF"
input_bg = "#1E293B" if is_dark else "#F8FAFC"
input_text = "#F8FAFC" if is_dark else "#0F172A"

today_highlight_bg = "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)" if is_dark else "linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%)"
today_highlight_text = "#FFFFFF" if is_dark else "#78350F"
today_highlight_border = "2px solid #F59E0B" if is_dark else "2px solid #D97706"

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
    }}

    .main .block-container {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        padding: 0.02rem 1px 0.05rem 1px !important;
        max-width: 100vw !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    h1 {{ font-size: clamp(15px, 4vw, 20px) !important; margin: 0px !important; padding: 0px !important; font-weight: 800 !important; white-space: nowrap !important; }}
    [data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{ background-color: {sidebar_bg} !important; color: {main_text_color} !important; }}
    p, span, label, .stMarkdown, h1, h2, h3, h4, h5, h6 {{ color: {main_text_color} !important; }}

    .month-header-card {{
        background: { "linear-gradient(135deg, #1E293B 0%, #0F172A 100%)" if is_dark else "linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%)" };
        border: 1px solid {border_color}; border-radius: 4px; padding: 2px 4px; margin: 2px 0; text-align: center;
    }}
    .month-header-card h2 {{ margin: 0 !important; font-size: clamp(12px, 3vw, 15px) !important; font-weight: 800 !important; color: {"#60A5FA" if is_dark else "#1D4ED8"} !important; }}

    .today-card {{
        background: { "linear-gradient(135deg, #0F172A 100%, #1E3A8A 100%)" if is_dark else "linear-gradient(135deg, #E0F2FE 100%, #BAE6FD 100%)" };
        color: {"white" if is_dark else "#0F172A"}; padding: 4px 6px; border-radius: 4px; border: 1px solid {border_color}; margin-bottom: 3px; width: 100%; box-sizing: border-box;
    }}
    .today-card .today-title {{ font-size: clamp(11px, 3vw, 14px) !important; opacity: 0.95; font-weight: 800; }}
    .today-card .today-content {{ font-size: clamp(12px, 3.5vw, 16px) !important; font-weight: 800; }}
    .today-card span {{ color: {"#FDE047" if is_dark else "#1D4ED8"} !important; font-weight: 900; }}

    .stButton > button {{
        width: 100% !important; min-width: 0 !important; height: auto !important; min-height: 28px !important;
        padding: 2px 4px !important; border: 1.5px solid {border_color} !important; border-radius: 3px !important;
        background-color: {btn_bg} !important; color: {btn_text} !important; box-sizing: border-box !important;
        text-align: center !important; font-size: 12px !important; font-weight: 600 !important; margin: 0 !important;
        cursor: pointer !important;
    }}

    /* 모바일 가로달력 7열이 한눈에 보이도록 가로폭 조절 및 세로폭 2배 확대 */
    div[data-testid="column"] .stButton > button {{
        min-height: clamp(104px, 22vw, 150px) !important;
        max-height: 156px !important;
        padding: 1px 0px !important;
        font-size: clamp(8px, 2vw, 11.5px) !important;
        color: { "#F8FAFC" if is_dark else "#0F172A" } !important;
        overflow: hidden !important;
        flex-shrink: 0 !important;
    }}

    .stButton > button span, .stButton > button p, .stButton > button div {{
        white-space: pre-wrap !important; word-wrap: break-word !important; word-break: break-all !important;
        overflow-wrap: anywhere !important; text-overflow: clip !important; overflow: hidden !important; line-height: 1.15 !important;
        pointer-events: none !important;
    }}
    .stButton > button:hover {{ border-color: {btn_hover_border} !important; background-color: {btn_hover_bg} !important; }}

    /* 7개 컬럼 간격 및 여백 최소화로 한눈에 정렬 */
    [data-testid="stHorizontalBlock"] {{
        display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
        width: 100% !important; max-width: 100% !important; min-width: 0 !important; gap: 0.5px !important; margin: 0 !important; padding: 0 !important; box-sizing: border-box !important;
    }}
    [data-testid="column"] {{
        width: 14.285% !important; max-width: 14.285% !important; min-width: 0 !important;
        flex: 1 1 14.285% !important; padding: 0px !important; margin: 0 !important; box-sizing: border-box !important;
    }}
    [data-testid="stElementContainer"] {{ width: 100% !important; margin: 0 !important; padding: 0 !important; }}

    /* 순환 등록 팝업 및 대화상자 모바일 세로 화면 맞춤 비율 조정 */
    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important; color: {main_text_color} !important;
        width: 98vw !important; max-width: 420px !important; max-height: 85vh !important;
        border-radius: 10px !important; padding: 0.4rem !important; overflow-y: auto !important;
        border: 1px solid {border_color} !important; margin: auto !important; position: fixed !important;
        top: 50% !important; left: 50% !important; transform: translate(-50%, -50%) !important;
    }}

    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"], input[type="date"] {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border: 1.5px solid {border_color} !important;
        font-weight: 600 !important;
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
# 브라우저 스크립트 (뒤로가기 연동 및 키보드 제어 보조)[cite: 1]
# ---------------------------------------------------------
calendar_enhancer_js_template = """
<script>
(function() {
    const doc = window.parent.document;
    if (!doc) return;

    if (!window.history.state || !window.history.state.appInitialized) {
        window.history.replaceState({ appInitialized: true, view: 'calendar' }, '', window.location.href);
    }

    window.addEventListener('popstate', function(event) {
        const closeButtons = Array.from(doc.querySelectorAll('button')).filter(b => {
            const txt = (b.innerText || '').trim();
            return txt.includes('🚪 닫기') || txt.includes('❌ 취소');
        });
        if (closeButtons.length > 0) {
            closeButtons[0].click();
            window.history.pushState({ appInitialized: true, view: 'calendar' }, '', window.location.href);
            return;
        }

        const tabs = Array.from(doc.querySelectorAll('[data-baseweb="tab"]'));
        if (tabs.length > 0) {
            tabs[0].click();
        }
        window.history.pushState({ appInitialized: true, view: 'calendar' }, '', window.location.href);
    });

    function preventUnwantedKeyboard() {
        const selects = doc.querySelectorAll('[data-baseweb="select"] input, select');
        selects.forEach(el => {
            if (!el.hasAttribute('data-kb-controlled')) {
                el.setAttribute('data-kb-controlled', 'true');
                el.setAttribute('readonly', 'readonly');
                el.addEventListener('focus', function(e) {
                    setTimeout(() => { el.removeAttribute('readonly'); }, 50);
                });
                el.addEventListener('blur', function(e) {
                    el.setAttribute('readonly', 'readonly');
                });
            }
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
                btn.style.setProperty('font-weight', '800', 'important');
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

    setInterval(enhanceCalendarUI, 200);
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
# 공통 엑셀 및 데이터 유틸함수[cite: 1]
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
        st.session_state.update({"df": sample_df, "sheet_names": ["숙직근무자"], "selected_sheet": "숙직근무자", "raw_df": pd.DataFrame(), "memos": {}, "batch_patterns": {}})

update_excel_download_bytes(st.session_state.df)

# ---------------------------------------------------------
# 다이얼로그 정의[cite: 1]
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
    tab_s1, tab_s2, tab_s3 = st.tabs(["🎨 화면 및 테마", "🔄 근무자 순환등록", "💬 카카오 센더"])
    with tab_s1:
        new_view = st.radio("달력 표출 형식", ["🗓️ 가로형 Grid", "📄 세로형 리스트"], index=0 if st.session_state.auto_view_type == "🗓️ 가로형 Grid" else 1)
        new_th = st.radio("대시보드 테마", ["☀️ 화이트 테마", "🌙 블랙 테마"], index=0 if st.session_state.app_theme == "☀️ 화이트 테마" else 1)
        if st.button("💾 화면 설정 적용", use_container_width=True, type="primary"):
            st.session_state.update({"auto_view_type": new_view, "app_theme": new_th, "show_settings_dialog": False})
            save_local_config("auto_view_type", new_view)
            save_local_config("app_theme", new_th)
            st.rerun()
    with tab_s2:
        st.markdown("📅 **입력된 근무자만 규칙적으로 순환 등록됩니다.**")
        start_d = st.date_input("시작 날짜", value=datetime.date.today(), help="날짜를 직접 선택할 때만 입력창이 동작합니다.")
        
        infinite_repeat = st.checkbox("♾️ 순환 패턴 계속 반복 적용 (시작일부터 선택 월 끝까지 무한 순환)", value=True)
        days_c = st.number_input("적용 총 일수", min_value=1, max_value=365, value=30, disabled=infinite_repeat)
        
        c1, c2 = st.columns(2)
        with c1:
            i1 = st.number_input("근무자1 주기", 1, 30, 3)
            w1_names = [st.text_input(f"순번 {i+1}", key=f"w1_{i}").strip() for i in range(int(i1))]
        with c2:
            i2 = st.number_input("근무자2 주기", 1, 30, 3)
            w2_names = [st.text_input(f"순번 {i+1}", key=f"w2_{i}").strip() for i in range(int(i2))]
            
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
                        df_cur.loc[idx, ["근무자1", "실제근무1"]] = v1[i % len(v1)]
                    if v2: 
                        df_cur.loc[idx, ["근무자2", "실제근무2"]] = v2[i % len(v2)]
                cur_d += datetime.timedelta(days=1)
                
            st.session_state.df = df_cur
            save_app_state(df_cur, st.session_state.selected_sheet, st.session_state.memos)
            st.session_state.show_settings_dialog = False
            st.rerun()
    with tab_s3:
        k_key = st.text_input("카카오 REST API 키", value=st.session_state.kakao_api_key, type="password")
        if k_key != st.session_state.kakao_api_key:
            st.session_state.kakao_api_key = k_key
            save_local_config("kakao_api_key", k_key)
        s_date = st.date_input("발송 대상 날짜", value=datetime.date.today())
        row_m = st.session_state.df[st.session_state.df["날짜"] == pd.Timestamp(s_date)]
        msg = f"📢 [{s_date} 숙직안내]\n- 1: {row_m.iloc[0]['실제근무1'] if not row_m.empty else '-'}\n- 2: {row_m.iloc[0]['실제근무2'] if not row_m.empty else '-'}"
        st.text_area("미리보기", value=msg)
        if st.button("💬 나에게 카카오톡 전송", use_container_width=True, type="primary"):
            if k_key:
                res = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send", headers={"Authorization": f"Bearer {k_key}"}, data={"template_object": json.dumps({"object_type": "text", "text": msg})})
                st.success("✅ 전송 성공!" if res.status_code == 200 else f"❌ 전송 실패: {res.text}")
            else:
                st.warning("API 키를 입력해주세요.")

@st.dialog("✏️ 근무자 수정 및 메모 작성")
def edit_worker_dialog(date_str, duty_info):
    st.write(f"📅 **{date_str} 근무 정보 수정**")
    row_idx = duty_info["idx"]
    curr_row = st.session_state.df.loc[row_idx]
    
    all_workers = set(st.session_state.df["근무자1"].dropna().unique()) | set(st.session_state.df["근무자2"].dropna().unique())
    all_workers.discard("미지정")
    worker_options = ["(선택 안함)"] + sorted(all_workers) + ["(직접 입력)"]
    def get_idx(val): return worker_options.index(val) if val in worker_options else 0

    with st.form(f"form_{date_str}"):
        c1, c2 = st.columns(2)
        with c1:
            p1_s = st.selectbox("근무자1", worker_options, index=get_idx(curr_row.get("근무자1", "")))
            p1_c = st.text_input("직접입력1", value=curr_row.get("근무자1", "")) if p1_s == "(직접 입력)" else ""
            sub1 = st.text_input("대직자1", value=str(curr_row.get("대직1", "")) if pd.notnull(curr_row.get("대직1")) else "")
        with c2:
            p2_s = st.selectbox("근무자2", worker_options, index=get_idx(curr_row.get("근무자2", "")))
            p2_c = st.text_input("직접입력2", value=curr_row.get("근무자2", "")) if p2_s == "(직접 입력)" else ""
            sub2 = st.text_input("대직자2", value=str(curr_row.get("대직2", "")) if pd.notnull(curr_row.get("대직2")) else "")
        
        memo_in = st.text_area("📌 메모", value=st.session_state.memos.get(date_str, ""))
        
        col_sub1, col_sub2 = st.columns([2, 1])
        with col_sub1: submitted = st.form_submit_button("💾 저장", use_container_width=True)
        with col_sub2: closed = st.form_submit_button("🚪 닫기", use_container_width=True)

        if submitted:
            f_p1 = p1_c if p1_s == "(직접 입력)" else ("" if p1_s == "(선택 안함)" else p1_s)
            f_p2 = p2_c if p2_s == "(직접 입력)" else ("" if p2_s == "(선택 안함)" else p2_s)
            
            st.session_state.df.loc[row_idx, ["근무자1", "근무자2", "대직1", "대직2"]] = [f_p1, f_p2, sub1 or None, sub2 or None]
            st.session_state.df.loc[row_idx, "실제근무1"] = sub1 if sub1 else f_p1
            st.session_state.df.loc[row_idx, "실제근무2"] = sub2 if sub2 else f_p2
            st.session_state.memos[date_str] = memo_in.strip()
            
            save_app_state(st.session_state.df, st.session_state.selected_sheet, st.session_state.memos)
            st.session_state.update({"editing_date": None, "editing_duty_info": None})
            st.rerun()
        if closed:
            st.session_state.update({"editing_date": None, "editing_duty_info": None})
            st.rerun()

# ---------------------------------------------------------
# 사이드바[cite: 1]
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
# 메인 화면[cite: 1]
# ---------------------------------------------------------
st.title("📋 광주교도소 의료과 숙직근무")
if st.button("⚙️ 대시보드 및 설정 관리 열기", use_container_width=True, type="secondary"):
    st.session_state.show_settings_dialog = True
    st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["📅 달력 메인", "✏️ 전체 수정", "📊 근무 통계", "🔍 데이터 점검"])

with tab1:
    today_df = df[df["날짜"].dt.date == today]
    if not today_df.empty:
        tr = today_df.iloc[0]
        p1 = f"{tr['실제근무1']}(대)" if pd.notnull(tr.get("대직1")) and str(tr.get("대직1")).strip() else tr["실제근무1"]
        p2 = f"{tr['실제근무2']}(대)" if pd.notnull(tr.get("대직2")) and str(tr.get("대직2")).strip() else tr["실제근무2"]
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
        duty_map = {row["날짜"].day: {"idx": i, "p1": row["실제근무1"], "p2": row["실제근무2"]} for i, row in m_df.iterrows()}

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
                ("일", "#FF6B6B" if is_dark else "#DC2626"), 
                ("월", main_text_color), 
                ("화", main_text_color), 
                ("수", main_text_color), 
                ("목", main_text_color), 
                ("금", main_text_color), 
                ("토", "#38BDF8" if is_dark else "#2563EB")
            ]
            for idx, (h_n, col_c) in enumerate(h_names):
                cols_h[idx].markdown(f"<div style='text-align: center; color: {col_c}; font-weight: 900; font-size: clamp(11px, 3vw, 15px); padding: 3px 0; background: rgba(128,128,128,0.1); border-radius: 3px; border: 1px solid {border_color};'>{h_n}</div>", unsafe_allow_html=True)

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

    if st.button("💾 변경사항 일괄 저장", use_container_width=True, type="primary"):
        save_app_state(df, st.session_state.selected_sheet, st.session_state.memos)
        st.success("✅ 저장되었습니다.")
        st.rerun()
    st.data_editor(target_df, num_rows="dynamic", key="editor_main", use_container_width=True)

with tab3:
    st.subheader("📊 숙직근무자 월별 통계")
    stat_ms = ["전체 기간"] + sorted(df["년월"].dropna().unique(), reverse=True)
    sel_st_m = st.selectbox("📅 통계 월선택", stat_ms)
    f_df = df.copy() if sel_st_m == "전체 기간" else df[df["년월"] == sel_st_m]
    
  comb = pd.concat(
        [
            f_df[["실제근무1", "근무구분_원본"]].rename(
                columns={"실제근무1": "근무자", "근무구분_원본": "구분"}
            ),
            f_df[["실제근무2", "근무구분_원본"]].rename(
                columns={"실제근무2": "근무자", "근무구분_원본": "구분"}
            ),
        ],
        ignore_index=True,
    )
    comb = comb[
        comb["근무자"].notnull()
        & (~comb["근무자"].isin(["미지정", "nan", "None", ""]))
    ]

    if not comb.empty:
        stats = pd.crosstab(comb["근무자"], comb["구분"])
        stats["총 근무 횟수"] = stats.sum(axis=1)
        st.dataframe(
            stats.sort_values(by="총 근무 횟수", ascending=False),
            use_container_width=True,
        )
    else:
        st.info("통계 데이터가 없습니다.")

with tab4:
    st.subheader("🔍 시트 데이터 원본 확인")
    st.dataframe(df, use_container_width=True)
```[cite: 1]
