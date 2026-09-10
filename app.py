 캘린더 가져오기
 날짜 및 시간을 가져옵니다 .
 글로브 가져오기
 io를 가져옵니다
 JSON 가져오기
 os를 가져옵니다
가져오기  요청
 pandas를  pd 로  가져옵니다 .
 Streamlit을  st 로  가져옵니다.
 streamlit.components.v1 을 components 로 가져  옵니다 .​ 
# 대한민국 공휴일 이벤트 처리
노력하다 :
    수입  휴일
    kr_holidays  =  holidays.KR ( )​
 ImportError 제외 :
    kr_holidays  = {}
# DATA 및 데이터 기본 폴더를 생성했습니다.
os.makedirs ( " DATA " , exist_ok = True )
os.makedirs ( " data " , exist_ok = True )
PERSISTENCE_STATE_PATH  =  os.path.join ( " DATA " , " edited_duty_schedule.json " )
CONFIG_PATH  =  os.path.join ( " DATA " , " local_config.json " )
# ---------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config (​​
    page_title = "숙직 근무테이블 대시보드" ,
    페이지 아이콘 = "📋" ,
    레이아웃 = "넓음" ,
    initial_sidebar_state = "확장됨" ,
)
# ---------------------------------------------------------
# 1. 하드웨어/기기 개별 설정 저장 및 로드 웹 방지(공유 웹 방지)
# ---------------------------------------------------------
def  load_local_config ():
    default_config  = {
        "auto_view_type" : " 📄 세로형리스트 " ,
        "auto_view_type" : " 🗓️ 가로형 Grid " ,
        "app_theme" : "☀️ 화이트 테마" ,
        "kakao_api_key" : "" ,
    }
@@ -89,7 +89,7 @@ def save_local_config(key, value):
    st . 정지 ()

# ---------------------------------------------------------
# 뒤섞인 CSS ( 테마별 스타일 & 모바일 7열 자동 화면 맞춤 및 줄바꿈 )
# 움직이고 있는 CSS (모바일 7열에 독점적으로 자리잡고 )
# ---------------------------------------------------------
is_dark  =  st . 세션_상태 . app_theme  ==  "🌙 블랙 테마"

@@ -109,6 +109,7 @@ def save_local_config(key, value):

