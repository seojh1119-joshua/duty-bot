import datetime
import calendar
import pandas as pd
import streamlit as st

# 페이지 기본 설정 (모바일 최적화 레이아웃 폭 640px 스타일 등 고려)
st.set_page_config(page_title="근무표 관리 시스템", layout="centered")

# CSS 스타일 적용 (토요일 파랑, 일요일/공휴일 빨강, 팝업 및 클릭 효과 등)
st.markdown(
    """
    <style>
    .sat-date { color: #0066cc; font-weight: bold; }
    .sun-hol-date { color: #cc0000; font-weight: bold; }
    .clickable-cell { cursor: pointer; transition: background-color 0.2s; }
    .clickable-cell:hover { background-color: #f0f2f6; }
    .today-box {
        background-color: #e6f2ff;
        border: 2px solid #3399ff;
        padding: 15px;
        border-radius: 10px;
        cursor: pointer;
        margin-bottom: 20px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# 세션 상태 초기화 (근무 데이터 및 팝업 상태 관리)
if "schedule_data" not in st.session_state:
  # 예시 데이터 프레임 (날짜별 근무자 정보)
  st.session_state.schedule_data = pd.DataFrame({
      "날짜": pd.date_range(
          start="2026-09-01", end="2026-09-30"
      ).strftime("%Y-%m-%d"),
      "근무자": ["홍길동", "김철수", "이영희", "박민수"]
      * 8,  # 임시 반복 데이터
  })

if "selected_date" not in st.session_state:
  st.session_state.selected_date = datetime.date.today().strftime("%Y-%m-%d")

if "show_popup" not in st.session_state:
  st.session_state.show_popup = False

if "popup_mode" not in st.session_state:
  st.session_state.popup_mode = (
      "manage"  # 'manage' (근무관리) 또는 'edit' (일자별수정)
  )

# --- 2. 오늘 근무안내 박스 (클릭 시 일자별 수정/관리 팝업 연동) ---
today_str = datetime.date.today().strftime("%Y-%m-%d")
# 오늘 근무자 조회
today_worker_row = st.session_state.schedule_data[
    st.session_state.schedule_data["날짜"] == today_str
]
today_worker = (
    today_worker_row["근무자"].values[0]
    if not today_worker_row.empty
    else "근무자 미지정"
)

st.markdown(
    f"""
    <div class="today-box" onclick="">
        <h3>📌 오늘 ({today_str}) 근무 안내</h3>
        <p>오늘의 근무자: <b>{today_worker}</b></p>
        <p style="font-size: 0.85em; color: #555;">(이 박스를 누르면 일자별 수정 및 근무관리 화면이 열립니다)</p>
    </div>
""",
    unsafe_allow_html=True,
)

# 스트림릿 버튼으로 대체 구현 (HTML onclick 제약 우회 및 확실한 동작 보장)
if st.button("👉 오늘 근무안내 박스 열기 (일자별 수정/관리)", use_container_width=True):
  st.session_state.selected_date = today_str
  st.session_state.show_popup = True
  st.session_state.popup_mode = "edit"
  st.rerun()

st.divider()

# --- 상단 메뉴탭 (가로형 달력 / 세로형 달력 / 일자별 수정) ---
tab1, tab2, tab3 = st.tabs(["📅 가로형 달력", "📋 세로형 달력", "✏️ 일자별 수정"])

# 공휴일 리스트 예시 (실제 엑셀 M열 또는 공휴일 데이터 연동부)
holidays = ["2026-09-25", "2026-09-28"]  # 예시 공휴일


# 요일별 색상 판별 함수
def get_date_style(date_obj):
  weekday = date_obj.weekday()  # 0:월, 5:토, 6:일
  date_str = date_obj.strftime("%Y-%m-%d")
  if weekday == 5:
    return "sat-date", "토"
  elif weekday == 6 or date_str in holidays:
    return "sun-hol-date", "일" if weekday == 6 else "공휴일"
  else:
    return "", ""


# --- Tab 1: 가로형 달력 ---
with tab1:
  st.subheader("가로형 달력")
  st.info("💡 일자 칸을 누르면 해당 날짜의 근무관리 메뉴가 팝업됩니다.")

  # 월 선택
  col_y, col_m = st.columns(2)
  with col_y:
    sel_year = st.selectbox(
        "연도", [2025, 2026, 2027], index=1, key="h_year"
    )
  with col_m:
    sel_month = st.selectbox(
        "월", list(range(1, 13)), index=8, key="h_month"
    )  # 9월 기본

  # 달력 그리드 생성 예시
  cal = calendar.monthcalendar(sel_year, sel_month)
  cols_header = ["월", "화", "수", "목", "금", "토", "일"]

  # 테이블 형태 출력 및 클릭 이벤트 시뮬레이션
  for week in cal:
    cols = st.columns(7)
    for i, day in enumerate(week):
      with cols[i]:
        if day == 0:
          st.write("")
        else:
          current_date = datetime.date(sel_year, sel_month, day)
          date_str = current_date.strftime("%Y-%m-%d")
          css_class, _ = get_date_style(current_date)

          # 해당 일자의 근무자 확인
          match_row = st.session_state.schedule_data[
              st.session_state.schedule_data["날짜"] == date_str
          ]
          worker = match_row["근무자"].values[0] if not match_row.empty else ""

          # 일자 버튼 (칸을 누르면 근무관리 메뉴 팝업)
          button_label = f"{day}\n({worker})" if worker else f"{day}"
          if st.button(
              button_label, key=f"h_btn_{date_str}", use_container_width=True
          ):
            st.session_state.selected_date = date_str
            st.session_state.show_popup = True
            st.session_state.popup_mode = "manage"
            st.rerun()

# --- Tab 2: 세로형 달력 ---
with tab2:
  st.subheader("세로형 달력 (리스트형)")
  st.info(
      "💡 토요일은 파란색, 일요일 및 공휴일은 빨간색으로 표시되며, 일자 칸을"
      " 누르면 근무관리 메뉴가 열립니다."
  )

  num_days = calendar.monthrange(sel_year, sel_month)[1]
  for day in range(1, num_days + 1):
    current_date = datetime.date(sel_year, sel_month, day)
    date_str = current_date.strftime("%Y-%m-%d")
    css_class, day_type = get_date_style(current_date)

    match_row = st.session_state.schedule_data[
        st.session_state.schedule_data["날짜"] == date_str
    ]
    worker = match_row["근무자"].values[0] if not match_row.empty else "-"

    # 색상 적용 텍스트 HTML
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    w_name = weekday_names[current_date.weekday()]

    col_date, col_work, col_btn = st.columns([2, 2, 1])
    with col_date:
      if css_class:
        st.markdown(
            f'<span class="{css_class}">{day}일 ({w_name})</span>',
            unsafe_allow_html=True,
        )
      else:
        st.write(f"{day}일 ({w_name})")

    with col_work:
      st.write(f"근무: **{worker}**")

    with col_btn:
      if st.button("선택", key=f"v_btn_{date_str}"):
        st.session_state.selected_date = date_str
        st.session_state.show_popup = True
        st.session_state.popup_mode = "manage"
        st.rerun()

# --- Tab 3: 일자별 수정 ---
with tab3:
  st.subheader("일자별 근무 수정")

  # 1. 날짜를 바꾸면 해당 날짜 근무자들이 바로 연동되어 보이도록 구성
  all_dates = st.session_state.schedule_data["날짜"].unique()
  selected_edit_date = st.selectbox(
      "수정할 날짜 선택",
      options=all_dates,
      index=(
          list(all_dates).index(st.session_state.selected_date)
          if st.session_state.selected_date in all_dates
          else 0
      ),
  )

  # 연동된 해당 날짜 근무자 불러오기
  current_worker_row = st.session_state.schedule_data[
      st.session_state.schedule_data["날짜"] == selected_edit_date
  ]
  current_worker_val = (
      current_worker_row["근무자"].values[0]
      if not current_worker_row.empty
      else ""
  )

  st.write(f"현재 선택된 날짜: **{selected_edit_date}**")
  new_worker = st.text_input(
      "근무자 수정", value=current_worker_val, key="input_edit_worker"
  )

  if st.button("변경사항 저장"):
    st.session_state.schedule_data.loc[
        st.session_state.schedule_data["날짜"] == selected_edit_date, "근무자"
    ] = new_worker
    st.success(f"{selected_edit_date} 근무자가 [{new_worker}](으)로 수정되었습니다!")

# --- 팝업창 구현 (근무관리 메뉴 / 일자별 수정 연동 팝업) ---
if st.session_state.show_popup:
  @st.dialog(f"🛠️ 근무 관리 메뉴 ({st.session_state.selected_date})")
  def popup_menu():
    st.write(
        f"선택하신 날짜: **{st.session_state.selected_date}**에 대한 관리"
        " 메뉴입니다."
    )

    # 해당 날짜 정보 확인
    target_row = st.session_state.schedule_data[
        st.session_state.schedule_data["날짜"] == st.session_state.selected_date
    ]
    cur_worker = (
        target_row["근무자"].values[0] if not target_row.empty else ""
    )

    # 팝업 내부 탭 또는 기능 분기
    edit_worker_popup = st.text_input(
        "근무자 변경", value=cur_worker, key="popup_worker_input"
    )

    col1, col2 = st.columns(2)
    with col1:
      if st.button("저장하기", use_container_width=True):
        st.session_state.schedule_data.loc[
            st.session_state.schedule_data["날짜"]
            == st.session_state.selected_date,
            "근무자",
        ] = edit_worker_popup
        st.success("저장되었습니다!")
        st.session_state.show_popup = False
        st.rerun()
    with col2:
      if st.button("닫기", use_container_width=True):
        st.session_state.show_popup = False
        st.rerun()


  popup_menu()
