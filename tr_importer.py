"""
Investment Watcher — Trade Republic Importer
Parses Trade Republic PDF portfolio statements (French format).
Also supports manual CSV upload.

TR French Statement Format:
--------------------------
Each position block looks like:

  0,285659 titre(s)    Alphabet Inc.
                        Reg. Shs Cap.Stk Cl. A DL-,001
                        ISIN : US02079K3059
                        Pays d'enregistrement: États-Unis
                        264,45              <-- price per share
                        26/02/2026          <-- date
                        75,54               <-- total value EUR

Multiple accounts may appear (CTO, PEA) with headers like:
  COMPTE-TITRES ORDINAIRE
  PLAN D'ÉPARGNE EN ACTIONS
"""

import re
import io
from typing import Optional


# ISIN pattern
ISIN_PATTERN = re.compile(r"ISIN\s*:\s*([A-Z]{2}[A-Z0-9]{10})")

# Account type detection
ACCOUNT_PATTERNS = {
    "CTO": re.compile(r"COMPTE-TITRES\s+ORDINAIRE", re.IGNORECASE),
    "PEA": re.compile(r"PLAN\s+D['\u2019]?\s*EPARGNE|PLAN\s+D['\u2019]?\s*\u00C9PARGNE", re.IGNORECASE),
}

# ISIN to Yahoo Finance ticker mapping
ISIN_TICKER_MAP = {
    # --- US Stocks ---
    "US0378331005": ("AAPL", "Apple Inc.", "US", "Technology"),
    "US5949181045": ("MSFT", "Microsoft Corp.", "US", "Technology"),
    "US0231351067": ("AMZN", "Amazon.com Inc.", "US", "Technology"),
    "US02079K3059": ("GOOGL", "Alphabet Inc.", "US", "Technology"),
    "US30303M1027": ("META", "Meta Platforms Inc.", "US", "Technology"),
    "US88160R1014": ("TSLA", "Tesla Inc.", "US", "Technology"),
    "US67066G1040": ("NVDA", "NVIDIA Corp.", "US", "Technology"),
    "US4781601046": ("JNJ", "Johnson & Johnson", "US", "Healthcare"),
    "US92826C8394": ("V", "Visa Inc.", "US", "Finance"),
    "US46625H1005": ("JPM", "JPMorgan Chase", "US", "Finance"),
    "US0846707026": ("BRK-B", "Berkshire Hathaway B", "US", "Finance"),
    "US7427181091": ("PG", "Procter & Gamble", "US", "Consumer"),
    "US4592001014": ("IBM", "IBM Corp.", "US", "Technology"),
    "US2546871060": ("DIS", "Walt Disney", "US", "Consumer"),
    "US0079031078": ("AMD", "Advanced Micro Devices", "US", "Technology"),
    "US7170811035": ("PFE", "Pfizer Inc.", "US", "Healthcare"),
    "US8740391003": ("TSM", "Taiwan Semiconductor", "US", "Technology"),
    "US68389X1054": ("ORCL", "Oracle Corp.", "US", "Technology"),
    "US5949724083": ("MSTR", "Strategy Inc.", "US", "Technology"),
    # --- European Stocks ---
    "NL0010273215": ("ASML.AS", "ASML Holding", "Amsterdam", "Technology"),
    "FR0000121014": ("MC.PA", "LVMH", "Paris", "Consumer"),
    "FR0000120271": ("TTE.PA", "TotalEnergies SE", "Paris", "Energy"),
    "DE0007164600": ("SAP.DE", "SAP SE", "Frankfurt", "Technology"),
    "DE0007236101": ("SIE.DE", "Siemens AG", "Frankfurt", "Industrial"),
    "FR0000120578": ("SAN.PA", "Sanofi", "Paris", "Healthcare"),
    "NL0000235190": ("AIR.PA", "Airbus SE", "Paris", "Industrial"),
    "FR0000131104": ("BNP.PA", "BNP Paribas", "Paris", "Finance"),
    "FR0000120321": ("OR.PA", "L'Oreal", "Paris", "Consumer"),
    "FR0000125338": ("CAP.PA", "Capgemini", "Paris", "Technology"),
    "FR0000121972": ("SE.PA", "Schneider Electric", "Paris", "Industrial"),
    "NL0000226223": ("STM.PA", "STMicroelectronics N.V.", "Paris", "Technology"),
    "FR001400X2S4": ("ATOS.PA", "Atos SE", "Paris", "Technology"),
    "DE000A0DJ6J9": ("S92.DE", "SMA Solar Technology AG", "Frankfurt", "Energy"),
    # --- ETFs ---
    "IE00B3WJKG14": ("IUIT.L", "iShares S&P 500 Info Tech ETF", "London", "ETF-Technology"),
    "IE00B4ND3602": ("IGLN.L", "iShares Physical Gold ETC", "London", "ETF-Commodities"),
    "IE00BM67HM91": ("XDWE.DE", "Xtrackers MSCI World Energy ETF", "Frankfurt", "ETF-Energy"),
    "IE000NXF88S1": ("OIH8.DE", "VanEck Oil Services UCITS ETF", "Frankfurt", "ETF-Energy"),
    "IE00B5BMR087": ("CSPX.L", "iShares Core S&P 500", "London", "ETF-US"),
    "IE00B4L5Y983": ("IWDA.AS", "iShares Core MSCI World", "Amsterdam", "ETF-Global"),
    "LU0392494562": ("MEUD.PA", "Lyxor Euro Stoxx 50", "Paris", "ETF-Europe"),
    "IE00BKM4GZ66": ("EIMI.L", "iShares Core EM IMI", "London", "ETF-EM"),
    # --- ELTIF / Alternative ---
    "LU3176111881": ("EQT-ELTIF", "EQT Nexus Fund ELTIF", "Luxembourg", "Alternative"),
    # --- African ---
    "ZAE000084992": ("EXX.JO", "Exxaro Resources Ltd.", "Johannesburg", "Energy"),
}


