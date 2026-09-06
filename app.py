import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
from pathlib import Path
import plotly.express as px

# ──────────────────────────────
# 페이지 기본 설정
# ──────────────────────────────
st.set_page_config(page_title="숙직 근무표 대시보드", layout="wide")

SHEET_NAME = "숙직근무자"
DEFAULT_EXCEL_PATH = Path("data/duty_schedule.xlsx")

REQUIRED_COLS = [
    "날짜", "근무자1", "대직1", "근무자2", "대직2", 
    "메모", "근무구분", "참고 년월", "실제근무1", "실제근무2", "요일"
]

# ──────────────────────────────
# 유틸리티 함수
# ──────────────────────────────
def create_sample_data() -> pd.DataFrame:
    """엑셀이 없을 때 화면 테스트용 더미 데이터 생성"""
    today = date.today()
    sample_list = []
    days = ["월", "화", "수", "목", "금", "토", "일"]
    workers = ["홍길동", "김철수", "이영희", "박민수", "정수진"]
    
    for i in range(10):
        dt = today + timedelta(days=i)
        sample_list.append({
            "날짜": pd.to_datetime(dt),
            "요일": days[dt.weekday()],
            "근무구분": "주말" if dt.weekday() >= 5 else "평일",
            "참고 년월": dt.strftime("%Y-%m"),
            "메모": "정상 근무" if i % 2 == 0 else "",
            "근무자1": workers[i % len(workers)],
            "대직1": "",
            "실제근무1": workers[i % len(workers)],
            "근무자2": workers[(i + 1) % len(workers)],
            "대직2": "",
            "실제근무2": workers[(i + 1) % len(workers)],
        })
    return pd.DataFrame(sample_list)

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
        st.error(f"엑셀 읽기 중 오류 발생: {e}")
        return pd.DataFrame()

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

# ──────────────────────────────
# 세션 상태 초기화
# ──────────────────────────────
if "master_df" not in st.session_state:
    if DEFAULT_EXCEL_PATH.exists():
        loaded = load_excel(DEFAULT_EXCEL_PATH)
        if not loaded.empty:
            st.session_state.master_df = apply_auto_calc(loaded)
        else:
            st.session_state.master_df = create_sample_data()
    else:
        # 파일이 없으면 생성된 샘플 데이터 사용
        st.session_state.master_df = create_sample_data()

# ──────────────────────────────
# 사이드바
# ──────────────────────────────
with st.sidebar:
    st.header("📂 데이터 파일")
    uploaded = st.file_uploader("엑셀(.xlsx) 업로드", type=["xlsx"])
    if uploaded:
        loaded_df = load_excel(uploaded)
        if not loaded_df.empty:
            st.session_state.master_df = apply_auto_calc(loaded_df)
            st.success(f"업로드 완료! ({len(loaded_df)}건)")
            st.rerun()
        else:
            st.error("엑셀 파일에서 읽을 수 있는 날짜 데이터가 없습니다.")

    st.divider()
    if st.button("🔄 테스트용 샘플 데이터 불러오기"):
        st.session_state.master_df = create_sample_data()
        st.success("샘플 데이터로 초기화되었습니다.")
        st.rerun()

# ──────────────────────────────
# 메인 화면
# ──────────────────────────────
st.title("📋 숙직 근무표 대시보드")

# 상태 디버깅 안내 카드
with st.expander("🔍 현재 로드된 데이터 상태 확인 (클릭)", expanded=True):
    row_cnt = len(st.session_state.master_df)
    st.write(f"- **현재 읽어온 행 개수**: {row_cnt}개")
    if row_cnt > 0:
        st.dataframe(st.session_state.master_df.head(3), use_container_width=True)

tab1, tab2 = st.tabs(["📅 근무 일정 확인", "✏️ 근무표 수정"])

# ===================== 탭 1: 일정 확인 =====================
with tab1:
    st.subheader("📋 전체 근무 목록")
    df = st.session_state.master_df.copy()
    
    if not df.empty:
        df_disp = df.copy()
        df_disp["날짜"] = df_disp["날짜"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            df_disp[["날짜", "요일", "근무구분", "근무자1", "대직1", "실제근무1", "근무자2", "대직2", "실제근무2", "메모"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("표시할 데이터가 없습니다.")

# ===================== 탭 2: 데이터 수정 =====================
with tab2:
    st.subheader("✏️ 테이블 직접 수정")
    
    edit_df = st.session_state.master_df.copy()
    edit_df["날짜"] = edit_df["날짜"].dt.strftime("%Y-%m-%d")
    
    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        height=400,
        num_rows="dynamic",
        key="editor_main"
    )
    
    if st.button("💾 변경사항 저장", type="primary"):
        edited["날짜"] = pd.to_datetime(edited["날짜"], errors="coerce")
        saved = apply_auto_calc(edited.dropna(subset=["날짜"]))
        st.session_state.master_df = saved
        st.success("저장되었습니다!")
        st.rerun()