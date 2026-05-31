from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import feedparser
from sqlmodel import Session, select
from .models import Holding, NewsItem

TRUSTED_QUERY_SUFFIX = " -blog -個人ブログ -掲示板"


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def build_queries(holding: Holding) -> list[str]:
    base = [
        f'"{holding.name}" 株 速報',
        f'"{holding.name}" 決算 適時開示',
        f'"{holding.name}" NAND AI データセンター',
        'NAND spot price SSD demand AI data center',
        'NAND flash price supply demand TrendForce',
    ]
    for competitor in [c.strip() for c in holding.competitors.split(',') if c.strip()]:
        base.append(f'{competitor} NAND 増産 供給過剰')
    return [q + TRUSTED_QUERY_SUFFIX for q in base]


def fetch_google_news(query: str, max_items: int = 10) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "title": getattr(entry, "title", ""),
            "url": getattr(entry, "link", ""),
            "source": getattr(getattr(entry, "source", None), "title", "Google News"),
            "published_at": _parse_date(getattr(entry, "published", None)),
            "summary": getattr(entry, "summary", ""),
        })
    return items


def collect_news_for_holding(session: Session, holding: Holding, max_per_query: int = 6) -> list[NewsItem]:
    saved: list[NewsItem] = []
    for query in build_queries(holding):
        for item in fetch_google_news(query, max_per_query):
            if not item["url"]:
                continue
            exists = session.exec(select(NewsItem).where(NewsItem.url == item["url"])).first()
            if exists:
                continue
            news = NewsItem(holding_id=holding.id, **item)
            session.add(news)
            saved.append(news)
    session.commit()
    for n in saved:
        session.refresh(n)
    return saved
