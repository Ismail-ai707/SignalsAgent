# Investment Watcher

Portfolio tracker with AI-powered investment intelligence. Analyzes real-time news, macroeconomic signals, company fundamentals, and your portfolio to generate actionable buy/sell/hold suggestions.

## Features

- **Portfolio Management** — Manual entry or Trade Republic PDF import
- **Live Prices** — Real-time quotes via Yahoo Finance (US, Euronext, global markets)
- **P&L Tracking** — Unrealized gains/losses per position and total portfolio
- **Allocation Analysis** — Breakdown by sector, market, asset type
- **Portfolio History** — Daily value snapshots with interactive chart
- **AI Investment Signals** — LLM-powered analysis combining:
  - Portfolio composition and P&L
  - Market news (Reuters, CNBC, MarketWatch, Seeking Alpha...)
  - Macro data (ECB, Fed, IMF)
  - Company-specific news per holding
  - Fundamental data (P/E, beta, 52-week range)
  - Generates BUY/SELL/HOLD/WATCH signals with confidence and reasoning
- **News Feed** — Aggregated market, macro, and per-holding news
- **Multi-LLM Support** — Anthropic, OpenAI, Google, Mistral, Groq, OpenRouter
- **Multi-User Auth** — Username/password, per-user portfolios
- **Dark Professional UI** — Emerald theme, clean design

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuration

1. Register/login
2. Go to **Settings** → select your LLM provider → paste API key → choose model
3. Go to **Portfolio** → add positions manually or import Trade Republic PDF/CSV
4. Go to **AI Signals** → click "Get Signals" to run analysis

## Trade Republic Import

Upload your portfolio statement PDF. The parser extracts:
- Asset names and ISINs
- Share counts
- Average cost (when available)

Common ISINs are auto-mapped to Yahoo Finance tickers. Edit unmapped tickers before importing.

### CSV Import Format

```csv
Ticker,Name,Shares,AvgCost,Market,Sector,AssetType
AAPL,Apple Inc.,10,150.00,US,Technology,stock
MC.PA,LVMH,5,850.00,Paris,Consumer,stock
```

## Supported Markets

| Market | Yahoo Suffix | Example |
|--------|-------------|---------|
| US (NYSE/NASDAQ) | (none) | AAPL, MSFT |
| Paris/Euronext | .PA | MC.PA, TTE.PA |
| Amsterdam | .AS | ASML.AS |
| Frankfurt | .DE | SAP.DE |
| London | .L | CSPX.L |
| Milan | .MI | — |
| Casablanca | .CS | — |

## LLM Providers

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| Groq | Yes (generous) | Fast, free analysis |
| Google Gemini | Yes (Flash) | Good free option |
| Mistral | Pay-per-use | Affordable, EU-based |
| Anthropic | Pay-per-use | Best quality analysis |
| OpenAI | Pay-per-use | Reliable alternative |
| OpenRouter | Varies | Access all models |

## Architecture

```
app.py           → Streamlit UI
database.py      → SQLite (Supabase-ready schema)
market_data.py   → Yahoo Finance (prices, fundamentals)
news_fetcher.py  → RSS aggregation (10+ sources)
ai_engine.py     → Multi-LLM abstraction + analysis prompts
portfolio.py     → P&L, allocation, snapshots
tr_importer.py   → Trade Republic PDF/CSV parser
```

## Data Sources (all free)

- Yahoo Finance — prices, historical data, fundamentals
- Google News RSS — ticker-specific and sector news
- Reuters, CNBC, MarketWatch — market headlines
- ECB, Fed, IMF — central bank and macro feeds
- Seeking Alpha — analyst opinions

All data is fetched on-demand when you open the app. No background processes.
