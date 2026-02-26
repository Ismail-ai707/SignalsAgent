"""
Investment Watcher — AI Engine
Multi-LLM abstraction layer. Supports any major provider.
Builds investment analysis prompts and parses structured responses.
"""

import json
import re
from datetime import datetime
from typing import Optional


# --- LLM Provider Registry ---

PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        "default_model": "claude-sonnet-4-20250514",
        "base_url": "https://api.anthropic.com/v1/messages",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "env_key": "OPENAI_API_KEY",
    },
    "google": {
        "name": "Google (Gemini)",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "default_model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "env_key": "GOOGLE_API_KEY",
    },
    "mistral": {
        "name": "Mistral AI",
        "models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "open-mistral-nemo"],
        "default_model": "mistral-small-latest",
        "base_url": "https://api.mistral.ai/v1/chat/completions",
        "env_key": "MISTRAL_API_KEY",
    },
    "groq": {
        "name": "Groq (fast inference)",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "env_key": "GROQ_API_KEY",
    },
    "openrouter": {
        "name": "OpenRouter (multi-model)",
        "models": ["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o", "google/gemini-2.0-flash-001"],
        "default_model": "anthropic/claude-sonnet-4-20250514",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "env_key": "OPENROUTER_API_KEY",
    },
}


def call_llm(provider: str, api_key: str, model: str, system_prompt: str,
             user_prompt: str, max_tokens: int = 4096) -> dict:
    """
    Universal LLM caller. Returns {"content": str, "error": str|None}.
    """
    import requests

    if not api_key:
        return {"content": "", "error": "No API key configured. Go to Settings to add your LLM API key."}

    try:
        if provider == "anthropic":
            return _call_anthropic(api_key, model, system_prompt, user_prompt, max_tokens)
        elif provider == "google":
            return _call_google(api_key, model, system_prompt, user_prompt, max_tokens)
        elif provider in ("openai", "mistral", "groq", "openrouter"):
            return _call_openai_compat(provider, api_key, model, system_prompt, user_prompt, max_tokens)
        else:
            return {"content": "", "error": f"Unknown provider: {provider}"}
    except Exception as e:
        return {"content": "", "error": str(e)}


def _call_anthropic(api_key: str, model: str, system: str, user: str, max_tokens: int) -> dict:
    import requests
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=120,
    )
    if resp.status_code != 200:
        return {"content": "", "error": f"Anthropic API error {resp.status_code}: {resp.text[:300]}"}
    data = resp.json()
    text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    return {"content": text, "error": None}


def _call_google(api_key: str, model: str, system: str, user: str, max_tokens: int) -> dict:
    import requests
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    resp = requests.post(url, json=body, timeout=120)
    if resp.status_code != 200:
        return {"content": "", "error": f"Google API error {resp.status_code}: {resp.text[:300]}"}
    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        text = ""
    return {"content": text, "error": None}