responsive_css  =  f"""
<스타일>
    /* 기본적으로 본체 및 건설 최적화 */
    html, 본문, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: { theme_bg } !important;
        색상: { main_text_color } !중요;
@@ -117,11 +118,15 @@ def save_local_config(key, value):
        overflow-x: 숨김 !중요;
    }}
    /* 메인 여백 극소화(모바일 화면 전체 활용) */
    .main .block-container {{
        background-color: { theme_bg } !important;
        색상: { main_text_color } !중요;
        패딩: 0.5rem 0.2rem !중요;
        최대 너비: 100% !중요;
        padding-left: 2px !important;
        padding-right: 2px !important;
        padding-top: 0.5rem !중요;
        padding-bottom: 1rem !important;
        최대 너비: 100vw !중요;
        너비: 100% !중요;
        박스 크기 조정: border-box !important;
    }}
@@ -130,7 +135,7 @@ def save_local_config(key, value):
        background-color: { sidebar_bg } !important;
        색상: { main_text_color } !중요;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] 범위, [data-testid="stSidebar"] 라벨 , [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] 범위, [data-testid="stSidebar"] 라벨 {{
        색상: { main_text_color } !중요;
    }}
@@ -140,28 +145,27 @@ def save_local_config(key, value):
    .월 헤더 카드 {{
        background: {  "linear-gradient(135deg, #1E293B 0%, #0F172A 100%)"  if  is_dark  else  "linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%)"  } ;
        border: 2px solid { border_color } ;
        테두리 반경: 12px ;
        패딩: 10px 15px ;
        상단 여백: 5px ;
        하단 여백: 10px ;
        테두리: 1px 솔리드 { 테두리 색상 } ;
        테두리 반경: 8px ;
        패딩: 6px 10px ;
        상단 여백: 2px ;
        margin-bottom: 6px ;
        텍스트 정렬: 가운데 정렬;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    .month-header-card h2 {{
        여백: 0 !중요;
        글꼴 크기: clamp( 18px, 4vw, 26px ) !important;
        글꼴 크기: clamp( 16px, 3.8vw, 22px ) !important;
        글꼴 두께: 800 !중요;
        색상: { "#60A5FA"  (어두우 면  ) 그렇지 않으면 "#2563EB" }   !중요;
    }}
    .오늘의카드 {{
        background: {  "linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%)"  if  is_dark  else  "linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%)"  } ;
        색상: { is_dark 이면 "white" ,  그렇지 않으면 "#0F172A" }    ;
        패딩: 10px 14px ;
        테두리 반경: 10px ;
        패딩: 8px 10px ;
        테두리 반경: 8px ;
        테두리: 1px 솔리드 { 테두리 색상 } ;
        하단 여백: 10px ;
        하단 여백: 8px ;
        너비: 100%;
        박스 크기 조정: 테두리 박스;
    }}
@@ -171,42 +175,70 @@ def save_local_config(key, value):
        글꼴 두께: 굵게;
    }}
    /* 버튼 스타일 및 줄바꿈 처리 */
    /* 🚨 모바일 세로 7열 전체에 완벽한 차는 셀 버튼 스타일 */
    .stButton > 버튼 {{
        너비: 100% !중요;
        최소 너비: 0 !중요;
        높이: 자동 !중요;
        최소 높이: 42px !중요;
        패딩: 4px 1px !중요;
        최소 높이: 52px !중요;
        패딩: 3px 1px !중요;
        border: 1px solid { border_color } !important;
        테두리 반경: 6px !중요;
        테두리 반경: 4px !중요;
        배경색: { btn_bg } !중요;
        색상: { btn_text } !중요;
        박스 크기 조정: border-box !important;
        텍스트 정렬: 가운데 정렬 !중요;
        글꼴 크기: clamp( 8px , 2.2vw, 12px ) !important;
        글꼴 크기: clamp( 7px , 2.0vw, 11px ) !important;
        글꼴 두께: 500 !중요;
        margin -bottom: 2px !important;
        여백 : 0 !중요;
        공백: 미리 줄 바꿈 !중요;
        단어 구분: 모두 끊기 !중요;
        overflow-wrap: 어디에서든 !important;
        줄 높이: 1.2 !중요;
        전환: 모든 0.2초 완화 !중요;
        줄 높이: 1.15 !중요;
    }}
    .stButton > 버튼:호버 {{
        border-color: { btn_hover_border } !important;
        background-color: { btn_hover_bg } !important;
        색상: { btn_text } !중요;
    }}
    /* 🚨 7개 방향을 전환하는 방향으로 반대(스크롤 대응 금지) */
    [data-testid="stHorizontalBlock"] {{
        표시: flex !important;
        flex-direction: 행 !important;
        flex-wrap: nowrap !important;
        너비: 100% !중요;
        최대 너비: 100% !중요;
        최소 너비: 0 !중요;
        간격: 1px !중요;
        여백: 0 !중요;
    }}
    [data-testid="column"] {{
        너비: 14.285% !중요;
        최대 너비: 14.285% !중요;
        최소 너비: 0 !중요;
        플렉스: 1 1 14.285% !중요;
        패딩: 0px 0px !중요;
        여백: 0 !중요;
        박스 크기 조정: border-box !important;
    }}
    [data-testid="stElementContainer"] {{
        너비: 100% !중요;
        여백: 0 !중요;
        패딩: 0 !중요;
    }}
    /* 팝업 스타일 */
    [data-testid="stDialog"] > div:first-child {{
        배경색: { dialog_bg } !important;
        색상: { main_text_color } !중요;
        너비: clamp( 300px , 92vw, 680px ) !important;
        너비: clamp( 290px , 92vw, 600px ) !important;
        최대 너비: 95vw !중요;
        최대 높이: 88vh !중요;
        테두리 반경: 12px !important;
        패딩: 1.2rem !중요;
        패딩: 1rem !중요;
        overflow-y: 자동 !중요;
        border: 1px solid { border_color } !important;
    }}
@@ -217,24 +249,7 @@ def save_local_config(key, value):
        테두리 색상: { border_color } !중요;
    }}
    /* 🚨 세로 화면 크기 축소 및 7열 가로 매트릭스 고정(스크롤 없이 화면 내부 표출) */
    [data-testid="stHorizontalBlock"] {{
        표시: flex !important;
        flex-direction: 행 !important;
        flex-wrap: nowrap !important;
        너비: 100% !중요;
        최소 너비: 0 !중요;
        간격: 2px !중요;
    }}
    [data-testid="column"] {{
        너비: 14.28% !중요;
        최소 너비: 0 !중요;
        플렉스: 1 1 0% !중요;
        패딩: 0 !중요;
    }}
    /* JS용 버튼 완전 컴팩트 */
    /* JS 히든스 버튼 은닉 */
    .swipe-hidden-container {{
        표시: 없음 !중요;
        높이: 0px !중요;
@@ -243,7 +258,6 @@ def save_local_config(key, value):
        패딩: 0px !중요;
        위치: 절대적 !중요;
        왼쪽: -9999px !중요;
        오버플로: 숨김 !중요;
    }}
</style>
"""
@@ -259,7 +273,7 @@ def save_local_config(key, value):
        const doc = window.parent.document;
        (!doc)이면 반환;
        // 1. 완전 숨김 버튼 처리
        // 1. 숨은 버튼 숨김
        const buttons = Array.from(doc.querySelectorAll('button'));
        buttons.forEach(btn => {
            const txt = btn.innerText || '';
@@ -268,14 +282,10 @@ def save_local_config(key, value):
                컨테이너인 경우 {
                    컨테이너.스타일.setProperty('display', 'none', 'important');
                    컨테이너.스타일.setProperty('높이', '0px', '중요');
                    컨테이너.스타일.setProperty('여백', '0px', '중요');
                    컨테이너.스타일.setProperty('padding', '0px', 'important');
                } 또 다른 {
                    btn.style.setProperty('display', 'none', 'important');
                }
            }
            // 2. 오늘 날짜를 알리고 스타일을 적용합니다.
            // 2. 오늘 날짜에 대한 강조 스타일
            만약 txt 파일에 '🌟'이 포함되어 있거나 '[오늘]'이 포함되어 있다면 {
                btn.style.setProperty('background', 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', 'important');
                btn.style.setProperty('color', '#FFFFFF', 'important');
@@ -284,20 +294,29 @@ def save_local_config(key, value):
            }
        });
        // 3. 7열의 위치(stHorizontalBlock)에 100% 위임 (화면 맞춤 )
        // 3. 7개의 방향 100% 거대 반란군 (모바일 스크롤 반대 )
        const horizBlocks = doc.querySelectorAll('[data-testid="stHorizontalBlock"]');
        horizBlocks.forEach(block => {
            블록의 자식 블록 길이가 7개이면
                block.style.setProperty('display', 'flex', 'important');
                block.style.setProperty('flex-direction', 'row', 'important');
                block.style.setProperty('flex-wrap', 'nowrap', 'important');
                block.style.setProperty('width', '100%', 'important');
                block.style.setProperty('min-width', '0px', 'important');
                block.style.setProperty('max-width', '100%', 'important');
                block.style.setProperty('gap', '1px', 'important');
                Array.from(block.children).forEach(child => {
                    child.style.setProperty('width', '14.285%', 'important');
                    child.style.setProperty('max-width', '14.285%', 'important');
                    child.style.setProperty('min-width', '0px', 'important');
                    child.style.setProperty('flex', '1 1 14.285%', 'important');
                    child.style.setProperty('padding', '0px', 'important');
                });
            }
        });
    }
    // 터치스 이벤트
    // 터치 하세요
    touchstartX = 0, touchstartY = 0, touchendX = 0, touchendY = 0으로 설정합니다.
    함수 triggerMonthChange(dir) {
        const doc = window.parent.document;
@@ -681,13 +700,11 @@ def get_all_workers_list(df):


# ---------------------------------------------------------
# 시계 기록 정의 (팝업 유지 세션 관리)
#시계로그 정의
# ---------------------------------------------------------
@ 성 . 대화상자 ( "⚠️ 프로그램 종료 확인" )
def  confirm_exit_dialog ():
    성 . 쓰기 ( "정말로 숙직 근무 시스템을 종료하는 사용자?" )
    성 . write ( "종료 시실행 세션이 정지됩니다." )

    col_e1 , col_e2  =  st.columns ( 2 )​​
     col_e1 과 함께 :
         st.button ( "❌ 취소" , use_container_width = True ) 인 경우 :
@@ -712,8 +729,8 @@ def settings_dialog():
        성 . markdown ( "**:blue[1. 현재 표시 방식 선택]**" )
        new_view_type  =  st.radio (​​
            "달력 표출 형식" ,
            options = [ " 📄 세로형리스트 " , " 🗓️ 가로형 그리드 " ],
            st 인 경우 인덱스 = 0  입니다 . 세션_상태 . auto_view_type == " 📄 세로형리스트 " else 1 ,     
            options = [ " 🗓️ 가로형 그리드 " , " 📄 세로형리스트 " ],
            st.session_state.auto_view_type 이 " 🗓️ 가로형 Grid " 인 경우 index = 0  , 그렇지 않으면 1 ,     
            키 = "cfg_view_type_radio" ,
        )

@@ -726,32 +743,25 @@ def settings_dialog():
            키 = "cfg_theme_radio" ,
        )

        성 . caption ( "💡 예외 화면 방식 시스템은 하드웨어(사용자 기기)에 저장되어 이후 인터페이스 시에도 유지됩니다." )

        만약  st . 버튼 ( "💾 설정 설정 적용하기" , use_container_width = True , type = "primary" ):
            st.session_state.auto_view_type = new_view_type​​​​  
            st.session_state.app_theme = new_theme​​​​  
            save_local_config ( "auto_view_type" , new_view_type )
            save_local_config ( "앱 테마" , 새 테마 )
            st.session_state.show_settings_dialog = False​​​​  
            성 . 성공 ( "✅ 화면 설정이 이 기기에 저장되었습니다." )
            성 . 성공 ( "✅ 화면 설정이 저장되었습니다." )
            st.rerun ( )​

     tab_s2 와 함께 :
        성 . markdown ( "📅 **입력되는 작업자만 규칙적으로 협의할 수 있으며, 비워둔 터널은 원시 데이터를 유지합니다.**" )

        성 . markdown ( "📅 **입력된 작업자만 규칙적으로 협력 등록됩니다.**" )
        today_default  =  datetime.date.today ( )​​​
        saved_pat  =  st.session_state.get ( " batch_patterns " , { } )

        col_b1 , col_b2  =  st.columns ( 2 )​​
         col_b1 과 함께 :
            start_date_input  =  st.date_input (​​
                "시작 날짜" , 값 = today_default , 키 = "dlg_batch_start"
            )
            start_date_input  =  st.date_input ( "시작 날짜" , value = today_default , key = " dlg_batch_start " )
         col_b2 와 함께 :
            total_days_count  =  st.number_input (​​
                "적용 총 일수" , min_value = 1 , max_value = 180 , value = 30 , step = 1 , key = "dlg_batch_days"
            )
            total_days_count  =  일 . number_input ( "적용 총 일수" , min_value = 1 , max_value = 180 , value = 30 , step = 1 , key = "dlg_batch_days" )

        col_p1 , col_p2  =  st.columns ( 2 )​​
         col_p1 과 함께 :
