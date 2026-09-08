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

# 세션 상태 초기화 (종료 여부 및 화면 방향 플래그)
if "is_app_closed" not in st.session_state:
    st.session_state.is_app_closed = False

if "auto_view_type" not in st.session_state:
    st.session_state.auto_view_type = "📄 세로형 리스트"

# 앱이 종료된 경우 화면 표시
if st.session_state.is_app_closed:
    st.title("👋 시스템이 종료되었습니다.")
    st.info("다시 이용하시려면 브라우저 페이지를 새로고침(F5) 해주세요.")
    st.stop()

# ---------------------------------------------------------
# CSS 및 화면 회전 자바스크립트 감지
# ---------------------------------------------------------
responsive_css = """
<style>
    /* viewport 최적화 및 모바일 기본 방어 */
    html, body, [data-testid="stAppViewContainer"] {
        width: 100vw !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }

    .main .block-container {
        padding: 0.5rem 0.5rem !important;
        max-width: 100% !important;
        width: 100% !important;
    }

    /* 조회월 선택 박스 스타일 */
    .month-select-box {
        background-color: #F8FAFC;
        border: 1.5px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
    }

    /* 오늘의 근무자 카드 */
    .today-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 10px;
        margin-bottom: 12px;
        width: 100%;
        box-sizing: border-box;
    }

    /* 버튼 모바일 반응형 폰트 및 패딩 조정 */
    .stButton > button {
        width: 100% !important;
        min-height: 44px !important;
        padding: 6px 8px !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        box-sizing: border-box !important;
        text-align: center !important;
        font-size: clamp(11px, 2.5vw, 14px) !important;
        font-weight: 500 !important;
        margin-bottom: 4px !important;
        white-space: pre-line !important;
        line-height: 1.2 !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        border-color: #2563EB !important;
        background-color: #F0F6FF !important;
    }

    /* 모바일 가로 모드 자동 대응 미디어 쿼리 */
    @media screen and (max-width: 768px) and (orientation: landscape) {
        .main .block-container {
            padding: 0.2rem 0.2rem !important;
        }
        .stButton > button {
            min-height: 38px !important;
            font-size: 11px !important;
        }
    }

    [data-testid="stDialog"] > div:first-child {
        width: clamp(300px, 90vw, 550px) !important;
        max-width: 95vw !important;
        max-height: 85vh !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        overflow-y: auto !important;
    }
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

# 화면 회전 및 Orientation 변경 자동 감지 JS
orientation_js = """
<script>
    function checkOrientation() {
        const isLandscape = window.matchMedia("(orientation: landscape)").matches;
        const currentMode = isLandscape ? "🗓️ 가로형 Grid" : "📄 세로형 리스트";
        
        // URL 쿼리 파라미터를 이용하여 자동 전환 트리거
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


def save_app_state(df, sheet_name, memos):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")

        if "날짜" in save_df.columns:
            cols = ["날짜"] + [c for c in save_df.columns if c != "날짜"]
            save_df = save_df[cols]

        state_data = {
            "selected_sheet": sheet_name,
            "memos": memos,
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
            )
        except Exception:
            return None, None, None
    return None, None, None


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
    saved_df, saved_sheet, saved_memos = load_app_state()

    if saved_df is not None:
        st.session_state.df = saved_df
        st.session_state.selected_sheet = saved_sheet
        st.session_state.memos = saved_memos
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
    else:
        today_date = datetime.date.today()
        dates = pd.date_range(start=today_date.replace(day=1), periods=60, freq="D")
        sample_df = pd.DataFrame({
            "날짜": dates,
            "근무구분_원본": ["평일", "금요일", "토요일", "일요일", "평일"] * 12,
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
# 하위 레이어: 근무자 수정 다이얼로그
# ---------------------------------------------------------
@st.dialog("✏️ 근무자 수정 및 메모 작성")
def edit_worker_dialog(date_str, duty_info):
    st.write(f"📅 **{date_str} 근무 정보 수정**")

    row_idx = duty_info["idx"]
    curr_row = st.session_state.df.loc[row_idx]

    worker_options = get_all_workers_list(st.session_state.df)

    val_p1 = (
        str(curr_row.get("근무자1", ""))
        if pd.notnull(curr_row.get("근무자1"))
        else ""
    )
    val_p2 = (
        str(curr_row.get("근무자2", ""))
        if pd.notnull(curr_row.get("근무자2"))
        else ""
    )
    val_sub1 = (
        str(curr_row.get("대직1", ""))
        if pd.notnull(curr_row.get("대직1"))
        else ""
    )
    val_sub2 = (
        str(curr_row.get("대직2", ""))
        if pd.notnull(curr_row.get("대직2"))
        else ""
    )

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
            p1_sel = st.selectbox(
                "근무자1 선택",
                options=worker_options,
                index=get_opt_idx(val_p1),
                key="p1_sel",
            )
            p1_custom = (
                st.text_input(
                    "근무자1 직접입력",
                    value=val_p1 if p1_sel == "(직접 입력)" else "",
                    key="p1_custom",
                )
                if p1_sel == "(직접 입력)"
                else ""
            )

            sub1_sel = st.selectbox(
                "대직자1 선택 (선택사항)",
                options=worker_options,
                index=get_opt_idx(val_sub1),
                key="sub1_sel",
            )
            sub1_custom = (
                st.text_input(
                    "대직자1 직접입력",
                    value=val_sub1 if sub1_sel == "(직접 입력)" else "",
                    key="sub1_custom",
                )
                if sub1_sel == "(직접 입력)"
                else ""
            )

        with col_f2:
            st.markdown("**:blue[근무자 2 / 대직자 2]**")
            p2_sel = st.selectbox(
                "근무자2 선택",
                options=worker_options,
                index=get_opt_idx(val_p2),
                key="p2_sel",
            )
            p2_custom = (
                st.text_input(
                    "근무자2 직접입력",
                    value=val_p2 if p2_sel == "(직접 입력)" else "",
                    key="p2_custom",
                )
                if p2_sel == "(직접 입력)"
                else ""
            )

            sub2_sel = st.selectbox(
                "대직자2 선택 (선택사항)",
                options=worker_options,
                index=get_opt_idx(val_sub2),
                key="sub2_sel",
            )
            sub2_custom = (
                st.text_input(
                    "대직자2 직접입력",
                    value=val_sub2 if sub2_sel == "(직접 입력)" else "",
                    key="sub2_custom",
                )
                if sub2_sel == "(직접 입력)"
                else ""
            )

        st.divider()
        edit_memo = st.text_area(
            "📌 날짜별 메모 (달력 표출)", value=current_memo, height=80
        )

        c_sub1, c_sub2 = st.columns([2, 1])
        with c_sub1:
            submitted = st.form_submit_button(
                "💾 엑셀 저장 및 반영", use_container_width=True
            )
        with c_sub2:
            close_dialog = st.form_submit_button(
                "🚪 창 닫기", use_container_width=True
            )

        if submitted:
            final_p1 = (
                p1_custom.strip()
                if p1_sel == "(직접 입력)"
                else ("" if p1_sel == "(선택 안함)" else p1_sel)
            )
            final_p2 = (
                p2_custom.strip()
                if p2_sel == "(직접 입력)"
                else ("" if p2_sel == "(선택 안함)" else p2_sel)
            )
            final_sub1 = (
                sub1_custom.strip()
                if sub1_sel == "(직접 입력)"
                else ("" if sub1_sel == "(선택 안함)" else sub1_sel)
            )
            final_sub2 = (
                sub2_custom.strip()
                if sub2_sel == "(직접 입력)"
                else ("" if sub2_sel == "(선택 안함)" else sub2_sel)
            )

            st.session_state.df.at[row_idx, "근무자1"] = final_p1
            st.session_state.df.at[row_idx, "근무자2"] = final_p2
            st.session_state.df.at[row_idx, "대직1"] = (
                final_sub1 if final_sub1 else None
            )
            st.session_state.df.at[row_idx, "대직2"] = (
                final_sub2 if final_sub2 else None
            )

            st.session_state.df.at[row_idx, "실제근무1"] = (
                final_sub1 if final_sub1 else final_p1
            )
            st.session_state.df.at[row_idx, "실제근무2"] = (
                final_sub2 if final_sub2 else final_p2
            )

            st.session_state.memos[date_str] = edit_memo.strip()

            save_app_state(
                st.session_state.df,
                st.session_state.selected_sheet,
                st.session_state.memos,
            )
            st.success(
                "✅ 변경사항이 엑셀 파일 및 달력에 성공적으로 저장되었습니다."
            )
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

        parsed_df, used_sheet, sheet_names, raw_df, f_bytes = load_excel_smart(
            file_bytes
        )

        st.session_state.file_path = save_path
        st.session_state.file_bytes = f_bytes
        st.session_state.file_name = uploaded_file.name
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
        st.session_state.memos = {}

        if os.path.exists(PERSISTENCE_STATE_PATH):
            os.remove(PERSISTENCE_STATE_PATH)
        save_app_state(parsed_df, used_sheet, {})

        st.success(f"✅ '{used_sheet}' 데이터 로드 완료")
        st.rerun()

    st.divider()
    if st.button("🔴 시스템 종료", use_container_width=True):
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
# TAB 1: 달력 메인 화면 (화면 회전 및 비례 자동 적용)
# ---------------------------------------------------------
with tab1:
    today_df = df[df["날짜"].dt.date == today]
    today_str = today.strftime("%Y년 %m월 %d일")

    if not today_df.empty:
        t_row = today_df.iloc[0]
        p1 = (
            f"{t_row['실제근무1']}(대)"
            if pd.notnull(t_row.get("대직1")) and str(t_row.get("대직1")).strip()
            else t_row["실제근무1"]
        )
        p2 = (
            f"{t_row['실제근무2']}(대)"
            if pd.notnull(t_row.get("대직2")) and str(t_row.get("대직2")).strip()
            else t_row["실제근무2"]
        )
        t_memo = st.session_state.memos.get(today.strftime("%Y-%m-%d"), "")
        memo_str = f" | 📌 메모: {t_memo}" if t_memo else ""

        st.markdown(
            f"""
        <div class="today-card">
            <div style="font-size:12px; opacity:0.9; margin-bottom:2px;">🚨 오늘의 숙직 근무자 ({today_str})</div>
            <div style="font-size:15px; font-weight:bold;">
                근무자 1: <span style="color:#FDE047;">{p1}</span> &nbsp;|&nbsp; 
                근무자 2: <span style="color:#FDE047;">{p2}</span>
                <span style="font-size:13px; font-weight:normal;">{memo_str}</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    available_months = sorted(df["년월"].dropna().unique())
    current_ym = today.strftime("%Y-%m")
    default_idx = (
        available_months.index(current_ym)
        if current_ym in available_months
        else 0
    )

    # URL 쿼리 파라미터를 읽어 회전 상태에 따라 라디오 기본값 자동 동기화
    query_params = st.query_params
    mode_param = query_params.get("mode", "list")
    default_radio_idx = 1 if mode_param == "grid" else 0

    with st.container():
        st.markdown('<div class="month-select-box">', unsafe_allow_html=True)
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            selected_month = st.selectbox(
                "📅 조회 월 선택",
                available_months,
                index=default_idx,
                key="calendar_month_select",
            )
        with col_m2:
            calendar_view_type = st.radio(
                "📐 달력 표시 방식 선택 (회전 시 자동 전환)",
                options=["📄 세로형 리스트", "🗓️ 가로형 Grid"],
                index=default_radio_idx,
                horizontal=True,
                key="calendar_view_type",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
        num_days = calendar.monthrange(year, month)[1]
        month_df = df[df["년월"] == selected_month].copy()

        duty_map = {}
        for idx_row, row in month_df.iterrows():
            d_day = row["날짜"].day
            d_date_str = row["날짜"].strftime("%Y-%m-%d")

            sub1_val = (
                str(row["대직1"]).strip() if pd.notnull(row["대직1"]) else ""
            )
            sub2_val = (
                str(row["대직2"]).strip() if pd.notnull(row["대직2"]) else ""
            )

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

        st.caption(
            "💡 각 날짜 항목을 클릭하면 근무자 수정 및 메모 작성이 가능합니다."
        )

        # ---------------------------------------------------------
        # 1) 세로형 리스트 보기 (세로 모드에 최적화)
        # ---------------------------------------------------------
        if calendar_view_type == "📄 세로형 리스트":
            weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]

            for day in range(1, num_days + 1):
                curr_date = datetime.date(year, month, day)
                date_str = curr_date.strftime("%Y-%m-%d")
                weekday_idx = curr_date.weekday()
                weekday_str = weekdays_kr[weekday_idx]
                duty_info = duty_map.get(day)

                if weekday_idx == 6 or curr_date in kr_holidays:
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

        # ---------------------------------------------------------
        # 2) 가로형 Grid 보기 (가로 모드 및 넓은 화면에 최적화)
        # ---------------------------------------------------------
        else:
            headers = ["일", "월", "화", "수", "목", "금", "토"]
            cols_header = st.columns(7)
            for idx, h_name in enumerate(headers):
                if idx == 0:
                    cols_header[idx].markdown(
                        f"<div style='text-align: center; color: red; font-weight: bold; font-size: 13px;'>{h_name}</div>",
                        unsafe_allow_html=True,
                    )
                elif idx == 6:
                    cols_header[idx].markdown(
                        f"<div style='text-align: center; color: blue; font-weight: bold; font-size: 13px;'>{h_name}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    cols_header[idx].markdown(
                        f"<div style='text-align: center; font-weight: bold; font-size: 13px;'>{h_name}</div>",
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
                        date_str = curr_date.strftime("%Y-%m-%d")
                        duty_info = duty_map.get(day_counter)

                        p1_txt = duty_info["p1_display"] if duty_info else "-"
                        p2_txt = duty_info["p2_display"] if duty_info else "-"
                        day_memo = st.session_state.memos.get(date_str, "")
                        memo_icon = "📌" if day_memo else ""

                        btn_text = f"{day_counter}일{memo_icon}\n1:{p1_txt}\n2:{p2_txt}"

                        if grid_cols[c].button(
                            btn_text, key=f"btn_grid_card_{date_str}"
                        ):
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
    default_edit_idx = (
        edit_months.index(current_ym) if current_ym in edit_months else 0
    )

    col_ctrl1, col_ctrl2 = st.columns([1, 1])

    with col_ctrl1:
        selected_edit_month = st.selectbox(
            "📅 근무 월 선택 검색",
            edit_months,
            index=default_edit_idx,
            key="edit_month_filter",
        )

    if selected_edit_month == "전체 기간":
        target_editor_df = st.session_state.df.copy()
    else:
        target_editor_df = st.session_state.df[
            st.session_state.df["년월"] == selected_edit_month
        ].copy()

    if "날짜" in target_editor_df.columns:
        cols = ["날짜"] + [c for c in target_editor_df.columns if c != "날짜"]
        target_editor_df = target_editor_df[cols]

    with col_ctrl2:
        st.write("")
        save_btn_clicked = st.button(
            "💾 변경사항 적용 및 엑셀 저장",
            key="top_save_btn",
            use_container_width=True,
            type="primary",
        )

    st.caption("아래 표에서 근무자, 대직자 및 근무 구분을 직접 수정할 수 있습니다.")

    edited_df = st.data_editor(
        target_editor_df,
        num_rows="dynamic",
        key=f"data_editor_{selected_edit_month}",
        use_container_width=True,
    )

    if save_btn_clicked:
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df = edited_df.dropna(subset=["날짜"]).copy()

        edited_df["근무구분_원본"] = (
            edited_df["근무구분_원본"].astype(str).str.strip()
        )
        edited_df["년월"] = edited_df["날짜"].dt.strftime("%Y-%m")

        edited_df["실제근무1"] = (
            edited_df["대직1"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자1"])
            .fillna("미지정")
        )
        edited_df["실제근무2"] = (
            edited_df["대직2"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자2"])
            .fillna("미지정")
        )

        if selected_edit_month == "전체 기간":
            full_df = edited_df
        else:
            other_df = st.session_state.df[
                st.session_state.df["년월"] != selected_edit_month
            ]
            full_df = pd.concat([other_df, edited_df], ignore_index=True)

        full_df = full_df.sort_values(by="날짜").reset_index(drop=True)
        cols = ["날짜"] + [c for c in full_df.columns if c != "날짜"]
        st.session_state.df = full_df[cols]

        save_app_state(
            st.session_state.df,
            st.session_state.selected_sheet,
            st.session_state.memos,
        )
        st.success("✅ 엑셀 파일 및 대시보드에 성공적으로 저장되었습니다.")
        st.rerun()

# ---------------------------------------------------------
# TAB 3: 숙직근무자 월별 근무 통계
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 숙직근무자 월별 근무 통계")

    duty_stat_df = st.session_state.df.copy()

    available_stat_months = ["전체 기간"] + sorted(
        duty_stat_df["년월"].dropna().unique(), reverse=True
    )
    curr_ym = today.strftime("%Y-%m")
    default_stat_idx = (
        available_stat_months.index(curr_ym)
        if curr_ym in available_stat_months
        else 0
    )

    stat_col1, stat_col2 = st.columns([1, 2])
    with stat_col1:
        selected_stat_month = st.selectbox(
            "📅 통계조회 월선택",
            available_stat_months,
            index=default_stat_idx,
            key="stat_month_select",
        )

    filtered_df = (
        duty_stat_df.copy()
        if selected_stat_month == "전체 기간"
        else duty_stat_df[duty_stat_df["년월"] == selected_stat_month].copy()
    )

    w1 = filtered_df[["실제근무1", "근무구분_원본"]].rename(
        columns={"실제근무1": "근무자", "근무구분_원본": "근무구분"}
    )
    w2 = filtered_df[["실제근무2", "근무구분_원본"]].rename(
        columns={"실제근무2": "근무자", "근무구분_원본": "근무구분"}
    )

    combined = pd.concat([w1, w2], ignore_index=True)
    combined["근무자"] = combined["근무자"].astype(str).str.strip()
    combined["근무구분"] = combined["근무구분"].astype(str).str.strip()

    combined = combined[
        combined["근무자"].notnull()
        & (~combined["근무자"].isin(["미지정", "nan", "None", "", "NaN"]))
        & (~combined["근무구분"].isin(["nan", "None", "", "NaN"]))
    ]

    if not combined.empty:
        stats_df = pd.crosstab(
            index=combined["근무자"],
            columns=combined["근무구분"],
            margins=False,
        )

        sat_cnt = stats_df["토요일"] if "토요일" in stats_df.columns else 0
        sun_cnt = stats_df["일요일"] if "일요일" in stats_df.columns else 0
        stats_df["휴일근무 횟수"] = sat_cnt + sun_cnt

        hours_per_type = {
            "금요일": 15,
            "토요일": 15,
            "일요일": 7,
            "평일": 7,
        }

        total_hours = pd.Series(0, index=stats_df.index)
        for col in stats_df.columns:
            if col in hours_per_type:
                total_hours += stats_df[col] * hours_per_type[col]
            elif col not in ["총 근무 횟수", "휴일근무 횟수"]:
                total_hours += stats_df[col] * 7

        stats_df["총 근무시간(h)"] = total_hours

        type_cols = [
            c
            for c in stats_df.columns
            if c not in ["총 근무 횟수", "휴일근무 횟수", "총 근무시간(h)"]
        ]
        stats_df["총 근무 횟수"] = stats_df[type_cols].sum(axis=1)

        ordered_cols = type_cols + [
            "휴일근무 횟수",
            "총 근무 횟수",
            "총 근무시간(h)",
        ]
        stats_df = stats_df[ordered_cols].sort_values(
            by="총 근무시간(h)", ascending=False
        )

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
