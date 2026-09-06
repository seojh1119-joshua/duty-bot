import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from pathlib import Path
import plotly.express as px

# Streamlit Calendar 안전 로드 (없거나 오류 시 대체 뷰 사용)
try:
    from streamlit_calendar import calendar
    HAS_CALENDAR_LIB = True
except ImportError:
    HAS_CALENDAR_LIB = False

# ──────────────────────────────
# 페이지 설정
# ──────────────────────────────
st.set_page_config(page_title="숙직 근무표 대시보드", layout="wide", initial_sidebar_state="expanded")

SHEET_NAME = "숙직근무자"
DEFAULT_EXCEL_PATH = Path("data/duty_schedule.xlsx")

REQUIRED_COLS = [
    "날짜", "근무자1", "대직1", "근무자2", "대직2", 
    "메모", "근무구분", "참고 년월", "실제근무1", "실제근무2", "요일"
]

# ──────────────────────────────
# 유틸 함수
# ──────────────────────────────
def load_excel(file_source) -> pd.DataFrame:
    try:
        if isinstance(file_source, bytes):
            file_source = BytesIO(file_source)

        xls = pd.ExcelFile(file_source)
        target_sheet = SHEET_NAME if SHEET_NAME in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=target_sheet, dtype=str).fillna("")
        
        df.columns = [str(c).replace(" ", "").strip() for c in df.columns]
        
        for c in REQUIRED_COLS:
            if c not in df.columns:
                df[c] = ""
        
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        df = df.dropna(subset=["날짜"]).copy()
        df = df.sort_values("날짜").reset_index(drop=True)
        return df[REQUIRED_COLS]
    except Exception as e:
        st.error(f"엑셀 로드 실패: {e}")
        return pd.DataFrame(columns=REQUIRED_COLS)

def apply_auto_calc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df = df.copy()
    for idx, row in df.iterrows():
        for i in (1, 2):
            act_col, pri_col, std_col = f"실제근무{i}", f"근무자{i}", f"대직{i}"
            if not str(row[act_col]).strip():
                std = str(row[std_col]).strip()
                pri = str(row[pri_col]).strip()
                df.at[idx, act_col] = std if std else pri
    return df

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=SHEET_NAME)
    return out.getvalue()

# ──────────────────────────────
# 세션 상태 초기화
# ──────────────────────────────
if "master_df" not in st.session_state:
    if DEFAULT_EXCEL_PATH.exists():
        st.session_state.master_df = apply_auto_calc(load_excel(DEFAULT_EXCEL_PATH))
    else:
        st.session_state.master_df = pd.DataFrame(columns=REQUIRED_COLS)

# ──────────────────────────────
# 사이드바
# ──────────────────────────────
with st.sidebar:
    st.header("📂 데이터 관리")
    uploaded = st.file_uploader("엑셀 파일 직접 업로드 (.xlsx)", type=["xlsx"])
    if uploaded:
        df = load_excel(uploaded)
        if not df.empty:
            st.session_state.master_df = apply_auto_calc(df)
            st.success(f"✅ 파일 업로드 완료 ({len(df)}행)")
            st.rerun()
            
    st.divider()
    if not st.session_state.master_df.empty:
        st.download_button(
            "💾 현재 데이터 엑셀 다운로드",
            data=to_excel_bytes(st.session_state.master_df),
            file_name=f"숙직근무표_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ──────────────────────────────
# 메인 화면
# ──────────────────────────────
st.title("📋 숙직 근무표 통합 대시보드")

if st.session_state.master_df.empty:
    st.warning("⚠️ 등록된 데이터가 없습니다. 사이드바에서 엑셀(.xlsx) 파일을 업로드해 주세요.")
    st.stop()

# 탭 생성
tab_cal, tab_edit, tab_stats = st.tabs(["📅 캘린더 보기", "✏️ 근무표 편집", "📊 근무 통계"])

# ===================== 탭 1: 캘린더 보기 =====================
with tab_cal:
    st.subheader("🗓️ 근무 일정 확인")
    df = st.session_state.master_df
    
    # 달력 라이브러리 정상 동작 시 FullCalendar 출력
    if HAS_CALENDAR_LIB:
        try:
            events = []
            for _, r in df.iterrows():
                d_str = r["날짜"].strftime("%Y-%m-%d")
                for slot in (1, 2):
                    act = str(r[f"실제근무{slot}"]).strip()
                    if act:
                        events.append({
                            "title": f"[{slot}조] {act}",
                            "start": d_str,
                            "allDay": True
                        })
            calendar(events=events, options={"initialView": "dayGridMonth", "locale": "ko", "height": 600}, key="main_cal")
        except Exception as e:
            st.warning(f"인터랙티브 달력을 로드하지 못해 목록표로 표시합니다. (사유: {e})")
            st.dataframe(df[["날짜", "요일", "근무구분", "근무자1", "대직1", "실제근무1", "근무자2", "대직2", "실제근무2"]], use_container_width=True)
    else:
        # 라이브러리 부재 시 대체 데이터프레임 뷰
        st.dataframe(df[["날짜", "요일", "근무구분", "근무자1", "대직1", "실제근무1", "근무자2", "대직2", "실제근무2"]], use_container_width=True)

# ===================== 탭 2: 근무표 편집 =====================
with tab_edit:
    st.subheader("✏️ 데이터 직접 수정")
    st.info("💡 표에서 내용을 직접 수정한 후 아래 [💾 변경사항 저장] 버튼을 누르세요.")
    
    edit_df = st.session_state.master_df.copy()
    
    # 데이터 에디터 (항상 표시되도록 구조 단순화)
    edited_df = st.data_editor(
        edit_df,
        use_container_width=True,
        height=500,
        num_rows="dynamic",
        key="data_editor_simple"
    )
    
    st.write("") # 여백
    # 저장 버튼 (강제 표출)
    if st.button("💾 변경사항 저장 및 반영", type="primary", use_container_width=True):
        try:
            edited_df["날짜"] = pd.to_datetime(edited_df["날짜"])
            saved_df = apply_auto_calc(edited_df)
            st.session_state.master_df = saved_df
            st.success("✅ 성공적으로 저장되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")

# ===================== 탭 3: 근무 통계 =====================
with tab_stats:
    st.subheader("📊 근무 현황 요약")
    df = st.session_state.master_df
    st.metric("총 등록 근무일 수", f"{len(df)} 일")
    st.dataframe(df[["날짜", "근무구분", "실제근무1", "실제근무2"]], use_container_width=True)