@@ -800,18 +810,12 @@ def settings_dialog():
            st.session_state.df = df​​​​  
            save_app_state ( df , st.session_state.selected_sheet , st.session_state.memos , st.session_state.batch_patterns )​​​​​​​​​​​​
            st.session_state.show_settings_dialog = False​​​​  
            성 . 성공 ( "✅ 협력 반복 패턴이 저장되고 적용되었습니다 ." )
            성 . 성공 ( "✅ 협력 반복 패턴이 있었습니다 ." )
            st.rerun ( )​

     tab_s3 포함 :
        성 . markdown ( "📱 **오늘 또는 휴가 배우자의 숙직에 인사합니다.**" )

        kakao_key  =  st.text_input (​​
            "카카오 REST API 키(또는 Access Token)" ,
            값 = st.session_state.kakao_api_key ,​​​​
            type = "비밀번호" ,
            키 = "카카오 키 입력" ,
        )
        성 . markdown ( "📱 **카카오톡현재 페이지 설정**" )
        kakao_key  =  st.text_input ( " 카카오 REST API 키 " , value = st.session_state.kakao_api_key , type = " password " , key = " kakao_key_input " )
         kakao_key  가  st.session_state.kakao_api_key 와 같지 않으면​​​
            st.session_state.kakao_api_key = kakao_key​​​​  
            save_local_config ( "kakao_api_key" , kakao_key )
