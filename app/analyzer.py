import json
from sqlmodel import Session, select
from openai import OpenAI
from .config import settings
from .models import Holding, NewsItem, Analysis, DailyReport


def _fallback_analysis(holding: Holding, news: NewsItem) -> dict:
    text = f"{news.title} {news.summary}".lower()
    neg_words = [w.strip().lower() for w in holding.negative_keywords.split(',') if w.strip()]
    pos_words = [w.strip().lower() for w in holding.positive_keywords.split(',') if w.strip()]
    neg = any(w in text for w in neg_words)
    pos = any(w in text for w in pos_words)
    if neg and not pos:
        sentiment, impact, thesis_effect, action = "negative", 4, "やや弱化", "様子見または一部利確検討"
    elif pos and not neg:
        sentiment, impact, thesis_effect, action = "positive", 3, "強化", "保有継続"
    else:
        sentiment, impact, thesis_effect, action = "neutral", 2, "維持", "様子見"
    return {
        "sentiment": sentiment,
        "impact": impact,
        "horizon": "中期",
        "thesis_effect": thesis_effect,
        "profit_taking_effect": "利確判断への直接影響は限定的",
        "reasoning": "キーワードベースの簡易判定です。OPENAI_API_KEYを設定するとAI分析に切り替わります。",
        "action": action,
    }


def analyze_news(holding: Holding, news: NewsItem) -> dict:
    if not settings.openai_api_key:
        return _fallback_analysis(holding, news)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""
あなたはメタトレンド投資を評価する慎重なアナリストです。断定せず、投資判断の材料として評価してください。

対象銘柄: {holding.name} ({holding.ticker})
投資仮説: {holding.thesis}
ポジティブ材料キーワード: {holding.positive_keywords}
ネガティブ材料キーワード: {holding.negative_keywords}
競合: {holding.competitors}

ニュースタイトル: {news.title}
ニュース要約: {news.summary}
URL: {news.url}

以下をJSONのみで出力してください。
- sentiment: positive / negative / neutral / mixed
- impact: 1から5の整数
- horizon: 短期 / 中期 / 長期
- thesis_effect: 強化 / 維持 / やや弱化 / 明確に弱化
- profit_taking_effect: 利確判断への影響を短く
- reasoning: 根拠を日本語で2〜4文
- action: 保有継続 / 一部利確検討 / 全利確検討 / 追加購入検討 / 様子見
"""
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        data = _fallback_analysis(holding, news)
        data["reasoning"] += f" AI応答のJSON解析に失敗しました: {raw[:200]}"
        return data


def analyze_unprocessed_news(session: Session, holding: Holding, limit: int = 20) -> list[Analysis]:
    news_items = session.exec(
        select(NewsItem).where(NewsItem.holding_id == holding.id).order_by(NewsItem.fetched_at.desc()).limit(limit)
    ).all()
    saved: list[Analysis] = []
    for news in news_items:
        exists = session.exec(select(Analysis).where(Analysis.news_item_id == news.id)).first()
        if exists:
            continue
        result = analyze_news(holding, news)
        analysis = Analysis(
            holding_id=holding.id,
            news_item_id=news.id,
            sentiment=result.get("sentiment", "neutral"),
            impact=int(result.get("impact", 2)),
            horizon=result.get("horizon", "中期"),
            thesis_effect=result.get("thesis_effect", "維持"),
            profit_taking_effect=result.get("profit_taking_effect", ""),
            reasoning=result.get("reasoning", ""),
            action=result.get("action", "様子見"),
        )
        session.add(analysis)
        saved.append(analysis)
    session.commit()
    return saved


def make_report(session: Session, holding: Holding) -> DailyReport:
    analyses = session.exec(
        select(Analysis).where(Analysis.holding_id == holding.id).order_by(Analysis.created_at.desc()).limit(30)
    ).all()
    neg_impact = sum(a.impact for a in analyses if a.sentiment == "negative")
    pos_impact = sum(a.impact for a in analyses if a.sentiment == "positive")
    weak_count = sum(1 for a in analyses if "弱化" in a.thesis_effect)
    profit_alert = min(100, 20 + neg_impact * 6 + weak_count * 8)
    downside = min(100, 25 + neg_impact * 7)
    meta = max(0, min(100, 75 + pos_impact * 3 - neg_impact * 4 - weak_count * 5))
    earnings = max(0, min(100, 70 + pos_impact * 2 - neg_impact * 3))
    upside = max(0, min(100, 65 + pos_impact * 2 - profit_alert // 5))

    negative_items = [a for a in analyses if a.sentiment == "negative"][:5]
    if negative_items:
        points = "\n".join([f"- {a.reasoning} / 提案: {a.action}" for a in negative_items])
    else:
        points = "- 直近の強いネガティブ材料は検出されていません。"
    summary = (
        f"{holding.name}の現時点の投資仮説評価です。\n"
        f"メタトレンドスコア {meta}点、利確警戒度 {profit_alert}点。\n"
        f"ネガティブ材料:\n{points}\n"
        "これは売買指示ではなく、投資判断の材料です。"
    )
    report = DailyReport(
        holding_id=holding.id,
        meta_trend_score=meta,
        earnings_score=earnings,
        upside_score=upside,
        downside_risk_score=downside,
        profit_taking_alert_score=profit_alert,
        summary=summary,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report
