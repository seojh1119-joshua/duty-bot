import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from pathlib import Path
import plotly.express as px

# ──────────────────────────────
# 페이지 기본 설정
# ──────────────────────────────
st.set_page_config(page_title="숙직 근무표 대시보드", layout="wide", initial_sidebar_state="expanded")

SHEET_NAME = "숙직근무자"
DEFAULT_EXCEL_PATH = Path("data/duty_schedule.xlsx")

REQUIRED_COLS = [
    "날짜", "근무자1", "대직1", "근무자2", "대직2", 
    "메모", "근무구분", "참고 년월", "실제근무1", "실제근무2", "요일"
]

# ──────────────────────────────
# 유틸리티 함수
# ──────────────────────────────
def load_excel(file_source) -> pd.DataFrame:
    """엑셀 데이터를 읽어 정제된 DataFrame 반환"""
    try:
        if isinstance(file_source, bytes):
            file_source = BytesIO(file_source)

        xls = pd.ExcelFile(file_source)
        target_sheet = SHEET_NAME if SHEET_NAME in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=target_sheet, dtype=str).fillna("")
        
        # 컬럼명 공백 제거
        df.columns = [str(c).replace(" ", "").strip() for c in df.columns]
        
        # 필수 컬럼 보장
        for c in REQUIRED_COLS:
            if c not in df.columns:
                df[c] = ""
        
        # 날짜 형식을 YYYY-MM-DD 문자열 및 datetime으로 정리
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        df = df.dropna(subset=["날짜"]).copy()
        df = df.sort_values("날짜").reset_index(drop=True)
        return df[REQUIRED_COLS]
    except Exception as e:
        st.error(f"엑셀 파일 읽기 오류: {e}")
        return pd.DataFrame(columns=REQUIRED_COLS)

