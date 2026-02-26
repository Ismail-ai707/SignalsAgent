"""
Investment Watcher — News Fetcher
Aggregates news from free RSS feeds, Google News, and public APIs.
Returns structured news items for AI analysis.
"""

import feedparser
import re
import html
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus


# --- RSS Feed Sources ---

MARKET_FEEDS = {
    "Reuters Business": "https://www.rss.app/feeds/v1.1/tJgGeNfeSVhF0nqA.xml",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "Financial Times": "https://www.ft.com/rss/home",
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "Seeking Alpha": "https://seekingalpha.com/market_currents.xml",
}

MACRO_FEEDS = {
    "ECB Press": "https://www.ecb.europa.eu/rss/press.html",
    "Fed News": "https://www.federalreserve.gov/feeds/press_all.xml",
    "IMF Blog": "https://www.imf.org/en/News/Rss?Language=ENG",
}

SECTOR_KEYWORDS = {
    "Technology": ["tech", "software", "AI", "semiconductor", "chip", "cloud", "SaaS", "FAANG", "NVIDIA", "Apple", "Microsoft", "Google", "Meta", "Amazon"],
    "Healthcare": ["pharma", "biotech", "FDA", "drug", "hospital", "medical", "vaccine"],
    "Finance": ["bank", "interest rate", "Fed", "ECB", "inflation", "credit", "loan", "fintech"],
    "Energy": ["oil", "gas", "renewable", "solar", "wind", "OPEC", "crude", "energy"],
    "Consumer": ["retail", "consumer", "luxury", "LVMH", "spending"],
    "Industrial": ["manufacturing", "aerospace", "defense", "supply chain"],
    "Real Estate": ["SCPI", "real estate", "REIT", "housing", "mortgage", "property"],
}


def _parse_feed(url: str, source_name: str, max_items: int = 10) -> list[dict]:
    """Parse an RSS feed and return structured items."""
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            pub_date = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6]).isoformat()
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6]).isoformat()

            title = html.unescape(entry.get("title", "")).strip()
            summary = html.unescape(entry.get("summary", "")).strip()
            # Strip HTML tags from summary
            summary = re.sub(r"<[^>]+>", "", summary)[:500]

            items.append({
                "source": source_name,
                "title": title,
                "summary": summary,
                "url": entry.get("link", ""),
                "published": pub_date,
            })
        return items
    except Exception:
        return []


def fetch_market_news(max_per_source: int = 5) -> list[dict]:
    """Fetch general market news from all RSS sources."""
    all_news = []
    for name, url in MARKET_FEEDS.items():
        items = _parse_feed(url, name, max_per_source)
        all_news.extend(items)
    return _deduplicate(all_news)


def fetch_macro_news(max_per_source: int = 5) -> list[dict]:
    """Fetch macroeconomic news (central banks, IMF, etc.)."""
    all_news = []
    for name, url in MACRO_FEEDS.items():
        items = _parse_feed(url, name, max_per_source)
        all_news.extend(items)
    return _deduplicate(all_news)


def fetch_ticker_news(ticker: str, company_name: str = "", max_items: int = 10) -> list[dict]:
    """Fetch news for a specific ticker via Google News RSS."""
    queries = [ticker]
    if company_name:
        queries.append(company_name)

    all_news = []
    for q in queries:
        encoded = quote_plus(q)
        url = f"https://news.google.com/rss/search?q={encoded}+stock&hl=en&gl=US&ceid=US:en"
        items = _parse_feed(url, f"Google News ({q})", max_items)
        all_news.extend(items)

    return _deduplicate(all_news)[:max_items]


def fetch_sector_news(sector: str, max_items: int = 10) -> list[dict]:
    """Fetch news for a specific sector."""
    keywords = SECTOR_KEYWORDS.get(sector, [sector])
    query = " OR ".join(keywords[:3])
    encoded = quote_plus(query + " stock market")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
    return _parse_feed(url, f"Google News ({sector})", max_items)


def fetch_all_for_portfolio(positions: list[dict], max_per_ticker: int = 5) -> dict:
    """
    Fetch all relevant news for a portfolio.
    Returns {
        "market": [...],
        "macro": [...],
        "by_ticker": {"AAPL": [...], ...},
        "by_sector": {"Technology": [...], ...},
    }
    """
    result = {
        "market": fetch_market_news(5),
        "macro": fetch_macro_news(5),
        "by_ticker": {},
        "by_sector": {},
    }

    # Per-ticker news
    seen_tickers = set()
    for pos in positions:
        t = pos["ticker"]
        if t not in seen_tickers:
            seen_tickers.add(t)
            result["by_ticker"][t] = fetch_ticker_news(t, pos.get("name", ""), max_per_ticker)

    # Per-sector news
    seen_sectors = set()
    for pos in positions:
        s = pos.get("sector", "")
        if s and s not in seen_sectors:
            seen_sectors.add(s)
            result["by_sector"][s] = fetch_sector_news(s, 5)

    return result


def _deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicate news by title similarity."""
    seen = set()
    unique = []
    for item in items:
        # Normalize title for dedup
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def format_news_for_llm(news_data: dict, max_total: int = 60) -> str:
    """Format all collected news into a text block for LLM consumption."""
    sections = []
    count = 0

    # Market headlines
    if news_data.get("market"):
        lines = ["## Market Headlines"]
        for item in news_data["market"][:10]:
            lines.append(f"- [{item['source']}] {item['title']}")
            if item["summary"]:
                lines.append(f"  {item['summary'][:200]}")
            count += 1
        sections.append("\n".join(lines))

    # Macro
    if news_data.get("macro"):
        lines = ["## Macroeconomic / Central Banks"]
        for item in news_data["macro"][:8]:
            lines.append(f"- [{item['source']}] {item['title']}")
            if item["summary"]:
                lines.append(f"  {item['summary'][:200]}")
            count += 1
        sections.append("\n".join(lines))

    # Per-ticker
    if news_data.get("by_ticker"):
        lines = ["## Company-Specific News"]
        for ticker, items in news_data["by_ticker"].items():
            if items:
                lines.append(f"\n### {ticker}")
                for item in items[:4]:
                    lines.append(f"- [{item['source']}] {item['title']}")
                    count += 1
                    if count >= max_total:
                        break
            if count >= max_total:
                break
        sections.append("\n".join(lines))

    # Per-sector
    if news_data.get("by_sector"):
        lines = ["## Sector News"]
        for sector, items in news_data["by_sector"].items():
            if items:
                lines.append(f"\n### {sector}")
                for item in items[:3]:
                    lines.append(f"- [{item['source']}] {item['title']}")
                    count += 1
                    if count >= max_total:
                        break
            if count >= max_total:
                break
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
