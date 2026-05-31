from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
PORTFOLIO_FILE = ROOT_DIR / "portfolio.json"

DEFAULT_PORTFOLIO = {
    "symbol_yahoo": "285A.T",
    "company_name": "キオクシアホールディングス",
    "sell_rule": "上昇トレンドが続く限り保有。売るときは全売却。",
    "positions": [
        {"account": "NISA", "average_price_yen": 51002.00, "shares": 30},
        {"account": "特定", "average_price_yen": 49803.13, "shares": 100},
    ],
}


def ensure_portfolio_file() -> None:
    if not PORTFOLIO_FILE.exists():
        PORTFOLIO_FILE.write_text(
            json.dumps(DEFAULT_PORTFOLIO, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def load_portfolio() -> dict[str, Any]:
    ensure_portfolio_file()
    try:
        return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_PORTFOLIO


def yen(value: float | int | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "取得不可"
    return f"{float(value):,.0f}円"


def pct(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "取得不可"
    return f"{value:+.1f}%"


def weighted_average_price(positions: list[dict[str, Any]]) -> float:
    total_cost = sum(float(p.get("average_price_yen", 0)) * float(p.get("shares", 0)) for p in positions)
    total_shares = sum(float(p.get("shares", 0)) for p in positions)
    if total_shares <= 0:
        return 0.0
    return total_cost / total_shares


def total_shares(positions: list[dict[str, Any]]) -> int:
    return int(sum(float(p.get("shares", 0)) for p in positions))


def fetch_yahoo_chart(symbol: str) -> dict[str, Any]:
    # Yahoo FinanceのチャートJSONを利用。公式APIではないため、取得できない時は画面に「取得不可」と表示する。
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "6mo", "interval": "1d", "region": "JP"}
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    result = data.get("chart", {}).get("result", [])
    if not result:
        raise RuntimeError("株価データを取得できませんでした")
    item = result[0]
    meta = item.get("meta", {})
    quote = item.get("indicators", {}).get("quote", [{}])[0]
    closes = [float(x) for x in quote.get("close", []) if x is not None]
    volumes = [float(x) for x in quote.get("volume", []) if x is not None]
    if not closes:
        raise RuntimeError("終値データが空です")
    current = float(meta.get("regularMarketPrice") or closes[-1])
    return {"current": current, "closes": closes, "volumes": volumes, "currency": meta.get("currency", "JPY")}


def moving_average(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def return_pct(values: list[float], days: int) -> float | None:
    if len(values) <= days or values[-days - 1] == 0:
        return None
    return (values[-1] / values[-days - 1] - 1.0) * 100


def max_drawdown_from_recent_high(values: list[float], lookback: int = 60) -> float | None:
    if not values:
        return None
    recent = values[-lookback:]
    high = max(recent)
    if high <= 0:
        return None
    return (values[-1] / high - 1.0) * 100


def evaluate_price_risk(current: float, closes: list[float], volumes: list[float], avg_price: float) -> dict[str, Any]:
    ma25 = moving_average(closes, 25)
    ma75 = moving_average(closes, 75)
    r5 = return_pct(closes, 5)
    r20 = return_pct(closes, 20)
    drawdown = max_drawdown_from_recent_high(closes, 60)
    gain_pct = (current / avg_price - 1.0) * 100 if avg_price else None

    trend_break_score = 0
    reasons: list[str] = []

    if ma25 is not None and current < ma25:
        trend_break_score += 10
        reasons.append("現在株価が25日移動平均を下回っています。")
    if ma25 is not None and ma75 is not None and ma25 < ma75:
        trend_break_score += 20
        reasons.append("25日移動平均が75日移動平均を下回っており、中期トレンド悪化に注意です。")
    if r5 is not None and r5 <= -5:
        trend_break_score += 8
        reasons.append("直近5営業日の下落がやや大きくなっています。")
    if r20 is not None and r20 <= -10:
        trend_break_score += 12
        reasons.append("直近20営業日の下落が大きくなっています。")
    if drawdown is not None and drawdown <= -15:
        trend_break_score += 12
        reasons.append("直近高値から15%以上下落しています。")
    elif drawdown is not None and drawdown <= -10:
        trend_break_score += 7
        reasons.append("直近高値から10%以上下落しています。")

    overheat_score = 0
    if r20 is not None and r20 >= 30:
        overheat_score += 18
        reasons.append("直近20営業日で急騰しており、短期的な過熱に注意です。")
    elif r20 is not None and r20 >= 15:
        overheat_score += 10
        reasons.append("直近20営業日の上昇が大きく、短期過熱に注意です。")
    if gain_pct is not None and gain_pct >= 100:
        overheat_score += 12
        reasons.append("取得単価から2倍以上の含み益があり、反転時の利益確定候補です。")
    elif gain_pct is not None and gain_pct >= 50:
        overheat_score += 6
        reasons.append("取得単価から50%以上上昇しています。")

    # ユーザーのルールは「上昇トレンド継続なら保有、売る時は全部売る」なので、
    # 単なる含み益よりもトレンド崩れを重くする。
    technical_alert = min(100, trend_break_score + int(overheat_score * 0.6))

    if not reasons:
        reasons.append("株価データ上、明確なトレンド崩れサインは強く出ていません。")

    return {
        "current": current,
        "ma25": ma25,
        "ma75": ma75,
        "return_5d": r5,
        "return_20d": r20,
        "drawdown_60d": drawdown,
        "gain_pct": gain_pct,
        "trend_break_score": trend_break_score,
        "overheat_score": overheat_score,
        "technical_alert": technical_alert,
        "reasons": reasons,
    }


def portfolio_snapshot() -> dict[str, Any]:
    portfolio = load_portfolio()
    positions = portfolio.get("positions", [])
    avg_price = weighted_average_price(positions)
    shares = total_shares(positions)
    symbol = portfolio.get("symbol_yahoo", "285A.T")

    result: dict[str, Any] = {
        "portfolio": portfolio,
        "positions": positions,
        "avg_price": avg_price,
        "shares": shares,
        "data_error": None,
    }
    try:
        chart = fetch_yahoo_chart(symbol)
        price_risk = evaluate_price_risk(chart["current"], chart["closes"], chart["volumes"], avg_price)
        current_value = chart["current"] * shares
        cost = avg_price * shares
        result.update({
            "current_price": chart["current"],
            "current_value": current_value,
            "cost": cost,
            "unrealized_profit": current_value - cost,
            "price_risk": price_risk,
        })
    except Exception as e:
        result["data_error"] = str(e)
    return result


def combined_alert_score(news_alert: int | None, technical_alert: int | None) -> int:
    # ニュース50%、株価トレンド50%。どちらか欠ける場合はある方を採用。
    if news_alert is None and technical_alert is None:
        return 0
    if news_alert is None:
        return int(technical_alert or 0)
    if technical_alert is None:
        return int(news_alert)
    return int(round(news_alert * 0.5 + technical_alert * 0.5))
