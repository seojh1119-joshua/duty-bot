import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import re
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
# 엑셀 파싱 유틸리티 함수
# ──────────────────────────────
def parse_korean_date(val):
    """다양한 형태의 날짜(문자열, 시리얼, datetime)를 안전하게 datetime으로 변환"""
    if pd.isna(val) or str(val).strip() == "":
        return pd.NaT
    
    val_str = str(val).strip()
    
    # 1. 엑셀 시리얼 번호(숫자 형태 ex: 45536) 대응
    if val_str.replace('.', '', 1).isdigit():
        try:
            num = float(val_str)
            if num > 30000:
                return pd.to_datetime(num, unit='D', origin='1899-12-30')
        except:
            pass

    # 2. '2026.09.01', '2026/09/01', '2026년 9월 1일' 등 특수문자/한글 구분자 표준화
    cleaned_str = re.sub(r'[년월일\.\/]', '-', val_str)
    cleaned_str = re.sub(r'-+', '-', cleaned_str).strip('-')

    return pd.to_datetime(cleaned_str, errors="coerce")

def find_header_and_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """상단 1~10행 내에서 '날짜' 관련 키워드가 포함된 헤더 행을 자동 탐색하여 정제"""
    header_idx = None
    
    # 상단 10개 행을 순회하며 '날짜' 관련 키워드가 있는 행 탐색
    for idx in range(min(10, len(df_raw))):
        row_values = [str(val).replace(" ", "").strip() for val in df_raw.iloc[idx].values]
        if any("날짜" in val or "일자" in val or "근무일" in val for val in row_values):
            header_idx = idx
            break

    # 헤더 행을 찾은 경우 해당 행을 컬럼명으로 지정
    if header_idx is not None:
        new_cols = [str(val).replace(" ", "").strip() for val in df_raw.iloc[header_idx].values]
        df_data = df_raw.iloc[header_idx + 1:].copy()
        df_data.columns = new_cols
        return df_data
    
    # 헤더를 찾지 못한 경우 기존 구조 유지
    df_raw.columns = [str(c).replace(" ", "").strip() for c in df_raw.columns]
    return df_raw

def load_excel(file_source) -> pd.DataFrame:
    """헤더 위치 자동 감지 및 날짜 파싱이 강화된 엑셀 로더"""
    try:
        if isinstance(file_source, bytes):
            file_source = BytesIO(file_source)

        xls = pd.ExcelFile(file_source)
        
        # '숙직근무자' 시트 탐색
        target_sheet = None
        for sheet in xls.sheet_names:
            if sheet.strip() == SHEET_NAME:
                target_sheet = sheet
                break
        if not target_sheet:
            target_sheet = xls.sheet_names[0]

        # 헤더 없이 원본 전체 읽기 (header=None)
        df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None, dtype=object).fillna("")
        
        # 1. 헤더 위치 자동 탐색 적용 (2열/3열 헤더 자동 감지)
        df = find_header_and_data(df_raw)

        # 2. '날짜' 단어가 포함된 열 자동 탐색
        date_col = None
        for col in df.columns:
            if "날짜" in str(col) or "일자" in str(col) or "근무일" in str(col):
                date_col = col
                break
        
        if not date_col and len(df.columns) > 0:
            date_col = df.columns[0]

        # 3. 날짜 파싱 적용
        df["날짜"] = df[date_col].apply(parse_korean_date)
        
        # 유효한 날짜가 있는 행만 추출
        valid_df = df.dropna(subset=["날짜"]).copy()
        
        if valid_df.empty:
            st.error(f"⚠️ '{target_sheet}' 시트에서 인식 가능한 날짜 데이터를 찾지 못했습니다.")
            return pd.DataFrame()

        valid_df = valid_df.sort_values("날짜").reset_index(drop=True)
        
        # 필수 컬럼 존재 여부 체크 및 빈값 채우기
        for c in REQUIRED_COLS:
            if c not in valid_df.columns:
                valid_df[c] = ""

        return valid_df[REQUIRED_COLS]
        
    except Exception as e:
        st.error(f"엑셀 파일 로드 중 오류 발생: {e}")
        return pd.DataFrame()

