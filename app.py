import calendar
import datetime
import glob
import io
import json
import os
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

# ---------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="숙직 근무표 대시보드",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 세션 상태 초기화 (종료 여부 및 화면 방향/테마 플래그)
if "is_app_closed" not in st.session_state:
    st.session_state.is_app_closed = False

if "auto_view_type" not in st.session_state:
    st.session_state.auto_view_type = "📄 세로형 리스트"

if "app_theme" not in st.session_state:
    st.session_state.app_theme = "☀️ 화이트 테마"

# 앱이 종료된 경우 화면 표시
if st.session_state.is_app_closed:
    st.title("👋 시스템이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# 동적 CSS (테마별 스타일 정의 및 오늘 날짜 특별 음영 처리)
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

# 팝업(Dialog) 내부 배경 및 입력창 테마 대응 CSS
dialog_bg = "#1E293B" if is_dark else "#FFFFFF"
input_bg = "#0F172A" if is_dark else "#FFFFFF"
input_text = "#F8FAFC" if is_dark else "#0F172A"

# 오늘 날짜 음영 및 강조 색상
today_btn_bg = "linear-gradient(135deg, #1E3E62 0%, #1D4ED8 100%)" if is_dark else "linear-gradient(135deg, #DBEAFE 0%, #93C5FD 100%)"
today_btn_border = "#60A5FA" if is_dark else "#2563EB"
today_btn_text = "#FFFFFF" if is_dark else "#0F172A"

responsive_css = f"""
<style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        width: 100vw !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }}

    .main .block-container {{
        background-color: {theme_bg} !important;
        color: {main_text_color} !important;
        padding: 0.5rem 0.5rem !important;
        max-width: 100% !important;
        width: 100% !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg} !important;
        color: {main_text_color} !important;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: {main_text_color} !important;
    }}

    p, span, label, .stMarkdown, h1, h2, h3, h4, h5, h6 {{
        color: {main_text_color} !important;
    }}

    .month-select-box {{
        background-color: {card_bg};
        border: 1.5px solid {border_color};
        border-radius: 10px;
        padding: 12px 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
    }}

    .today-card {{
        background: { "linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%)" if is_dark else "linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%)" };
        color: {"white" if is_dark else "#0F172A"};
        padding: 12px 16px;
        border-radius: 10px;
        border: 1px solid {border_color};
        margin-bottom: 12px;
        width: 100%;
        box-sizing: border-box;
    }}
    
    .today-card span {{
        color: {"#FDE047" if is_dark else "#1D4ED8"} !important;
        font-weight: bold;
    }}

    .stButton > button {{
        width: 100% !important;
        height: auto !important;
        min-height: 52px !important;
        padding: 6px 4px !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        background-color: {btn_bg} !important;
        color: {btn_text} !important;
        box-sizing: border-box !important;
        text-align: center !important;
        font-size: clamp(10px, 2.2vw, 13px) !important;
        font-weight: 500 !important;
        margin-bottom: 4px !important;
        white-space: pre-wrap !important;
        word-break: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.35 !important;
        transition: all 0.2s ease !important;
    }}

    .stButton > button:hover {{
        border-color: {btn_hover_border} !important;
        background-color: {btn_hover_bg} !important;
        color: {btn_text} !important;
    }}

    /*오늘 날짜 카드/버튼 가독성을 높이기 위한 특별 음영 스타일 */
    div[data-testid="stButton"] button[aria-label*="[오늘]"] {{
        background: {today_btn_bg} !important;
        color: {today_btn_text} !important;
        border: 2px solid {today_btn_border} !important;
        box-shadow: 0 4px 12px {"rgba(96, 165, 250, 0.4)" if is_dark else "rgba(37, 99, 235, 0.3)"} !important;
        font-weight: bold !important;
    }}
    div[data-testid="stButton"] button[aria-label*="[오늘]"]:hover {{
        background: {"linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)" if is_dark else "linear-gradient(135deg, #BFDBFE 0%, #60A5FA 100%)"} !important;
        border-color: {"#93C5FD" if is_dark else "#1D4ED8"} !important;
    }}

    /* 팝업 창 테마 대응 */
    [data-testid="stDialog"] > div:first-child {{
        background-color: {dialog_bg} !important;
        color: {main_text_color} !important;
        width: clamp(300px, 90vw, 600px) !important;
        max-width: 95vw !important;
        max-height: 85vh !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        overflow-y: auto !important;
        border: 1px solid {border_color} !important;
    }}

    /* 입력창, 셀렉트박스 테마 대응 */
    input, select, textarea, [data-baseweb="input"], [data-baseweb="select"], div[data-baseweb="input"] > div, [data-baseweb="base-input"] {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border-color: {border_color} !important;
    }}
    
    input[type="text"], input[type="number"], input[readonly], [data-baseweb="input"] input, [data-baseweb="calendar"] input {{
        color: {input_text} !important;
        background-color: {input_bg} !important;
        -webkit-text-fill-color: {input_text} !important;
    }}

    input:focus, select:focus, textarea:focus, [data-baseweb="input"] input:focus, [data-baseweb="base-input"] input:focus {{
        outline: none !important;
        box-shadow: none !important;
        border-color: {btn_hover_border} !important;
        background-color: {input_bg} !important;
    }}

    div[data-baseweb="popover"], div[data-baseweb="menu"], div[data-baseweb="calendar"], div[data-baseweb="select"] ul, ul[data-baseweb="menu"] {{
        background-color: {card_bg} !important;
        color: {main_text_color} !important;
        border-color: {border_color} !important;
    }}
    
    div[data-baseweb="calendar"], 
    div[data-baseweb="calendar"] > div, 
    div[data-baseweb="calendar"] section, 
    div[data-baseweb="calendar"] ul, 
    div[data-baseweb="calendar"] li,
    div[data-baseweb="calendar"] div[role="grid"],
    div[data-baseweb="calendar"] div[role="row"],
    div[data-baseweb="calendar"] div[role="gridcell"] {{
        background-color: {card_bg} !important;
        color: {main_text_color} !important;
    }}

    div[data-baseweb="calendar"] button, 
    div[data-baseweb="calendar"] span,
    div[data-baseweb="calendar"] div {{
        color: {main_text_color} !important;
    }}
    
    div[data-baseweb="calendar"] button:hover {{
        background-color: {btn_hover_bg} !important;
    }}

    li[role="option"], div[role="option"] {{
        background-color: {card_bg} !important;
        color: {main_text_color} !important;
    }}
    li[role="option"]:hover, div[role="option"]:hover {{
        background-color: {btn_hover_bg} !important;
        color: {main_text_color} !important;
    }}

    ::selection {{
        background-color: #3b82f6 !important;
        color: #ffffff !important;
    }}
    ::-moz-selection {{
        background-color: #3b82f6 !important;
        color: #ffffff !important;
    }}

    @media screen and (max-width: 768px) and (orientation: landscape) {{
        .main .block-container {{
            padding: 0.2rem 0.2rem !important;
        }}
        .stButton > button {{
            font-size: 10px !important;
            padding: 4px 2px !important;
        }}
    }}
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# 화면 회전 감지 JS
orientation_js = """
<script>
    function checkOrientation() {
        const isLandscape = window.matchMedia("(orientation: landscape)").matches;
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('mode') !== (isLandscape ? 'grid' : 'list')) {
            const newUrl = window.location.pathname + '?mode=' + (isLandscape ? 'grid' : 'list');
            window.history.replaceState(null, '', newUrl);
        }
    }
    window.addEventListener("orientationchange", checkOrientation);
    window.addEventListener("resize", checkOrientation);
