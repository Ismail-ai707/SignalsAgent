"""
Investment Watcher — Trade Republic Importer
Parses Trade Republic PDF portfolio statements and trade confirmations.
Also supports manual CSV upload.

TR Portfolio Statement typically contains:
- Asset name + ISIN
- Number of shares
- Current price + value
- Average cost / purchase price
- P&L

TR Trade Confirmation contains:
- Buy/Sell action
- Asset name + ISIN
- Shares + price
- Fees
- Date
"""

import re
import io
from typing import Optional

# ISIN pattern: 2 letters + 10 alphanumeric
ISIN_PATTERN = re.compile(r"\b([A-Z]{2}[A-Z0-9]{10})\b")

# Common ISIN to Yahoo ticker mapping for popular stocks
ISIN_TICKER_MAP = {
    # US stocks
    "US0378331005": ("AAPL", "Apple Inc.", "US"),
    "US5949181045": ("MSFT", "Microsoft Corp.", "US"),
    "US0231351067": ("AMZN", "Amazon.com Inc.", "US"),
    "US02079K3059": ("GOOGL", "Alphabet Inc.", "US"),
    "US30303M1027": ("META", "Meta Platforms Inc.", "US"),
    "US88160R1014": ("TSLA", "Tesla Inc.", "US"),
    "US67066G1040": ("NVDA", "NVIDIA Corp.", "US"),
    "US4781601046": ("JNJ", "Johnson & Johnson", "US"),
    "US92826C8394": ("V", "Visa Inc.", "US"),
    "US46625H1005": ("JPM", "JPMorgan Chase", "US"),
    "US0846707026": ("BRK-B", "Berkshire Hathaway B", "US"),
    "US7427181091": ("PG", "Procter & Gamble", "US"),
    "US4592001014": ("IBM", "IBM Corp.", "US"),
    "US2546871060": ("DIS", "Walt Disney", "US"),
    "US00507V1098": ("ATVI", "Activision Blizzard", "US"),
    "US0079031078": ("AMD", "Advanced Micro Devices", "US"),
    "US7170811035": ("PFE", "Pfizer Inc.", "US"),
    "US2855121099": ("LRCX", "Lam Research", "US"),
    "US8740391003": ("TSM", "Taiwan Semiconductor", "US"),
    # European stocks
    "NL0010273215": ("ASML.AS", "ASML Holding", "Amsterdam"),
    "FR0000121014": ("MC.PA", "LVMH", "Paris"),
    "FR0000120271": ("TTE.PA", "TotalEnergies", "Paris"),
    "DE0007164600": ("SAP.DE", "SAP SE", "Frankfurt"),
    "DE0007236101": ("SIE.DE", "Siemens AG", "Frankfurt"),
    "FR0000120578": ("SAN.PA", "Sanofi", "Paris"),
    "NL0000235190": ("AIR.PA", "Airbus SE", "Paris"),
    "FR0000131104": ("BNP.PA", "BNP Paribas", "Paris"),
    "FR0000120321": ("OR.PA", "L'Oreal", "Paris"),
    "FR0000125338": ("CAP.PA", "Capgemini", "Paris"),
    "FR0000121972": ("SCR.PA", "Schneider Electric", "Paris"),
    "IE00B4BNMY34": ("ACWI", "iShares MSCI ACWI ETF", "US"),
    # Popular ETFs
    "IE00B5BMR087": ("CSPX.L", "iShares Core S&P 500", "London"),
    "IE00B4L5Y983": ("IWDA.AS", "iShares Core MSCI World", "Amsterdam"),
    "LU0392494562": ("MEUD.PA", "Lyxor Euro Stoxx 50", "Paris"),
    "IE00BKM4GZ66": ("EIMI.L", "iShares Core EM IMI", "London"),
}


def parse_tr_portfolio_pdf(file_bytes: bytes) -> list[dict]:
    """
    Parse Trade Republic portfolio statement PDF.
    Returns list of position dicts.
    """
    text = _extract_pdf_text(file_bytes)
    if not text:
        return []

    positions = []
    lines = text.split("\n")

    # Strategy: find ISINs, then extract surrounding context
    for i, line in enumerate(lines):
        isins = ISIN_PATTERN.findall(line)
        for isin in isins:
            position = _extract_position_from_context(lines, i, isin)
            if position:
                positions.append(position)

    # Deduplicate by ISIN
    seen = set()
    unique = []
    for p in positions:
        if p["isin"] not in seen:
            seen.add(p["isin"])
            unique.append(p)

    return unique