@@ -827,42 +831,27 @@ def settings_dialog():
            memo  =  st.session_state.memos.get ( send_date.strftime ( " % Y- % m- %d " ) , " 없음 " )
            msg_content  =  f"📢 [ { send_date . strftime ( '%Y-%m-%d' ) } 숙직근무 안내] \n - 일하는자 1: { p1 } \n - 일하는자 2: { p2 } \n - 메모: { memo } "
        또 다른 :
            msg_content  =  f"📢 [ { send_date . strftime ( '%Y-%m-%d' ) } 숙직근무 안내] \n 해당 날짜의 저 정보가 등록되어 있었습니다."

        성 . text_area ( "전송예정일 미리보기" , 값 = msg_content , 높이 = 110 )

        col_k1 , col_k2  =  st.columns ( 2 )​​
         col_k1 과 함께 :
            만약  st . 버튼 ( "💬 나에게 카카오톡 전송" , use_container_width = True , 유형 = "기본" ):
                 카카오키 가  아니면 :
                    성 . warning ( "⚠️ 카카오 API 키 또는 Access Token을 입력해주세요." )
                또 다른 :
                    노력하다 :
                        헤더  = { "인증" : f"베어러 { 카카오키 } " }
                        페이로드  = {
                            "template_object" : json . dumps ({
                                "object_type" : "text" ,
                                "텍스트" : msg_content ,
                                "link" : { "web_url" : "https://streamlit.io" , "mobile_web_url" : "https://streamlit.io" },
                            })
                        }
                        res  =  requests.post ( " https://kapi.kakao.com/v2/api/talk/memo/default/send " , headers = headers , data = payload )
                         res.status_code 가 200 이면 :​​  
                            성 . 성공 ( "✅ 카카오톡 메시지 전송 성공!" )
                        또 다른 :
                            성 . error ( f"❌ 전송 실패 (코드: { res . status_code } ): { res . text } " )
                     예외  를  제외 합니다 .
                        성 . 오류 ( f"전송 오류 오류: { ex } " )
         col_k2 와 함께 :
            encoded_msg  =  requests.utils.quote ( msg_content )​​​​
            st . 마크다운 (
                f' <a href="https://sharer.kakao.com/talk/friends/picker/easylink?app_key=sample&message= { encoded_msg } " target="_blank"> <button style="width:100%; min-height:48px; border-radius:8px; background-color:#FEE500; color:#000; font-weight:bold; border:none; cursor:pointer;">💛 카카오톡 외부 공유창 열기</button></a>' ,
                unsafe_allow_html = True ,
            )
            msg_content  =  f"📢 [ { send_date . strftime ( '%Y-%m-%d' ) } 숙직근무 안내] \n 해당 날짜의 근무 정보가 없습니다."

        성 . text_area ( "미리보기" , 값 = msg_content , 높이 = 100 )
        만약  st . 버튼 ( "💬 나에게 카카오톡 전송" , use_container_width = True , 유형 = "기본" ):
             카카오키 가  아니면 :
                성 . 경고 ( "⚠️ API 키를 입력해주세요." )
            또 다른 :
                노력하다 :
                    헤더  = { "인증" : f"베어러 { 카카오키 } " }
                    payload  = { "template_object" : json . dumps ({ "object_type" : "text" , "text" : msg_content , "link" : { "web_url" : "https://streamlit.io" }})}
                    res  =  requests.post ( " https://kapi.kakao.com/v2/api/talk/memo/default/send " , headers = headers , data = payload )
                     res.status_code 가 200 이면 :​​  
                        성 . 성공 ( "✅ 전송 성공!" )
                    또 다른 :
                        성 . error ( f"❌ 전송 실패 ( { res . status_code } ): { res . text } " )
                 예외  를  제외 합니다 .
                    성 . error ( f"오류발생: { ex } " )


