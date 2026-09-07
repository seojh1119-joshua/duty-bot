import calendar
import datetime
import io
import os
import glob
import pandas as pd
import streamlit as st

# 대한민국 공휴일 라이브러리
try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

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
# 반응형 CSS 및 스타일
# ---------------------------------------------------------
responsive_css = """
<style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    
    .duty-card-header {
        border-radius: 8px 8px 0 0;
        padding: 6px 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        font-weight: bold;
        font-size: 13px;
        border-bottom: 1px solid rgba(0,0,0,0.08);
    }
    .duty-card-memo {
        margin: 3px 0;
        padding: 3px 6px;
        background-color: #FFFDE7;
        border-left: 3px solid #FBC02D;
        font-size: 11px;
        color: #555555;
        border-radius: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* 근무자 버튼 스타일 */
    .stButton > button {
        width: 100% !important;
        font-size: 11px !important;
        padding: 2px 4px !important;
        min-height: 26px !important;
        height: auto !important;
        margin-bottom: 2px !important;
    }

    /* Popover 버튼 커스텀 */
    div[data-testid="stPopover"] > button {
        width: 100% !important;
        font-size: 11px !important;
        padding: 2px 4px !important;
        min-height: 24px !important;
        height: 24px !important;
    }

    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.2rem;
            padding-right: 0.2rem;
        }
        .duty-card-header {
            font-size: 10px !important;
            padding: 4px !important;
        }
        .stButton > button {
            font-size: 9px !important;
            padding: 1px 2px !important;
        }
    }
</style>
"""
st.markdown(responsive_css, unsafe_allow_html=True)

DEFAULT_FILE_PATH = os.path.join("data", "duty_schedule.xlsx")

# ---------------------------------------------------------
# 1. 엑셀 로더 및 원본 파일 저장 함수
# ---------------------------------------------------------
def load_excel_smart(file_source, selected_sheet=None):
    """파일 경로 또는 파일 바이트로부터 데이터프레임 로드"""
    if isinstance(file_source, bytes):
        file_obj = io.BytesIO(file_source)
    else:
        file_obj = file_source

    excel_file = pd.ExcelFile(file_obj)
    sheet_names = excel_file.sheet_names

    target_sheet = selected_sheet
    if not target_sheet or target_sheet not in sheet_names:
        priority_sheets = [s for s in sheet_names if any(k in s for k in ["의료과", "초과근무", "숙직", "근무"])]
        target_sheet = priority_sheets[0] if priority_sheets else sheet_names[0]

    if isinstance(file_source, bytes):
        file_obj.seek(0)

    df_raw = pd.read_excel(file_obj, sheet_name=target_sheet, header=None)

    header_idx = None
    for idx in range(min(25, len(df_raw))):
        row_values = [str(val).strip() for val in df_raw.iloc[idx].values]
        row_str = " ".join(row_values)
        if any(k in row_str for k in ["날짜", "일자", "근무일", "Date", "근무자", "성명", "이름"]):
            header_idx = idx
            break

    if header_idx is None:
        header_idx = 0

    if isinstance(file_source, bytes):
        file_obj.seek(0)

    df = pd.read_excel(file_obj, sheet_name=target_sheet, header=header_idx)

    # 컬럼 정제
    clean_cols = []
    for i, col in enumerate(df.columns):
        c_str = (
            str(col).replace("\n", "").replace("\r", "").strip()
            if not str(col).startswith("Unnamed")
            else f"열_{i}"
        )
        clean_cols.append(c_str)
    df.columns = clean_cols

    # 날짜 컬럼 자동 인식
    date_col = next(
        (col for col in df.columns if any(k in col.lower() for k in ["날짜", "일자", "근무일", "date", "일자/요일"])),
        df.columns[0]
    )
    df.rename(columns={date_col: "날짜"}, inplace=True)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).copy()

    # 근무자 매핑
    cols = list(df.columns)
    p1_col = next((c for c in cols if any(k in c for k in ["근무자1", "근무자 1", "1근무", "숙직1", "당직1", "성명", "이름"]) and "대직" not in c), None)
    p2_col = next((c for c in cols if any(k in c for k in ["근무자2", "근무자 2", "2근무", "숙직2", "당직2"]) and "대직" not in c), None)
    sub1_col = next((c for c in cols if any(k in c for k in ["대직1", "대직자1", "대직 1", "대직자"])), None)
    sub2_col = next((c for c in cols if any(k in c for k in ["대직2", "대직자2", "대직 2"])), None)

    df["근무자1"] = df[p1_col] if p1_col else "미지정"
    df["근무자2"] = df[p2_col] if p2_col else "미지정"
    df["대직1"] = df[sub1_col] if sub1_col else None
    df["대직2"] = df[sub2_col] if sub2_col else None

    # 근무시간
    time_col = next((c for c in cols if any(k in c for k in ["근무시간", "초과근무시간", "인정시간", "시간", "시간수"])), None)
    if time_col:
        df["근무시간"] = pd.to_numeric(df[time_col], errors="coerce").fillna(0)
    else:
        df["근무시간"] = 8.0

    def classify_day(d):
        w = d.weekday()
        if w in [0, 1, 2, 3]:
            return "평일(월~목)"
        elif w == 4:
            return "금요일"
        else:
            return "토/일요일"

    df["상세구분"] = df["날짜"].apply(classify_day)
    df["근무구분"] = df["날짜"].dt.weekday.map(lambda x: "주말" if x in [5, 6] else "평일")
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")

    # 실제 근무자 처리
    df["실제근무1"] = (
        df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
        .combine_first(df["근무자1"]).fillna("미지정")
    )
    df["실제근무2"] = (
        df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
        .combine_first(df["근무자2"]).fillna("미지정")
    )

    return df, target_sheet, sheet_names, df_raw


