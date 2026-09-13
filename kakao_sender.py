import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests

app = FastAPI()

# ──────────────────────────────
# 설정 및 파일 경로 정의
# ──────────────────────────────
CONFIG_FILE = Path("config.yaml")
TOKEN_FILE = Path("data/kakao_tokens.json")
WORKERS_DB_FILE = Path("data/workers_db.json")

# 설정 파일 로드 (config.yaml이 있는 경우)
REST_API_KEY = ""
if CONFIG_FILE.exists():
    try:
        config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
        REST_API_KEY = config.get("kakao", {}).get("rest_api_key", "")
    except Exception as e:
        print(f"config.yaml 로드 중 오류 발생: {e}")


# ──────────────────────────────
# Pydantic 모델 정의
# ──────────────────────────────
class ConsentRequest(BaseModel):
    name: str
    phone: str
    consent_agreed: bool


# ──────────────────────────────
# 데이터 관리 함수 (토큰 및 근무자 DB)
# ──────────────────────────────
def load_tokens() -> dict:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    return {}

def save_tokens(tokens: dict):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2))

def refresh_access_token(refresh_token: str) -> Optional[str]:
    """리프레시 토큰으로 액세스 토큰 갱신"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": refresh_token
    }
    resp = requests.post(url, data=data)
    if resp.status_code == 200:
        new_tokens = resp.json()
        tokens = load_tokens()
        tokens["access_token"] = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            tokens["refresh_token"] = new_tokens["refresh_token"]
        save_tokens(tokens)
        return new_tokens["access_token"]
    return None

def get_valid_access_token(user_key: str) -> Optional[str]:
    """저장된 토큰 중 해당 유저의 유효한 액세스 토큰 반환 (만료 시 갱신 시도)"""
    tokens = load_tokens()
    user_token = tokens.get(user_key)
    if not user_token:
        return None
    
    access_token = user_token.get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    test_resp = requests.get(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send", 
        headers=headers, 
        data={"template_object": json.dumps({"object_type": "text", "text": "token_test", "link": {}})}
    )
    
    if test_resp.status_code == 200:
        return access_token
    elif test_resp.status_code == 401:  # 토큰 만료
        print(f"[{user_key}] Access Token 만료, 갱신 시도...")
        new_token = refresh_access_token(user_token.get("refresh_token"))
        return new_token
    return None

def load_workers() -> list:
    if WORKERS_DB_FILE.exists():
        return json.loads(WORKERS_DB_FILE.read_text(encoding="utf-8"))
    return []

def save_workers(workers: list):
    WORKERS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKERS_DB_FILE.write_text(json.dumps(workers, ensure_ascii=False, indent=2))


# ──────────────────────────────
# 메시지 전송 함수들
# ──────────────────────────────
def send_to_me(access_token: str, text: str, web_url: str = "") -> bool:
    """'나에게 보내기' (가장 간단, 본인만 수신)"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/x-www-form-urlencoded"}
    template = {
        "object_type": "text",
        "text": text[:200],  # 텍스트 타입 200자 제한
        "link": {"web_url": web_url, "mobile_web_url": web_url},
        "button_title": "대시보드 확인"
    }
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    resp = requests.post(url, headers=headers, data=data)
    return resp.status_code == 200

def send_to_friend(access_token: str, receiver_uuids: List[str], text: str, web_url: str = "") -> bool:
    """'친구에게 보내기' (동의한 친구 목록 UUID 필요)"""
    url = "https://kapi.kakao.com/v1/api/talk/friends/message/default/send"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/x-www-form-urlencoded"}
    template = {
        "object_type": "text",
        "text": text[:200],
        "link": {"web_url": web_url, "mobile_web_url": web_url},
        "button_title": "일정 확인"
    }
    data = {
        "template_object": json.dumps(template, ensure_ascii=False),
        "receiver_uuids": json.dumps(receiver_uuids)
    }
    resp = requests.post(url, headers=headers, data=data)
    return resp.status_code == 200