def _extract_position_from_context(lines: list[str], isin_line_idx: int, isin: str) -> Optional[dict]:
    """Extract position details from lines around where ISIN was found."""
    # Get context: 5 lines before and after
    start = max(0, isin_line_idx - 5)
    end = min(len(lines), isin_line_idx + 6)
    context = "\n".join(lines[start:end])

    # Look up known ISIN
    known = ISIN_TICKER_MAP.get(isin)
    ticker = known[0] if known else ""
    name = known[1] if known else ""
    market = known[2] if known else "US"

    # Try to extract name from context if not known
    if not name:
        # Usually the line before or same line as ISIN has the name
        for j in range(max(0, isin_line_idx - 2), isin_line_idx + 1):
            if j < len(lines):
                candidate = lines[j].strip()
                # Name is usually a line with text that's not just numbers
                if candidate and not re.match(r"^[\d\s,.\-+%€$]+$", candidate):
                    candidate = re.sub(ISIN_PATTERN, "", candidate).strip()
                    if len(candidate) > 3:
                        name = candidate[:60]
                        break

    # Extract numbers from context
    shares = _extract_number(context, patterns=[
        r"(\d+[.,]?\d*)\s*(?:Stk|pcs|shares|parts|Anteile|actions)",
        r"(?:Stk|Anzahl|Quantity|Nombre)[:\s]*(\d+[.,]?\d*)",
        r"(\d+[.,]?\d*)\s*(?:x\s)",
    ])

    avg_cost = _extract_number(context, patterns=[
        r"(?:Durchschnittskurs|Avg\.?\s*(?:cost|price)|Prix\s*moyen|Kaufkurs)[:\s]*(?:EUR\s*)?(\d+[.,]?\d*)",
        r"(?:Einstandskurs|Cost\s*basis)[:\s]*(?:EUR\s*)?(\d+[.,]?\d*)",
    ])

    current_price = _extract_number(context, patterns=[
        r"(?:Kurs|Price|Cours|Current)[:\s]*(?:EUR\s*)?(\d+[.,]?\d*)",
        r"(?:Aktueller\s*Kurs)[:\s]*(?:EUR\s*)?(\d+[.,]?\d*)",
    ])

    value = _extract_number(context, patterns=[
        r"(?:Wert|Value|Valeur|Gegenwert)[:\s]*(?:EUR\s*)?(\d+[.,]?\d*)",
        r"EUR\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
    ])

    # If we have value and shares but not avg_cost, estimate
    if shares and value and not avg_cost and current_price:
        avg_cost = current_price  # Rough estimate

    if not shares:
        shares = 0
    if not avg_cost:
        avg_cost = current_price or 0

    return {
        "isin": isin,
        "ticker": ticker,
        "name": name or isin,
        "shares": shares,
        "avg_cost": avg_cost,
        "current_price": current_price or 0,
        "value": value or 0,
        "market": market,
        "asset_type": _guess_asset_type(name, isin),
    }


def _extract_number(text: str, patterns: list[str]) -> float:
    """Try multiple regex patterns to extract a number."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num_str = match.group(1).replace(",", ".")
            # Handle European thousands separator
            parts = num_str.split(".")
            if len(parts) > 2:
                # 1.234.56 -> 1234.56
                num_str = "".join(parts[:-1]) + "." + parts[-1]
            try:
                return float(num_str)
            except ValueError:
                continue
    return 0.0


def _guess_asset_type(name: str, isin: str) -> str:
    """Guess if position is stock, ETF, or SCPI."""
    name_lower = (name or "").lower()
    if any(kw in name_lower for kw in ["etf", "ishares", "vanguard", "lyxor", "amundi", "spdr", "xtrackers"]):
        return "ETF"
    if any(kw in name_lower for kw in ["scpi", "opci", "reit", "real estate", "immobilier"]):
        return "SCPI"
    return "stock"


def parse_tr_csv(file_content: str) -> list[dict]:
    """
    Parse a manual CSV export with columns:
    Ticker,Name,Shares,AvgCost,Market,Sector,AssetType
    """
    import csv
    positions = []
    reader = csv.DictReader(io.StringIO(file_content))

    for row in reader:
        ticker = (row.get("Ticker") or row.get("ticker") or row.get("Symbol") or "").strip().upper()
        if not ticker:
            continue

        positions.append({
            "ticker": ticker,
            "name": row.get("Name") or row.get("name") or ticker,
            "shares": float(row.get("Shares") or row.get("shares") or row.get("Quantity") or 0),
            "avg_cost": float(row.get("AvgCost") or row.get("avg_cost") or row.get("Cost") or 0),
            "market": row.get("Market") or row.get("market") or "US",
            "sector": row.get("Sector") or row.get("sector") or "",
            "asset_type": row.get("AssetType") or row.get("asset_type") or "stock",
            "isin": row.get("ISIN") or row.get("isin") or "",
        })

    return positions


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber or PyPDF2."""
    try:
        import pdfplumber
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
            text += "\n"
        pdf.close()
        return text
    except ImportError:
        pass

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            text += "\n"
        return text
    except ImportError:
        pass

    return ""
