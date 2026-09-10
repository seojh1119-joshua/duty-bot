import calendar
import datetime
import io
import json
import os
import holidays
import openpyxl
import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# 1. 페이지 설정 및 기본 구성
# ---------------------------------------------------------
st.set_page_config(
    page_title="숙직 근무표 관리 시스템",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 커스텀 CSS (모바일 레이아웃 및 카드 스타일 조정)
st.markdown(
    """
    <style>
    .month-header-card {
        text-align: center;
        background-color: #f0f2f6;
        padding: 8px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .today-card {
        background-color: #e8f4f8;
        border-left: 5px solid #1E88E5;
        padding: 10px 15px;
        border-radius: 5px;
        margin-bottom: 15px;
        font-size: 0.95rem;
    }
    .swipe-hidden-container {
        display: none;
    }
    div[data-testid="stForm"] {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
    }
    .stButton>button {
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 파일 경로 정의
DATA_DIR = "DATA"
JSON_FILE = os.path.join(DATA_DIR, "edited_duty_schedule.json")
EXCEL_FILE = os.path.join(DATA_DIR, "숙직근무표.xlsx")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 한국 공휴일 정보
kr_holidays = holidays.KR()


# ---------------------------------------------------------
# 2. 데이터 유틸리티 함수
# ---------------------------------------------------------
def generate_dummy_data():
    """기본 데이터 생성 (데이터가 없을 때 사용)"""
    today = datetime.date.today()
    start_date = datetime.date(today.year, 1, 1)
    end_date = datetime.date(today.year, 12, 31)

    date_range = pd.date_range(start_date, end_date)
    df = pd.DataFrame(
        {
            "날짜": date_range,
            "근무자1": ["홍길동"] * len(date_range),
            "대직1": [None] * len(date_range),
            "실제근무1": ["홍길동"] * len(date_range),
            "근무자2": ["김철수"] * len(date_range),
            "대직2": [None] * len(date_range),
            "실제근무2": ["김철수"] * len(date_range),
        }
    )
    return df


def save_app_state(df, selected_sheet, memos, batch_patterns):
    """현재 앱 상태를 JSON 및 Excel로 저장"""
    try:
        # JSON 저장
        export_df = df.copy()
        if "날짜" in export_df.columns:
            export_df["날짜"] = export_df["날짜"].dt.strftime("%Y-%m-%d")

        state_data = {
            "selected_sheet": selected_sheet,
            "memos": memos,
            "batch_patterns": batch_patterns,
            "df_data": export_df.to_dict(orient="records"),
        }
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

        # 엑셀 저장
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
            export_df["메모"] = export_df["날짜"].map(
                lambda d: memos.get(str(d), "")
            )
            export_df.to_excel(writer, index=False, sheet_name="근무표")
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")


def load_app_state():
    """저장된 상태 읽기"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            df = pd.DataFrame(state_data.get("df_data", []))
            if not df.empty and "날짜" in df.columns:
                df["날짜"] = pd.to_datetime(df["날짜"])

            return (
                df,
                state_data.get("selected_sheet", "근무표"),
                state_data.get("memos", {}),
                state_data.get("batch_patterns", {}),
            )
        except Exception:
            pass
    return generate_dummy_data(), "근무표", {}, {}


def load_excel_smart(file_source, sheet_name=None):
    """엑셀 파일 스마트 로딩"""
    try:
        excel_file = pd.ExcelFile(file_source)
        sheet_names = excel_file.sheet_names
        target_sheet = (
            sheet_name if sheet_name in sheet_names else sheet_names[0]
        )

        raw_df = pd.read_excel(excel_file, sheet_name=target_sheet)

        # 열 이름 정규화
        df = raw_df.copy()
        if "날짜" in df.columns:
            df["날짜"] = pd.to_datetime(df["날짜"])
        else:
            df["날짜"] = pd.date_range(
                start=f"{datetime.date.today().year}-01-01", periods=len(df)
            )

        for col in [
            "근무자1",
            "대직1",
            "실제근무1",
            "근무자2",
            "대직2",
            "실제근무2",
        ]:
            if col not in df.columns:
                df[col] = None

        # 실제근무 계산
        df["실제근무1"] = df.apply(
            lambda r: (
                r["대직1"]
                if pd.notnull(r["대직1"]) and str(r["대직1"]).strip() != ""
                else r["근무자1"]
            ),
            axis=1,
        )
        df["실제근무2"] = df.apply(
            lambda r: (
                r["대직2"]
                if pd.notnull(r["대직2"]) and str(r["대직2"]).strip() != ""
                else r["근무자2"]
            ),
            axis=1,
        )

        f_bytes = (
            file_source.getvalue()
            if hasattr(file_source, "getvalue")
            else None
        )
        return df, target_sheet, sheet_names, raw_df, f_bytes
    except Exception as e:
        st.error(f"엑셀을 불러오는 중 오류가 발생했습니다: {e}")
        df = generate_dummy_data()
        return df, "기본", ["기본"], df, None


# ---------------------------------------------------------
# 3. 세션 상태 초기화
# ---------------------------------------------------------
if "df" not in st.session_state:
    init_df, init_sheet, init_memos, init_patterns = load_app_state()
    st.session_state.df = init_df
    st.session_state.selected_sheet = init_sheet
    st.session_state.sheet_names = [init_sheet]
    st.session_state.memos = init_memos
    st.session_state.batch_patterns = init_patterns

if "show_settings_dialog" not in st.session_state:
    st.session_state.show_settings_dialog = False

if "show_exit_dialog" not in st.session_state:
    st.session_state.show_exit_dialog = False

if "auto_view_type" not in st.session_state:
    st.session_state.auto_view_type = "🗓️ 가로형 Grid"


# ---------------------------------------------------------
# 4. 다이얼로그 정의 (Pop-up Window)
# ---------------------------------------------------------
@st.dialog("⚙️ 대시보드 및 근무 관리 설정")
def settings_dialog():
    st.subheader("🛠️ 시스템 설정")

    # 뷰 방식 선택
    view_type = st.radio(
        "달력 표출 방식",
        options=["🗓️ 가로형 Grid", "📄 세로형 리스트"],
        index=0
        if st.session_state.auto_view_type == "🗓️ 가로형 Grid"
        else 1,
    )
    st.session_state.auto_view_type = view_type

    st.divider()
    st.subheader("🔄 순환 근무 자동 배치")
    st.caption("특정 기간 동안 근무자를 순환 패턴으로 자동 입력합니다.")

    p_workers = st.text_input(
        "근무자 목록 (쉼표로 구분)", value="홍길동, 김철수, 이영희, 박민수"
    )
    start_d = st.date_input("시작일", value=datetime.date.today())
    days_cnt = st.number_input("배치 일수", min_value=1, max_value=365, value=30)
    target_slot = st.selectbox(
        "배치할 슬롯", options=["근무자 1", "근무자 2", "전체"]
    )

    if st.button("🚀 자동 배치 실행", use_container_width=True, type="primary"):
        worker_list = [
            w.strip() for w in p_workers.split(",") if w.strip() != ""
        ]
        if worker_list:
            df = st.session_state.df
            w_idx = 0
            for i in range(days_cnt):
                curr_date = pd.Timestamp(start_d + datetime.timedelta(days=i))
                matches = df[df["날짜"] == curr_date]
                if not matches.empty:
                    r_idx = matches.index[0]
                    assigned_worker = worker_list[w_idx % len(worker_list)]

                    if target_slot in ["근무자 1", "전체"]:
                        df.at[r_idx, "근무자1"] = assigned_worker
                        if pd.isna(df.at[r_idx, "대직1"]):
                            df.at[r_idx, "실제근무1"] = assigned_worker

                    if target_slot in ["근무자 2", "전체"]:
                        df.at[r_idx, "근무자2"] = assigned_worker
                        if pd.isna(df.at[r_idx, "대직2"]):
                            df.at[r_idx, "실제근무2"] = assigned_worker

                    w_idx += 1

            st.session_state.df = df
            save_app_state(
                df,
                st.session_state.selected_sheet,
                st.session_state.memos,
                st.session_state.batch_patterns,
            )
            st.success("✅ 자동 배치가 완료되었습니다.")
            st.rerun()

    if st.button("닫기", use_container_width=True):
        st.session_state.show_settings_dialog = False
        st.rerun()


@st.dialog("🔴 시스템 종료")
def confirm_exit_dialog():
    st.write("시스템을 종료하시겠습니까? 현재까지의 변경사항은 모두 저장되었습니다.")
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("확인 (종료)", type="primary", use_container_width=True):
            st.session_state.show_exit_dialog = False
            st.success("시스템이 종료되었습니다. 브라우저 탭을 닫아주세요.")
            st.stop()
    with col_e2:
        if st.button("취소", use_container_width=True):
            st.session_state.show_exit_dialog = False
            st.rerun()


@st.dialog("✏️ 근무자/대직자 변경 및 메모")
def edit_worker_dialog(date_str, duty_info):
    st.markdown(f"### 📅 **{date_str}** 근무 변경")

    row_idx = duty_info["idx"]
    df = st.session_state.df
    row = df.loc[row_idx]

    # 기존 등록된 근무자 목록 추출
    existing_workers = set()
    for col in ["근무자1", "실제근무1", "근무자2", "실제근무2"]:
        existing_workers.update(
            df[col].dropna().astype(str).str.strip().tolist()
        )

    worker_options = ["(선택 안함)", "(직접 입력)"] + sorted(
        list(existing_workers)
    )

    val_p1 = (
        str(row["근무자1"])
        if pd.notnull(row["근무자1"])
        else "(선택 안함)"
    )
    val_sub1 = (
        str(row["대직1"])
        if pd.notnull(row["대직1"]) and str(row["대직1"]).strip() != ""
        else "(선택 안함)"
    )

    val_p2 = (
        str(row["근무자2"])
        if pd.notnull(row["근무자2"])
        else "(선택 안함)"
    )
    val_sub2 = (
        str(row["대직2"])
        if pd.notnull(row["대직2"]) and str(row["대직2"]).strip() != ""
        else "(선택 안함)"
    )

    current_memo = st.session_state.memos.get(date_str, "")

    def get_opt_idx(val):
        return worker_options.index(val) if val in worker_options else 1

    with st.form(key=f"edit_form_{date_str}"):
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            st.markdown("**:blue[근무자 1 / 대직자 1]**")
            p1_sel = st.selectbox(
                "근무자 1",
                options=worker_options,
                index=get_opt_idx(val_p1),
                key=f"sel_p1_{date_str}",
            )
            p1_custom = (
                st.text_input(
                    "근무자 1 (직접 입력)",
                    value=val_p1 if val_p1 not in worker_options else "",
                    key=f"custom_p1_{date_str}",
                )
                if p1_sel == "(직접 입력)"
                else ""
            )

            sub1_sel = st.selectbox(
                "대직자 1 (없으면 선택 안함)",
                options=worker_options,
                index=get_opt_idx(val_sub1),
                key=f"sel_sub1_{date_str}",
            )
            sub1_custom = (
                st.text_input(
                    "대직자 1 (직접 입력)",
                    value=val_sub1 if val_sub1 not in worker_options else "",
                    key=f"custom_sub1_{date_str}",
                )
                if sub1_sel == "(직접 입력)"
                else ""
            )

        with col_f2:
            st.markdown("**:blue[근무자 2 / 대직자 2]**")
            p2_sel = st.selectbox(
                "근무자 2",
                options=worker_options,
                index=get_opt_idx(val_p2),
                key=f"sel_p2_{date_str}",
            )
            p2_custom = (
                st.text_input(
                    "근무자 2 (직접 입력)",
                    value=val_p2 if val_p2 not in worker_options else "",
                    key=f"custom_p2_{date_str}",
                )
                if p2_sel == "(직접 입력)"
                else ""
            )

            sub2_sel = st.selectbox(
                "대직자 2 (없으면 선택 안함)",
                options=worker_options,
                index=get_opt_idx(val_sub2),
                key=f"sel_sub2_{date_str}",
            )
            sub2_custom = (
                st.text_input(
                    "대직자 2 (직접 입력)",
                    value=val_sub2 if val_sub2 not in worker_options else "",
                    key=f"custom_sub2_{date_str}",
                )
                if sub2_sel == "(직접 입력)"
                else ""
            )

        st.markdown("**:blue[메모 / 비고]**")
        memo_val = st.text_area(
            "특이사항 및 메모",
            value=current_memo,
            height=80,
            key=f"memo_area_{date_str}",
        )

        submit_btn = st.form_submit_button(
            "💾 저장하기", use_container_width=True, type="primary"
        )

        if submit_btn:
            final_p1 = (
                p1_custom.strip()
                if p1_sel == "(직접 입력)"
                else ("미지정" if p1_sel == "(선택 안함)" else p1_sel)
            )
            final_sub1 = (
                sub1_custom.strip()
                if sub1_sel == "(직접 입력)"
                else (
                    None
                    if sub1_sel == "(선택 안함)" or not sub1_sel
                    else sub1_sel
                )
            )

            final_p2 = (
                p2_custom.strip()
                if p2_sel == "(직접 입력)"
                else ("미지정" if p2_sel == "(선택 안함)" else p2_sel)
            )
            final_sub2 = (
                sub2_custom.strip()
                if sub2_sel == "(직접 입력)"
                else (
                    None
                    if sub2_sel == "(선택 안함)" or not sub2_sel
                    else sub2_sel
                )
            )

            df = st.session_state.df
            df.at[row_idx, "근무자1"] = final_p1
            df.at[row_idx, "대직1"] = final_sub1
            df.at[row_idx, "실제근무1"] = final_sub1 if final_sub1 else final_p1

            df.at[row_idx, "근무자2"] = final_p2
            df.at[row_idx, "대직2"] = final_sub2
            df.at[row_idx, "실제근무2"] = final_sub2 if final_sub2 else final_p2

            if memo_val.strip():
                st.session_state.memos[date_str] = memo_val.strip()
            else:
                st.session_state.memos.pop(date_str, None)

            st.session_state.df = df
            save_app_state(
                df,
                st.session_state.selected_sheet,
                st.session_state.memos,
                st.session_state.batch_patterns,
            )
            st.success("✅ 근무 정보 및 메모가 성공적으로 저장되었습니다.")
            st.rerun()


# ---------------------------------------------------------
# 5. 팝업 다이얼로그 출력 제어
# ---------------------------------------------------------
if st.session_state.show_settings_dialog:
    settings_dialog()

if st.session_state.show_exit_dialog:
    confirm_exit_dialog()


# ---------------------------------------------------------
# 6. 상단 컨트롤 및 사이드바 영역
# ---------------------------------------------------------
df_main = st.session_state.df
available_years = sorted(list(df_main["날짜"].dt.year.unique()))
if not available_years:
    available_years = [datetime.date.today().year]

today = datetime.date.today()
default_year = (
    today.year if today.year in available_years else available_years[0]
)
default_month = today.month

if "selected_year" not in st.session_state:
    st.session_state.selected_year = default_year

if "selected_month" not in st.session_state:
    st.session_state.selected_month = default_month

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 메뉴 및 설정")

    uploaded_file = st.file_uploader(
        "📁 엑셀 파일 업로드", type=["xlsx", "xls"]
    )
    if uploaded_file is not None:
        if st.button("📥 업로드 파일 적용", use_container_width=True):
            parsed_df, used_sheet, sheet_names, raw_df, f_bytes = (
                load_excel_smart(uploaded_file)
            )
            st.session_state.df = parsed_df
            st.session_state.selected_sheet = used_sheet
            st.session_state.sheet_names = sheet_names
            st.session_state.raw_df = raw_df
            st.session_state.file_bytes = f_bytes
            st.session_state.file_name = uploaded_file.name
            save_app_state(
                parsed_df,
                used_sheet,
                st.session_state.memos,
                st.session_state.batch_patterns,
            )
            st.success("엑셀 파일이 불러와졌습니다.")
            st.rerun()

    st.markdown("---")

    if len(st.session_state.get("sheet_names", [])) > 1:
        selected_s = st.selectbox(
            "📋 시트 선택",
            options=st.session_state.sheet_names,
            index=(
                st.session_state.sheet_names.index(
                    st.session_state.selected_sheet
                )
                if st.session_state.selected_sheet
                in st.session_state.sheet_names
                else 0
            ),
        )
        if selected_s != st.session_state.selected_sheet:
            if "file_bytes" in st.session_state:
                parsed_df, used_sheet, _, raw_df, _ = load_excel_smart(
                    st.session_state.file_bytes, selected_s
                )
                st.session_state.df = parsed_df
                st.session_state.selected_sheet = used_sheet
                st.session_state.raw_df = raw_df
                st.rerun()

    if st.button("⚙️ 대시보드 및 근무 관리 설정", use_container_width=True):
        st.session_state.show_settings_dialog = True
        st.rerun()

    output_io = io.BytesIO()
    with pd.ExcelWriter(output_io, engine="openpyxl") as writer:
        export_df = st.session_state.df.copy()
        if "날짜" in export_df.columns:
            export_df["날짜"] = export_df["날짜"].dt.strftime("%Y-%m-%d")
        export_df["메모"] = export_df["날짜"].map(
            lambda d: st.session_state.memos.get(str(d), "")
        )
        export_df.to_excel(writer, index=False)

    st.download_button(
        label="📥 현재 근무표 엑셀 다운로드",
        data=output_io.getvalue(),
        file_name=f"숙직근무표_{st.session_state.selected_year}_{st.session_state.selected_month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.markdown("---")
    if st.button("🔴 시스템 종료", use_container_width=True):
        st.session_state.show_exit_dialog = True
        st.rerun()


# ---------------------------------------------------------
# 7. 헤더 및 월 이동 컨트롤
# ---------------------------------------------------------
col_top1, col_top2, col_top3, col_top4, col_top5 = st.columns(
    [1.5, 1, 2.5, 1, 1.5]
)

with col_top1:
    sel_y = st.selectbox(
        "연도",
        options=available_years,
        index=available_years.index(st.session_state.selected_year),
        key="sb_year",
        label_visibility="collapsed",
    )
    if sel_y != st.session_state.selected_year:
        st.session_state.selected_year = sel_y
        st.rerun()

with col_top2:
    if st.button("◀ 이전달", use_container_width=True, key="btn_prev_month"):
        if st.session_state.selected_month == 1:
            st.session_state.selected_month = 12
            if st.session_state.selected_year - 1 in available_years:
                st.session_state.selected_year -= 1
        else:
            st.session_state.selected_month -= 1
        st.rerun()

with col_top3:
    st.markdown(
        f'<div class="month-header-card"><h2>📅 {st.session_state.selected_year}년 {st.session_state.selected_month}월</h2></div>',
        unsafe_allow_html=True,
    )

with col_top4:
    if st.button("다음달 ▶", use_container_width=True, key="btn_next_month"):
        if st.session_state.selected_month == 12:
            st.session_state.selected_month = 1
            if st.session_state.selected_year + 1 in available_years:
                st.session_state.selected_year += 1
        else:
            st.session_state.selected_month += 1
        st.rerun()

with col_top5:
    sel_m = st.selectbox(
        "월 선택",
        options=list(range(1, 13)),
        index=st.session_state.selected_month - 1,
        key="sb_month",
        label_visibility="collapsed",
    )
    if sel_m != st.session_state.selected_month:
        st.session_state.selected_month = sel_m
        st.rerun()

# 터치 스와이프 연동 숨김 버튼
st.markdown('<div class="swipe-hidden-container">', unsafe_allow_html=True)
if st.button("HIDDEN_PREV", key="hidden_prev_btn"):
    if st.session_state.selected_month == 1:
        st.session_state.selected_month = 12
        if st.session_state.selected_year - 1 in available_years:
            st.session_state.selected_year -= 1
    else:
        st.session_state.selected_month -= 1
    st.rerun()

if st.button("HIDDEN_NEXT", key="hidden_next_btn"):
    if st.session_state.selected_month == 12:
        st.session_state.selected_month = 1
        if st.session_state.selected_year + 1 in available_years:
            st.session_state.selected_year += 1
    else:
        st.session_state.selected_month += 1
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------
# 8. 오늘의 근무 안내 요약 카드
# ---------------------------------------------------------
today_ts = pd.Timestamp(today)
today_row = df_main[df_main["날짜"] == today_ts]

if not today_row.empty:
    r_today = today_row.iloc[0]
    p1_t = r_today["실제근무1"]
    p2_t = r_today["실제근무2"]
    memo_t = st.session_state.memos.get(today.strftime("%Y-%m-%d"), "")
    memo_str = f" | 📝 메모: {memo_t}" if memo_t else ""
    st.markdown(
        f"""
        <div class="today-card">
            🌟 <b>오늘의 숙직근무 ({today.strftime('%Y-%m-%d')})</b>: 
            <span>1근무: {p1_t}</span> | <span>2근무: {p2_t}</span>{memo_str}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# 9. 달력 표출 영역 (Grid형 vs List형)
# ---------------------------------------------------------
year = st.session_state.selected_year
month = st.session_state.selected_month

m_start = pd.Timestamp(year, month, 1)
m_end = pd.Timestamp(
    year, month, calendar.monthrange(year, month)[1], 23, 59, 59
)
month_df = df_main[
    (df_main["날짜"] >= m_start) & (df_main["날짜"] <= m_end)
].copy()

if st.session_state.auto_view_type == "🗓️ 가로형 Grid":
    days_hdr = ["월", "화", "수", "목", "금", "토", "일"]
    hdr_cols = st.columns(7)
    for idx, day_name in enumerate(days_hdr):
        color = (
            "#EF4444" if idx == 6 else ("#3B82F6" if idx == 5 else "inherit")
        )
        hdr_cols[idx].markdown(
            f"<div style='text-align:center; font-weight:bold; color:{color}; padding:2px 0;'>{day_name}</div>",
            unsafe_allow_html=True,
        )

    cal_matrix = calendar.monthcalendar(year, month)

    for week in cal_matrix:
        week_cols = st.columns(7)
        for day_idx, day_num in enumerate(week):
            with week_cols[day_idx]:
                if day_num == 0:
                    st.write("")
                else:
                    curr_date = datetime.date(year, month, day_num)
                    curr_ts = pd.Timestamp(curr_date)
                    date_str = curr_date.strftime("%Y-%m-%d")

                    match = month_df[month_df["날짜"] == curr_ts]

                    is_holiday = curr_date in kr_holidays
                    holiday_name = (
                        kr_holidays.get(curr_date) if is_holiday else ""
                    )

                    is_today = curr_date == today
                    prefix = "🌟" if is_today else ""

                    if match.empty:
                        btn_label = f"{prefix}{day_num}일\n미지정"
                        duty_info = {"idx": None}
                    else:
                        r_idx = match.index[0]
                        row = match.loc[r_idx]

                        w1 = (
                            row["실제근무1"]
                            if pd.notnull(row["실제근무1"])
                            else "미지정"
                        )
                        w2 = (
                            row["실제근무2"]
                            if pd.notnull(row["실제근무2"])
                            else "미지정"
                        )

                        sub1_flag = (
                            "🔄"
                            if pd.notnull(row.get("대직1"))
                            and str(row.get("대직1")).strip()
                            not in ["", "nan", "None"]
                            else ""
                        )
                        sub2_flag = (
                            "🔄"
                            if pd.notnull(row.get("대직2"))
                            and str(row.get("대직2")).strip()
                            not in ["", "nan", "None"]
                            else ""
                        )

                        memo_flag = (
                            "📝" if date_str in st.session_state.memos else ""
                        )

                        duty_info = {"idx": r_idx}
                        btn_label = f"{prefix}{day_num}일 {holiday_name[:3] if holiday_name else ''}{memo_flag}\n1:{w1}{sub1_flag}\n2:{w2}{sub2_flag}"

                    if st.button(btn_label, key=f"grid_btn_{date_str}"):
                        if duty_info["idx"] is not None:
                            edit_worker_dialog(date_str, duty_info)

else:
    # 📄 세로형 리스트 뷰
    st.markdown("### 📄 일별 근무 리스트")

    if month_df.empty:
        st.info("해당 월의 근무 데이터가 없습니다.")
    else:
        for r_idx, row in month_df.iterrows():
            d_obj = row["날짜"].date()
            d_str = d_obj.strftime("%Y-%m-%d")

            w1 = row["실제근무1"] if pd.notnull(row["실제근무1"]) else "미지정"
            w2 = row["실제근무2"] if pd.notnull(row["실제근무2"]) else "미지정"
            memo = st.session_state.memos.get(d_str, "")

            col_l1, col_l2, col_l3, col_l4 = st.columns([2, 2, 2, 1])

            with col_l1:
                st.write(
                    f"**{d_str} ({['월','화','수','목','금','토','일'][d_obj.weekday()]})**"
                )

            with col_l2:
                st.write(f"1근무: **{w1}**")

            with col_l3:
                st.write(f"2근무: **{w2}**")

            with col_l4:
                if st.button("✏️ 수정", key=f"list_btn_{d_str}"):
                    edit_worker_dialog(d_str, {"idx": r_idx})

            if memo:
                st.caption(f"📝 메모: {memo}")
            st.divider()