# ---------------------------------------------------------
# 날짜별 시계 기록 (날짜별 동적 키 날짜)
# 작동자 시간 기록
# ---------------------------------------------------------
@ 성 . 대화 상자 ( "✏️ 근무자 수정 및 메모 작성" )
def  edit_worker_dialog ( date_str , duty_info ):
@@ -911,13 +900,13 @@ def get_opt_idx(val):
            sub2_custom  =  st . text_input ( "대직자2 직접입력" , value = val_sub2  if  sub2_sel  ==  "(직접입력)"  else  "" , key = f"sub2_custom_ { date_str } " ) if  sub2_sel  ==  "(직접입력)"  else  ""

        st . 구분자 ()
        edit_memo  =  st . text_area ( "your 데이트별 메모 (달력 표출)" , value = current_memo , height = 80 , key = f"edit_memo_ { date_str } " )
        edit_memo  =  st . text_area ( "date별 메모 (달력 표출)" , value = current_memo , height = 70 , key = f"edit_memo_ { date_str } " )

        c_sub1 , c_sub2  =  st.columns ( [ 2 , 1 ] )
         c_sub1 과 함께 :
            제출됨  =  st . form_submit_button ( "💾 공격 저장 및 공격" , use_container_width = True )
            제출됨  =  st . form_submit_button ( "💾 저장 및 복원" , use_container_width = True )
         c_sub2 와 함께 :
            close_dialog  =  st.form_submit_button ( " 🚪 창 닫기 " , use_container_width = True )
            close_dialog  =  st.form_submit_button ( " 🚪 닫기" , use_container_width = True )

         제출된 경우 :
            final_p1  =  p1_custom . Strip () if  p1_sel  ==  "(직접 입력)"  else ( ""  if  p1_sel  ==  "(선택 안함)"  else  p1_sel )
