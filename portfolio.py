"""
Investment Watcher — Portfolio Analytics
P&L calculations, allocation breakdowns, portfolio value tracking.
"""

import json
from datetime import datetime
import database as db


def compute_portfolio(positions: list[dict], prices: dict) -> dict:
    """
    Compute full portfolio analytics.
    Returns {
        "total_value", "total_cost", "total_pnl", "total_pnl_pct",
        "positions": [{...position with live data...}],
        "by_sector", "by_market", "by_asset_type"
    }
    """
    enriched = []
    total_value = 0.0
    total_cost = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        price_info = prices.get(ticker, {})
        current_price = price_info.get("price", 0)
        day_change = price_info.get("change", 0)
        day_change_pct = price_info.get("change_pct", 0)

        shares = pos["shares"]
        avg_cost = pos["avg_cost"]
        value = shares * current_price
        cost = shares * avg_cost
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        day_pnl = shares * day_change

        total_value += value
        total_cost += cost

        enriched.append({
            **pos,
            "current_price": current_price,
            "value": round(value, 2),
            "cost": round(cost, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "day_change": round(day_change, 2),
            "day_change_pct": round(day_change_pct, 2),
            "day_pnl": round(day_pnl, 2),
            "weight": 0,  # filled below
        })

    # Compute weights
    for p in enriched:
        p["weight"] = round((p["value"] / total_value * 100) if total_value > 0 else 0, 1)

    # Sort by value descending
    enriched.sort(key=lambda x: x["value"], reverse=True)

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    return {
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "positions": enriched,
        "by_sector": _group_by(enriched, "sector"),
        "by_market": _group_by(enriched, "market"),
        "by_asset_type": _group_by(enriched, "asset_type"),
    }


def _group_by(positions: list[dict], field: str) -> dict:
    """Group positions by a field. Returns {group: {value, cost, pnl, weight, count}}."""
    groups = {}
    total = sum(p["value"] for p in positions)

    for p in positions:
        key = p.get(field, "Other") or "Other"
        if key not in groups:
            groups[key] = {"value": 0, "cost": 0, "pnl": 0, "count": 0, "tickers": []}
        groups[key]["value"] += p["value"]
        groups[key]["cost"] += p["cost"]
        groups[key]["pnl"] += p["pnl"]
        groups[key]["count"] += 1
        groups[key]["tickers"].append(p["ticker"])

    for key in groups:
        g = groups[key]
        g["value"] = round(g["value"], 2)
        g["cost"] = round(g["cost"], 2)
        g["pnl"] = round(g["pnl"], 2)
        g["weight"] = round((g["value"] / total * 100) if total > 0 else 0, 1)
        g["pnl_pct"] = round((g["pnl"] / g["cost"] * 100) if g["cost"] > 0 else 0, 2)

    return dict(sorted(groups.items(), key=lambda x: x[1]["value"], reverse=True))


def take_snapshot(user_id: str, portfolio: dict):
    """Save daily portfolio snapshot for historical tracking."""
    positions_json = json.dumps([{
        "ticker": p["ticker"],
        "name": p["name"],
        "shares": p["shares"],
        "price": p["current_price"],
        "value": p["value"],
        "pnl": p["pnl"],
    } for p in portfolio["positions"]])

    db.save_snapshot(
        user_id=user_id,
        total_value=portfolio["total_value"],
        total_cost=portfolio["total_cost"],
        positions_json=positions_json,
    )


def get_portfolio_history(user_id: str) -> list[dict]:
    """Get historical portfolio values for charting."""
    snapshots = db.get_snapshots(user_id)
    # Return chronological
    return [
        {
            "date": s["snapshot_date"],
            "value": s["total_value"],
            "cost": s["total_cost"],
            "pnl": round(s["total_value"] - s["total_cost"], 2),
        }
        for s in reversed(snapshots)
    ]


def format_portfolio_summary(portfolio: dict) -> str:
    """Text summary for display or export."""
    lines = [
        f"Portfolio Value: EUR {portfolio['total_value']:,.2f}",
        f"Total Cost: EUR {portfolio['total_cost']:,.2f}",
        f"Total P&L: EUR {portfolio['total_pnl']:+,.2f} ({portfolio['total_pnl_pct']:+.1f}%)",
        f"Positions: {len(portfolio['positions'])}",
        "",
    ]

    for p in portfolio["positions"]:
        lines.append(
            f"  {p['ticker']:8s} {p['name'][:25]:25s} "
            f"{p['shares']:>8.2f} sh  @ EUR {p['current_price']:>8.2f}  "
            f"Val: EUR {p['value']:>10,.2f}  P&L: EUR {p['pnl']:>+10,.2f} ({p['pnl_pct']:>+6.1f}%)  "
            f"Wt: {p['weight']:>5.1f}%"
        )

    return "\n".join(lines)
