from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select
from .config import settings
from .db import engine
from .models import Holding
from .news import collect_news_for_holding
from .analyzer import analyze_unprocessed_news, make_report
from .notifications import send_line_message

scheduler = BackgroundScheduler(timezone=settings.app_timezone)


def run_watch_cycle(report_type: str = "scheduled"):
    with Session(engine) as session:
        holdings = session.exec(select(Holding)).all()
        for holding in holdings:
            collect_news_for_holding(session, holding)
            analyze_unprocessed_news(session, holding)
            report = make_report(session, holding)
            # ネガティブまたは利確警戒が一定以上なら通知。定時実行では毎回サマリも送る。
            text = f"【MetaTrend Watcher {report_type}】\n{report.summary}"
            send_line_message(text)


def start_scheduler():
    if not settings.enable_scheduler:
        return
    if scheduler.running:
        return
    scheduler.add_job(
        run_watch_cycle,
        CronTrigger(hour=9, minute=0, timezone=settings.app_timezone),
        kwargs={"report_type": "9時レポート"},
        id="morning_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_watch_cycle,
        CronTrigger(hour=16, minute=0, timezone=settings.app_timezone),
        kwargs={"report_type": "16時レポート"},
        id="evening_report",
        replace_existing=True,
    )
    scheduler.start()
