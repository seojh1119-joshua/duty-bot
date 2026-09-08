import calendar
import datetime
import glob
import io
import json
import os
import pandas as pd
import streamlit as st

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

# ---------------------------------------------------------
# CSS 스타일링 (전체 화면 맞춤 & 요일/셀 비율 고정 & 팝업 반응형)
# ---------------------------------------------------------
responsive_css = """
<style>
    /* 1. 전체 루트 및 메인 레이아웃 뷰포트 고정 */
    html, body, [data-testid="stAppViewContainer"] {
        height: 100vh !important;
        overflow-x: hidden !important;
    }

    .main .block-container {
        padding: 0.5rem 0.5rem 0.5rem 0.5rem !important;
        max-width: 100% !important;
        height: calc(100vh - 1rem) !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* 탭 영역 수직 자동 확장 */
    [data-testid="stTabs"] {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
        height: 100% !important;
        overflow: hidden !important;
    }

    [data-testid="stTabPanel"] {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
        height: 100% !important;
        overflow: auto !important;
    }

    /* 2. 요일 및 달력 7열 정렬 (Grid 1fr 방식 적용하여 너비 어긋남 방지) */
    [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(7, minmax(0, 1fr)) !important;
        gap: 4px !important;
        width: 100% !important;
        margin: 0 0 4px 0 !important;
    }

    [data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        flex: none !important;
        padding: 0px !important;
        margin: 0px !important;
    }

    /* 3. 요일 헤더 박스 */
    .cal-header {
        text-align: center;
        font-size: clamp(11px, 1.1vw, 15px);
        font-weight: bold;
        padding: 6px 0;
        border-radius: 4px;
        width: 100% !important;
        box-sizing: border-box;
        white-space: nowrap;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .calendar-header-sun {
        background-color: #FEE2E2;
        color: #DC2626;
    }
    
    .calendar-header-sat {
        background-color: #DBEAFE;
        color: #2563EB;
    }

    .calendar-header-weekday {
        background-color: #F1F5F9;
        color: #1E293B;
    }

    /* 4. 달력 버튼 셀 비율 자동 조절 */
    .stButton {
        width: 100% !important;
        height: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    .stButton > button {
        width: 100% !important;
        height: 100% !important;
        min-height: clamp(60px, 9.5vh, 120px) !important;
        padding: 4px 5px !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 4px !important;
        background-color: #FFFFFF !important;
        color: #1E293B !important;
        font-size: clamp(9px, 0.85vw, 13px) !important;
        line-height: 1.3 !important;
        text-align: left !important;
        box-sizing: border-box !important;

        /* 자동 줄바꿈 및 오버플로우 제어 */
        white-space: pre-wrap !important;
        white-space: break-spaces !important;
        word-break: break-all !important;
        overflow-wrap: break-word !important;

        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
    }

    .stButton > button * {
        white-space: pre-wrap !important;
        white-space: break-spaces !important;
        word-break: break-all !important;
        text-align: left !important;
    }

    .stButton > button:hover {
        border-color: #2563EB !important;
        background-color: #F8FAFC !important;
    }

    /* 5. 수정 다이얼로그(팝업) 반응형 자동 조절 및 중앙 배치 */
    [data-testid="stDialog"] > div:first-child {
        width: clamp(320px, 85vw, 600px) !important;
        max-width: 90vw !important;
        max-height: 85vh !important;
        border-radius: 12px !important;
        padding: 1.2rem !important;
        overflow-y: auto !important;
    }

    /* 오늘 근무자 카드 */
    .today-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
        flex-shrink: 0;
    }

    /* 모바일 기기 반응형 미세 조절 */
    @media (max-width: 600px) {
        .stButton > button {
            min-height: 50px !important;
            padding: 2px 2px !important;
            font-size: 8px !important;
            line-height: 1.15 !important;
        }
        .cal-header {
            font-size: 10px !important;
            padding: 4px 0 !important;
        }
    }
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)


# ---------------------------------------------------------
# DATA/data 폴더 내 기본 엑셀 파일 자동 탐색
# ---------------------------------------------------------
def get_initial_excel_file():
    candidates = (
        glob.glob(os.path.join("DATA", "*.xlsx"))
        + glob.glob(os.path.join("data", "*.xlsx"))
        + glob.glob("*.xlsx")
    )
    valid_files = [f for f in candidates if not os.path.basename(f).startswith("~$")]
    return valid_files[0] if valid_files else None


# ---------------------------------------------------------
# 앱 데이터 영구 저장/로드 관리
# ---------------------------------------------------------
def save_app_state(df, sheet_name, memos):
    try:
        save_df = df.copy()
        if "날짜" in save_df.columns:
            save_df["날짜"] = pd.to_datetime(save_df["날짜"]).dt.strftime("%Y-%m-%d")

        state_data = {
            "selected_sheet": sheet_name,
            "memos": memos,
            "df_dict": save_df.to_dict(orient="records"),
        }
        with open(PERSISTENCE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
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

    return df, target_sheet, sheet_names, df_raw, file_bytes


# ---------------------------------------------------------
# 세션 상태 초기화 및 파일 로드
# ---------------------------------------------------------
initial_file = get_initial_excel_file()

if "file_bytes" not in st.session_state and initial_file:
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
            "근무자1": ["서진호", "김철수", "이영희", "박민수", "정수진"] * 12,
            "근무자2": ["김철수", "이영희", "박민수", "정수진", "서진호"] * 12,
            "대직1": [None] * 60,
            "대직2": [None] * 60,
        })
        sample_df["년월"] = sample_df["날짜"].dt.strftime("%Y-%m")
        sample_df["실제근무1"] = sample_df["근무자1"]
        sample_df["실제근무2"] = sample_df["근무자2"]

        st.session_state.df = sample_df
        st.session_state.sheet_names = ["숙직근무자"]
        st.session_state.selected_sheet = "숙직근무자"
        st.session_state.raw_df = pd.DataFrame()
        st.session_state.memos = {}


# ---------------------------------------------------------
# 수정 다이얼로그 모달 (반응형 비율 조절 & 뒤로 가기 감지)
# ---------------------------------------------------------
@st.dialog("✏️ 근무자 수정 및 메모 작성")
def edit_worker_dialog(date_str, duty_info):
    # 뒤로 가기(popstate) 이벤트 감지를 위한 스크립트
    st.components.v1.html(
        """
        <script>
            if (window.location.hash !== "#edit-dialog") {
                window.history.pushState({dialogOpen: true}, "", "#edit-dialog");
            }

            window.addEventListener("popstate", function(event) {
                const closeBtn = window.parent.document.querySelector('[data-testid="stDialog"] button[aria-label="Close"]');
                if (closeBtn) {
                    closeBtn.click();
                }
            }, { once: true });
        </script>
        """,
        height=0,
    )

    st.write(f"📅 **{date_str} 정보 수정**")

    current_memo = st.session_state.memos.get(date_str, "")

    with st.form(key=f"dialog_form_{date_str}"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            edit_p1 = st.text_input("근무자1", value=duty_info["p1_orig"])
            edit_sub1 = st.text_input("대직자1", value=duty_info["sub1"])
        with col_f2:
            edit_p2 = st.text_input("근무자2", value=duty_info["p2_orig"])
            edit_sub2 = st.text_input("대직자2", value=duty_info["sub2"])

        st.divider()
        edit_memo = st.text_area(
            "📌 날짜별 메모 (달력 셀에 즉시 반영)",
            value=current_memo,
            height=90,
        )

        submitted = st.form_submit_button("💾 저장하기", use_container_width=True)

        if submitted:
            row_idx = duty_info["idx"]

            st.session_state.df.at[row_idx, "근무자1"] = edit_p1.strip()
            st.session_state.df.at[row_idx, "근무자2"] = edit_p2.strip()
            st.session_state.df.at[row_idx, "대직1"] = (
                edit_sub1.strip() if edit_sub1.strip() else None
            )
            st.session_state.df.at[row_idx, "대직2"] = (
                edit_sub2.strip() if edit_sub2.strip() else None
            )

            st.session_state.df.at[row_idx, "실제근무1"] = (
                edit_sub1.strip() if edit_sub1.strip() else edit_p1.strip()
            )
            st.session_state.df.at[row_idx, "실제근무2"] = (
                edit_sub2.strip() if edit_sub2.strip() else edit_p2.strip()
            )

            st.session_state.memos[date_str] = edit_memo.strip()

            save_app_state(
                st.session_state.df,
                st.session_state.selected_sheet,
                st.session_state.memos,
            )
            st.success("✅ 변경사항이 반영되었습니다.")
            st.rerun()


# ---------------------------------------------------------
# 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 파일 및 시트 설정")

    if "file_name" in st.session_state:
        st.info(f"📄 로드된 파일: `{st.session_state.file_name}`")

    uploaded_file = st.file_uploader("새 엑셀 파일 업로드", type=["xlsx"])

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        parsed_df, used_sheet, sheet_names, raw_df, f_bytes = load_excel_smart(
            file_bytes
        )

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

        st.success(f"✅ '{used_sheet}' 시트를 불러왔습니다.")
        st.rerun()

    if "sheet_names" in st.session_state and st.session_state.sheet_names:
        sheets = st.session_state.sheet_names
        curr_sheet = st.session_state.selected_sheet
        curr_idx = sheets.index(curr_sheet) if curr_sheet in sheets else 0

        selected_s = st.selectbox("📌 시트 선택", sheets, index=curr_idx)
        if selected_s != st.session_state.selected_sheet:
            st.session_state.selected_sheet = selected_s
            if "file_bytes" in st.session_state:
                parsed_df, used_sheet, _, raw_df, _ = load_excel_smart(
                    st.session_state.file_bytes, selected_s
                )
                st.session_state.df = parsed_df
                st.session_state.raw_df = raw_df
                save_app_state(parsed_df, used_sheet, st.session_state.memos)
                st.rerun()

df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
st.title("📋 야근/숙직 근무 현황 및 통계")

tab1, tab_sheet, tab2, tab3 = st.tabs([
    "📅 달력 메인 화면",
    "📊 시트 데이터 점검",
    "✏️ 근무표 전체 수정",
    "📊 숙직근무자 월별 근무 통계",
])

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면
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
                <span style="font-size:12px; font-weight:normal;">{memo_str}</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.info(f"💡 오늘({today_str}) 지정된 숙직 근무 정보가 없습니다.")

    available_months = sorted(df["년월"].dropna().unique())
    current_ym = today.strftime("%Y-%m")
    default_idx = (
        available_months.index(current_ym)
        if current_ym in available_months
        else 0
    )

    selected_month = st.selectbox(
        "📅 조회 월 선택",
        available_months,
        index=default_idx,
        key="calendar_month_select",
    )

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)
        month_df = df[df["년월"] == selected_month].copy()

        duty_map = {}
        for idx_row, row in month_df.iterrows():
            d_day = row["날짜"].day
            d_date_str = row["날짜"].strftime("%Y-%m-%d")
            duty_map[d_day] = {
                "idx": idx_row,
                "date_str": d_date_str,
                "p1_orig": str(row["근무자1"]),
                "p2_orig": str(row["근무자2"]),
                "sub1": (
                    str(row["대직1"]) if pd.notnull(row["대직1"]) else ""
                ),
                "sub2": (
                    str(row["대직2"]) if pd.notnull(row["대직2"]) else ""
                ),
                "p1_real": str(row["실제근무1"]),
                "p2_real": str(row["실제근무2"]),
            }

        headers = [
            ("일", "calendar-header-sun"),
            ("월", "calendar-header-weekday"),
            ("화", "calendar-header-weekday"),
            ("수", "calendar-header-weekday"),
            ("목", "calendar-header-weekday"),
            ("금", "calendar-header-weekday"),
            ("토", "calendar-header-sat"),
        ]

        # 요일 헤더 7열 Grid 정렬
        header_cols = st.columns(7)
        for i, (h_name, h_class) in enumerate(headers):
            with header_cols[i]:
                st.markdown(
                    f"<div class='cal-header {h_class}'>{h_name}</div>",
                    unsafe_allow_html=True,
                )

        # 주차별 7열 셀 Grid 정렬
        for week in month_days:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                with week_cols[i]:
                    if day != 0:
                        curr_date = datetime.date(year, month, day)
                        date_str = curr_date.strftime("%Y-%m-%d")
                        duty_info = duty_map.get(day)

                        is_today = curr_date == today

                        if i == 0 or curr_date in kr_holidays:
                            date_prefix = f"🔴 [{day}일]"
                        elif i == 6:
                            date_prefix = f"🔵 [{day}일]"
                        else:
                            date_prefix = f"[{day}일]"

                        lines = []
                        if is_today:
                            lines.append(f"{date_prefix}(오늘)")
                        else:
                            lines.append(date_prefix)

                        if duty_info:
                            p1_txt = duty_info["p1_real"] + (
                                "(대)" if duty_info["sub1"] else ""
                            )
                            p2_txt = duty_info["p2_real"] + (
                                "(대)" if duty_info["sub2"] else ""
                            )
                            lines.append(p1_txt)
                            lines.append(p2_txt)

                        day_memo = st.session_state.memos.get(date_str, "")
                        if day_memo:
                            lines.append(f"📌 {day_memo}")

                        card_label = "\n".join(lines)

                        if st.button(card_label, key=f"btn_card_{date_str}"):
                            if duty_info:
                                edit_worker_dialog(date_str, duty_info)

# ---------------------------------------------------------
# TAB 2: 시트 데이터 점검
# ---------------------------------------------------------
with tab_sheet:
    st.subheader(
        f"🔍 [{st.session_state.selected_sheet}] 시트 데이터 확인"
    )
    st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# TAB 3: 전체 근무표 수정
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 전체 근무표 수정")
    edited_df = st.data_editor(
        st.session_state.df, num_rows="dynamic", key="data_editor"
    )

    if st.button("💾 변경사항 적용 및 영구 저장"):
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

        st.session_state.df = edited_df
        save_app_state(
            edited_df,
            st.session_state.selected_sheet,
            st.session_state.memos,
        )
        st.success("✅ 성공적으로 저장되었습니다.")
        st.rerun()

# ---------------------------------------------------------
# TAB 4: 월별 근무 통계
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

    col_s1, _ = st.columns([1, 2])
    with col_s1:
        selected_stat_month = st.selectbox(
            "📅 통계 조회 월 선택",
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
        m2.metric(
            "총 근무건수 합계", f"{int(stats_df['총 근무 횟수'].sum())}건"
        )
        m3.metric(
            "총 근무시간 합계", f"{int(stats_df['총 근무시간(h)'].sum())}시간"
        )

        st.markdown("---")
        st.dataframe(stats_df, use_container_width=True)
    else:
        st.info("조회할 근무 정보가 없습니다.")