@@ -939,7 +928,7 @@ def get_opt_idx(val):
            st.session_state.df = st.session_state.df.sort_values ( by = " 날짜 " ) .reset_index ( drop = True )​​​​​​​​  

            save_app_state ( st.session_state.df , st.session_state.selected_sheet , st.session_state.memos , st.session_state.batch_patterns )​​​​​​​​​​​​​​​​
            성 . 성공 ( "✅ 변경사항이 저장되었습니다." )
            성 . 성공 ( "✅저장했습니다." )
            st.rerun ( )​

         close_dialog 인 경우 :
@@ -951,12 +940,10 @@ def get_opt_idx(val):
# ---------------------------------------------------------
 st . 사이드바 포함 :
    성 . 헤더 ( "📂 작업표 파일 관리" )

     st.session_state 에 "file_name"  이 있는 경우 : 
        성 . info ( f"📄 현재 파일: ` { st . session_state . file_name } `" )

    Upload_file  =  st . file_uploader ( "새 공격 파일 업로드" , type = [ "xlsx" ])
        st.info ( f " 📄 파일 : ` { st.session_state.file_name } ` " )

    Upload_file  =  st . file_uploader ( "새로 몰려오는 공격" , type = [ "xlsx" ])
     uploaded_file  이 None 이   아니면 :
        file_bytes  =  uploaded_file.getvalue ( )​
        save_path  =  os.path.join ( " DATA " , uploaded_file.name )​​​​
