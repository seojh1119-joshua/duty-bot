import os
import json
import io
from datetime import datetime, date
import pandas as pd
import numpy as np
import streamlit as st

# 공휴일 라이브러리 예외 처리
try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# -----------------------------------------------------------------------------
# 1. 페이지 및 스티일 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="야근/숙직 근무표 관리 시스템",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS (달력 및 통계 스타일링)
st.markdown("""
<style>
    /* 메인 배경 및 타이틀 */
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    
    /* 오늘 당직자 배너 */
    .today-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
    }
    
    .today-card h3 {
        color: #93C5FD !important;
        font-size: 1rem !important;
        margin-bottom: 0.3rem !important;
    }
    
    .today-card .worker-names {
        font-size: 1.5rem;
        font-weight: 700;
    }

    /* 달력 헤더 */
    .cal-weekday {
        text-align: center;
        font-weight: 700;
        padding: 8px 0;
        background-color: #F1F5F9;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .cal-sun { color: #EF4444; }
    .cal-sat { color: #2563EB; }
    
    /* 메모 표시 스타일 */
    .memo-tag {
        background-color: #FEF3C7;
        color: #92400E;
        font-size: 0.75rem;
        padding: 2px 6px;
        border-radius: 4px;
        margin-top: 4px;
        display: inline-block;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
</style>
""", unsafe_allow_html=True)

DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "edited_duty_schedule.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 저장 함수
# -----------------------------------------------------------------------------
def load_app_state():
    """저장된 영구 데이터 상태(대직자/메모 수정건)를 불러옵니다."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_app_state(state_dict):
    """수정된 데이터를 JSON 파일에 저장합니다."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2)

@st.cache_data
def create_sample_data():
    """엑셀 파일이 없을 경우 사용할 기본 샘플 데이터 생성"""
    today = datetime.now()
    year = today.year
    month = today.month
    num_days = pd.Period(f"{year}-{month}").days_in_month
    
    dates = [date(year, month, d) for d in range(1, num_days + 1)]
    workers_pool = ["김철수", "이영희", "박민수", "정지원", "최동현", "강서연", "윤재석", "한지민"]
    
    data = []
    for i, d in enumerate(dates):
        w1 = workers_pool[i % len(workers_pool)]
        w2 = workers_pool[(i + 1) % len(workers_pool)]
        data.append({
            "날짜": d.strftime("%Y-%m-%d"),
            "근무자1": w1,
            "근무자2": w2,
            "대직자1": "",
            "대직자2": "",
            "메모": ""
        })
    return pd.DataFrame(data)