def apply_auto_calc(df: pd.DataFrame) -> pd.DataFrame:
    """근무자/대직 정보를 바탕으로 실제근무 자동 계산"""
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
    """DataFrame을 엑셀 바이너리로 변환"""
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        export_df = df.copy()
        export_df["날짜"] = export_df["날짜"].dt.strftime("%Y-%m-%d")
        export_df.to_excel(writer, index=False, sheet_name=SHEET_NAME)
    return out.getvalue()

# ──────────────────────────────
# 세션 상태 초기화
# ──────────────────────────────
if "master_df" not in st.session_state:
    if DEFAULT_EXCEL_PATH.exists():
        loaded = load_excel(DEFAULT_EXCEL_PATH)
        st.session_state.master_df = apply_auto_calc(loaded)
    else:
        st.session_state.master_df = pd.DataFrame(columns=REQUIRED_COLS)

# ──────────────────────────────
# 사이드바
# ──────────────────────────────
with st.sidebar:
    st.header("📂 데이터 파일 관리")
    uploaded = st.file_uploader("엑셀(.xlsx) 파일 업로드", type=["xlsx"])
    if uploaded:
        loaded_df = load_excel(uploaded)
        if not loaded_df.empty:
            st.session_state.master_df = apply_auto_calc(loaded_df)
            st.success(f"✅ 업로드 완료! ({len(loaded_df)}건 감지됨)")
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

# 디버그 박스 (데이터 로드 상태 확인용)
with st.expander("🔍 데이터 읽기 결과 확인 (클릭)", expanded=False):
    row_cnt = len(st.session_state.master_df)
    st.write(f"- **성공적으로 읽어온 행 개수**: {row_cnt}개")
    st.dataframe(st.session_state.master_df.head(3), use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 근무 일정 확인", "✏️ 근무표 수정", "📊 근무 통계"])

# ===================== 탭 1: 일정 확인 =====================
with tab1:
    st.subheader("📋 상세 근무 목록")
    df = st.session_state.master_df.copy()
    
    df_disp = df.copy()
    df_disp["날짜"] = df_disp["날짜"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        df_disp[["날짜", "요일", "근무구분", "근무자1", "대직1", "실제근무1", "근무자2", "대직2", "실제근무2", "메모"]],
        use_container_width=True,
        hide_index=True
    )

# ===================== 탭 2: 데이터 수정 =====================
with tab2:
    st.subheader("✏️ 원본 데이터 직접 수정")
    st.info("💡 셀 내용을 수정한 후 아래 [💾 변경사항 저장] 버튼을 누르세요.")
    
    edit_df = st.session_state.master_df.copy()
    edit_df["날짜"] = edit_df["날짜"].dt.strftime("%Y-%m-%d")
    
    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        height=500,
        num_rows="dynamic",
        key="editor_main"
    )
    
    if st.button("💾 변경사항 저장 및 반영", type="primary", use_container_width=True):
        edited["날짜"] = pd.to_datetime(edited["날짜"], errors="coerce")
        saved = apply_auto_calc(edited.dropna(subset=["날짜"]))
        st.session_state.master_df = saved
        st.success("✅ 저장되었습니다!")
        st.rerun()

# ===================== 탭 3: 근무 통계 =====================
with tab3:
    st.subheader("📊 근무 현황 통계")
    df = st.session_state.master_df
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("총 등록 근무일 수", f"{len(df)} 일")
    with col2:
        workers = set(df["실제근무1"].tolist() + df["실제근무2"].tolist()) - {""}
        st.metric("총 근무 참여 인원", f"{len(workers)} 명")
    
    st.divider()
    all_workers = [w for w in df["실제근무1"].tolist() + df["실제근무2"].tolist() if str(w).strip()]
    if all_workers:
        work_counts = pd.Series(all_workers).value_counts().reset_index()
        work_counts.columns = ["근무자 이름", "근무 횟수"]
        fig_bar = px.bar(work_counts, x="근무자 이름", y="근무 횟수", text_auto=True, title="개인별 총 근무 횟수")
        st.plotly_chart(fig_bar, use_container_width=True)