def apply_auto_calc(df: pd.DataFrame) -> pd.DataFrame:
    """근무자/대직 정보를 바탕으로 실제근무 자동 계산"""
    if df.empty: 
        return df
    df = df.copy()
    for idx, row in df.iterrows():
        for i in (1, 2):
            act_col, pri_col, std_col = f"실제근무{i}", f"근무자{i}", f"대직{i}"
            # 실제근무가 비어있는 경우에만 자동 계산 적용
            if not str(row[act_col]).strip():
                std = str(row[std_col]).strip()
                pri = str(row[pri_col]).strip()
                df.at[idx, act_col] = std if std else pri
    return df

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame을 엑셀 바이너리로 변환"""
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        # datetime 형태를 엑셀 저장용 문자열로 변환
        export_df = df.copy()
        export_df["날짜"] = export_df["날짜"].dt.strftime("%Y-%m-%d")
        export_df.to_excel(writer, index=False, sheet_name=SHEET_NAME)
    return out.getvalue()

# ──────────────────────────────
# 세션 상태 관리
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
    st.header("📂 파일 관리")
    uploaded = st.file_uploader("엑셀 파일(.xlsx) 업로드", type=["xlsx"])
    if uploaded:
        loaded_df = load_excel(uploaded)
        if not loaded_df.empty:
            st.session_state.master_df = apply_auto_calc(loaded_df)
            st.success(f"✅ 업로드 완료 ({len(loaded_df)}건)")
            st.rerun()
            
    st.divider()
    if not st.session_state.master_df.empty:
        st.download_button(
            "💾 엑셀 파일로 백업 다운로드",
            data=to_excel_bytes(st.session_state.master_df),
            file_name=f"숙직근무표_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ──────────────────────────────
# 메인 영역
# ──────────────────────────────
st.title("📋 숙직 근무표 관리 시스템")

if st.session_state.master_df.empty:
    st.warning("⚠️ 등록된 근무 데이터가 없습니다. 좌측 사이드바에서 엑셀(.xlsx) 파일을 업로드하세요.")
    st.stop()

# 탭 구성 (캘린더 / 데이터 편집 / 근무 통계)
tab_cal, tab_edit, tab_stats = st.tabs(["📅 근무 캘린더", "✏️ 근무표 수정", "📊 근무 통계"])

# ===================== 탭 1: 근무 캘린더 (안전 타임라인/카드 뷰) =====================
with tab_cal:
    st.subheader("🗓️ 월별 근무 일정")
    df = st.session_state.master_df.copy()
    
    # 년-월 선택 필터
    df["년월"] = df["날짜"].dt.strftime("%Y-%m")
    available_months = sorted(df["년월"].unique())
    
    if available_months:
        selected_month = st.selectbox("📅 조회할 년-월 선택", available_months, index=len(available_months)-1)
        m_df = df[df["년월"] == selected_month].sort_values("날짜")
        
        # 타임라인 차트 데이터 구성
        chart_data = []
        for _, r in m_df.iterrows():
            d_str = r["날짜"].strftime("%Y-%m-%d")
            for slot in (1, 2):
                act = str(r[f"실제근무{slot}"]).strip()
                if act:
                    chart_data.append({
                        "날짜": d_str,
                        "근무자": f"{act} ({slot}조)",
                        "구분": r["근무구분"] if r["근무구분"] else "일반",
                        "메모": r["메모"]
                    })
        
        if chart_data:
            cdf = pd.DataFrame(chart_data)
            fig = px.timeline(
                cdf, 
                x_start="날짜", 
                x_end="날짜", 
                y="근무자", 
                color="구분", 
                title=f"{selected_month} 근무 타임라인",
                hover_data=["메모"]
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        st.subheader("📋 상세 근무 목록")
        
        # 메인 표 표시
        display_df = m_df.copy()
        display_df["날짜"] = display_df["날짜"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            display_df[["날짜", "요일", "근무구분", "근무자1", "대직1", "실제근무1", "근무자2", "대직2", "실제근무2", "메모"]],
            use_container_width=True,
            hide_index=True
        )

# ===================== 탭 2: 근무표 수정 (저장 버튼 100% 동작) =====================
with tab_edit:
    st.subheader("✏️ 근무표 원본 수정")
    st.info("💡 표 안의 내용을 수정한 뒤, 표 아래의 **[💾 변경사항 저장]** 버튼을 누르면 캘린더에 즉시 반영됩니다.")
    
    edit_df = st.session_state.master_df.copy()
    edit_df["날짜"] = edit_df["날짜"].dt.strftime("%Y-%m-%d")
    
    # 데이터 에디터
    edited_data = st.data_editor(
        edit_df,
        use_container_width=True,
        height=500,
        num_rows="dynamic",
        key="data_editor_safe"
    )
    
    st.write("") # 간격 조정
    
    # 저장 버튼 (반드시 화면에 노출됨)
    if st.button("💾 변경사항 저장 및 캘린더 반영", type="primary", use_container_width=True):
        try:
            # 날짜 변환 및 자동 계산 적용
            updated_df = edited_data.copy()
            updated_df["날짜"] = pd.to_datetime(updated_df["날짜"], errors="coerce")
            updated_df = updated_df.dropna(subset=["날짜"])
            
            # 자동 계산 적용 후 세션 저장
            saved_df = apply_auto_calc(updated_df)
            st.session_state.master_df = saved_df
            
            st.success("✅ 정상적으로 저장되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")

# ===================== 탭 3: 근무 통계 =====================
with tab_stats:
    st.subheader("📊 근무 현황 통계")
    df = st.session_state.master_df
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("총 등록 데이터 수", f"{len(df)} 건")
    with col2:
        workers = set(df["실제근무1"].tolist() + df["실제근무2"].tolist()) - {""}
        st.metric("총 근무 인원", f"{len(workers)} 명")
    
    st.divider()
    st.write("**근무자별 실제 근무 횟수 Summary**")
    
    # 근무 횟수 집계
    all_workers = [w for w in df["실제근무1"].tolist() + df["실제근무2"].tolist() if str(w).strip()]
    if all_workers:
        work_counts = pd.Series(all_workers).value_counts().reset_index()
        work_counts.columns = ["근무자 이름", "근무 횟수"]
        
        fig_bar = px.bar(work_counts, x="근무자 이름", y="근무 횟수", text_auto=True, title="개인별 총 근무 횟수")
        st.plotly_chart(fig_bar, use_container_width=True)