@@ -974,13 +961,12 @@ def get_opt_idx(val):
        st.session_state.raw_df = raw_df​​​​  

        save_app_state ( parsed_df , used_sheet , st.session_state.get ( " memos" , {}) , st.session_state.get ( " batch_patterns " , { } ) )

        성 . 성공 ( f"✅ ' { Used_sheet } ' 데이터 로드 ●" )
        성 . 성공 ( "✅ 파일 로드하기" )
        st.rerun ( )​

     st.session_state 에 "  file_bytes " 가 있고 st.session_state.file_bytes 가 있는 경우 :​   
        st . 다운로드_버튼 (
            label = "📥 수정된 파일 다운로드" ,
            label = "📥 파일 다운로드" ,
            데이터 = st.session_state.file_bytes ,​​​​
            파일명 = st . 세션_상태 . get ( "file_name" , "숙직근무표_수정본.xlsx" ),
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ,
@@ -992,17 +978,12 @@ def get_opt_idx(val):
        st.session_state.show_exit_dialog = True​​​​  
        st.rerun ( )​


# ---------------------------------------------------------
#개의 세션 기반 시계 로그 호출 처리
# ---------------------------------------------------------
 세션 상태의 설정 대화 상자 가 표시 되면
    설정 대화 상자 ()

 세션 상태 가 종료 대화 상자를 표시 하는 경우 :
    confirm_exit_dialog ()


df  =  st.session_state.df​​​​
오늘  =  날짜 . 날짜 . 오늘 ()

@@ -1030,16 +1011,15 @@ def get_opt_idx(val):
        p1  =  f" { t_row [ '실제근무1' ] } (대)"  if  pd . notnull ( t_row . get ( "대직1" )) 및  str ( t_row . get ( "대직1" )). Strip () else  t_row [ "실제근무1" ]
        p2  =  f" { t_row [ '실제근무2' ] } (대)"  if  pd . notnull ( t_row . get ( "대직2" )) 및  str ( t_row . get ( "대직2" )). Strip () else  t_row [ "실제근무2" ]
        t_memo  =  st.session_state.memos.get ( today.strftime ( " % Y-%m- % d " ) ) , " " )
        memo_str  =  f" | pine 메모: { t_memo } "  if  t_memo  else  ""
        memo_str  =  f" | 📌 { t_memo } "  if  t_memo  else  ""

        st . 마크다운 (
            에프"""
        <div class="today-card">
            <div style="font-size:12px; opacity:0.9; margin-bottom:2px;">🚨 오늘의 숙직 근무자 ( { today_str } )</div>
            <div style="font-size:14px; font-weight:bold;">
                근무자 1: <span> { p1 } </span>  | 
                근무자 2: <span> { p2 } </span>
                <span style="font-size:12px; font-weight:normal;"> { memo_str } </span>
            <div style="font-size:11px; opacity:0.9;">🚨 오늘 일하는자 ( { today_str } )</div>
            <div style="font-size:13px; font-weight:bold;">
                1: <스팬> { p1 } </span> | 2: <스팬> { p2 } </span>
                <span style="font-size:11px; font-weight:normal;"> { memo_str } </span>
            </div>
        </div>
        """ ,
@@ -1134,8 +1114,6 @@ def go_next_month():
                "p2_display" : p2_display ,
            }

        성 . caption ( "💡 각 날짜 항목을 클릭하면 작동자 수정 및 메모 작성이 가능하며, 저장할 수 있도록 달을 이동할 수 있습니다." )

        calendar_view_type  =  st.session_state.auto_view_type​​​​

        if  Calendar_view_type  ==  "📄 세로형리스트" :
