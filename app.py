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
# 페이지 기본 설정 (가로 너비 전체 활용)
# ---------------------------------------------------------
st.set_page_config(
    page_title="숙직 근무표 대시보드",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# CSS 스타일링 (화면 비율 맞춤 자동 조절 + 가로 쓰기 강제)
# ---------------------------------------------------------
responsive_css = """
<style>
    /* 1. 전체 루트 및 메인 레이아웃 상대 비율 적용 */
    html, body, [data-testid="stAppViewContainer"] {
        width: 100vw !important;
        height: 100vh !important;
        overflow-x: hidden !important;
    }

    .main .block-container {
        padding: 0.5rem 1rem !important;
        max-width: 100% !important;
        width: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* 2. 요일 및 달력 7열 반응형 Grid (화면 폭 100% 1fr 분할) */
    [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(7, minmax(0, 1fr)) !important;
        gap: 3px !important;
        width: 100% !important;
        margin: 0 0 3px 0 !important;
    }

    [data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        flex: 1 1 0 !important;
        padding: 0px !important;
        margin: 0px !important;
    }

    /* 3. 요일 헤더 박스 (가로 비율 맞춤) */
    .cal-header {
        text-align: center;
        font-size: clamp(12px, 1.2vw, 16px);
        font-weight: bold;
        padding: 8px 0;
        border-radius: 4px;
        width: 100% !important;
        box-sizing: border-box;
        white-space: nowrap !important;
        overflow: hidden;
        text-overflow: ellipsis;
        display: flex;
        align-items: center;
        justify-content: center;
        writing-mode: horizontal-tb !important;
    }

    .calendar-header-sun { background-color: #991B1B; color: #FFFFFF; }
    .calendar-header-sat { background-color: #1E3A8A; color: #FFFFFF; }
    .calendar-header-weekday { background-color: #475569; color: #FFFFFF; }

    /* 4. 달력 버튼 셀 및 반응형 비율 조절 */
    .stButton {
        width: 100% !important;
        height: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    .stButton > button {
        width: 100% !important;
        height: 100% !important;
        min-height: clamp(80px, 12vh, 150px) !important;
        padding: 6px 4px !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 6px !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        box-sizing: border-box !important;

        /* 완전 가로 쓰기 및 한 줄/비율 자동 조정 */
        writing-mode: horizontal-tb !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;

        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        font-size: clamp(11px, 1vw, 15px) !important;
        line-height: 1.3 !important;
    }

    .stButton > button * {
        writing-mode: horizontal-tb !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    .stButton > button:hover {
        border-color: #2563EB !important;
        background-color: #F1F5F9 !important;
    }

    /* 5. 다이얼로그(팝업) 세로 쓰기 방지 및 가로 화면 비율 적용 */
    [data-testid="stDialog"] *, 
    [data-testid="stDialog"] input, 
    [data-testid="stDialog"] textarea, 
    [data-testid="stDialog"] div {
        writing-mode: horizontal-tb !important;
    }

    [data-testid="stDialog"] > div:first-child {
        width: clamp(300px, 80vw, 550px) !important;
        max-width: 95vw !important;
        max-height: 85vh !important;
        border-radius: 12px !important;
        padding: 1.2rem !important;
        overflow-y: auto !important;
    }

    /* 오늘 근무자 카드 */
    .today-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        margin-bottom: 10px;
        width: 100%;
        box-sizing: border-box;
    }

    /* 모바일 반응형 자동 비율 조절 */
    @media (max-width: 600px) {
        .stButton > button {
            min-height: 65px !important;
            padding: 3px 2px !important;
            font-size: 10px !important;
        }
        .cal-header {
            font-size: 11px !important;
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
            "근무자1": ["우정수", "오기희", "이승헌", "유진수", "이원철"] * 12,
            "근무자2": ["정찬웅", "서진호", "장민우", "우정수", "오기희"] * 12,
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
# 근무자 수정 및 메모 작성 다이얼로그 (모달)
# ---------------------------------------------------------
@st.dialog("✏️ 근무자 수정 및 메모 작성")
def edit_worker_dialog(date_str, duty_info):
    # 모바일 뒤로가기 / 이전 버튼 대응 스크립트
    st.components.v1.html(
        """
        <script>
            if (window.location.hash !== "#edit-dialog") {
                window.history.pushState({dialogOpen: true}, "", "#edit-dialog");
            }
            window.addEventListener("popstate", function(event) {
                const closeBtn = window.parent.document.querySelector('[data-testid="stDialog"] button[aria-label="Close"]');
                if (closeBtn) closeBtn.click();
            }, { once: true });
        </script>
        """,
        height=0,
    )

    st.write(f"📅 **{date_str} 근무 정보 수정**")

    row_idx = duty_info["idx"]
    curr_row = st.session_state.df.loc[row_idx]

    val_p1 = str(curr_row.get("근무자1", "")) if pd.notnull(curr_row.get("근무자1")) else ""
    val_p2 = str(curr_row.get("근무자2", "")) if pd.notnull(curr_row.get("근무자2")) else ""
    val_sub1 = str(curr_row.get("대직1", "")) if pd.notnull(curr_row.get("대직1")) else ""
    val_sub2 = str(curr_row.get("대직2", "")) if pd.notnull(curr_row.get("대직2")) else ""

    if val_p1 == "nan": val_p1 = ""
    if val_p2 == "nan": val_p2 = ""
    if val_sub1 == "nan": val_sub1 = ""
    if val_sub2 == "nan": val_sub2 = ""

    current_memo = st.session_state.memos.get(date_str, "")

    with st.form(key=f"dialog_form_{date_str}"):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            edit_p1 = st.text_input("근무자1 이름", value=val_p1)
            edit_sub1 = st.text_input("대직자1 이름 (선택)", value=val_sub1)
        with col_f2:
            edit_p2 = st.text_input("근무자2 이름", value=val_p2)
            edit_sub2 = st.text_input("대직자2 이름 (선택)", value=val_sub2)

        st.divider()
        edit_memo = st.text_area(
            "📌 날짜별 메모 (달력 셀 반영)",
            value=current_memo,
            height=80,
        )

        submitted = st.form_submit_button("💾 저장하기", use_container_width=True)

        if submitted:
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
# 사이드바 (시트 선택 부분 제거)
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 근무표 파일 관리")

    if "file_name" in st.session_state:
        st.info(f"📄 현재 파일: `{st.session_state.file_name}`")

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

        st.success(f"✅ '{used_sheet}' 데이터 로드 완료")
        st.rerun()

df = st.session_state.df
today = datetime.date.today()

# ---------------------------------------------------------
# 메인 화면 - 탭 구성
# ---------------------------------------------------------
st.title("📋 숙직 근무 관리 대시보드")

tab1, tab2, tab3, tab4 = st.tabs([
    "📅 달력 메인 화면",
    "✏️ 근무표 전체 수정",
    "📊 숙직근무자 월별 근무 통계",
    "🔍 시트 데이터 점검",
])

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면 (반응형 비율 기반)
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
            <div style="font-size:16px; font-weight:bold;">
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

    col_m1, col_m2 = st.columns([1, 3])
    with col_m1:
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

        # 요일 헤더 (가로 화면비율 7등분 정렬)
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

                        p1_txt = duty_info["p1_real"] if duty_info else ""
                        p2_txt = duty_info["p2_real"] if duty_info else ""

                        sub_info = ""
                        if duty_info:
                            if duty_info["sub1"]:
                                sub_info += f"대:{duty_info['sub1']} "
                            if duty_info["sub2"]:
                                sub_info += f"대:{duty_info['sub2']}"

                        day_memo = st.session_state.memos.get(date_str, "")

                        # 가로 쓰기 전용 텍스트 생성
                        btn_label = f"{day}일\n"
                        if p1_txt and p1_txt != "미지정":
                            btn_label += f"{p1_txt}\n"
                        if p2_txt and p2_txt != "미지정":
                            btn_label += f"{p2_txt}\n"
                        if sub_info:
                            btn_label += f"({sub_info.strip()})\n"
                        if day_memo:
                            btn_label += f"📌{day_memo}"

                        if st.button(btn_label, key=f"btn_card_{date_str}"):
                            if duty_info:
                                edit_worker_dialog(date_str, duty_info)

# ---------------------------------------------------------
# TAB 2: 근무표 전체 수정
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 전체 근무표 수정")
    st.caption("아래 표에서 근무자, 대직자 및 근무 구분을 직접 수정할 수 있습니다.")

    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        key="data_editor",
        use_container_width=True,
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

    # 가로 배치 메뉴
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

        # 화면 너비 비율에 자동 조정되는 지표 박스
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
    st.subheader(f"🔍 시트 데이터 원본 확인")
    st.dataframe(df, use_container_width=True)
