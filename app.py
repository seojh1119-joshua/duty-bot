import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import json
from streamlit_calendar import calendar
import plotly.express as px

# ──────────────────────────────
# 페이지 설정
# ──────────────────────────────
st.set_page_config(page_title="?? 숙직 근무표 대시보드", layout="wide", initial_sidebar_state="expanded")

# ──────────────────────────────
# 상수 & 컬럼 매핑
# ──────────────────────────────
SHEET_NAME = "숙직근무자"
REQUIRED_COLS = [
    "날짜", "근무자1", "대직1", "근무자2", "대직2", 
    "메모", "근무구분", "참고 년월", "실제근무1", "실제근무2", "요일"
]
PLAN_COLS = ["근무자1", "대직1", "근무자2", "대직2"]
ACTUAL_COLS = ["실제근무1", "실제근무2"]

# ──────────────────────────────
# 유틸 함수
# ──────────────────────────────
def load_excel(file_bytes: bytes) -> pd.DataFrame:
    """엑셀 바이트 -> 정제된 DataFrame"""
    try:
        xls = pd.ExcelFile(file_bytes)
        # 시트명 유연하게 매칭
        target_sheet = SHEET_NAME if SHEET_NAME in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=target_sheet, dtype=str).fillna("")
        
        # 컬럼명 정리 (공백 제거)
        df.columns = [c.strip() for c in df.columns]
        
        # 필수 컬럼 없으면 생성
        for c in REQUIRED_COLS:
            if c not in df.columns:
                df[c] = ""
        
        # 날짜 파싱
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        df = df.dropna(subset=["날짜"]).copy()
        df = df.sort_values("날짜").reset_index(drop=True)
        return df[REQUIRED_COLS]
    except Exception as e:
        st.error(f"엑셀 로드 실패: {e}")
        return pd.DataFrame(columns=REQUIRED_COLS)

def compute_actuals(row: pd.Series) -> pd.Series:
    """계획(근무자/대직) -> 실제근무 자동 계산 로직
    규칙: 대직이 있으면 대직, 없으면 근무자. 단, 기존 실제근무 값이 있으면 우선(수동 수정 보존)"""
    for i in (1, 2):
        actual_col = f"실제근무{i}"
        primary_col = f"근무자{i}"
        standby_col = f"대직{i}"
        
        # 이미 실제근무가 입력되어 있으면 유지 (사용자 수동 수정 존중)
        if row[actual_col].strip():
            continue
        
        # 자동 계산
        standby = row[standby_col].strip()
        primary = row[primary_col].strip()
        row[actual_col] = standby if standby else primary
    return row

def apply_auto_calc(df: pd.DataFrame) -> pd.DataFrame:
    """전체 행에 자동 계산 적용 (실제근무 비어있는 행만)"""
    return df.apply(compute_actuals, axis=1)

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=SHEET_NAME)
    return out.getvalue()

def make_calendar_events(df: pd.DataFrame) -> list:
    """FullCalendar 이벤트 리스트 생성"""
    events = []
    color_map = {
        "평일": "#3b82f6", "금요일": "#2563eb", 
        "토요일": "#f59e0b", "일요일": "#ef4444", "공휴일": "#dc2626"
    }
    for _, row in df.iterrows():
        dt = row["날짜"]
        if pd.isna(dt): continue
        date_str = dt.strftime("%Y-%m-%d")
        
        # 슬롯 1, 2 각각 이벤트 생성
        for slot, (actual_col, plan_col, standby_col) in enumerate([
            ("실제근무1", "근무자1", "대직1"),
            ("실제근무2", "근무자2", "대직2")
        ], start=1):
            actual = row[actual_col].strip()
            if not actual: continue
            
            plan = row[plan_col].strip()
            standby = row[standby_col].strip()
            duty_type = row["근무구분"].strip()
            memo = row["메모"].strip()
            holiday = row["참고 년월"].strip() # 참고년월 컬럼에 공휴일명이 있는 경우 대비
            
            # 툴팁용 상세 정보
            detail = (
                f"?? {date_str} ({row['요일']}) | {duty_type}\n"
                f"?? 슬롯 {slot}: {actual}\n"
                f"?? 계획: {plan}" + (f" → 대직: {standby}" if standby else "") + "\n"
                f"?? 메모: {memo if memo else '없음'}"
            )
            
            events.append({
                "title": f"[{slot}] {actual}",
                "start": date_str,
                "allDay": True,
                "backgroundColor": color_map.get(duty_type, "#64748b"),
                "borderColor": color_map.get(duty_type, "#64748b"),
                "extendedProps": {
                    "tooltip": detail,
                    "slot": slot,
                    "plan": plan,
                    "standby": standby,
                    "duty_type": duty_type,
                    "memo": memo
                }
            })
    return events