@@ -1169,7 +1147,7 @@ def go_next_month():
                     duty_info 인 경우 :
                        edit_worker_dialog ( date_str , duty_info )
        또 다른 :
            # 🗓️ 화면에 100% 회전하는 방식 과 스크롤 없이 7열 표출 + 자동 줄바꿈을 위한
            # 🗓️ [요청 반대] 이동식 7열 세로 에 가로 손잡이 배치
            cols_header  =  st.columns ( 7 )​​
            color_sun  =  "#FF6B6B"  if  is_dark  else  "#DC2626"
            색상 채도  =  "#38BDF8"  (어두우 면  ) 그렇지 않으면 "#2563EB"  
@@ -1182,11 +1160,10 @@ def go_next_month():

             enumerate ( headers ) 의 idx , ( h_name , color ) 에 대해 : 
                cols_header [ idx ]. 마크다운 (
                    f"<div style='text-align: center; color: { color } ; font-weight: bold; font-size: clamp( 11px , 2. 3vw, 14px ); padding-bottom: 2px;'> { h_name } </div>" ,
                    f"<div style='text-align: center; color: { color } ; font-weight: bold; font-size: clamp( 10px , 2. 2vw, 13px ); padding-bottom: 2px;'> { h_name } </div>" ,
                    unsafe_allow_html = True ,
                )

            st.markdown ( "< div style = 'margin-bottom: 4px;'></div>" , unsafe_allow_html = True )
            first_day_weekday  =  calendar.monthrange ( year , month ) [ 0 ]​
            start_offset  = ( first_day_weekday  +  1 ) %  7
            일수 카운터  =  1
@@ -1211,7 +1188,12 @@ def go_next_month():
                        is_today  = ( curr_date  ==  today )
                        day_label  =  f"🌟 { day_counter } 일"  if  is_today  else  f" { day_counter } 일"

                        btn_text  =  f" { day_label } \n { p1_txt } \n { p2_txt } \n 📌 { day_memo } "  if  day_memo  else  f" { day_label } \n { p1_txt } \n { p2_txt } "
                        # 🚨 [요청에 대하여] 1줄: 데이트 / 2줄: 실제근무자1 / 3줄: 실제근무자2 / 4줄: 메모
                        cell_lines  = [ day_label , p1_txt , p2_txt ]
                         day_memo 인 경우 :
                            cell_lines.append ( f " 📌 { day_memo } " )

                        btn_text  =  " \n " . join ( cell_lines )

                         grid_cols [ c ] .button ( btn_text , key = f"btn_grid_card_ { date_str } " ) 인 경우 :
                             duty_info 인 경우 :
@@ -1260,7 +1242,7 @@ def go_next_month():
        st.session_state.df = full_df [ cols ]​​​​  

        save_app_state ( st.session_state.df , st.session_state.selected_sheet , st.session_state.memos , st.session_state.batch_patterns )​​​​​​​​​​​​​​​​
        성 . 성공 ( "✅ 파일 및 대시보드에 저장되었습니다." )
        성 . 성공 ( "✅저장했습니다." )
        st.rerun ( )​

# ---------------------------------------------------------
