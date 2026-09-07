import os
import json
import io
from datetime import datetime, date
import pandas as pd
import numpy as np
import streamlit as st

# 한국 공휴일 라이브러리 예외 처리
try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 커스텀 CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="야근/숙직 근무표 관리 시스템",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.5rem;
    }
    
    /* 오늘 당직자 메인 배너 */
    .today-banner {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
    }
    .today-banner h3 {
        color: #93C5FD !important;
        font-size: 1rem !important;
        margin-bottom: 0.3rem !important;
    }
    .today-banner .worker-info {
        font-size: 1.4rem;
        font-weight: 700;
    }

    /* 달력 요일 헤더 */
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
</style>
""", unsafe_allow_html=True)

DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "duty_schedule_state.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# -----------------------------------------------------------------------------
# 2. 데이터 처리 및 영구 저장 함수
# -----------------------------------------------------------------------------
def load_app_state():
    """저장된 수정 상태(대직자/메모)를 불러옵니다."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_app_state(state_dict):
    """수정된 상태를 JSON 파일로 저장합니다."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2)

@st.cache_data
def generate_sample_data():
    """엑셀 파일이 없을 경우 제공되는 샘플 데이터"""
    today = datetime.now()
    year, month = today.year, today.month
    num_days = pd.Period(f"{year}-{month}").days_in_month
    
    dates = [date(year, month, d) for d in range(1, num_days + 1)]
    workers = ["김철수", "이영희", "박민수", "정지원", "최동현", "강서연", "윤재석", "한지민"]
    
    data = []
    for i, d in enumerate(dates):
        w1 = workers[i % len(workers)]
        w2 = workers[(i + 1) % len(workers)]
        data.append({
            "날짜": d.strftime("%Y-%m-%d"),
            "근무자1": w1,
            "근무자2": w2,
            "대직자1": "",
            "대직자2": "",
            "메모": ""
        })
    return pd.DataFrame(data)

def load_excel_data(file):
    """업로드된 엑셀 파싱"""
    if file is None:
        return generate_sample_data()
    try:
        xls = pd.ExcelFile(file)
        sheet_name = xls.sheet_names[0]
        for s in xls.sheet_names:
            if any(k in s for k in ["숙직", "야근", "근무자", "의료과"]):
                sheet_name = s
                break
        
        df = pd.read_excel(file, sheet_name=sheet_name)
        header_idx = 0
        for idx, row in df.iterrows():
            r_str = row.astype(str).str.cat(sep=" ")
            if "날짜" in r_str or "일자" in r_str or "근무자" in r_str:
                header_idx = idx
                break
        
        df = pd.read_excel(file, sheet_name=sheet_name, header=header_idx).dropna(how="all")
        cols = list(df.columns)
        date_col = next((c for c in cols if "날짜" in str(c) or "일자" in str(c)), cols[0])
        w_cols = [c for c in cols if "근무자" in str(c) or "당직" in str(c) or "성명" in str(c)]
        
        res = pd.DataFrame()
        res["날짜"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
        res = res.dropna(subset=["날짜"])
        
        res["근무자1"] = df[w_cols[0]].astype(str).fillna("") if len(w_cols) > 0 else "미정"
        res["근무자2"] = df[w_cols[1]].astype(str).fillna("") if len(w_cols) > 1 else ""
        res["대직자1"] = df["대직자1"].astype(str).replace("nan", "") if "대직자1" in df.columns else ""
        res["대직자2"] = df["대직자2"].astype(str).replace("nan", "") if "대직자2" in df.columns else ""
        res["메모"] = df["메모"].astype(str).replace("nan", "") if "메모" in df.columns else ""
        return res
    except Exception as e:
        st.error(f"엑셀을 로드하는 중 오류가 발생했습니다: {e}")
        return generate_sample_data()

# -----------------------------------------------------------------------------
# 3. 세션 및 데이터 동기화
# -----------------------------------------------------------------------------
saved_state = load_app_state()

if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = generate_sample_data()

# 저장된 수정 건 적용
for idx, row in st.session_state.schedule_df.iterrows():
    d = row["날짜"]
    if d in saved_state:
        st.session_state.schedule_df.at[idx, "대직자1"] = saved_state[d].get("대직자1", row["대직자1"])
        st.session_state.schedule_df.at[idx, "대직자2"] = saved_state[d].get("대직자2", row["대직자2"])
        st.session_state.schedule_df.at[idx, "메모"] = saved_state[d].get("메모", row["메모"])

# -----------------------------------------------------------------------------
# 4. 달력 클릭 시 팝업되는 수정 대화상자 (@st.dialog)
# -----------------------------------------------------------------------------
@st.dialog("📅 근무 수정 및 메모 입력")
def edit_date_dialog(target_date_str):
    st.caption(f"선택 일자: **{target_date_str}**")
    
    df = st.session_state.schedule_df
    matches = df[df["날짜"] == target_date_str]
    
    if matches.empty:
        st.warning("해당 날짜 데이터가 없습니다.")
        return
        
    idx = matches.index[0]
    row = df.loc[idx]
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**기존 근무자 1:** `{row['근무자1']}`")
        new_sub1 = st.text_input("대직자 1", value=row["대직자1"], key=f"dlg_sub1_{target_date_str}")
        
    with col2:
        st.markdown(f"**기존 근무자 2:** `{row['근무자2']}`")
        new_sub2 = st.text_input("대직자 2", value=row["대직자2"], key=f"dlg_sub2_{target_date_str}")
        
    new_memo = st.text_area("메모 (특이사항/사유)", value=row["메모"], key=f"dlg_memo_{target_date_str}")
    
    if st.button("저장하기", type="primary", use_container_width=True):
        # 1. 세션 업데이트
        st.session_state.schedule_df.at[idx, "대직자1"] = new_sub1.strip()
        st.session_state.schedule_df.at[idx, "대직자2"] = new_sub2.strip()
        st.session_state.schedule_df.at[idx, "메모"] = new_memo.strip()
        
        # 2. 파일 저장 (영구 보존)
        curr_state = load_app_state()
        curr_state[target_date_str] = {
            "대직자1": new_sub1.strip(),
            "대직자2": new_sub2.strip(),
            "메모": new_memo.strip()
        }
        save_app_state(curr_state)
        
        st.success("수정사항이 반영되었습니다.")
        st.rerun()

# -----------------------------------------------------------------------------
# 5. 사이드바 (엑셀 파일 업로드 및 조회 연월 선택)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 옵션 및 데이터")
    
    up_file = st.file_uploader("근무표 엑셀 업로드", type=["xlsx", "xls"])
    if up_file is not None:
        if st.button("엑셀 데이터 적용", use_container_width=True):
            st.session_state.schedule_df = load_excel_data(up_file)
            st.success("엑셀 파일이 정상 적용되었습니다!")
            st.rerun()
            
    st.markdown("---")
    
    df_dates = pd.to_datetime(st.session_state.schedule_df["날짜"], errors="coerce").dropna()
    if not df_dates.empty:
        available_months = sorted(list(set(df_dates.dt.strftime("%Y-%m").tolist())))
        curr_m = datetime.now().strftime("%Y-%m")
        default_idx = available_months.index(curr_m) if curr_m in available_months else len(available_months) - 1
        selected_ym = st.selectbox("조회 연월 선택", available_months, index=default_idx)
    else:
        selected_ym = datetime.now().strftime("%Y-%m")

# -----------------------------------------------------------------------------
# 6. 메인 화면 - 오늘의 숙직자 실시간 배너
# -----------------------------------------------------------------------------
st.markdown("<div class='main-title'>📅 야근/숙직 근무표 관리 시스템</div>", unsafe_allow_html=True)

today_str = datetime.now().strftime("%Y-%m-%d")
today_match = st.session_state.schedule_df[st.session_state.schedule_df["날짜"] == today_str]

if not today_match.empty:
    t_row = today_match.iloc[0]
    p1 = f"{t_row['대직자1']}(대직)" if t_row['대직자1'] else t_row['근무자1']
    p2 = f"{t_row['대직자2']}(대직)" if t_row['대직자2'] else t_row['근무자2']
    
    workers_display = f"{p1}" + (f", {p2}" if p2 else "")
    memo_display = f" (메모: {t_row['메모']})" if t_row['메모'] else ""
else:
    workers_display = "오늘 등록된 근무 일정 없음"
    memo_display = ""

st.markdown(f"""
<div class='today-banner'>
    <h3>🔔 TODAY'S DUTY ({today_str})</h3>
    <div class='worker-info'>{workers_display}<span style='font-size: 1rem; font-weight: normal; opacity: 0.9;'>{memo_display}</span></div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 7. 탭 구성 (달력 / 전체 수정 / 시트 데이터 / 근무 통계)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 근무 달력 (클릭 수정)", "📝 전체 일괄 수정", "🔍 시트 데이터 목록", "📊 월별 통계 & 다운로드"
])

