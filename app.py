import os
import io
import json
import calendar
import datetime
import requests
import pandas as pd
from pathlib import Path
import streamlit as int_streamlit  # 네임스페이스 충돌 방지용 별칭
import streamlit as st

try:
    import holidays
    kr_holidays = holidays.KR()
except ImportError:
    kr_holidays = {}

# 페이지 설정 (모바일 최적화 레이아웃)
st.set_page_config(
    page_title="광주교도소 의료과 숙직근무",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 데이터 및 설정 경로
DATA_DIR = Path("DATA")
DATA_DIR.mkdir(exist_ok=True)
CONFIG_PATH = DATA_DIR / "local_config.json"
EXCEL_PATH = DATA_DIR / "edited_duty_schedule.xlsx"
STATE_PATH = DATA_DIR / "edited_duty_schedule.json"

def load_config():
    default_cfg = {
        "app_theme": "light",
        "kakao_access_token": "",
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                default_cfg.update(json.load(f))
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_memos():
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("memos", {})
        except Exception:
            pass
    return {}

def save_memos(memos):
    data = {"memos": memos, "last_saved": str(datetime.datetime.now())}
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_duty_df():
    if EXCEL_PATH.exists():
        df = pd.read_excel(EXCEL_PATH)
        df["날짜"] = pd.to_datetime(df["날짜"])
        return df
    
    dates = pd.date_range(start=datetime.date.today().replace(day=1), periods=90, freq="D")
    df = pd.DataFrame({
        "날짜": dates,
        "근무자1": "미지정", "대직1": None,
        "근무자2": "미지정", "대직2": None,
        "실제근무1": "미지정", "실제근무2": "미지정",
        "M열구분": "", "년월": dates.strftime("%Y-%m")
    })
    save_duty_df(df)
    return df

def save_duty_df(df):
    df.to_excel(EXCEL_PATH, index=False)

# 상태 초기화
if "config" not in st.session_state:
    st.session_state.config = load_config()
if "memos" not in st.session_state:
    st.session_state.memos = load_memos()

# 메인 타이틀
st.title("🏥 광주교도소 의료과 숙직")

# 상단 탭 구성 (모바일 터치 친화적)
tab_cal, tab_stats, tab_edit, tab_kakao, tab_setting = st.tabs(["📅 달력", "📊 통계", "✏️ 수정/입력", "💬 알림", "⚙️ 설정"])

df = get_duty_df()
today_str = str(datetime.date.today())
current_ym = datetime.date.today().strftime("%Y-%m")

# 1. 달력 뷰 탭
with tab_cal:
    st.subheader("근무 일정표")
    
    # 월 선택
    months = sorted(df["년월"].dropna().unique().tolist())
    selected_ym = st.selectbox("조회할 년월 선택", months, index=months.index(current_ym) if current_ym in months else 0)
    
    sub_df = df[df["년월"] == selected_ym]
    
    # 오늘 근무 요약 배너
    today_row = df[df["날짜"].dt.strftime("%Y-%m-%d") == today_str]
    if not today_row.empty:
        r = today_row.iloc[0]
        r1 = r["대직1"] if pd.notnull(r["대직1"]) and str(r["대직1"]) not in ["nan", "None", ""] else r["근무자1"]
        r2 = r["대직2"] if pd.notnull(r["대직2"]) and str(r["대직2"]) not in ["nan", "None", ""] else r["근무자2"]
        m_val = st.session_state.memos.get(today_str, "")
        st.info(f"**📌 오늘 ({today_str}) 근무**\n\n- 1근무: **{r1}** | 2근무: **{r2}**" + (f" | 메모: {m_val}" if m_val else ""))

    st.markdown("---")
    
    # 날짜별 카드 리스트 형태 출력 (모바일에서 보기에 가장 직관적)
    for _, row in sub_df.iterrows():
        d_str = row["날짜"].strftime("%Y-%m-%d")
        c_date = row["날짜"].date()
        w_idx = c_date.weekday()
        
        is_holiday = c_date in kr_holidays
        is_sat = (w_idx == 5)
        is_sun = (w_idx == 6)
        
        p1 = str(row.get("근무자1", "미지정"))
        p2 = str(row.get("근무자2", "미지정"))
        sub1 = str(row.get("대직1", "")) if pd.notnull(row.get("대직1")) else ""
        sub2 = str(row.get("대직2", "")) if pd.notnull(row.get("대직2")) else ""
        
        real1 = sub1 if sub1 and sub1 not in ["nan", "None"] else p1
        real2 = sub2 if sub2 and sub2 not in ["nan", "None"] else p2
        memo = st.session_state.memos.get(d_str, "")
        
        day_label = f"{d_str} ({['월','화','수','목','금','토','일'][w_idx]})"
        if is_sun or is_holiday:
            day_label = f"🔴 {day_label} [휴일]"
        elif is_sat:
            day_label = f"🔵 {day_label} [토요]"
            
        if d_str == today_str:
            day_label += " ⭐ [오늘]"

        with st.expander(f"{day_label} → 1: {real1} / 2: {real2}" + (" 📌" if memo else "")):
            st.write(f"- **원근무자**: 1계: {p1} | 2계: {p2}")
            if sub1 or sub2:
                st.write(f"- **대직자**: 1계: {sub1 or '없음'} | 2계: {sub2 or '없음'}")
            if memo:
                st.write(f"- **메모**: {memo}")

# 2. 통계 탭
with tab_stats:
    st.subheader("근무 시간 통계")
    stat_ym = st.selectbox("통계 기간 선택", ["all"] + months, key="stat_ym_select")
    
    f_df = df if stat_ym == "all" else df[df["년월"] == stat_ym]
    expanded = []
    duty_dates = set()
    
    for _, r in f_df.iterrows():
        c_date = r["날짜"].date()
        w_idx = c_date.weekday()
        is_holiday = c_date in kr_holidays
        is_weekend = (w_idx >= 5) or is_holiday
        hours = 15 if is_weekend else 7
        
        w1, w2 = str(r.get("실제근무1", "")).strip(), str(r.get("실제근무2", "")).strip()
        has_duty = False
        for w in [w1, w2]:
            if w and w not in ["미지정", "nan", "None"]:
                expanded.append({"worker": w, "hours": hours})
                has_duty = True
        if has_duty:
            duty_dates.add(c_date)
            
    if expanded:
        e_df = pd.DataFrame(expanded)
        summary = e_df.groupby("worker").agg(근무횟수=("hours", "count"), 총시간=("hours", "sum")).reset_index()
        summary = summary.sort_values(by="총시간", ascending=False)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("총 근무자 수", f"{len(summary)}명")
        col2.metric("총 근무 일수", f"{len(duty_dates)}일")
        col3.metric("총 근무 시간", f"{int(e_df['hours'].sum())}h")
        
        st.markdown("---")
        st.dataframe(summary, use_container_width=True)
        st.bar_chart(summary.set_index("worker")["총시간"])
    else:
        st.warning("표시할 근무 데이터가 없습니다.")

# 3. 수정/입력 탭
with tab_edit:
    st.subheader("개별 날짜 근무 수정")
    edit_date = st.date_input("수정할 날짜 선택", datetime.date.today())
    d_str_target = edit_date.strftime("%Y-%m-%d")
    
    target_row = df[df["날짜"].dt.strftime("%Y-%m-%d") == d_str_target]
    
    if not target_row.empty:
        r = target_row.iloc[0]
        curr_p1 = str(r.get("근무자1", "미지정"))
        curr_p2 = str(r.get("근무자2", "미지정"))
        curr_sub1 = str(r.get("대직1", "")) if pd.notnull(r.get("대직1")) else ""
        curr_sub2 = str(r.get("대직2", "")) if pd.notnull(r.get("대직2")) else ""
        curr_memo = st.session_state.memos.get(d_str_target, "")
        
        with st.form("edit_form"):
            new_p1 = st.text_input("근무자 1", value=curr_p1 if curr_p1 != "미지정" else "")
            new_sub1 = st.text_input("대직자 1 (선택)", value=curr_sub1 if curr_sub1 != "None" else "")
            new_p2 = st.text_input("근무자 2", value=curr_p2 if curr_p2 != "미지정" else "")
            new_sub2 = st.text_input("대직자 2 (선택)", value=curr_sub2 if curr_sub2 != "None" else "")
            new_memo = st.text_area("메모", value=curr_memo)
            
            submitted = st.form_submit_button("변경사항 저장")
            if submitted:
                idx = target_row.index[0]
                df.loc[idx, "근무자1"] = new_p1 if new_p1 else "미지정"
                df.loc[idx, "근무자2"] = new_p2 if new_p2 else "미지정"
                df.loc[idx, "대직1"] = new_sub1 if new_sub1 else None
                df.loc[idx, "대직2"] = new_sub2 if new_sub2 else None
                df.loc[idx, "실제근무1"] = new_sub1 if new_sub1 else (new_p1 if new_p1 else "미지정")
                df.loc[idx, "실제근무2"] = new_sub2 if new_sub2 else (new_p2 if new_p2 else "미지정")
                save_duty_df(df)
                
                if new_memo:
                    st.session_state.memos[d_str_target] = new_memo
                else:
                    st.session_state.memos.pop(d_str_target, None)
                save_memos(st.session_state.memos)
                
                st.success("성공적으로 수정되었습니다!")
                st.rerun()

# 4. 카카오 알림 탭
with tab_kakao:
    st.subheader("💬 카카오톡 나에게 보내기")
    kakao_token = st.text_input("카카오 액세스 토큰", value=st.session_state.config.get("kakao_access_token", ""), type="password")
    if kakao_token != st.session_state.config.get("kakao_access_token", ""):
        st.session_state.config["kakao_access_token"] = kakao_token
        save_config(st.session_state.config)
        
    msg_date = st.date_input("알림 대상 날짜", datetime.date.today(), key="kakao_date")
    m_str = msg_date.strftime("%Y-%m-%d")
    
    match_r = df[df["날짜"].dt.strftime("%Y-%m-%d") == m_str]
    default_msg = ""
    if not match_r.empty:
        r = match_r.iloc[0]
        r1 = r["실제근무1"] if pd.notnull(r["실제근무1"]) else "미지정"
        r2 = r["실제근무2"] if pd.notnull(r["실제근무2"]) else "미지정"
        default_msg = f"[광주교도소 의료과 숙직 안내]\n일자: {m_str}\n1근무: {r1}\n2근무: {r2}"
        
    kakao_msg = st.text_area("전송할 메시지 내용 (200자 이내)", value=default_msg, height=100)
    
    if st.button("카카오톡 메시지 전송"):
        if not kakao_token:
            st.error("카카오 액세스 토큰을 입력해주세요.")
        elif len(kakao_msg) > 200:
            st.error("메시지는 200자를 초과할 수 없습니다.")
        else:
            url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
            headers = {"Authorization": f"Bearer {kakao_token}", "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
            payload = {"template_object": json.dumps({"object_type": "text", "text": kakao_msg, "link": {"web_url": "https://developers.kakao.com"}})}
            
            try:
                resp = requests.post(url, headers=headers, data=payload, timeout=5)
                if resp.status_code == 200:
                    st.success("메시지가 성공적으로 전송되었습니다!")
                else:
                    st.error(f"전송 실패: {resp.text}")
            except Exception as e:
                st.error(f"오류 발생: {e}")

# 5. 설정 및 엑셀 다운로드/업로드 탭
with tab_setting:
    st.subheader("⚙️ 파일 관리 및 설정")
    
    # 엑셀 다운로드
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_download = df.copy()
        df_download["메모"] = df_download["날짜"].dt.strftime("%Y-%m-%d").map(lambda d: st.session_state.memos.get(d, ""))
        df_download.to_excel(writer, index=False, sheet_name="숙직근무자")
    output.seek(0)
    
    st.download_button(
        label="📥 엑셀 파일 다운로드",
        data=output,
        file_name="숙직근무표.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown("---")
    
    # 엑셀 업로드
    uploaded_file = st.file_uploader("📤 엑셀 파일 업로드 (기존 데이터 덮어쓰기)", type=["xlsx"])
    if uploaded_file is not None:
        try:
            new_df = pd.read_excel(uploaded_file)
            new_df["날짜"] = pd.to_datetime(new_df["날짜"])
            save_duty_df(new_df)
            st.success("엑셀 파일이 성공적으로 업로드 및 적용되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"파일 처리 중 오류가 발생했습니다: {e}")