def _call_openai_compat(provider: str, api_key: str, model: str, system: str,
                         user: str, max_tokens: int) -> dict:
    """Works for OpenAI, Mistral, Groq, OpenRouter (all use OpenAI-compatible API)."""
    import requests
    base_url = PROVIDERS[provider]["base_url"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://investment-watcher.app"

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    resp = requests.post(base_url, headers=headers, json=body, timeout=120)
    if resp.status_code != 200:
        return {"content": "", "error": f"{provider} API error {resp.status_code}: {resp.text[:300]}"}
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        text = ""
    return {"content": text, "error": None}


# --- Investment Analysis Prompts ---

SYSTEM_PROMPT = """You are an expert investment analyst and portfolio advisor.
You analyze market news, macroeconomic signals, company fundamentals, and portfolio composition
to provide actionable investment suggestions.

Your analysis must be:
- Data-driven and specific (cite the news/data that supports each suggestion)
- Balanced between opportunities and risks
- Covering both the user's existing holdings and new opportunities globally
- Practical with clear action items (BUY, SELL, HOLD, WATCH)

Currency context: The user's portfolio is in EUR.

IMPORTANT: Respond ONLY with valid JSON matching this structure:
{
  "market_summary": "Brief overview of current market conditions (2-3 sentences)",
  "portfolio_assessment": "Assessment of the user's current portfolio given market conditions",
  "signals": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "action": "BUY|SELL|HOLD|WATCH",
      "confidence": "HIGH|MEDIUM|LOW",
      "timeframe": "SHORT_TERM|LONG_TERM",
      "summary": "One-line recommendation",
      "reasoning": "Detailed reasoning with data points (2-4 sentences)",
      "in_portfolio": true,
      "risk_level": "LOW|MEDIUM|HIGH"
    }
  ],
  "macro_outlook": "Key macro factors to watch (interest rates, geopolitics, sector trends)",
  "risk_warnings": ["Warning 1", "Warning 2"]
}

Provide 5-10 signals covering:
- Existing positions that need attention (sell/hold/add)
- 2-4 new opportunities outside the current portfolio
- At least 1 signal about a sector or theme, not just individual stocks
"""


def build_analysis_prompt(positions: list[dict], prices: dict,
                          news_text: str, fundamentals: dict = None) -> str:
    """Build the user prompt with portfolio context and news."""
    parts = []

    # Portfolio summary
    parts.append("## Current Portfolio")
    if positions:
        total_value = 0
        total_cost = 0
        for pos in positions:
            ticker = pos["ticker"]
            price_info = prices.get(ticker, {})
            current_price = price_info.get("price", 0)
            value = pos["shares"] * current_price
            cost = pos["shares"] * pos["avg_cost"]
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            total_value += value
            total_cost += cost

            line = (f"- {ticker} ({pos['name']}): {pos['shares']} shares @ "
                    f"avg EUR {pos['avg_cost']:.2f}, current EUR {current_price:.2f}, "
                    f"P&L: EUR {pnl:+.2f} ({pnl_pct:+.1f}%)")
            if pos.get("sector"):
                line += f" | Sector: {pos['sector']}"
            if pos.get("market"):
                line += f" | Market: {pos['market']}"
            parts.append(line)

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        parts.append(f"\nTotal Portfolio Value: EUR {total_value:,.2f}")
        parts.append(f"Total Cost Basis: EUR {total_cost:,.2f}")
        parts.append(f"Total P&L: EUR {total_pnl:+,.2f} ({total_pnl_pct:+.1f}%)")
    else:
        parts.append("(Empty portfolio — suggest starting positions)")

    # Fundamentals
    if fundamentals:
        parts.append("\n## Key Fundamentals")
        for ticker, fund in fundamentals.items():
            if not fund.get("error"):
                line = f"- {ticker}: P/E={fund.get('pe_ratio', 'N/A')}, "
                line += f"Beta={fund.get('beta', 'N/A')}, "
                line += f"52w range={fund.get('52w_low', '?')}-{fund.get('52w_high', '?')}"
                parts.append(line)

    # News
    parts.append(f"\n## Latest News & Market Intelligence\n{news_text}")

    # Date context
    parts.append(f"\n## Context\nToday's date: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    parts.append("Portfolio currency: EUR")
    parts.append("User profile: Active investor, open to all global markets, stocks and SCPI/real estate. No crypto, no bonds.")

    return "\n".join(parts)


def parse_signals(raw_response: str) -> dict:
    """Parse LLM JSON response into structured signals."""
    # Try to extract JSON from response
    text = raw_response.strip()

    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError:
        # Try to find JSON block in response
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Fallback: return raw text as summary
    return {
        "market_summary": "Could not parse structured response.",
        "portfolio_assessment": "",
        "signals": [],
        "macro_outlook": "",
        "risk_warnings": [],
        "raw_text": raw_response,
    }


def run_analysis(provider: str, api_key: str, model: str,
                 positions: list[dict], prices: dict,
                 news_text: str, fundamentals: dict = None) -> dict:
    """
    Full pipeline: build prompt → call LLM → parse response.
    Returns parsed signals dict + metadata.
    """
    user_prompt = build_analysis_prompt(positions, prices, news_text, fundamentals)

    result = call_llm(provider, api_key, model, SYSTEM_PROMPT, user_prompt)

    if result["error"]:
        return {
            "success": False,
            "error": result["error"],
            "signals": [],
            "raw_response": "",
        }

    parsed = parse_signals(result["content"])
    parsed["success"] = True
    parsed["raw_response"] = result["content"]
    parsed["provider"] = provider
    parsed["model"] = model
    parsed["timestamp"] = datetime.now().isoformat()

    return parsed