# --- TAB 1: 달력 화면 ---
with tab1:
    st.subheader(f"🗓️ {selected_ym} 근무표")
    st.caption("💡 수정하려는 **날짜 버튼**을 클릭하면 근무자/대직자 변경 및 메모 입력이 가능합니다.")
    
    # 요일 표시
    weekdays = ["일", "월", "화", "수", "목", "금", "토"]
    hdr_cols = st.columns(7)
    for idx, w in enumerate(weekdays):
        clr = "cal-sun" if idx == 0 else ("cal-sat" if idx == 6 else "")
        hdr_cols[idx].markdown(f"<div class='cal-weekday {clr}'>{w}</div>", unsafe_allow_html=True)
    
    # 날짜 그리드 로직
    year_num, month_num = map(int, selected_ym.split("-"))
    first_day = date(year_num, month_num, 1)
    days_in_month = pd.Period(selected_ym).days_in_month
    start_w = (first_day.weekday() + 1) % 7 # 일요일=0, 월요일=1 ...
    
    day_cnt = 1
    total_slots = start_w + days_in_month
    rows_needed = (total_slots + 6) // 7
    
    for r in range(rows_needed):
        grid_cols = st.columns(7)
        for c in range(7):
            slot = r * 7 + c
            if slot < start_w or day_cnt > days_in_month:
                grid_cols[c].write("")
            else:
                curr_d = date(year_num, month_num, day_cnt)
                d_str = curr_d.strftime("%Y-%m-%d")
                
                # 날짜 데이터 조회
                d_data = st.session_state.schedule_df[st.session_state.schedule_df["날짜"] == d_str]
                
                if not d_data.empty:
                    row_item = d_data.iloc[0]
                    w1 = f"{row_item['대직자1']}(대)" if row_item['대직자1'] else row_item['근무자1']
                    w2 = f"{row_item['대직자2']}(대)" if row_item['대직자2'] else row_item['근무자2']
                    names = f"{w1} {w2}".strip()
                    memo_txt = f"📌 {row_item['메모']}" if row_item['메모'] else ""
                else:
                    names = "-"
                    memo_txt = ""
                
                is_hol = curr_d in kr_holidays
                prefix = "🚩 " if is_hol else ""
                
                # 버튼에 표시될 라벨 (사람 이미지 제거, 이름 + 메모 형태)
                btn_label = f"{prefix}{day_cnt}일\n{names}\n{memo_txt}".strip()
                
                if grid_cols[c].button(
                    btn_label,
                    key=f"cal_btn_{d_str}",
                    use_container_width=True,
                    type="primary" if d_str == today_str else "secondary"
                ):
                    edit_date_dialog(d_str)
                    
                day_cnt += 1

# --- TAB 2: 전체 일괄 수정 ---
with tab2:
    st.subheader("📝 전체 데이터 일괄 수정")
    st.caption("표에서 직접 내용을 변경하고 아래 [수정 사항 저장] 버튼을 누르세요.")
    
    edited_data = st.data_editor(
        st.session_state.schedule_df,
        use_container_width=True,
        num_rows="dynamic",
        key="global_data_editor"
    )
    
    if st.button("수정 사항 저장", type="primary"):
        st.session_state.schedule_df = edited_data
        
        # JSON 보존 파일에 전체 저장
        curr_state = load_app_state()
        for _, r in edited_data.iterrows():
            d = r["날짜"]
            curr_state[d] = {
                "대직자1": str(r.get("대직자1", "")),
                "대직자2": str(r.get("대직자2", "")),
                "메모": str(r.get("메모", ""))
            }
        save_app_state(curr_state)
        st.success("성공적으로 저장되었습니다!")
        st.rerun()

# --- TAB 3: 시트 데이터 점검 ---
with tab3:
    st.subheader("🔍 전체 근무 데이터 목록")
    st.dataframe(st.session_state.schedule_df, use_container_width=True)

# --- TAB 4: 월별 통계 & 다운로드 (확장 기능) ---
with tab4:
    st.subheader(f"📊 {selected_ym} 근무 통계")
    
    m_df = st.session_state.schedule_df[
        st.session_state.schedule_df["날짜"].str.startswith(selected_ym)
    ].copy()
    
    if m_df.empty:
        st.info("해당 월의 데이터가 없습니다.")
    else:
        # 실제 근무자(대직 반영) 계산
        m_df["실제1"] = np.where(m_df["대직자1"] != "", m_df["대직자1"], m_df["근무자1"])
        m_df["실제2"] = np.where(m_df["대직자2"] != "", m_df["대직자2"], m_df["근무자2"])
        
        def calc_hours(row_data):
            dt = datetime.strptime(row_data["날짜"], "%Y-%m-%d")
            w = dt.weekday()
            if w in [4, 5]: # 금, 토
                return 15, True
            elif w == 6: # 일
                return 7, True
            else: # 평일
                return 7, False

        stats = {}
        for _, r in m_df.iterrows():
            hrs, is_wknd = calc_hours(r)
            for c in ["실제1", "실제2"]:
                person = r[c]
                if person and person != "미정":
                    if person not in stats:
                        stats[person] = {"총근무시간": 0, "휴일근무": 0, "평일근무": 0}
                    stats[person]["총근무시간"] += hrs
                    if is_wknd:
                        stats[person]["휴일근무"] += 1
                    else:
                        stats[person]["평일근무"] += 1
                        
        stats_df = pd.DataFrame.from_dict(stats, orient="index").reset_index()
        stats_df.rename(columns={"index": "근무자"}, inplace=True)
        stats_df = stats_df.sort_values(by="총근무시간", ascending=False)
        
        st.markdown("#### 📈 개인별 총 근무 시간")
        st.bar_chart(stats_df.set_index("근무자")["총근무시간"])
        
        st.markdown("#### 📋 상세 집계표")
        st.dataframe(stats_df, use_container_width=True)
        
        st.markdown("---")
        st.markdown("#### 📥 통계 파일 다운로드")
        col_dl1, col_dl2 = st.columns(2)
        
        # CSV 다운로드
        csv_bytes = stats_df.to_csv(index=False).encode('utf-8-sig')
        col_dl1.download_button(
            label="📄 CSV 파일 다운로드",
            data=csv_bytes,
            file_name=f"근무집계_{selected_ym}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # Excel 다운로드
        x_buf = io.BytesIO()
        with pd.ExcelWriter(x_buf, engine='openpyxl') as writer:
            stats_df.to_excel(writer, index=False, sheet_name="월별통계")
            m_df.to_excel(writer, index=False, sheet_name="상세내역")
        x_bytes = x_buf.getvalue()
        
        col_dl2.download_button(
            label="📊 Excel 파일 다운로드 (.xlsx)",
            data=x_bytes,
            file_name=f"근무집계_{selected_ym}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
