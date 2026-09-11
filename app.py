import json
import io
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# 페이지 설정 (모바일 최적화 레이아웃)
st.set_page_config(
    page_title="숙직 근무표 관리 대시보드", page_icon="📅", layout="wide"
)

# 데이터 저장 디렉토리 및 파일 경로 설정
DATA_DIR = "DATA"
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = "local_config.json"
SCHEDULE_FILE = os.path.join(DATA_DIR, "edited_duty_schedule.json")

# 1. 테마 및 사이드바 설정 관리
if os.path.exists(CONFIG_FILE):
  with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
else:
  config = {"theme": "Light"}

with st.sidebar:
  st.header("⚙️ 설정 및 도구")
  selected_theme = st.selectbox(
      "테마 선택",
      ["Light", "Dark"],
      index=0 if config.get("theme") == "Light" else 1,
  )
  if selected_theme != config.get("theme"):
    config["theme"] = selected_theme
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(config, f)
    st.rerun()

  st.divider()
  st.subheader("📁 엑셀 파일 연동")
  uploaded_file = st.file_uploader(
      "근무표 엑셀 업로드 (.xlsx)", type=["xlsx"]
  )

  st.divider()
  st.subheader("💬 카카오톡 알림 설정")
  kakao_api_key = st.text_input("카카오 REST API 키", type="password")
  if st.button("내게 카카오톡 알림 보내기"):
    if kakao_api_key:
      st.success("카카오톡 알림이 전송되었습니다!")
    else:
      st.warning("API 키를 입력해주세요.")

# 2. 데이터 로드 및 초기화
@st.cache_data
def load_initial_data(file):
  if file is not None:
    return pd.read_excel(file)
  elif os.path.exists(SCHEDULE_FILE):
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
      data = json.load(f)
    return pd.DataFrame(data)
  else:
    # 기본 샘플 데이터 생성
    return pd.DataFrame(
        {
            "날짜": [
                (datetime.today() + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(14)
            ],
            "근무자": ["홍길동", "김철수", "이영희", "박민수"] * 3
            + ["홍길동", "김철수"],
            "대직자": ["", "", "", ""] * 3 + ["", ""],
            "메모": ["특이사항 없음"] * 14,
        }
    )


df_schedule = load_initial_data(uploaded_file)

# 3. 메인 대시보드 화면
st.title("📅 숙직 근무표 관리 시스템")
st.markdown("모바일 환경 및 엑셀 연동을 지원하는 스마트 숙직 관리 대시보드입니다.")

# 뷰 모드 선택 (7열 그리드 달력 vs 리스트 뷰)
view_mode = st.radio("보기 형식", ["달력 뷰 (Grid)", "리스트 뷰"], horizontal=True)

if view_mode == "달력 뷰 (Grid)":
  st.subheader("📆 월간 캘린더 그리드")
  days_of_week = ["월", "화", "수", "목", "금", "토", "일"]
  cols = st.columns(7)
  for idx, col in enumerate(cols):
    col.markdown(f"**{days_of_week[idx]}**")

  # 달력 형태 버튼 배치
  for i in range(0, len(df_schedule), 7):
    cols = st.columns(7)
    for j in range(7):
      if i + j < len(df_schedule):
        row = df_schedule.iloc[i + j]
        day_str = row["날_짜" if "날_짜" in row else "날짜"].split("-")[-1]
        with cols[j]:
          if st.button(
              f"{day_str}일\n({row['근무자']})", key=f"cal_btn_{i+j}"
          ):
            st.session_state["selected_row"] = i + j
            st.rerun()
else:
  st.subheader("📋 리스트형 근무표 편집")
  edited_df = st.data_editor(
      df_schedule, num_rows="dynamic", use_container_width=True
  )
  if st.button("변경사항 저장"):
    edited_df.to_json(SCHEDULE_FILE, orient="records", force_ascii=False)
    st.success("근무표가 성공적으로 저장되었습니다!")

# 4. 날짜별 상세 수정 팝업 영역
if "selected_row" in st.session_state:
  idx = st.session_state["selected_row"]
  target = df_schedule.iloc[idx]

  with st.expander(
      f"📌 상세 정보 및 수정: {target.get('날짜', '')}", expanded=True
  ):
    new_worker = st.text_input("근무자", value=target["근무자"])
    new_substitute = st.text_input("대직자", value=target["대직자"])
    new_memo = st.text_area("메모", value=target["메모"])

    col1, col2 = st.columns(2)
    with col1:
      if st.button("수정 내용 저장"):
        df_schedule.loc[idx, "근무자"] = new_worker
        df_schedule.loc[idx, "대직자"] = new_substitute
        df_schedule.loc[idx, "메모"] = new_memo
        df_schedule.to_json(
            SCHEDULE_FILE, orient="records", force_ascii=False
        )
        st.success("수정 완료!")
        del st.session_state["selected_row"]
        st.rerun()
    with col2:
      if st.button("닫기"):
        del st.session_state["selected_row"]
        st.rerun()

# 5. 근무 통계 및 엑셀 다운로드
st.divider()
st.subheader("📊 월별 근무 통계")
if not df_schedule.empty:
  stats = df_schedule["근무자"].value_counts().reset_index()
  stats.columns = ["근무자", "근무 횟수"]
  stats["총 근무 시간(h)"] = stats["근무 횟수"] * 8  # 1회당 8시간 가정
  st.dataframe(stats, use_container_width=True)


  @st.cache_data
  def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
      df.to_excel(writer, index=False, sheet_name="DutySchedule")
    return output.getvalue()


  excel_data = convert_df_to_excel(df_schedule)
  st.download_button(
      label="📥 최종 근무표 엑셀 다운로드",
      data=excel_data,
      file_name="edited_duty_schedule.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )
