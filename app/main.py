from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from .db import init_db, get_session
from .models import Holding, NewsItem, Analysis, DailyReport
from .news import collect_news_for_holding
from .analyzer import analyze_unprocessed_news, make_report
from .scheduler import start_scheduler, run_watch_cycle
from .portfolio import portfolio_snapshot, combined_alert_score, yen, pct

app = FastAPI(title="MetaTrend Watcher", version="0.2.0")


@app.on_event("startup")
def on_startup():
    init_db()
    start_scheduler()


@app.get("/")
def root():
    return {"app": "MetaTrend Watcher", "status": "ok", "dashboard": "/dashboard"}


@app.get("/holdings")
def list_holdings(session: Session = Depends(get_session)):
    return session.exec(select(Holding)).all()


@app.post("/holdings")
def add_holding(holding: Holding, session: Session = Depends(get_session)):
    session.add(holding)
    session.commit()
    session.refresh(holding)
    return holding


@app.post("/run-now")
def run_now():
    run_watch_cycle(report_type="手動実行")
    return {"status": "completed"}


@app.post("/holdings/{holding_id}/collect")
def collect(holding_id: int, session: Session = Depends(get_session)):
    holding = session.get(Holding, holding_id)
    if not holding:
        return {"error": "holding not found"}
    news = collect_news_for_holding(session, holding)
    analyses = analyze_unprocessed_news(session, holding)
    report = make_report(session, holding)
    return {"new_news": len(news), "new_analyses": len(analyses), "report": report}


def profit_taking_label(score: int):
    if score <= 30:
        return "低い", "現時点では、急いで全売却を検討する必要は低い状態です。上昇トレンドが維持される限り、保有継続寄りです。"
    if score <= 60:
        return "中等度", "注意ゾーンです。ニュース悪化または株価トレンド崩れが続く場合、全売却の準備を検討します。"
    if score <= 80:
        return "高い", "利確検討ゾーンです。上昇トレンドの崩れ、材料出尽くし、悪材料増加が目立ち始めています。"
    return "かなり高い", "強い利確警戒ゾーンです。上昇トレンド継続の根拠が弱い場合、全売却を具体的に検討する段階です。"


def html_escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(session: Session = Depends(get_session)):
    holdings = session.exec(select(Holding)).all()
    snap = portfolio_snapshot()
    price_risk = snap.get("price_risk") or {}
    technical_alert = price_risk.get("technical_alert")

    parts = [
        "<html><head><meta charset='utf-8'><title>MetaTrend Watcher</title>",
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:1080px;margin:40px auto;line-height:1.6;color:#111}"
        ".card{border:1px solid #ddd;border-radius:14px;padding:22px;margin:18px 0;background:#fff}"
        ".score{font-size:30px;font-weight:bold;margin:8px 0}.subscore{font-size:18px;font-weight:bold}"
        ".note{background:#f7f7f7;border-radius:10px;padding:14px;margin:12px 0}"
        ".warn{background:#fff7e6;border:1px solid #f0c36d;border-radius:10px;padding:12px;margin:12px 0}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:12px 0}"
        ".metric{background:#fafafa;border:1px solid #eee;border-radius:10px;padding:12px}.metric b{display:block;font-size:13px;color:#555}.metric span{font-size:20px;font-weight:700}"
        ".neg{color:#b00020}.pos{color:#006400}a{color:#0645ad}table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border-bottom:1px solid #eee;padding:8px;text-align:left}"
        "</style></head><body>",
        "<h1>MetaTrend Watcher v0.2</h1><p>売買指示ではなく、投資判断の材料を整理するダッシュボードです。</p>",
    ]

    parts.append("<div class='card'><h2>保有状況・株価トレンド</h2>")
    portfolio = snap.get("portfolio", {})
    parts.append(f"<p><b>売却ルール:</b> {html_escape(portfolio.get('sell_rule', '未設定'))}</p>")
    parts.append("<table><tr><th>口座</th><th>平均取得単価</th><th>株数</th><th>取得額</th></tr>")
    for p in snap.get("positions", []):
        avg = float(p.get("average_price_yen", 0))
        shares = float(p.get("shares", 0))
        parts.append(f"<tr><td>{html_escape(p.get('account',''))}</td><td>{yen(avg)}</td><td>{int(shares)}株</td><td>{yen(avg * shares)}</td></tr>")
    parts.append("</table>")

    if snap.get("data_error"):
        parts.append(f"<div class='warn'><b>株価自動取得に失敗:</b> {html_escape(snap['data_error'])}<br>銘柄コードや通信状況を確認してください。</div>")
    else:
        pr = price_risk
        parts.append("<div class='grid'>")
        parts.append(f"<div class='metric'><b>現在株価</b><span>{yen(snap.get('current_price'))}</span></div>")
        parts.append(f"<div class='metric'><b>加重平均取得単価</b><span>{yen(snap.get('avg_price'))}</span></div>")
        parts.append(f"<div class='metric'><b>保有株数</b><span>{snap.get('shares',0)}株</span></div>")
        parts.append(f"<div class='metric'><b>評価額</b><span>{yen(snap.get('current_value'))}</span></div>")
        parts.append(f"<div class='metric'><b>含み損益</b><span>{yen(snap.get('unrealized_profit'))}</span></div>")
        parts.append(f"<div class='metric'><b>取得単価比</b><span>{pct(pr.get('gain_pct'))}</span></div>")
        parts.append(f"<div class='metric'><b>5営業日騰落率</b><span>{pct(pr.get('return_5d'))}</span></div>")
        parts.append(f"<div class='metric'><b>20営業日騰落率</b><span>{pct(pr.get('return_20d'))}</span></div>")
        parts.append(f"<div class='metric'><b>25日移動平均</b><span>{yen(pr.get('ma25'))}</span></div>")
        parts.append(f"<div class='metric'><b>75日移動平均</b><span>{yen(pr.get('ma75'))}</span></div>")
        parts.append(f"<div class='metric'><b>直近高値から</b><span>{pct(pr.get('drawdown_60d'))}</span></div>")
        parts.append("</div>")
        parts.append("<div class='note'><b>株価トレンド評価:</b><ul>")
        for reason in pr.get("reasons", []):
            parts.append(f"<li>{html_escape(reason)}</li>")
        parts.append("</ul></div>")
    parts.append("</div>")

    for h in holdings:
        report = session.exec(
            select(DailyReport)
            .where(DailyReport.holding_id == h.id)
            .order_by(DailyReport.created_at.desc())
        ).first()
        analyses = session.exec(
            select(Analysis)
            .where(Analysis.holding_id == h.id)
            .order_by(Analysis.created_at.desc())
            .limit(10)
        ).all()
        news_map = {
            n.id: n
            for n in session.exec(
                select(NewsItem)
                .where(NewsItem.holding_id == h.id)
                .order_by(NewsItem.fetched_at.desc())
                .limit(30)
            ).all()
        }

        parts.append(f"<div class='card'><h2>{html_escape(h.name)} ({html_escape(h.ticker)})</h2><p><b>投資仮説:</b> {html_escape(h.thesis)}</p>")

        if report:
            news_alert = report.profit_taking_alert_score
            total_alert = combined_alert_score(news_alert, technical_alert)
            label, judgment = profit_taking_label(total_alert)

            parts.append(f"<p class='score'>総合利確警戒度: {total_alert}/100（{label}）</p>")
            parts.append(f"<p><b>現在の判断:</b> {judgment}</p>")
            parts.append("<div class='grid'>")
            parts.append(f"<div class='metric'><b>ニュース由来</b><span>{news_alert}/100</span></div>")
            parts.append(f"<div class='metric'><b>株価トレンド由来</b><span>{technical_alert if technical_alert is not None else '取得不可'}/100</span></div>")
            parts.append(f"<div class='metric'><b>メタトレンド</b><span>{report.meta_trend_score}/100</span></div>")
            parts.append(f"<div class='metric'><b>業績期待</b><span>{report.earnings_score}/100</span></div>")
            parts.append(f"<div class='metric'><b>上値余地</b><span>{report.upside_score}/100</span></div>")
            parts.append(f"<div class='metric'><b>下落リスク</b><span>{report.downside_risk_score}/100</span></div>")
            parts.append("</div>")
            parts.append("<div class='note'>")
            parts.append("<b>総合利確警戒度とは：</b><br>")
            parts.append("ニュース悪化と株価トレンド悪化を合わせた、全売却を検討すべき度合いです。あなたの方針に合わせ、単なる含み益よりも『上昇トレンドが崩れたか』を重めに見ます。")
            parts.append("</div>")
            parts.append(f"<pre>{html_escape(report.summary)}</pre>")

        parts.append("<h3>直近分析</h3><ul>")
        for a in analyses:
            n = news_map.get(a.news_item_id)
            title = n.title if n else "ニュース"
            url = n.url if n else "#"
            cls = "neg" if a.sentiment == "negative" else "pos" if a.sentiment == "positive" else ""
            parts.append(
                f"<li class='{cls}'><a href='{html_escape(url)}' target='_blank'>{html_escape(title)}</a><br>"
                f"判定: {html_escape(a.sentiment)} / 影響度: {a.impact} / {html_escape(a.action)}<br>"
                f"{html_escape(a.reasoning)}</li>"
            )
        parts.append("</ul></div>")

    parts.append("</body></html>")
    return "".join(parts)