def save_to_excel_file(df, sheet_name):
    """현재 데이터프레임을 원본 엑셀 파일(.xlsx)에 저장"""
    save_path = st.session_state.get("file_path", DEFAULT_FILE_PATH)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # 엑셀 저장용 파이프라인
    save_df = df.copy()
    save_df["날짜"] = save_df["날짜"].dt.strftime("%Y-%m-%d")
    
    # 엑셀 파일 저장
    if os.path.exists(save_path):
        try:
            with pd.ExcelWriter(save_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                save_df.to_excel(writer, sheet_name=sheet_name, index=False)
        except Exception:
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                save_df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
            save_df.to_excel(writer, sheet_name=sheet_name, index=False)

    # 내보낸 데이터를 세션 바이트에도 동기화
    with open(save_path, "rb") as f:
        st.session_state.excel_bytes = f.read()


# ---------------------------------------------------------
# 세션 상태(Session State) 유지 및 기본 로드
# ---------------------------------------------------------
if "file_path" not in st.session_state:
    if os.path.exists("data"):
        files = glob.glob(os.path.join("data", "*.xlsx"))
        st.session_state.file_path = files[0] if files else DEFAULT_FILE_PATH
    else:
        st.session_state.file_path = DEFAULT_FILE_PATH

if "memos" not in st.session_state:
    st.session_state.memos = {}

if "df" not in st.session_state:
    if os.path.exists(st.session_state.file_path):
        parsed_df, used_sheet, sheet_names, raw_df = load_excel_smart(st.session_state.file_path)
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
    else:
        today = datetime.date.today()
        dates = pd.date_range(start=today.replace(day=1), periods=60, freq="D")
        sample_df = pd.DataFrame({
            "날짜": dates,
            "근무자1": ["홍길동", "김철수", "이영희", "박민수", "정수진"] * 12,
            "근무자2": ["김철수", "이영희", "박민수", "정수진", "홍길동"] * 12,
            "대직1": [None] * 60,
            "대직2": [None] * 60,
            "근무시간": [8.0 if d.weekday() < 5 else 12.0 for d in dates],
        })
        
        def classify_day_sample(d):
            w = d.weekday()
            if w in [0, 1, 2, 3]: return "평일(월~목)"
            elif w == 4: return "금요일"
            else: return "토/일요일"

        sample_df["상세구분"] = sample_df["날짜"].apply(classify_day_sample)
        sample_df["근무구분"] = sample_df["날짜"].dt.weekday.map(lambda x: "주말" if x in [5, 6] else "평일")
        sample_df["년월"] = sample_df["날짜"].dt.strftime("%Y-%m")
        sample_df["실제근무1"] = sample_df["근무자1"]
        sample_df["실제근무2"] = sample_df["근무자2"]
        
        st.session_state.df = sample_df
        st.session_state.sheet_names = ["의료과 초과근무내역"]
        st.session_state.selected_sheet = "의료과 초과근무내역"
        st.session_state.raw_df = pd.DataFrame()
        save_to_excel_file(sample_df, st.session_state.selected_sheet)


# ---------------------------------------------------------
# 모달 팝업(Dialog) 정의: 근무자 직접 수정
# ---------------------------------------------------------
@st.dialog("✏️ 근무자 수정 및 원본 저장")
def edit_worker_dialog(date_str, duty_info):
    st.write(f"📅 **{date_str} 근무자 수정**")
    
    with st.form(key=f"dialog_form_{date_str}"):
        edit_p1 = st.text_input("원래 근무자1", value=duty_info["p1_orig"])
        edit_sub1 = st.text_input("대직자1 (없으면 빈칸)", value=duty_info["sub1"])
        st.divider()
        edit_p2 = st.text_input("원래 근무자2", value=duty_info["p2_orig"])
        edit_sub2 = st.text_input("대직자2 (없으면 빈칸)", value=duty_info["sub2"])
        
        submitted = st.form_submit_button("💾 변경사항 저장 (파일에 기록)", use_container_width=True)
        
        if submitted:
            row_idx = duty_info["idx"]
            
            # 1. 데이터프레임 업데이트
            st.session_state.df.at[row_idx, "근무자1"] = edit_p1.strip()
            st.session_state.df.at[row_idx, "근무자2"] = edit_p2.strip()
            st.session_state.df.at[row_idx, "대직1"] = edit_sub1.strip() if edit_sub1.strip() else None
            st.session_state.df.at[row_idx, "대직2"] = edit_sub2.strip() if edit_sub2.strip() else None
            
            # 실제 근무자 적용
            st.session_state.df.at[row_idx, "실제근무1"] = edit_sub1.strip() if edit_sub1.strip() else edit_p1.strip()
            st.session_state.df.at[row_idx, "실제근무2"] = edit_sub2.strip() if edit_sub2.strip() else edit_p2.strip()
            
            # 2. 원본 엑셀 파일(.xlsx)에 저장
            save_to_excel_file(st.session_state.df, st.session_state.selected_sheet)
            
            st.success("✅ 파일에 성공적으로 저장되었습니다!")
            # 3. 팝업창을 닫고 전체 페이지 갱신
            st.rerun()


# ---------------------------------------------------------
# 사이드바: 파일 관리
# ---------------------------------------------------------
with st.sidebar:
    st.header("📂 파일 및 시트 관리")
    uploaded_file = st.file_uploader("새로운 엑셀(.xlsx) 파일 업로드", type=["xlsx"])

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        
        # 파일 저장
        with open(st.session_state.file_path, "wb") as f:
            f.write(file_bytes)
            
        parsed_df, used_sheet, sheet_names, raw_df = load_excel_smart(file_bytes)
        st.session_state.df = parsed_df
        st.session_state.selected_sheet = used_sheet
        st.session_state.sheet_names = sheet_names
        st.session_state.raw_df = raw_df
        st.success("✅ 새로운 파일로 갱신되었습니다!")
        st.rerun()

    if "sheet_names" in st.session_state:
        sheets = st.session_state.sheet_names
        curr_idx = sheets.index(st.session_state.selected_sheet) if st.session_state.selected_sheet in sheets else 0
        
        selected_s = st.selectbox("📌 불러올 시트 선택", sheets, index=curr_idx, key="sheet_selector")

        if selected_s != st.session_state.selected_sheet:
            st.session_state.selected_sheet = selected_s
            parsed_df, used_sheet, _, raw_df = load_excel_smart(
                st.session_state.file_path, selected_s
            )
            st.session_state.df = parsed_df
            st.session_state.raw_df = raw_df
            st.rerun()

        st.caption(f"🟢 현재 사용 중: **[{st.session_state.selected_sheet}]** 시트")

df = st.session_state.df

# ---------------------------------------------------------
# 메인 화면 구성
# ---------------------------------------------------------
st.title("📋 숙직 근무표 통합 대시보드")

tab1, tab_sheet, tab2, tab3 = st.tabs([
    "📅 달력 메인 화면",
    "📊 시트 데이터 점검",
    "✏️ 근무표 직접 수정",
    "📊 월별 근무 통계",
])

today = datetime.date.today()

# ---------------------------------------------------------
# TAB 1: 달력 메인 화면
# ---------------------------------------------------------
with tab1:
    st.subheader("📅 오늘 기준 숙직 근무 현황")

    today_df = df[df["날짜"].dt.date == today]

    col_card1, col_card2 = st.columns([1.2, 1])
    with col_card1:
        st.info(f"📌 **오늘 날짜 ({today.strftime('%Y-%m-%d')}) 실제 근무자**")
        if not today_df.empty:
            p1 = today_df.iloc[0]["실제근무1"]
            p2 = today_df.iloc[0]["실제근무2"]
            st.markdown(f"### 👤 근무1: **{p1}** | 👤 근무2: **{p2}**")
        else:
            st.write("오늘 등록된 숙직 정보가 없습니다.")

    with col_card2:
        available_months = sorted(df["년월"].dropna().unique())
        current_ym = today.strftime("%Y-%m")
        default_idx = (
            available_months.index(current_ym)
            if current_ym in available_months
            else 0
        )

        selected_month = (
            st.selectbox("조회 월 선택", available_months, index=default_idx)
            if available_months
            else current_ym
        )

    st.markdown("---")

    st.subheader(f"🗓️ {selected_month} 숙직 근무 달력")
    st.caption("💡 근무자 버튼을 클릭하면 팝업 창이 뜨고, 수정 후 저장 시 원본 파일에도 저장됩니다.")

    if selected_month in available_months:
        year, month = map(int, selected_month.split("-"))
        
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)

        month_df = df[df["년월"] == selected_month].copy()
        
        duty_map = {}
        for idx_row, row in month_df.iterrows():
            d_day = row["날짜"].day
            duty_map[d_day] = {
                "idx": idx_row,
                "p1_orig": str(row["근무자1"]),
                "p2_orig": str(row["근무자2"]),
                "sub1": str(row["대직1"]) if pd.notnull(row["대직1"]) else "",
                "sub2": str(row["대직2"]) if pd.notnull(row["대직2"]) else "",
                "p1_real": str(row["실제근무1"]),
                "p2_real": str(row["실제근무2"]),
                "type": row["근무구분"],
                "date_obj": row["날짜"].date(),
            }

        days_header = ["일", "월", "화", "수", "목", "금", "토"]
        cols = st.columns(7)
        for idx, day_name in enumerate(days_header):
            header_color = "🔴" if idx == 0 else ("🔵" if idx == 6 else "⚪")
            cols[idx].markdown(f"**{header_color} {day_name}**", unsafe_allow_html=True)

        for week in month_days:
            week_cols = st.columns(7)
            for i, day in enumerate(week):
                with week_cols[i]:
                    if day != 0:
                        curr_date = datetime.date(year, month, day)
                        date_str = curr_date.strftime("%Y-%m-%d")
                        duty_info = duty_map.get(day)
                        
                        is_today = (curr_date == today)
                        is_sunday = (i == 0)
                        is_saturday = (i == 6)
                        
                        holiday_name = kr_holidays.get(curr_date)
                        is_holiday = holiday_name is not None

                        if is_today:
                            bg_color = "#FFF3E0"
                            border_color = "#FF9800"
                        elif is_holiday or is_sunday:
                            bg_color = "#FFEBEE"
                            border_color = "#FFCDD2"
                        elif is_saturday:
                            bg_color = "#E3F2FD"
                            border_color = "#BBDEFB"
                        else:
                            bg_color = "#F9F9F9"
                            border_color = "#E0E0E0"

                        if is_holiday or is_sunday:
                            title_color = "#D32F2F"
                        elif is_saturday:
                            title_color = "#1976D2"
                        else:
                            title_color = "#333333"

                        title_label = f"{day}일"
                        if is_today:
                            title_label += " (오늘)"
                        elif is_holiday:
                            title_label += f" ({holiday_name})"

                        # 카드 날짜 제목
                        header_html = f"""
                        <div class="duty-card-header" style="background-color:{bg_color}; border:1.5px solid {border_color}; color:{title_color};">
                            {title_label}
                        </div>
                        """
                        st.markdown(header_html, unsafe_allow_html=True)

                        # 근무자 수정 버튼 (클릭 시 Dialog 팝업 오픈)
                        if duty_info:
                            p1_display = duty_info['p1_real']
                            p2_display = duty_info['p2_real']
                            if duty_info['sub1']: p1_display += " (대)"
                            if duty_info['sub2']: p2_display += " (대)"

                            if st.button(f"👤 {p1_display} / {p2_display}", key=f"btn_edit_{date_str}"):
                                edit_worker_dialog(date_str, duty_info)
                        else:
                            st.caption("근무 정보 없음")

                        # 메모 표시 및 작성
                        day_memo = st.session_state.memos.get(date_str, "")
                        if day_memo:
                            st.markdown(f'<div class="duty-card-memo" title="{day_memo}">📌 {day_memo}</div>', unsafe_allow_html=True)

                        btn_memo_label = "📌 메모수정" if day_memo else "📝 메모"
                        with st.popover(btn_memo_label, use_container_width=True):
                            st.caption(f"📅 **{date_str} 메모**")
                            memo_input = st.text_area(
                                "메모 내용",
                                value=day_memo,
                                key=f"memo_input_{date_str}",
                                height=90,
                                label_visibility="collapsed"
                            )
                            c_save, c_del = st.columns([1, 1])
                            with c_save:
                                if st.button("저장", key=f"save_btn_{date_str}", use_container_width=True):
                                    if memo_input.strip():
                                        st.session_state.memos[date_str] = memo_input.strip()
                                    else:
                                        st.session_state.memos.pop(date_str, None)
                                    st.rerun()
                            with c_del:
                                if st.button("삭제", key=f"del_btn_{date_str}", use_container_width=True):
                                    st.session_state.memos.pop(date_str, None)
                                    st.rerun()

                    else:
                        st.markdown("<div style='min-height: 110px;'></div>", unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("#### 📋 상세 근무 목록")
        display_cols = [
            c for c in [
                "날짜", "근무구분", "상세구분", "근무자1", "근무자2",
                "대직1", "대직2", "실제근무1", "실제근무2", "근무시간"
            ] if c in month_df.columns
        ]

        st.dataframe(
            month_df[display_cols].style.highlight_between(
                left=pd.Timestamp(today),
                right=pd.Timestamp(today),
                subset=["날짜"],
                color="#FFE0B2",
            ),
            use_container_width=True,
        )

# ---------------------------------------------------------
# TAB 2: 시트 데이터 점검
# ---------------------------------------------------------
with tab_sheet:
    current_s = st.session_state.selected_sheet or "기본"
    st.subheader(f"🔍 시트 데이터 분석: [{current_s}]")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 등록 데이터(행)", f"{len(df)}건")
    m2.metric("인식된 컬럼 수", f"{len(df.columns)}개")
    m3.metric(
        "근무자1 지정률",
        f"{(df['근무자1'] != '미지정').mean() * 100:.1f}%" if "근무자1" in df.columns else "0%",
    )
    m4.metric(
        "총 초과/근무시간 합계",
        f"{df['근무시간'].sum():.1f} 시간" if "근무시간" in df.columns else "0 시간",
    )

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### ⚙️ 자동 인식 및 정제된 데이터")
        st.dataframe(df, height=350, use_container_width=True)

    with col_b:
        st.markdown("#### 📄 원본 시트 데이터 구조 (상단)")
        if not st.session_state.raw_df.empty:
            st.dataframe(
                st.session_state.raw_df.head(15),
                height=350,
                use_container_width=True,
            )
        else:
            st.info("원본 원천 데이터가 없습니다.")

# ---------------------------------------------------------
# TAB 3: 근무표 직접 수정 (표 일괄 수정)
# ---------------------------------------------------------
with tab2:
    st.subheader("✏️ 원본 데이터 전체 수정 (표 형태)")
    st.caption("💡 표 전체 데이터를 직접 수정한 뒤 저장 버튼을 누르면 원본 파일에도 저장됩니다.")

    edited_df = st.data_editor(
        st.session_state.df, num_rows="dynamic", key="data_editor"
    )

    if st.button("💾 전체 변경사항 원본 파일에 저장"):
        edited_df["날짜"] = pd.to_datetime(edited_df["날짜"], errors="coerce")
        edited_df = edited_df.dropna(subset=["날짜"]).copy()
        
        def classify_day(d):
            w = d.weekday()
            if w in [0, 1, 2, 3]: return "평일(월~목)"
            elif w == 4: return "금요일"
            else: return "토/일요일"

        edited_df["상세구분"] = edited_df["날짜"].apply(classify_day)
        edited_df["근무구분"] = edited_df["날짜"].dt.weekday.map(lambda x: "주말" if x in [5, 6] else "평일")
        edited_df["년월"] = edited_df["날짜"].dt.strftime("%Y-%m")
        
        edited_df["실제근무1"] = (
            edited_df["대직1"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자1"]).fillna("미지정")
        )
        edited_df["실제근무2"] = (
            edited_df["대직2"].fillna("").astype(str).str.strip().replace(["", "nan", "None"], None)
            .combine_first(edited_df["근무자2"]).fillna("미지정")
        )
        st.session_state.df = edited_df
        save_to_excel_file(edited_df, st.session_state.selected_sheet)
        st.success("✅ 파일에 원본 데이터가 성공적으로 저장되었습니다!")
        st.rerun()

# ---------------------------------------------------------
# TAB 4: 월별 근무 통계
# ---------------------------------------------------------
with tab3:
    st.subheader("📊 의료과 월별 근무 및 초과근무 통계")

    available_months_stat = ["전체 기간"] + sorted(df["년월"].dropna().unique(), reverse=True)
    current_ym = today.strftime("%Y-%m")
    default_stat_idx = (
        available_months_stat.index(current_ym)
        if current_ym in available_months_stat
        else 0
    )

    col_m1, _ = st.columns([1, 2])
    with col_m1:
        selected_stat_month = st.selectbox(
            "📅 통계 조회 월 선택",
            available_months_stat,
            index=default_stat_idx,
            key="stat_month_selector"
        )

    if selected_stat_month == "전체 기간":
        filtered_df = df.copy()
    else:
        filtered_df = df[df["년월"] == selected_stat_month].copy()

    w1 = filtered_df[["실제근무1", "상세구분", "근무시간"]].rename(columns={"실제근무1": "근무자"})
    w2 = filtered_df[["실제근무2", "상세구분", "근무시간"]].rename(columns={"실제근무2": "근무자"})
    
    combined_workers = pd.concat([w1, w2], ignore_index=True)
    combined_workers = combined_workers[
        combined_workers["근무자"].notnull()
        & (~combined_workers["근무자"].isin(["미지정", "nan", "None"]))
    ]

    if not combined_workers.empty:
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("총 근무자 수", f"{combined_workers['근무자'].nunique()}명")
        kpi2.metric("총 근무시간 합계", f"{combined_workers['근무시간'].sum():.1f} 시간")
        kpi3.metric("총 근무 건수", f"{len(combined_workers)}건")

        st.markdown("---")

        st.markdown(f"#### ⏱️ [{selected_stat_month}] 개인별 총 근무시간 (시간)")
        time_stats = combined_workers.groupby("근무자")["근무시간"].sum().reset_index()
        time_stats.columns = ["근무자", "총 근무시간(h)"]
        time_stats = time_stats.sort_values(by="총 근무시간(h)", ascending=False)

        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            st.bar_chart(time_stats.set_index("근무자"))
        with col_t2:
            st.dataframe(time_stats, use_container_width=True, height=300)

        st.markdown("---")

        st.markdown(f"#### 📅 [{selected_stat_month}] 개인별 요일 세분화 근무 횟수 (평일 / 금요일 / 토·일요일)")
        
        count_stats = (
            combined_workers.groupby(["근무자", "상세구분"])
            .size()
            .unstack(fill_value=0)
        )
        
        desired_order = ["평일(월~목)", "금요일", "토/일요일"]
        existing_cols = [c for c in desired_order if c in count_stats.columns]
        count_stats = count_stats[existing_cols]

        col_c1, col_c2 = st.columns([2, 1])
        with col_c1:
            st.bar_chart(count_stats)
        with col_c2:
            count_stats_with_total = count_stats.copy()
            count_stats_with_total["합계"] = count_stats_with_total.sum(axis=1)
            st.dataframe(count_stats_with_total, use_container_width=True, height=300)

    else:
        st.info(f"[{selected_stat_month}] 기간에 집계할 근무 데이터가 존재하지 않습니다.")