def parse_tr_portfolio_pdf(file_bytes: bytes) -> list[dict]:
    """
    Parse Trade Republic portfolio statement PDF (French format).
    Returns list of position dicts with account info.
    """
    text = _extract_pdf_text(file_bytes)
    if not text:
        return []

    positions = []
    current_account = "CTO"

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Detect account type
        for acct_type, pattern in ACCOUNT_PATTERNS.items():
            if pattern.search(line):
                current_account = acct_type

        # Look for position start: "X,XXXX titre(s)"
        shares_match = re.match(r"(\d+(?:[.,]\d+)?)\s*titre\(s\)\s*(.*)", line)
        if shares_match:
            shares_str = shares_match.group(1).replace(",", ".")
            shares = float(shares_str)
            remainder = shares_match.group(2).strip()

            # Collect all lines of this position block until next position or section end
            block_lines = [remainder] if remainder else []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                # Stop at next position
                if re.match(r"\d+(?:[.,]\d+)?\s*titre\(s\)", next_line):
                    break
                # Stop at section markers
                if "NOMBRE DE POSITIONS" in next_line:
                    break
                if next_line.startswith("Veuillez noter"):
                    break
                if any(p.search(next_line) for p in ACCOUNT_PATTERNS.values()):
                    break
                # Stop at page headers
                if "TRADE REPUBLIC BANK" in next_line:
                    break
                if next_line:
                    block_lines.append(next_line)
                j += 1

            position = _parse_position_block(shares, block_lines, current_account)
            if position:
                positions.append(position)

            i = j
            continue

        i += 1

    return positions


