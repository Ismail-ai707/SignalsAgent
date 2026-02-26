"""
Investment Watcher — Market Data Layer
Free data via yfinance (Yahoo Finance).
Handles price fetching, caching, and basic fundamentals.
"""

import yfinance as yf
import database as db
from datetime import datetime, timedelta
from typing import Optional


# Euronext tickers need .PA suffix for Yahoo Finance
MARKET_SUFFIXES = {
    "US": "",
    "Paris": ".PA",
    "Euronext": ".PA",
    "Amsterdam": ".AS",
    "Brussels": ".BR",
    "Frankfurt": ".DE",
    "London": ".L",
    "Milan": ".MI",
    "Madrid": ".MC",
    "Casablanca": ".CS",
}


def resolve_ticker(ticker: str, market: str = "US") -> str:
    """Add market suffix if needed."""
    t = ticker.upper().strip()
    suffix = MARKET_SUFFIXES.get(market, "")
    if suffix and not t.endswith(suffix):
        return t + suffix
    return t


def get_current_price(ticker: str, market: str = "US") -> Optional[dict]:
    """Get current/latest price for a ticker. Returns dict with price info."""
    try:
        yt = resolve_ticker(ticker, market)
        stock = yf.Ticker(yt)
        info = stock.fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            hist = stock.history(period="5d")
            if hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])

        prev_close = getattr(info, "previous_close", None) or getattr(info, "regular_market_previous_close", None)
        change = 0.0
        change_pct = 0.0
        if prev_close and prev_close > 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100

        return {
            "ticker": ticker.upper(),
            "yahoo_ticker": yt,
            "price": round(price, 2),
            "prev_close": round(prev_close, 2) if prev_close else None,
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": getattr(info, "currency", "EUR") or "EUR",
        }
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e)}


def get_historical_prices(ticker: str, market: str = "US", period: str = "1y") -> list[dict]:
    """Fetch historical daily prices. Caches in DB."""
    try:
        yt = resolve_ticker(ticker, market)
        stock = yf.Ticker(yt)
        hist = stock.history(period=period)
        if hist.empty:
            return []

        prices = []
        for dt, row in hist.iterrows():
            prices.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row.get("Volume", 0)),
            })

        # Cache
        db.cache_prices(ticker, prices)
        return prices
    except Exception:
        # Fallback to cache
        return db.get_cached_prices(ticker)


def get_fundamentals(ticker: str, market: str = "US") -> dict:
    """Get fundamental data for analysis."""
    try:
        yt = resolve_ticker(ticker, market)
        stock = yf.Ticker(yt)
        info = stock.info or {}

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "country": info.get("country", ""),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "description": info.get("longBusinessSummary", "")[:500],
        }
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e)}


def batch_prices(positions: list[dict]) -> dict:
    """Fetch current prices for all positions. Returns {ticker: price_dict}."""
    results = {}
    for pos in positions:
        ticker = pos["ticker"]
        market = pos.get("market", "US")
        if ticker not in results:
            price_data = get_current_price(ticker, market)
            if price_data:
                results[ticker] = price_data
    return results


def search_ticker(query: str) -> list[dict]:
    """Search for tickers by name or symbol."""
    try:
        results = []
        # Try direct lookup
        stock = yf.Ticker(query.upper())
        info = stock.info or {}
        if info.get("longName") or info.get("shortName"):
            results.append({
                "ticker": query.upper(),
                "name": info.get("longName") or info.get("shortName", ""),
                "exchange": info.get("exchange", ""),
                "type": info.get("quoteType", ""),
            })

        # Also try yfinance search
        search = yf.Search(query)
        if hasattr(search, "quotes"):
            for q in search.quotes[:5]:
                t = q.get("symbol", "")
                if t and t not in [r["ticker"] for r in results]:
                    results.append({
                        "ticker": t,
                        "name": q.get("longname") or q.get("shortname", ""),
                        "exchange": q.get("exchange", ""),
                        "type": q.get("quoteType", ""),
                    })
        return results[:8]
    except Exception:
        return []
