import requests
from sqlmodel import Session, select

from .config import settings
from .models import Holding, NewsItem
from .news import collect_news_for_holding
from .analyzer import analyze_unprocessed_news, make_report


def _dashboard_url() -> str:
    base = getattr(settings, "app_public_url", "") or "https://metatrend-watcher.onrender.com"
    return base.rstrip("/") + "/dashboard"


def reply_line_message(reply_token: str, text: str):
    token = settings.line_channel_access_token

    if not token:
        print("LINE_CHANNEL_ACCESS_TOKEN is missing.")
        print(text)
        return {"status": "skipped"}

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # LINEの1メッセージ上限対策
    text = text[:4500]

    body = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        r.raise_for_status()
        return {"status": "sent"}
    except Exception as e:
        print("LINE reply failed:", repr(e))
        print(text)
        return {"status": "failed", "error": str(e)}


def quick_check(session: Session) -> str:
    """
    OpenAI APIを使わない簡易チェック。
    ニュース取得とリンク表示だけを行う。
    """
    holding = session.exec(select(Holding)).first()

    if not holding:
        return "保有銘柄がまだ登録されていません。"

    try:
        collect_news_for_holding(session, holding)
    except Exception as e:
        print("News collection failed:", repr(e))

    news_items = session.exec(
        select(NewsItem)
        .where(NewsItem.holding_id == holding.id)
        .order_by(NewsItem.fetched_at.desc())
        .limit(5)
    ).all()

    lines = [
        "【MetaTrend Watcher｜簡易チェック】",
        "",
        f"対象：{holding.name}（{holding.ticker}）",
        "",
        "これはOpenAI APIを使わない簡易チェックです。",
        "AI分析・利確警戒度の再計算はしていません。",
        "",
        "直近ニュース：",
    ]

    if not news_items:
        lines.append("直近ニュースは取得できませんでした。")
    else:
        for i, n in enumerate(news_items, start=1):
            lines.append(f"{i}. {n.title}")
            lines.append(n.url)

    lines.extend(
        [
            "",
            "詳しい画面：",
            _dashboard_url(),
            "",
            "AI分析したい場合は「分析して」と送ってください。",
        ]
    )

    return "\n".join(lines)


def ai_analysis(session: Session) -> str:
    """
    OpenAI APIを使う詳細分析。
    これはAPI料金が発生する。
    """
    holding = session.exec(select(Holding)).first()

    if not holding:
        return "保有銘柄がまだ登録されていません。"

    collect_news_for_holding(session, holding)
    analyze_unprocessed_news(session, holding)
    report = make_report(session, holding)

    return "\n".join(
        [
            "【MetaTrend Watcher｜AI分析】",
            "",
            f"対象：{holding.name}（{holding.ticker}）",
            "",
            f"利確警戒度：{report.profit_taking_alert_score}/100",
            f"メタトレンド：{report.meta_trend_score}",
            f"業績期待：{report.earnings_score}",
            f"上値余地：{report.upside_score}",
            f"下落リスク：{report.downside_risk_score}",
            "",
            "分析結果：",
            report.summary,
            "",
            "ダッシュボード：",
            _dashboard_url(),
            "",
            "※これは売買指示ではなく、投資判断の材料です。",
        ]
    )


def handle_line_webhook(payload: dict, session: Session):
    events = payload.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        text = message.get("text", "").strip()
        reply_token = event.get("replyToken")

        if not reply_token:
            continue

        if text in ["どう？", "どう", "どお？"]:
            reply = quick_check(session)
        elif text in ["分析して", "詳しく", "AI分析", "詳細分析"]:
            reply = ai_analysis(session)
        else:
            reply = (
                "使い方：\n"
                "「どう？」→ OpenAI APIなしで簡易チェック\n"
                "「分析して」→ OpenAI APIを使って詳しく分析\n\n"
                f"ダッシュボード：\n{_dashboard_url()}"
            )

        reply_line_message(reply_token, reply)

    return {"status": "ok"}