</script>
"""
components.html(orientation_js, height=0, width=0)


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

        if "날짜" in save_df.columns:
            cols = ["날짜"] + [c for c in save_df.columns if c != "날짜"]
            save_df = save_df[cols]

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
        st.session_state.memos = saved_memos
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
# 상위 메뉴용 종료 확인 다이얼로그 (팝업)
# ---------------------------------------------------------
@st.dialog("⚠️ 프로그램 종료 확인")
def confirm_exit_dialog():
    st.write("정말로 숙직 근무 관리 시스템을 종료하시겠습니까?")
    st.write("종료 시 실행 중인 세션이 정지됩니다.")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("❌ 취소", use_container_width=True):
            st.rerun()
    with col_e2:
        if st.button("🔴 예 (종료)", use_container_width=True, type="primary"):
            st.session_state.is_app_closed = True
            st.rerun()


# ---------------------------------------------------------
# 근무자 수동 반복 등록 다이얼로그
# ---------------------------------------------------------
@st.dialog("🔄 근무자 수동 반복 등록")
def batch_register_worker_dialog():
    st.write("📅 **입력된 근무자만 규칙적으로 순환 등록되며, 비워둔 칸은 기존 엑셀 데이터를 유지합니다.**")

    today_default = datetime.date.today()
    saved_pat = st.session_state.get("batch_patterns", {})

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        start_date_input = st.date_input(
            "시작 날짜 선택",
            value=today_default,
            help="오늘 기준 앞뒤로 날짜를 선택하여 반복 등록을 시작할 지점입니다.",
        )
    with col_b2:
        total_days_count = st.number_input(
            "적용할 총 일수", min_value=1, max_value=180, value=30, step=1
        )

    st.divider()

    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.markdown("**:blue[근무자 1 패턴 설정]**")
        default_w1_int = saved_pat.get("interval1", 3)
        interval1 = st.number_input(
            "근무자1 반복 칸수 (주기)",
            min_value=1,
            max_value=30,
            value=int(default_w1_int),
            step=1,
            key="batch_w1_interval",
        )
        st.caption(f"💡 설정된 주기({interval1}개)만큼 아래에 이름 입력 칸이 생성됩니다.")
        
        default_w1_slots = saved_pat.get("w1_names", [])
        w1_names = []
        for i in range(int(interval1)):
            default_val = default_w1_slots[i] if i < len(default_w1_slots) else ""
            name_val = st.text_input(f"근무자1 - 순번 {i+1}", value=default_val, key=f"w1_slot_{i}")
            w1_names.append(name_val.strip())

    with col_p2:
        st.markdown("**:blue[근무자 2 패턴 설정]**")
        default_w2_int = saved_pat.get("interval2", 3)
        interval2 = st.number_input(
            "근무자2 반복 칸수 (주기)",
            min_value=1,
            max_value=30,
            value=int(default_w2_int),
            step=1,
            key="batch_w2_interval",
        )
        st.caption(f"💡 설정된 주기({interval2}개)만큼 아래에 이름 입력 칸이 생성됩니다.")
        
        default_w2_slots = saved_pat.get("w2_names", [])
        w2_names = []
        for i in range(int(interval2)):
            default_val = default_w2_slots[i] if i < len(default_w2_slots) else ""
            name_val = st.text_input(f"근무자2 - 순번 {i+1}", value=default_val, key=f"w2_slot_{i}")
            w2_names.append(name_val.strip())

    st.markdown("---")

    col_sub1, col_sub2 = st.columns([2, 1])
    with col_sub1:
        if st.button("💾 반복 순서 규칙 적용 및 저장", use_container_width=True, type="primary"):
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
                        
                        sub1_val = df.at[idx, "대직1"] if "대직1" in df.columns else None
                        if pd.isna(sub1_val) or str(sub1_val).strip() in ["", "nan", "None"]:
                            df.at[idx, "실제근무1"] = assigned_w1

                    if valid_w2:
                        assigned_w2 = valid_w2[i % len(valid_w2)]
                        df.at[idx, "근무자2"] = assigned_w2
                        
                        sub2_val = df.at[idx, "대직2"] if "대직2" in df.columns else None
                        if pd.isna(sub2_val) or str(sub2_val).strip() in ["", "nan", "None"]:
                            df.at[idx, "실제근무2"] = assigned_w2

                current_date += datetime.timedelta(days=1)

            st.session_state.df = df
            st.session_state.df["날짜"] = pd.to_datetime(st.session_state.df["날짜"], errors="coerce")
            st.session_state.df["년월"] = st.session_state.df["날짜"].dt.strftime("%Y-%m")
            st.session_state.df = st.session_state.df.sort_values(by="날짜").reset_index(drop=True)

            save_app_state(
                st.session_state.df,
                st.session_state.selected_sheet,
                st.session_state.memos,
                st.session_state.batch_patterns,
            )
            st.success("✅ 반복 패턴이 저장되었으며, 규칙에 따라 근무표에 성공적으로 반영되었습니다.")
            st.rerun()

    with col_sub2:
        if st.button("🚪 닫기", use_container_width=True):
            st.rerun()


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
            p1_sel = st.selectbox("근무자1 선택", options=worker_options, index=get_opt_idx(val_p1), key="p1_sel")
            p1_custom = st.text_input("근무자1 직접입력", value=val_p1 if p1_sel == "(직접 입력)" else "", key="p1_custom") if p1_sel == "(직접 입력)" else ""

            sub1_sel = st.selectbox("대직자1 선택 (선택사항)", options=worker_options, index=get_opt_idx(val_sub1), key="sub1_sel")
            sub1_custom = st.text_input("대직자1 직접입력", value=val_sub1 if sub1_sel == "(직접 입력)" else "", key="sub1_custom") if sub1_sel == "(직접 입력)" else ""

        with col_f2:
            st.markdown("**:blue[근무자 2 / 대직자 2]**")
            p2_sel = st.selectbox("근무자2 선택", options=worker_options, index=get_opt_idx(val_p2), key="p2_sel")
            p2_custom = st.text_input("근무자2 직접입력", value=val_p2 if p2_sel == "(직접 입력)" else "", key="p2_custom") if p2_sel == "(직접 입력)" else ""

            sub2_sel = st.selectbox("대직자2 선택 (선택사항)", options=worker_options, index=get_opt_idx(val_sub2), key="sub2_sel")
            sub2_custom = st.text_input("대직자2 직접입력", value=val_sub2 if sub2_sel == "(직접 입력)" else "", key="sub2_custom") if sub2_sel == "(직접 입력)" else ""

        st.divider()
        edit_memo = st.text_area("📌 날짜별 메모 (달력 표출)", value=current_memo, height=80)

        c_sub1, c_sub2 = st.columns([2, 1])
        with c_sub1:
            submitted = st.form_submit_button("💾 엑셀 저장 및 반영", use_container_width=True)
        with c_sub2:
            close_dialog = st.form_submit_button("🚪 창 닫기", use_container_width=True)

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
            st.success("✅ 변경사항이 성공적으로 저장되었습니다.")
            st.rerun()

        if close_dialog:
            st.rerun()


# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 근무표 파일 관리")

    if "file_name" in st.session_state:
        st.info(f"📄 현재 파일: `{st.session_state.file_name}`")

    uploaded_file = st.file_uploader("새 엑셀 파일 업로드", type=["xlsx"])

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

        st.success(f"✅ '{used_sheet}' 데이터 로드 완료 (기존 반복 패턴 유지됨)")
        st.rerun()

    st.divider()
    if st.button("🔴 앱종료", use_container_width=True):
        confirm_exit_dialog()


df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 화면 - 탭 구성
# ---------------------------------------------------------
st.title("📋 숙직 근무 관리 대시보드")

tab1, tab2, tab3, tab4 = st.tabs([
    "📅 달력 메인 화면",
    "✏️ 근무표 전체 수정",
    "📊 월별 근무 통계",
    "🔍 시트 데이터 점검",
])

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면 (스와이프/드래그 이동 & 오늘 날짜 강조)
# ---------------------------------------------------------
with tab1:
    today_df = df[df["날짜"].dt.date == today]
    today_str = today.strftime("%Y년 %m월 %d일")

    if not today_df.empty:
        t_row = today_df.iloc[0]
        p1 = f"{t_row['실제근무1']}(대)" if pd.notnull(t_row.get("대직1")) and str(t_row.get("대직1")).strip() else t_row["실제근무1"]
        p2 = f"{t_row['실제근무2']}(대)" if pd.notnull(t_row.get("대직2")) and str(t_row.get("대직2")).strip() else t_row["실제근무2"]
        t_memo = st.session_state.memos.get(today.strftime("%Y-%m-%d"), "")
        memo_str = f" | 📌 메모: {t_memo}" if t_memo else ""

        st.markdown(
            f"""
        <div class="today-card">
            <div style="font-size:12px; opacity:0.9; margin-bottom:2px;">🚨 오늘의 숙직 근무자 ({today_str})</div>
            <div style="font-size:15px; font-weight:bold;">
                근무자 1: <span>{p1}</span> &nbsp;|&nbsp; 
                근무자 2: <span>{p2}</span>
                <span style="font-size:13px; font-weight:normal;">{memo_str}</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    available_months = sorted(df["년월"].dropna().unique())
    current_ym = today.strftime("%Y-%m")
    
    # URL 파라미터에서 스와이프를 통한 월 변경 감지
    query_params = st.query_params
    param_month = query_params.get("month", None)

    if param_month and param_month in available_months:
        default_idx = available_months.index(param_month)
    else:
        default_idx = available_months.index(current_ym) if current_ym in available_months else 0

    mode_param = query_params.get("mode", "list")
    default_radio_idx = 1 if mode_param == "grid" else 0

    with st.container():
        st.markdown('<div class="month-select-box">', unsafe_allow_html=True)
        col_m1, col_m2, col_m3, col_m4 = st.columns([1, 1.2, 1, 0.9])
        with col_m1:
            selected_month = st.selectbox(
                "📅 조회 월 선택 (좌우 스와이프 지원)",
                available_months,
                index=default_idx,
                key="calendar_month_select",
            )
        with col_m2:
            calendar_view_type = st.radio(
                "📐 달력 표시 방식",
                options=["📄 세로형 리스트", "🗓️ 가로형 Grid"],
                index=default_radio_idx,
                horizontal=True,
                key="calendar_view_type",
            )
        with col_m3:
            selected_theme = st.radio(
                "🎨 테마 선택",
                options=["☀️ 화이트 테마", "🌙 블랙 테마"],
                index=1 if st.session_state.app_theme == "🌙 블랙 테마" else 0,
                horizontal=True,
                key="theme_radio_select",
            )
            if selected_theme != st.session_state.app_theme:
                st.session_state.app_theme = selected_theme
                st.rerun()
        with col_m4:
            st.write("")
            st.write("")
            if st.button("🔄 수동 반복 등록", use_container_width=True):
                batch_register_worker_dialog()

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 터치 스와이프 및 마우스 드래그 감지 JavaScript 주입 (버튼 없이 거리 비례 이동)
    # ---------------------------------------------------------
    available_months_json = json.dumps(available_months)
    swipe_js = f"""
    <script>
    (function() {{
        const doc = window.parent.document || document;
        let startX = 0;
        let startY = 0;
        let isDragging = false;
        const THRESHOLD = 70; // 1달 이동 기준 픽셀 거리

        function handleStart(x, y) {{
            startX = x;
            startY = y;
            isDragging = true;
        }}

        function handleEnd(endX, endY) {{
            if (!isDragging) return;
            isDragging = false;

            const diffX = startX - endX; // 양수: 왼쪽으로 드래그(다음달), 음수: 오른쪽으로 드래그(이전달)
            const diffY = startY - endY;

            // 수평 드래그가 수직 스크롤보다 크고, 최소 THRESHOLD 이상일 때 실행
            if (Math.abs(diffX) > Math.abs(diffY) * 1.2 && Math.abs(diffX) >= THRESHOLD) {{
                // 이동한 거리에 비례하여 월 오프셋(개수) 계산
                const offset = Math.round(diffX / THRESHOLD);
                if (offset !== 0) {{
                    const months = {available_months_json};
                    const current = "{selected_month}";
                    const idx = months.indexOf(current);
                    if (idx !== -1) {{
                        let newIdx = idx + offset;
                        if (newIdx < 0) newIdx = 0;
                        if (newIdx >= months.length) newIdx = months.length - 1;

                        if (newIdx !== idx) {{
                            const targetMonth = months[newIdx];
                            const url = new URL(window.parent.location.href);
                            url.searchParams.set('month', targetMonth);
                            window.parent.location.href = url.href;
                        }}
                    }}
                }}
            }}
        }}

        // 터치 스와이프 이벤트
        doc.addEventListener('touchstart', function(e) {{
            if (e.touches && e.touches.length === 1) {{
                handleStart(e.touches[0].clientX, e.touches[0].clientY);
            }}
        }}, {{passive: true}});

        doc.addEventListener('touchend', function(e) {{
            if (e.changedTouches && e.changedTouches.length === 1) {{
                handleEnd(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
            }}
        }}, {{passive: true}});

        // 마우스 드래그 이벤트 (입력창/버튼 클릭 시 무시)
        doc.addEventListener('mousedown', function(e) {{
            const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
            if (['button', 'input', 'select', 'textarea', 'a'].includes(tag)) return;
            handleStart(e.clientX, e.clientY);
        }});

        doc.addEventListener('mouseup', function(e) {{
            handleEnd(e.clientX, e.clientY);
        }});
    }})();
    </script>
    """
    components.html(swipe_js, height=0, width=0)

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
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

        st.caption("💡 화면을 좌우로 터치 스와이프하거나 드래그하여 밀어낸 거리만큼 전후달로 쉽게 이동할 수 있습니다.")

        if calendar_view_type == "📄 세로형 리스트":
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
            for day in range(1, num_days + 1):
                curr_date = datetime.date(year, month, day)
                is_today = (curr_date == today)
                date_str = curr_date.strftime("%Y-%m-%d")
                weekday_idx = curr_date.weekday()
                weekday_str = weekdays_kr[weekday_idx]
                duty_info = duty_map.get(day)

                today_tag = "📍 [오늘] " if is_today else ""

                if weekday_idx == 6 or curr_date in kr_holidays:
                    day_title = f"{today_tag}🔴 {day:02d}일({weekday_str})"
                elif weekday_idx == 5:
                    day_title = f"{today_tag}🔵 {day:02d}일({weekday_str})"
                else:
                    day_title = f"{today_tag}🗓️ {day:02d}일({weekday_str})"

                p1_txt = duty_info["p1_display"] if duty_info else "미지정"
                p2_txt = duty_info["p2_display"] if duty_info else "미지정"
                day_memo = st.session_state.memos.get(date_str, "")
                memo_display = f" | 📌 {day_memo}" if day_memo else ""

                btn_label = f"{day_title} | 1:{p1_txt} | 2:{p2_txt}{memo_display}"

                if st.button(btn_label, key=f"btn_v_card_{date_str}"):
                    if duty_info:
                        edit_worker_dialog(date_str, duty_info)
        else:
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
                    f"<div style='text-align: center; color: {color}; font-weight: bold; font-size: clamp(12px, 2.5vw, 15px); padding-bottom: 5px;'>{h_name}</div>",
                    unsafe_allow_html=True,
                )

            st.divider()
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
                        is_today = (curr_date == today)
                        date_str = curr_date.strftime("%Y-%m-%d")
                        duty_info = duty_map.get(day_counter)

                        p1_txt = duty_info["p1_display"] if duty_info else "-"
                        p2_txt = duty_info["p2_display"] if duty_info else "-"
                        day_memo = st.session_state.memos.get(date_str, "")

                        today_tag = "📍[오늘]\n" if is_today else ""
                        memo_tag = f"\n📌{day_memo}" if day_memo else ""

                        btn_text = f"{today_tag}{day_counter}일\n{p1_txt}\n{p2_txt}{memo_tag}"

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
        st.success("✅ 엑셀 파일 및 대시보드에 성공적으로 저장되었습니다.")
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
