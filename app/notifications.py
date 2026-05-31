import requests
from .config import settings


def send_line_message(text: str) -> bool:
    if not settings.line_channel_access_token or not settings.line_user_id:
        print("LINE settings are not configured. Message was not sent.")
        print(text)
        return False
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {settings.line_channel_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": settings.line_user_id,
        "messages": [{"type": "text", "text": text[:4900]}],
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"LINE通知に失敗しました。アプリ処理は継続します: {e}")
        print(text)
        return False