def render_stats(df: pd.DataFrame):
    """하단 통계 패널"""
    st.subheader("?? 근무 통계 요약")
    if df.empty: return
    
    # 실제근무 기준 롱포맷 변환
    actuals = []
    for _, r in df.iterrows():
        for col in ACTUAL_COLS:
            name = r[col].strip()
            if name:
                actuals.append({
                    "날짜": r["날짜"], "이름": name, 
                    "근무구분": r["근무구분"], "요일": r["요일"]
                })
    act_df = pd.DataFrame(actuals)
    if act_df.empty: return
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 근무 건수", len(act_df))
    with col2:
        st.metric("근무자 수", act_df["이름"].nunique())
    with col3:
        holiday_cnt = len(act_df[act_df["근무구분"].isin(["토요일","일요일","공휴일"])])
        st.metric("휴일 근무 건수", holiday_cnt)
    
    # 개인별 월별 건수
    act_df["년월"] = act_df["날짜"].dt.to_period("M").astype(str)
    monthly = act_df.groupby(["년월", "이름"]).size().reset_index(name="횟수")
    
    tab1, tab2 = st.tabs(["?? 월별 개인 근무 횟수", "?? 공정성 분석 (표준편차)"])
    with tab1:
        fig = px.bar(monthly, x="이름", y="횟수", color="년월", barmode="group", 
                     title="월별 개인별 근무 횟수", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)
    with tab2:
        fairness = monthly.groupby("년월")["횟수"].std().reset_index()
        fairness.columns = ["년월", "표준편차"]
        fairness["표준편차"] = fairness["표준편차"].round(2)
        st.dataframe(fairness, use_container_width=True, hide_index=True)
        st.caption("표준편차가 낮을수록 근무 분배가 공정함")

# ──────────────────────────────
# 세션 상태 초기화
# ──────────────────────────────
if "master_df" not in st.session_state:
    st.session_state.master_df = pd.DataFrame(columns=REQUIRED_COLS)
if "calendar_view" not in st.session_state:
    st.session_state.calendar_view = "dayGridMonth"  # month, timeGridWeek, timeGridDay
if "auto_calc_enabled" not in st.session_state:
    st.session_state.auto_calc_enabled = True

