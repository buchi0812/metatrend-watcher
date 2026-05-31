from datetime import datetime
from sqlmodel import SQLModel, Field

class Holding(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ticker: str = Field(index=True)
    name: str
    market: str = "JP"
    shares: float = 0
    average_price: float = 0
    thesis: str
    positive_keywords: str = ""
    negative_keywords: str = ""
    competitors: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NewsItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    holding_id: int = Field(index=True)
    title: str
    url: str = Field(index=True, unique=True)
    source: str = ""
    published_at: datetime | None = None
    summary: str = ""
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

class Analysis(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    holding_id: int = Field(index=True)
    news_item_id: int | None = Field(default=None, index=True)
    sentiment: str
    impact: int
    horizon: str
    thesis_effect: str
    profit_taking_effect: str
    reasoning: str
    action: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DailyReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    holding_id: int = Field(index=True)
    report_type: str = "scheduled"
    meta_trend_score: int
    earnings_score: int
    upside_score: int
    downside_risk_score: int
    profit_taking_alert_score: int
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
