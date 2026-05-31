import requests
from .config import settings


def send_line_message(text: str):
    """
    LINE通知を送る。
    LINE設定が未入力、または送信失敗してもアプリ全体は止めない。
    """
    token = settings.line_channel_access_token
    user_id = settings.line_user_id

    if not token or not user_id:
        print("LINE通知は未設定です。通知内容をログに出力します。")
        print(text)
        return {"status": "skipped", "reason": "LINE settings are missing"}

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        response.raise_for_status()
        return {"status": "sent"}
    except Exception as e:
        print("LINE通知に失敗しましたが、処理は継続します。")
        print(repr(e))
        print(text)
        return {"status": "failed", "error": str(e)}