# ──────────────────────────────
# 사이드바: 파일 입출력 & 설정
# ──────────────────────────────
with st.sidebar:
    st.header("?? 데이터 관리")
    uploaded = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=["xlsx"])
    if uploaded:
        df = load_excel(uploaded.read())
        if not df.empty:
            st.session_state.master_df = df
            st.success(f"? '{uploaded.name}' 로드 완료 ({len(df)}행)")
    
    st.divider()
    st.header("?? 설정")
    st.session_state.auto_calc_enabled = st.checkbox(
        "자동 계산 활성화 (대직 있으면 대직, 없으면 근무자 → 실제근무 반영)", 
        value=st.session_state.auto_calc_enabled
    )
    
    if st.button("?? 자동 계산 강제 실행"):
        st.session_state.master_df = apply_auto_calc(st.session_state.master_df)
        st.success("자동 계산 적용 완료")
    
    st.divider()
    # 다운로드
    if not st.session_state.master_df.empty:
        st.download_button(
            "?? 현재 데이터 엑셀 저장",
            data=to_excel_bytes(st.session_state.master_df),
            file_name=f"숙직근무표_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ──────────────────────────────
# 메인 화면
# ──────────────────────────────
st.title("?? 숙직 근무표 통합 대시보드")

if st.session_state.master_df.empty:
    st.info("?? 사이드바에서 엑셀 파일을 업로드하세요. (시트명: '숙직근무자' 또는 첫 번째 시트)")
    st.stop()

# ──────────────────────────────
# 탭 구성
# ──────────────────────────────
tab_cal, tab_edit, tab_stats, tab_mapping = st.tabs(["?? 캘린더", "?? 편집", "?? 통계", "?? 직원/알림 설정"])

with tab_mapping:
    st.subheader("직원별 카카오 알림 설정")
    st.caption("카카오 '나에게 보내기' 사용 시: 직원별 Access/Refresh Token 저장 필요. 초기 1회 토큰 발급 후 저장하면 자동 갱신됨.")
    
    # 매핑 파일 로드/초기화
    MAPPING_FILE = Path("data/staff_mapping.csv")
    if MAPPING_FILE.exists():
        map_df = pd.read_csv(MAPPING_FILE, dtype=str).fillna("")
    else:
        # 기존 근무자 명단으로 초기화
        names = pd.unique(st.session_state.master_df[["근무자1","대직1","근무자2","대직2","실제근무1","실제근무2"]].values.ravel("K"))
        names = [n for n in names if n]
        map_df = pd.DataFrame({"이름": sorted(names), "카카오키": "", "알림여부": "Y"})
    
    # 편집기
    edited_map = st.data_editor(
        map_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "이름": st.column_config.TextColumn("직원명", disabled=True),
            "카카오키": st.column_config.TextColumn("카카오 식별키", help="나에게보내기: 임의 키(예:_홍길동) / 알림톡: 전화번호(010xxxxxxxx)"),
            "알림여부": st.column_config.SelectboxColumn("알림수신", options=["Y", "N"], default="Y"),
        },
        hide_index=True
    )
    
    if st.button("?? 매핑 저장", type="primary"):
        MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
        edited_map.to_csv(MAPPING_FILE, index=False, encoding="utf-8-sig")
        st.success("저장 완료! 워커가 이 파일을 읽습니다.")
    
    st.divider()
    st.markdown("### ?? 카카오 토큰 발급 가이드 (나에게 보내기 방식)")
    st.code("""
1. 카카오 개발자 콘솔 → 내 애플리케이션 → 제품 설정 → 카카오톡 메시지 → 동의항목: '나에게 보내기' 추가
2. [REST API 키] 복사 → config.yaml 에 입력
3. 아래 인가코드 발급 URL 브라우저에서 접속:
   https://kauth.kakao.com/oauth/authorize?client_id={REST_API_KEY}&redirect_uri=http://localhost:8080/callback&response_type=code&scope=talk_message
4. 리다이렉트 URL에서 'code=XXXX' 값 복사
5. 터미널에서 토큰 교환:
   curl -X POST "https://kauth.kakao.com/oauth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code&client_id={REST_API_KEY}&redirect_uri=http://localhost:8080/callback&code={위_코드값}"
6. 반환된 access_token, refresh_token 을 data/kakao_tokens.json 에 저장:
   { "_홍길동": { "access_token": "...", "refresh_token": "..." } }
7. 위 '카카오키' 컬럼에 '_홍길동' 입력
""", language="bash")
# ===================== 탭 1: 캘린더 =====================
with tab_cal:
    st.subheader("근무 일정 캘린더")
    
    # 뷰 선택 버튼
    view_cols = st.columns([1,1,1,3])
    views = {"month": "월간", "timeGridWeek": "주간", "timeGridDay": "일간", "listMonth": "목록"}
    for i, (key, label) in enumerate(views.items()):
        if view_cols[i].button(label, use_container_width=True, type="primary" if st.session_state.calendar_view==key else "secondary"):
            st.session_state.calendar_view = key
            st.rerun()
    
    # 이벤트 생성
    events = make_calendar_events(st.session_state.master_df)
    
    # 캘린더 옵션
    calendar_options = {
        "initialView": st.session_state.calendar_view,
        "locale": "ko",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listMonth"
        },
        "height": 650,
        "eventDisplay": "block",
        "eventDidMount": "function(info) { info.el.title = info.event.extendedProps.tooltip; }", # 툴팁
        "dayMaxEvents": True,
    }
    
    # 캘린더 렌더링
    selected = calendar(events=events, options=calendar_options, key="duty_cal")
    
    # 클릭 시 상세 표시
    if selected.get("eventClick"):
        evt = selected["eventClick"]["event"]
        props = evt["extendedProps"]
        st.toast(f"선택: {evt['title']} ({evt['start']})", icon="??")
        with st.expander(f"?? 상세: {evt['title']} - {evt['start']}", expanded=True):
            st.markdown(f"""
            - **날짜**: {evt['start']}
            - **슬롯**: {props['slot']}번
            - **실제 근무자**: {evt['title'].split('] ')[1]}
            - **계획 근무자**: {props['plan']}
            - **대직자**: {props['standby'] if props['standby'] else '없음'}
            - **근무구분**: {props['duty_type']}
            - **메모**: {props['memo'] if props['memo'] else '없음'}
            """)