def _parse_position_block(shares: float, lines: list[str], account: str) -> Optional[dict]:
    """Parse a position block into a structured dict."""
    if not lines:
        return None

    name = ""
    description = ""
    isin = ""
    country = ""
    numeric_values = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # ISIN
        isin_match = ISIN_PATTERN.search(line)
        if isin_match:
            isin = isin_match.group(1)
            continue

        # Country
        if "enregistrement" in line.lower():
            country_match = re.search(r":\s*(.+)", line)
            if country_match:
                country = country_match.group(1).strip()
            continue

        # Skip "Relevé de transaction" lines
        if "transaction" in line.lower() and "relev" in line.lower():
            continue

        # Date pattern (DD/MM/YYYY) — skip
        if re.match(r"\d{2}/\d{2}/\d{4}$", line):
            continue

        # Pure number (price or value)
        num = _parse_french_number(line)
        if num is not None:
            numeric_values.append(num)
            continue

        # Otherwise it's name or description text
        if not name:
            name = line
        elif not description:
            description = line

    # Numeric values: [price_per_share, total_value_eur]
    price = 0.0
    value = 0.0
    if len(numeric_values) >= 2:
        price = numeric_values[0]
        value = numeric_values[-1]
    elif len(numeric_values) == 1:
        price = numeric_values[0]
        value = shares * price

    # ISIN lookup
    known = ISIN_TICKER_MAP.get(isin)
    ticker = ""
    market = "US"
    sector = ""

    if known:
        ticker, mapped_name, market, sector = known
        if not name or len(name) < 3:
            name = mapped_name
    else:
        market = _country_to_market(country)

    asset_type = _guess_asset_type(name, description, sector)

    return {
        "ticker": ticker,
        "name": name,
        "description": description,
        "isin": isin,
        "shares": shares,
        "price_per_share": round(price, 4),
        "value_eur": round(value, 2),
        "avg_cost": round(price, 4),
        "market": market,
        "sector": sector.split("-")[-1] if "-" in sector else sector,
        "asset_type": asset_type,
        "country": country,
        "account": account,
    }


def _parse_french_number(text: str) -> Optional[float]:
    """Parse a French-formatted number: 1.234,56 or 264,45."""
    text = text.strip()
    if not re.match(r"^-?\d[\d.,]*$", text):
        return None
    try:
        if "," in text:
            parts = text.split(",")
            integer_part = parts[0].replace(".", "")
            decimal_part = parts[1] if len(parts) > 1 else "0"
            return float(f"{integer_part}.{decimal_part}")
        else:
            # Pure integer or already dot-decimal
            if text.count(".") > 1:
                return float(text.replace(".", ""))
            return float(text)
    except ValueError:
        return None


def _country_to_market(country: str) -> str:
    """Map French country name to market identifier."""
    country_lower = (country or "").lower()
    mapping = {
        "france": "Paris",
        "tats-unis": "US",  # "États-Unis" without É
        "allemagne": "Frankfurt",
        "pays-bas": "Amsterdam",
        "irlande": "London",
        "luxembourg": "Luxembourg",
        "royaume-uni": "London",
        "italie": "Milan",
        "espagne": "Madrid",
        "afrique du sud": "Johannesburg",
    }
    for key, val in mapping.items():
        if key in country_lower:
            return val
    return "US"


def _guess_asset_type(name: str, description: str, sector: str) -> str:
    """Determine asset type from name/description/sector."""
    combined = f"{name} {description} {sector}".lower()
    if any(kw in combined for kw in ["etf", "ucits", "ishares", "vanguard", "lyxor",
                                      "amundi", "spdr", "xtrackers", "vaneck",
                                      "physical", "open end zt"]):
        return "ETF"
    if any(kw in combined for kw in ["eltif", "nexus", "alternative"]):
        return "Alternative"
    if any(kw in combined for kw in ["scpi", "opci", "reit", "immobilier"]):
        return "SCPI"
    return "stock"


def parse_tr_csv(file_content: str) -> list[dict]:
    """Parse a manual CSV. Columns: Ticker,Name,Shares,AvgCost,Market,Sector,AssetType"""
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
            "account": row.get("Account") or "CTO",
        })
    return positions


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber."""
    import pdfplumber
    pdf = pdfplumber.open(io.BytesIO(file_bytes))
    text = ""
    for page in pdf.pages:
        text += page.extract_text() or ""
        text += "\n"
    pdf.close()
    return text