import json
import os
import pandas as pd
import streamlit as st

# 데이터베이스 파일 경로 설정
DB_PATH = 'data/workers_db.json'


def load_workers():
  """JSON 파일에서 등록된 근무자 데이터를 로드합니다."""
  if os.path.exists(DB_PATH):
    with open(DB_PATH, 'r', encoding='utf-8') as f:
      try:
        return json.load(f)
      except json.JSONDecodeError:
        return []
  return []


def save_workers(workers):
  """근무자 데이터를 JSON 파일에 저장합니다."""
  os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
  with open(DB_PATH, 'w', encoding='utf-8') as f:
    json.dump(workers, f, ensure_ascii=False, indent=4)


def main():
  st.title('📋 근무자 연락처 관리 시스템')

  # 1. 신규 근무자 등록 폼
  with st.form('worker_form'):
    st.subheader('신규 근무자 등록')
    name = st.text_input('성명')
    phone = st.text_input('휴대전화번호 (예: 010-1234-5678)')
    send_option = st.selectbox('발송 옵션', ['즉시 발송', '예약 발송'])
    send_time = st.time_input('발송 시간')
    consent = st.checkbox('문자 수신 동의 여부')

    submitted = st.form_submit_button('등록하기')
    if submitted:
      if name and phone:
        workers = load_workers()
        new_worker = {
            'name': name,
            'phone': phone,
            'send_option': send_option,
            'send_time': str(send_time),
            'consent': '동의' if consent else '미동의',
        }
        workers.append(new_worker)
        save_workers(workers)
        st.success(f'{name} 님의 정보가 성공적으로 등록되었습니다.')
      else:
        st.warning('성명과 휴대전화번호를 모두 입력해 주세요.')

  # 2. 등록된 근무자 연락처 리스트 표(Table) 출력
  st.subheader('등록된 근무자 연락처 리스트')
  workers = load_workers()

  if workers:
    # 데이터를 pandas DataFrame으로 변환하여 표 형태로 시각화
    df = pd.DataFrame(workers)
    df.columns = [
        '성명',
        '휴대전화번호',
        '발송 옵션',
        '발송 시간',
        '수신 동의 여부',
    ]

    # Streamlit 표 컴포넌트 사용 (가독성 향상 및 스크롤 지원)
    st.dataframe(df, use_container_width=True)

    # 3. 개별 근무자 정보 삭제 기능
    st.markdown('---')
    st.subheader('근무자 정보 관리')
    worker_names = [w['name'] for w in workers]
    selected_to_delete = st.selectbox('삭제할 근무자 선택', worker_names)

    if st.button('선택한 근무자 삭제'):
      workers = [w for w in workers if w['name'] != selected_to_delete]
      save_workers(workers)
      st.success(f'{selected_to_delete} 님의 정보가 삭제되었습니다.')
      st.rerun()
  else:
    st.info('현재 등록된 근무자가 없습니다. 상단에서 근무자를 등록해 주세요.')


if __name__ == '__main__':
  main()