# ===================== 탭 2: 편집기 =====================
with tab_edit:
    st.subheader("근무표 원본 데이터 편집")
    st.caption("?? `근무자1, 대직1, 근무자2, 대직2` 수정 시 → `실제근무1, 2` 자동 반영 (자동 계산 ON 시). `실제근무` 열을 직접 수정하면 자동 계산 무시됨.")
    
    edit_df = st.session_state.master_df.copy()
    
    # 편집 가능한 컬럼만 노출 (순서 조정)
    display_cols = [
        "날짜", "요일", "근무구분", "참고 년월", "메모",
        "근무자1", "대직1", "실제근무1",
        "근무자2", "대직2", "실제근무2"
    ]
    
    # 고유 키 생성을 위해 인덱스 리셋
    edit_df = edit_df.reset_index(drop=True)
    
    edited = st.data_editor(
        edit_df[display_cols],
        use_container_width=True,
        height=600,
        num_rows="dynamic",
        column_config={
            "날짜": st.column_config.DateColumn("날짜", disabled=True, format="YYYY-MM-DD"),
            "요일": st.column_config.TextColumn("요일", disabled=True, width="small"),
            "근무구분": st.column_config.SelectboxColumn("구분", options=["평일","금요일","토요일","일요일","공휴일"], width="small"),
            "참고 년월": st.column_config.TextColumn("비고(년월/공휴일)", width="medium"),
            "메모": st.column_config.TextColumn("메모", width="large"),
            "근무자1": st.column_config.TextColumn("근무자1", required=True),
            "대직1": st.column_config.TextColumn("대직1"),
            "실제근무1": st.column_config.TextColumn("실제근무1", help="비우면 자동 계산, 입력 시 수동 고정"),
            "근무자2": st.column_config.TextColumn("근무자2"),
            "대직2": st.column_config.TextColumn("대직2"),
            "실제근무2": st.column_config.TextColumn("실제근무2", help="비우면 자동 계산, 입력 시 수동 고정"),
        },
        hide_index=True,
        key="data_editor_main"
    )
    
    # 저장 버튼
    if st.button("?? 변경사항 저장 및 캘린더 반영", type="primary", use_container_width=True):
        # 편집된 데이터프레임으로 마스터 업데이트
        # 날짜 컬럼 타입 복원
        edited["날짜"] = pd.to_datetime(edited["날짜"])
        
        # 자동 계산 로직 적용 (세션 설정 확인)
        if st.session_state.auto_calc_enabled:
            edited = apply_auto_calc(edited)
        
        # 원본 컬럼 순서로 맞춰 저장
        st.session_state.master_df = edited[REQUIRED_COLS].copy()
        st.success("저장 완료! 캘린더 탭에서 확인하세요.")
        st.rerun()

# ===================== 탭 3: 통계 =====================
with tab_stats:
    render_stats(st.session_state.master_df)

# ──────────────────────────────
# 푸터
# ──────────────────────────────
st.caption("ⓒ 2026 숙직 근무표 대시보드 ? Streamlit + FullCalendar ? 데이터는 브라우저 세션에만 저장됩니다. 중요 데이터는 엑셀 다운로드로 백업하세요.")ㅁ