# ──────────────────────────────
# FastAPI 엔드포인트 (웹 화면 및 API)
# ──────────────────────────────
@app.get("/", response_class=HTMLResponse)
def serve_consent_page():
    """근무자 수신 동의 HTML 페이지 제공"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>근무 알림 수신 동의</title>
        <style>
            body { font-family: 'Arial', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f4f6f9; margin: 0; }
            .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 350px; }
            h2 { text-align: center; color: #333; margin-bottom: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input[type="text"], input[type="tel"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            .checkbox-group { display: flex; align-items: center; margin-top: 20px; }
            .checkbox-group input { margin-right: 10px; }
            button { width: 100%; padding: 12px; background-color: #fee500; color: #3c1e1e; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; margin-top: 15px; }
            button:hover { background-color: #fada0a; }
        </style>
    </head>
    <body>
    <div class="card">
        <h2>근무 알림 수신 동의</h2>
        <form id="consentForm">
            <div class="form-group">
                <label for="name">이름</label>
                <input type="text" id="name" required placeholder="홍길동">
            </div>
            <div class="form-group">
                <label for="phone">휴대폰 번호</label>
                <input type="tel" id="phone" required placeholder="01012345678" pattern="[0-9]{10,11}">
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="consent" required>
                <label for="consent" style="font-weight: normal; font-size: 14px;">[필수] 근무일자 안내 카카오 알림 수신에 동의합니다.</label>
            </div>
            <button type="submit">등록하기</button>
        </form>
    </div>
    <script>
        document.getElementById('consentForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const name = document.getElementById('name').value;
            const phone = document.getElementById('phone').value;
            const consent_agreed = document.getElementById('consent').checked;

            try {
                const response = await fetch('/api/consent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, phone, consent_agreed })
                });
                const result = await response.json();
                if (response.ok) {
                    alert(result.message);
                    document.getElementById('consentForm').reset();
                } else {
                    alert('저장 실패: ' + (result.detail || '알 수 없는 오류'));
                }
            } catch (error) {
                console.error('통신 에러:', error);
                alert('서버와 통신 중 오류가 발생했습니다.');
            }
        });
    </script>
    </body>
    </html>
    """
    return html_content

@app.post("/api/consent")
def register_consent(data: ConsentRequest):
    """근무자 수신 동의 및 전화번호 저장 API"""
    workers = load_workers()
    
    # 전화번호 기준으로 기존 등록 여부 확인 후 업데이트 또는 추가
    existing_worker = next((w for w in workers if w["phone"] == data.phone), None)
    
    if existing_worker:
        existing_worker["name"] = data.name
        existing_worker["consent_agreed"] = data.consent_agreed
    else:
        workers.append({
            "name": data.name,
            "phone": data.phone,
            "consent_agreed": data.consent_agreed,
            "duty_dates": []  # 근무일자는 관리자 페이지나 DB에서 추가 가능
        })
    
    save_workers(workers)
    return {"status": "success", "message": f"{data.name}님의 수신 동의 정보가 저장되었습니다."}


@app.post("/api/send-duty-notifications")
def trigger_duty_notifications():
    """오늘 근무자 중 수신 동의한 사람에게 카카오 메시지를 전송하는 트리거 API"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    workers = load_workers()
    
    # 1. 오늘 날짜 근무가 있고 + 수신 동의를 한 근무자 필터링
    target_workers = [
        w for w in workers 
        if today_str in w.get("duty_dates", []) and w.get("consent_agreed", False)
    ]
    
    if not target_workers:
        return {"status": "success", "message": f"[{today_str}] 오늘 발송 대상 근무자가 없습니다."}

    # 2. 유효한 액세스 토큰 확보 (시스템 관리자 계정 키 기준 예시)
    admin_user_key = "admin"
    access_token = get_valid_access_token(admin_user_key)
    
    if not access_token:
        raise HTTPException(status_code=500, detail="카카오 액세스 토큰이 유효하지 않습니다.")

    # 3. 대상자 UUID 추출 후 전송 (친구톡 활용 시 UUID 필요)
    receiver_uuids = [w["kakao_uuid"] for w in target_workers if "kakao_uuid" in w]
    
    if receiver_uuids:
        message_text = f"[근무 안내] 안녕하세요! 오늘({today_str})은 배정된 근무일입니다. 성실한 근무 부탁드립니다."
        success = send_to_friend(access_token, receiver_uuids, message_text)
        
        if success:
            return {"status": "success", "message": f"총 {len(receiver_uuids)}명에게 오늘의 근무 안내 전송 완료!"}
        else:
            raise HTTPException(status_code=500, detail="카카오 API 전송 실패")
    
    return {"status": "fail", "message": "발송 가능한 근무자의 카카오 UUID가 등록되어 있지 않습니다."}
