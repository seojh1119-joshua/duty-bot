# kakao_sender.py
import requests
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

CONFIG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
KAKAO_CONFIG = CONFIG["kakao"]
REST_API_KEY = KAKAO_CONFIG["rest_api_key"]

# ──────────────────────────────
# 토큰 관리 (간단 파일 기반, 프로덕션이면 Redis/DB 권장)
# ──────────────────────────────
TOKEN_FILE = Path("data/kakao_tokens.json")

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
        # 기존 토큰 정보에 새 액세스 토큰만 업데이트 (리프레시 토큰은 만료 시에만 갱신됨)
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
   _token = tokens.get(user_key)
    if not_token:
        return None
    
    access_token =_token.get("access_token")
    # 간단 검증: 나에게 보내기 API로 테스트
    headers = {"Authorization": f"Bearer {access_token}"}
    test_resp = requests.get("https://kapi.kakao.com/v2/api/talk/memo/default/send", 
                             headers=headers, 
                             data={"template_object": json.dumps({"object_type": "text", "text": "token_test", "link": {}})} )
    
    if test_resp.status_code == 200:
        return access_token
    elif test_resp.status_code == 401: # 토큰 만료
        print(f"[{_key}] Access Token 만료, 갱신 시도...")
        new_token = refresh_access_token(user_token["refresh_token"])
        return new_token
    return None

# ──────────────────────────────
# 메시지 전송 함수들
# ──────────────────────────────
def send_to_me(access_token: str, text: str, web_url: str = "") -> bool:
    """'나에게 보내기' (가장 간단, 본인만 수신)"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/x-www-form-urlencoded"}
    template = {
        "object_type": "text",
        "text": text[:200], # 텍스트 타입 200자 제한
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
# 알림톡(AlimTalk) 전송 
# ──────────────────────────────
def send_alimtalk_batch(messages: List[dict]) -> bool:
    """
    messages: [{"phone": "010xxxxxxxx", "template_code": "TPL_001", "vars": {"name": "홍길동", "date": "2026-09-04", "duty": "야간"}}, ...]
    """
    # 1. 직접 연동: 카카오 비즈메시지 API (인증 헤더 복잡, 문서 참고)
    # 2. 대행사 SDK (알리고, 센드버드비즈, 솔라피 등) 사용 권장 - 훨씬 간편
    # 예: 솔라피(solapi) pip install solapi
    # from solapi import SolapiMessageService
    # service = SolapiMessageService(API_KEY, API_SECRET)
    # for m in messages: service.send_alimtalk(m["phone"], m["template_code"], m["vars"])
    pass