def load_excel_smart(uploaded_file):
    """엑셀 스마트 로더"""
    if uploaded_file is None:
        return create_sample_data()
    
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet_name = xls.sheet_names[0]
        for name in xls.sheet_names:
            if any(k in name for k in ["숙직근무자", "숙직", "의료과", "야근"]):
                sheet_name = name
                break
        
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        
        # 헤더 자동 찾기
        header_row = 0
        for idx, row in df.iterrows():
            row_str = row.astype(str).str.cat(sep=" ")
            if "날짜" in row_str or "일자" in row_str or "근무자" in row_str:
                header_row = idx
                break
        
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=header_row)
        df = df.dropna(how="all").dropna(subset=[df.columns[0]])
        
        # 컬럼 표준화
        cols = list(df.columns)
        date_col = next((c for c in cols if "날짜" in str(c) or "일자" in str(c)), cols[0])
        worker_cols = [c for c in cols if "근무자" in str(c) or "당직" in str(c) or "성명" in str(c)]
        
        res_df = pd.DataFrame()
        res_df["날짜"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
        res_df = res_df.dropna(subset=["날짜"])
        
        res_df["근무자1"] = df[worker_cols[0]].astype(str).fillna("") if len(worker_cols) > 0 else "미정"
        res_df["근무자2"] = df[worker_cols[1]].astype(str).fillna("") if len(worker_cols) > 1 else ""
        res_df["대직자1"] = df["대직자1"].astype(str).replace("nan", "") if "대직자1" in df.columns else ""
        res_df["대직자2"] = df["대직자2"].astype(str).replace("nan", "") if "대직자2" in df.columns else ""
        res_df["메모"] = df["메모"].astype(str).replace("nan", "") if "메모" in df.columns else ""
        
        return res_df
    except Exception as e:
        st.error(f"엑셀 파일 읽기 오류: {e}")
        return create_sample_data()

# -----------------------------------------------------------------------------
# 3. 세션 상태 초기화
# -----------------------------------------------------------------------------
saved_state = load_app_state()

if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = create_sample_data()

# 저장된 수정사항(JSON)을 DataFrame에 동기화
for idx, row in st.session_state.schedule_df.iterrows():
    d_str = row["날짜"]
    if d_str in saved_state:
        st.session_state.schedule_df.at[idx, "대직자1"] = saved_state[d_str].get("대직자1", row["대직자1"])
        st.session_state.schedule_df.at[idx, "대직자2"] = saved_state[d_str].get("대직자2", row["대직자2"])
        st.session_state.schedule_df.at[idx, "메모"] = saved_state[d_str].get("메모", row["메모"])

# -----------------------------------------------------------------------------
# 4. 모달 다이얼로그 (날짜 클릭 시 수정 창)
# -----------------------------------------------------------------------------
@st.dialog("📅 근무자 및 메모 수정")
def edit_duty_dialog(selected_date_str):
    st.caption(f"선택한 날짜: **{selected_date_str}**")
    
    df = st.session_state.schedule_df
    row_idx = df[df["날짜"] == selected_date_str].index
    
    if len(row_idx) == 0:
        st.warning("해당 날짜의 데이터가 없습니다.")
        return
    
    idx = row_idx[0]
    curr_row = df.loc[idx]
    
    w1 = curr_row["근무자1"]
    w2 = curr_row["근무자2"]
    sub1 = curr_row["대직자1"]
    sub2 = curr_row["대직자2"]
    memo = curr_row["메모"]
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**근무자 1:** `{w1}`")
        new_sub1 = st.text_input("대직자 1 (없으면 빈칸)", value=sub1, key=f"sub1_{selected_date_str}")
        
    with col2:
        st.markdown(f"**근무자 2:** `{w2}`")
        new_sub2 = st.text_input("대직자 2 (없으면 빈칸)", value=sub2, key=f"sub2_{selected_date_str}")
        
    new_memo = st.text_area("일자 메모", value=memo, key=f"memo_{selected_date_str}", placeholder="특이사항이나 연차/대직 사유 입력")
    
    if st.button("저장하기", type="primary", use_container_width=True):
        # 세션 데이터 업데이트
        st.session_state.schedule_df.at[idx, "대직자1"] = new_sub1.strip()
        st.session_state.schedule_df.at[idx, "대직자2"] = new_sub2.strip()
        st.session_state.schedule_df.at[idx, "메모"] = new_memo.strip()
        
        # JSON 저장
        saved_state = load_app_state()
        saved_state[selected_date_str] = {
            "대직자1": new_sub1.strip(),
            "대직자2": new_sub2.strip(),
            "메모": new_memo.strip()
        }
        save_app_state(saved_state)
        
        st.success("수정 사항이 저장되었습니다!")
        st.rerun()

# -----------------------------------------------------------------------------
# 5. 사이드바 (파일 업로드 & 월 선택)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 설정 및 데이터")
    
    uploaded_file = st.file_uploader("근무표 엑셀 파일 업로드", type=["xlsx", "xls"])
    if uploaded_file is not None:
        if st.button("엑셀 데이터 적용", use_container_width=True):
            st.session_state.schedule_df = load_excel_smart(uploaded_file)
            st.success("새 근무표가 로드되었습니다!")
            st.rerun()
            
    st.markdown("---")
    
    # 조회 연월 선택
    df_dates = pd.to_datetime(st.session_state.schedule_df["날짜"], errors="coerce").dropna()
    if not df_dates.empty:
        available_months = sorted(list(set(df_dates.dt.strftime("%Y-%m").tolist())))
        default_idx = len(available_months) - 1
        selected_ym = st.selectbox("조회 연월 선택", available_months, index=default_idx)
    else:
        selected_ym = datetime.now().strftime("%Y-%m")

# -----------------------------------------------------------------------------
# 6. 메인 화면 - 상단 배너 (오늘의 숙직자 연동)
# -----------------------------------------------------------------------------
st.markdown("<div class='main-title'>📅 야근/숙직 근무표 시스템</div>", unsafe_allow_html=True)

today_str = datetime.now().strftime("%Y-%m-%d")
today_df = st.session_state.schedule_df[st.session_state.schedule_df["날짜"] == today_str]

if not today_df.empty:
    t_row = today_df.iloc[0]
    p1 = f"{t_row['대직자1']}(대직)" if t_row['대직자1'] else t_row['근무자1']
    p2 = f"{t_row['대직자2']}(대직)" if t_row['대직자2'] else t_row['근무자2']
    
    workers_text = f"{p1}" + (f", {p2}" if p2 else "")
    memo_text = f" | 메모: {t_row['메모']}" if t_row['메모'] else ""
else:
    workers_text = "오늘 일정 없음"
    memo_text = ""

st.markdown(f"""
<div class='today-card'>
    <h3>🔔 TODAY'S DUTY ({today_str})</h3>
    <div class='worker-names'>{workers_text} <span style='font-size: 1rem; font-weight: normal; opacity: 0.9;'>{memo_text}</span></div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 7. 탭 구성 (달력, 전체 수정, 시트 데이터, 월별 통계)
# -----------------------------------------------------------------------------
tab_cal, tab_edit, tab_view, tab_stats = st.tabs([
    "📅 달력 근무표 (클릭 수정)", "📝 전체 일괄 수정", "🔍 시트 데이터 점검", "📊 월별 근무 통계 & 다운로드"
])

# -----------------------------------------------------------------------------
# TAB 1: 달력 메인 화면 (날짜 버튼 클릭 시 수정)
# -----------------------------------------------------------------------------
with tab_cal:
    st.subheader(f"🗓️ {selected_ym} 근무 달력")
    st.caption("💡 수정할 **날짜 버튼**을 직접 누르면 근무자/대직자 및 메모를 편집할 수 있습니다.")
    
    # 요일 헤더 표시
    weekdays = ["일", "월", "화", "수", "목", "금", "토"]
    cols_hdr = st.columns(7)
    for idx, w in enumerate(weekdays):
        clr = "cal-sun" if idx == 0 else ("cal-sat" if idx == 6 else "")
        cols_hdr[idx].markdown(f"<div class='cal-weekday {clr}'>{w}</div>", unsafe_allow_html=True)
    
    # 선택된 월 데이터 필터링
    year_sel, month_sel = map(int, selected_ym.split("-"))
    first_date = date(year_sel, month_sel, 1)
    num_days = pd.Period(selected_ym).days_in_month
    start_weekday = (first_date.weekday() + 1) % 7 # 일요일:0, 월요일:1 ...
    
    # 7열 달력 그리드 생성
    day_counter = 1
    total_slots = start_weekday + num_days
    num_rows = (total_slots + 6) // 7
    
    for r in range(num_rows):
        cols = st.columns(7)
        for c in range(7):
            cell_idx = r * 7 + c
            if cell_idx < start_weekday or day_counter > num_days:
                cols[c].write("") # 빈 공간
            else:
                curr_date = date(year_sel, month_sel, day_counter)
                date_str = curr_date.strftime("%Y-%m-%d")
                
                # 데이터 검색
                day_data = st.session_state.schedule_df[st.session_state.schedule_df["날짜"] == date_str]
                
                # 표시 문구 생성
                if not day_data.empty:
                    row = day_data.iloc[0]
                    w1 = f"{row['대직자1']}(대)" if row['대직자1'] else row['근무자1']
                    w2 = f"{row['대직자2']}(대)" if row['대직자2'] else row['근무자2']
                    names = f"{w1} {w2}".strip()
                    memo_str = f"📌{row['메모']}" if row['메모'] else ""
                else:
                    names = "-"
                    memo_str = ""
                
                # 공휴일 및 주말 강조
                is_holiday = curr_date in kr_holidays
                label_prefix = "🚩 " if is_holiday else ""
                
                # 날짜 버튼 라벨 구성 (이름 + 메모 포함)
                button_label = f"{label_prefix}{day_counter}일\n{names}\n{memo_str}".strip()
                
                # 버튼 생성 (클릭 시 모달 호출)
                if cols[c].button(
                    button_label,
                    key=f"btn_cal_{date_str}",
                    use_container_width=True,
                    type="primary" if date_str == today_str else "secondary"
                ):
                    edit_duty_dialog(date_str)
                    
                day_counter += 1

# -----------------------------------------------------------------------------
# TAB 2: 전체 일괄 수정 (st.data_editor)
# -----------------------------------------------------------------------------
with tab_edit:
    st.subheader("📝 전체 근무표 일괄 수정")
    st.caption("표에서 직접 대직자나 메모를 수정한 후 [수정 사항 저장] 버튼을 누르세요.")
    
    edited_df = st.data_editor(
        st.session_state.schedule_df,
        use_container_width=True,
        num_rows="dynamic",
        key="data_editor_table"
    )
    
    if st.button("수정 사항 저장", type="primary"):
        st.session_state.schedule_df = edited_df
        
        # 변경 내용을 JSON persistence 저장
        saved_state = load_app_state()
        for _, row in edited_df.iterrows():
            d_str = row["날짜"]
            saved_state[d_str] = {
                "대직자1": str(row.get("대직자1", "")),
                "대직자2": str(row.get("대직자2", "")),
                "메모": str(row.get("메모", ""))
            }
        save_app_state(saved_state)
        st.success("전체 수정 내용이 저장되었습니다!")
        st.rerun()

# -----------------------------------------------------------------------------
# TAB 3: 시트 데이터 점검
# -----------------------------------------------------------------------------
with tab_view:
    st.subheader("🔍 현재 등록된 근무 데이터 목록")
    st.dataframe(st.session_state.schedule_df, use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 4: 월별 근무 통계 및 데이터 다운로드 (확장 기능)
# -----------------------------------------------------------------------------
with tab_stats:
    st.subheader(f"📊 {selected_ym} 근무 집계 통계")
    
    # 선택 연월 데이터 필터
    df_month = st.session_state.schedule_df[
        st.session_state.schedule_df["날짜"].str.startswith(selected_ym)
    ].copy()
    
    if df_month.empty:
        st.info("해당 월의 데이터가 없습니다.")
    else:
        # 실제 근무자 계산 (대직자 우선)
        df_month["실제1"] = np.where(df_month["대직자1"] != "", df_month["대직자1"], df_month["근무자1"])
        df_month["실제2"] = np.where(df_month["대직자2"] != "", df_month["대직자2"], df_month["근무자2"])
        
        # 근무 시간 계산 함수 (금: 15h, 토: 15h, 일: 7h, 평일: 7h)
        def get_duty_hours(row):
            dt = datetime.strptime(row["날짜"], "%Y-%m-%d")
            w = dt.weekday() # 0:월~6:일
            if w == 4 or w == 5: # 금, 토
                return 15, True
            elif w == 6: # 일
                return 7, True
            else: # 평일(월~목)
                return 7, False

        stats = {}
        for _, row in df_month.iterrows():
            hrs, is_weekend = get_duty_hours(row)
            for w_col in ["실제1", "실제2"]:
                worker = row[w_col]
                if worker and worker != "미정":
                    if worker not in stats:
                        stats[worker] = {"총근무시간": 0, "휴일근무횟수": 0, "평일근무횟수": 0}
                    stats[worker]["총근무시간"] += hrs
                    if is_weekend:
                        stats[worker]["휴일근무횟수"] += 1
                    else:
                        stats[worker]["평일근무횟수"] += 1
                        
        stats_df = pd.DataFrame.from_dict(stats, orient="index").reset_index()
        stats_df.rename(columns={"index": "근무자"}, inplace=True)
        stats_df = stats_df.sort_values(by="총근무시간", ascending=False)
        
        # 시각화 차트
        st.markdown("#### 📈 근무자별 총 근무 시간")
        st.bar_chart(stats_df.set_index("근무자")["총근무시간"])
        
        st.markdown("#### 📋 상세 집계표")
        st.dataframe(stats_df, use_container_width=True)
        
        # 📥 데이터 다운로드 (확장 기능: Excel 및 CSV)
        st.markdown("---")
        st.markdown("#### 📥 통계 집계표 파일 다운로드")
        col_dl1, col_dl2 = st.columns(2)
        
        # 1. CSV 다운로드
        csv_data = stats_df.to_csv(index=False).encode('utf-8-sig')
        col_dl1.download_button(
            label="📄 CSV 파일로 다운로드",
            data=csv_data,
            file_name=f"근무통계_{selected_ym}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # 2. Excel 다운로드
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            stats_df.to_excel(writer, index=False, sheet_name="월별근무통계")
            df_month.to_excel(writer, index=False, sheet_name="상세근무내역")
        excel_data = excel_buffer.getvalue()
        
        col_dl2.download_button(
            label="📊 Excel 파일로 다운로드 (.xlsx)",
            data=excel_data,
            file_name=f"근무통계_{selected_ym}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
