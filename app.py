"""
Investment Watcher — Main Application
Streamlit-based portfolio tracker with AI investment intelligence.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import hashlib
import json
import time
from datetime import datetime

import database as db
import market_data as md
import news_fetcher as nf
import ai_engine as ai
import portfolio as pf
import tr_importer as tri

# --- Page Config ---

st.set_page_config(
    page_title="Investment Watcher",
    page_icon="W",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Theme ---

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global */
    .stApp {
        background: #0a0f0d;
        color: #e0e0e0;
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0d1510 !important;
        border-right: 1px solid #1a2f22;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] label {
        color: #c0c0c0 !important;
    }

    /* Headers */
    h1, h2, h3 { color: #e8e8e8 !important; font-weight: 600 !important; }
    h1 { font-size: 1.6rem !important; letter-spacing: -0.02em; }
    h2 { font-size: 1.25rem !important; }
    h3 { font-size: 1.05rem !important; }

    /* Cards */
    .metric-card {
        background: linear-gradient(145deg, #111f17, #0d1510);
        border: 1px solid #1a2f22;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 10px;
    }
    .metric-label { color: #7a8a7f; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
    .metric-value { color: #e8e8e8; font-size: 1.5rem; font-weight: 700; }
    .metric-delta-pos { color: #34d399; font-size: 0.85rem; font-weight: 500; }
    .metric-delta-neg { color: #f87171; font-size: 0.85rem; font-weight: 500; }

    /* Signal cards */
    .signal-card {
        background: linear-gradient(145deg, #111f17, #0d1510);
        border: 1px solid #1a2f22;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .signal-buy { border-left: 4px solid #34d399; }
    .signal-sell { border-left: 4px solid #f87171; }
    .signal-hold { border-left: 4px solid #fbbf24; }
    .signal-watch { border-left: 4px solid #60a5fa; }

    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .badge-buy { background: #064e3b; color: #34d399; }
    .badge-sell { background: #450a0a; color: #f87171; }
    .badge-hold { background: #451a03; color: #fbbf24; }
    .badge-watch { background: #172554; color: #60a5fa; }
    .badge-high { background: #064e3b; color: #34d399; }
    .badge-medium { background: #451a03; color: #fbbf24; }
    .badge-low { background: #1e1e1e; color: #999; }

    /* Tables */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox select,
    div[data-baseweb="select"] > div {
        background: #111f17 !important;
        border: 1px solid #1a2f22 !important;
        color: #e0e0e0 !important;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #065f46, #047857) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.4rem 1.2rem !important;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #047857, #059669) !important;
        box-shadow: 0 4px 12px rgba(5, 120, 87, 0.3) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #7a8a7f;
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        background: #111f17;
        color: #34d399;
        border-bottom: 2px solid #34d399;
    }

    /* Expanders */
    .streamlit-expanderHeader { color: #c0c0c0 !important; background: #111f17 !important; border-radius: 8px; }

    /* Plotly chart backgrounds */
    .js-plotly-plot .plotly .bg { fill: #0a0f0d !important; }

    /* Divider */
    hr { border-color: #1a2f22 !important; }

    /* Status text */
    .status-text { font-size: 0.8rem; color: #7a8a7f; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)


# --- Auth ---

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def check_auth():
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = ""
    return bool(st.session_state.get("user_id"))


def auth_page():
    st.markdown("# Investment Watcher")
    st.markdown("Portfolio tracker with AI-powered investment intelligence")
    st.write("")

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login", key="login_btn"):
            user = db.get_user(username)
            if user and user["password_hash"] == hash_pw(password):
                st.session_state["user_id"] = user["id"]
                st.session_state["username"] = user["username"]
                st.rerun()
            else:
                st.error("Invalid credentials.")

    with tab_register:
        new_user = st.text_input("Choose username", key="reg_user")
        new_pw = st.text_input("Choose password", type="password", key="reg_pw")
        if st.button("Register", key="reg_btn"):
            if len(new_user) < 2 or len(new_pw) < 4:
                st.warning("Username must be 2+ chars, password 4+ chars.")
            else:
                uid = db.create_user(new_user, hash_pw(new_pw))
                if uid:
                    st.session_state["user_id"] = uid
                    st.session_state["username"] = new_user
                    st.rerun()
                else:
                    st.error("Username already taken.")


# --- Helpers ---

def metric_card(label: str, value: str, delta: str = "", is_positive: bool = True):
    delta_class = "metric-delta-pos" if is_positive else "metric-delta-neg"
    delta_html = f'<div class="{delta_class}">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def signal_card(signal: dict):
    action = signal.get("action", "WATCH").upper()
    css_class = f"signal-{action.lower()}" if action.lower() in ("buy", "sell", "hold", "watch") else "signal-watch"
    badge_class = f"badge-{action.lower()}" if action.lower() in ("buy", "sell", "hold", "watch") else "badge-watch"
    conf = signal.get("confidence", "MEDIUM").upper()
    conf_class = f"badge-{conf.lower()}" if conf.lower() in ("high", "medium", "low") else "badge-medium"
    tf = signal.get("timeframe", "")
    in_pf = " (in portfolio)" if signal.get("in_portfolio") else " (new opportunity)"
    risk = signal.get("risk_level", "")

    st.markdown(f"""
    <div class="signal-card {css_class}">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
            <span style="font-size:1.1rem; font-weight:600; color:#e8e8e8;">{signal.get('ticker', '')}</span>
            <span style="color:#7a8a7f; font-size:0.85rem;">{signal.get('name', '')}</span>
            <span class="badge {badge_class}">{action}</span>
            <span class="badge {conf_class}">{conf}</span>
            {"<span class='badge badge-low'>" + tf.replace("_", " ") + "</span>" if tf else ""}
        </div>
        <div style="color:#c0c0c0; font-size:0.9rem; font-weight:500; margin-bottom:6px;">
            {signal.get('summary', '')}
        </div>
        <div style="color:#7a8a7f; font-size:0.82rem;">
            {signal.get('reasoning', '')}
        </div>
        <div class="status-text" style="margin-top:6px;">{in_pf} {"| Risk: " + risk if risk else ""}</div>
    </div>
    """, unsafe_allow_html=True)


def plotly_dark_layout(fig, title: str = ""):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0f0d",
        plot_bgcolor="#0a0f0d",
        title=dict(text=title, font=dict(size=14, color="#c0c0c0")),
        font=dict(family="Inter", color="#7a8a7f"),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#1a2f22", zerolinecolor="#1a2f22"),
        yaxis=dict(gridcolor="#1a2f22", zerolinecolor="#1a2f22"),
    )
    return fig


# --- Main Pages ---

def page_dashboard(user_id: str):
    positions = db.get_positions(user_id)

    if not positions:
        st.info("No positions yet. Go to Portfolio to add positions or import from Trade Republic.")
        return

    # Fetch prices
    with st.spinner("Fetching latest prices..."):
        prices = md.batch_prices(positions)

    # Compute portfolio
    port = pf.compute_portfolio(positions, prices)
    pf.take_snapshot(user_id, port)

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Portfolio Value", f"EUR {port['total_value']:,.2f}")
    with col2:
        metric_card(
            "Total P&L",
            f"EUR {port['total_pnl']:+,.2f}",
            f"{port['total_pnl_pct']:+.1f}%",
            port['total_pnl'] >= 0,
        )
    with col3:
        metric_card("Positions", str(len(port['positions'])))
    with col4:
        day_pnl = sum(p["day_pnl"] for p in port["positions"])
        metric_card("Day P&L", f"EUR {day_pnl:+,.2f}", is_positive=day_pnl >= 0)

    st.write("")

    # Charts row
    col_chart, col_alloc = st.columns([3, 2])

    with col_chart:
        # Portfolio value over time
        history = pf.get_portfolio_history(user_id)
        if len(history) > 1:
            df_hist = pd.DataFrame(history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_hist["date"], y=df_hist["value"],
                mode="lines", name="Value",
                line=dict(color="#34d399", width=2),
                fill="tozeroy", fillcolor="rgba(52,211,153,0.1)",
            ))
            fig.add_trace(go.Scatter(
                x=df_hist["date"], y=df_hist["cost"],
                mode="lines", name="Cost Basis",
                line=dict(color="#7a8a7f", width=1, dash="dot"),
            ))
            fig = plotly_dark_layout(fig, "Portfolio Value Over Time")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<p class="status-text">Portfolio history chart will appear after 2+ days of data.</p>', unsafe_allow_html=True)

    with col_alloc:
        # Allocation donut
        if port["by_sector"]:
            labels = list(port["by_sector"].keys())
            values = [port["by_sector"][s]["value"] for s in labels]
            colors = ["#34d399", "#60a5fa", "#fbbf24", "#f87171", "#a78bfa",
                      "#fb923c", "#2dd4bf", "#e879f9", "#94a3b8"]
            fig = go.Figure(data=[go.Pie(
                labels=labels, values=values,
                hole=0.55,
                marker=dict(colors=colors[:len(labels)]),
                textinfo="label+percent",
                textfont=dict(size=11),
            )])
            fig = plotly_dark_layout(fig, "Sector Allocation")
            st.plotly_chart(fig, use_container_width=True)

    # Positions table
    st.markdown("### Positions")
    rows = []
    for p in port["positions"]:
        rows.append({
            "Ticker": p["ticker"],
            "Name": p["name"][:30],
            "Shares": p["shares"],
            "Avg Cost": f"{p['avg_cost']:.2f}",
            "Price": f"{p['current_price']:.2f}",
            "Value (EUR)": f"{p['value']:,.2f}",
            "P&L": f"{p['pnl']:+,.2f}",
            "P&L %": f"{p['pnl_pct']:+.1f}%",
            "Day": f"{p['day_change_pct']:+.1f}%",
            "Weight": f"{p['weight']:.1f}%",
        })
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Market allocation
    if port["by_market"] and len(port["by_market"]) > 1:
        st.markdown("### Market Breakdown")
        cols = st.columns(len(port["by_market"]))
        for i, (market, data) in enumerate(port["by_market"].items()):
            with cols[i]:
                metric_card(
                    market,
                    f"EUR {data['value']:,.0f}",
                    f"{data['weight']:.1f}% | P&L {data['pnl_pct']:+.1f}%",
                    data["pnl"] >= 0,
                )


def page_portfolio(user_id: str):
    tab_manage, tab_import = st.tabs(["Manage Positions", "Import"])

    with tab_manage:
        st.markdown("### Add Position")
        col1, col2, col3 = st.columns(3)
        with col1:
            ticker = st.text_input("Ticker", placeholder="e.g. AAPL, MC.PA")
            name = st.text_input("Company Name", placeholder="e.g. Apple Inc.")
        with col2:
            shares = st.number_input("Shares", min_value=0.0, step=0.01, format="%.4f")
            avg_cost = st.number_input("Avg Cost (EUR)", min_value=0.0, step=0.01, format="%.2f")
        with col3:
            market = st.selectbox("Market", ["US", "Paris", "Euronext", "Amsterdam", "Frankfurt", "London", "Milan", "Madrid", "Casablanca"])
            asset_type = st.selectbox("Asset Type", ["stock", "ETF", "SCPI"])
            sector = st.text_input("Sector", placeholder="e.g. Technology")

        if st.button("Add Position"):
            if ticker and shares > 0:
                db.add_position(user_id, ticker, name or ticker, shares, avg_cost,
                                asset_type=asset_type, market=market, sector=sector)
                st.success(f"Added {ticker}")
                st.rerun()
            else:
                st.warning("Ticker and shares are required.")

        # Current positions
        st.markdown("---")
        st.markdown("### Current Positions")
        positions = db.get_positions(user_id)
        if positions:
            for pos in positions:
                col_info, col_edit, col_del = st.columns([4, 2, 1])
                with col_info:
                    st.markdown(
                        f"**{pos['ticker']}** — {pos['name'][:35]} | "
                        f"{pos['shares']} shares @ EUR {pos['avg_cost']:.2f} | "
                        f"{pos['market']} | {pos['asset_type']}"
                    )
                with col_edit:
                    new_shares = st.number_input(
                        "Shares", value=pos["shares"], min_value=0.0,
                        step=0.01, key=f"sh_{pos['id']}", format="%.4f", label_visibility="collapsed"
                    )
                    if new_shares != pos["shares"]:
                        db.update_position(pos["id"], shares=new_shares)
                        st.rerun()
                with col_del:
                    if st.button("x", key=f"del_{pos['id']}"):
                        db.delete_position(pos["id"])
                        st.rerun()
        else:
            st.info("No positions yet.")

    with tab_import:
        st.markdown("### Import from Trade Republic")
        st.markdown("Upload your Trade Republic portfolio statement PDF or a CSV file.")

        uploaded = st.file_uploader("Upload file", type=["pdf", "csv"], key="tr_upload")

        if uploaded:
            if uploaded.name.lower().endswith(".pdf"):
                with st.spinner("Parsing Trade Republic PDF..."):
                    file_bytes = uploaded.read()
                    parsed = tri.parse_tr_portfolio_pdf(file_bytes)
            else:
                content = uploaded.read().decode("utf-8", errors="replace")
                parsed = tri.parse_tr_csv(content)

            if parsed:
                st.success(f"Found {len(parsed)} positions")

                # Preview
                preview_rows = []
                for p in parsed:
                    preview_rows.append({
                        "Ticker": p.get("ticker") or p.get("isin", "?"),
                        "Name": p["name"][:40],
                        "Shares": p["shares"],
                        "Avg Cost": p.get("avg_cost", 0),
                        "Market": p.get("market", "US"),
                        "Type": p.get("asset_type", "stock"),
                    })
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

                st.markdown("Edit tickers if needed before importing (some ISINs may not auto-resolve).")

                # Editable tickers
                edited = []
                for i, p in enumerate(parsed):
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        new_ticker = st.text_input(
                            "Ticker", value=p.get("ticker") or "", key=f"imp_t_{i}",
                            placeholder="Enter Yahoo ticker"
                        )
                    with col2:
                        st.markdown(f"{p['name'][:40]} — {p['shares']} shares — {p.get('market', 'US')}")
                    edited.append({**p, "ticker": new_ticker or p.get("ticker", "")})

                if st.button("Import All Positions"):
                    imported = 0
                    for p in edited:
                        if p["ticker"] and p["shares"] > 0:
                            db.add_position(
                                user_id, p["ticker"], p["name"],
                                p["shares"], p.get("avg_cost", 0),
                                asset_type=p.get("asset_type", "stock"),
                                market=p.get("market", "US"),
                            )
                            imported += 1
                    st.success(f"Imported {imported} positions")
                    st.rerun()
            else:
                st.warning("Could not parse any positions from the file. Check format.")

        # CSV template
        st.markdown("---")
        st.markdown("### CSV Template")
        st.code("Ticker,Name,Shares,AvgCost,Market,Sector,AssetType\nAAPL,Apple Inc.,10,150.00,US,Technology,stock\nMC.PA,LVMH,5,850.00,Paris,Consumer,stock", language="csv")


def page_signals(user_id: str):
    user = db.get_user_by_id(user_id) if hasattr(db, "get_user_by_id") else None

    # Get LLM settings from session or DB
    provider = st.session_state.get("llm_provider", "")
    api_key = st.session_state.get("llm_api_key", "")
    model = st.session_state.get("llm_model", "")

    if not provider or not api_key:
        st.warning("Configure your AI provider in Settings before requesting signals.")
        return

    positions = db.get_positions(user_id)

    st.markdown("### AI Investment Intelligence")
    st.markdown("Analyzes real-time news, macro conditions, and your portfolio to generate actionable signals.")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"Provider: **{ai.PROVIDERS.get(provider, {}).get('name', provider)}** | Model: **{model}**")
    with col2:
        run_analysis = st.button("Get Signals", type="primary")

    if run_analysis:
        if not positions:
            st.warning("Add positions to your portfolio first.")
            return

        progress = st.progress(0, text="Fetching market prices...")

        # Step 1: Prices
        prices = md.batch_prices(positions)
        progress.progress(20, text="Fetching news and market intelligence...")

        # Step 2: News
        news_data = nf.fetch_all_for_portfolio(positions)
        news_text = nf.format_news_for_llm(news_data)
        progress.progress(50, text="Gathering fundamentals...")

        # Step 3: Fundamentals
        fundamentals = {}
        for pos in positions[:10]:  # Limit to avoid rate limiting
            fund = md.get_fundamentals(pos["ticker"], pos.get("market", "US"))
            if fund and not fund.get("error"):
                fundamentals[pos["ticker"]] = fund
        progress.progress(70, text="AI is analyzing... this may take 30-60 seconds...")

        # Step 4: AI analysis
        result = ai.run_analysis(provider, api_key, model, positions, prices, news_text, fundamentals)
        progress.progress(100, text="Done!")
        time.sleep(0.5)
        progress.empty()

        if not result.get("success"):
            st.error(f"AI Analysis failed: {result.get('error', 'Unknown error')}")
            return

        # Store in session and DB
        st.session_state["last_signals"] = result

        # Save signals to DB
        for sig in result.get("signals", []):
            db.save_signal(
                user_id=user_id,
                signal_type="ai_analysis",
                summary=sig.get("summary", ""),
                reasoning=sig.get("reasoning", ""),
                ticker=sig.get("ticker", ""),
                action=sig.get("action", ""),
                confidence=sig.get("confidence", ""),
                raw_response="",
            )

    # Display results
    result = st.session_state.get("last_signals")
    if result and result.get("success"):
        # Market summary
        if result.get("market_summary"):
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Market Summary</div>
                <div style="color:#c0c0c0; font-size:0.92rem; margin-top:6px;">{result['market_summary']}</div>
            </div>
            """, unsafe_allow_html=True)

        # Portfolio assessment
        if result.get("portfolio_assessment"):
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Portfolio Assessment</div>
                <div style="color:#c0c0c0; font-size:0.92rem; margin-top:6px;">{result['portfolio_assessment']}</div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Signals
        signals = result.get("signals", [])
        if signals:
            # Filter tabs
            all_actions = sorted(set(s.get("action", "WATCH").upper() for s in signals))
            filter_tabs = ["All"] + all_actions
            sel_tab = st.radio("Filter", filter_tabs, horizontal=True, label_visibility="collapsed")

            filtered = signals if sel_tab == "All" else [s for s in signals if s.get("action", "").upper() == sel_tab]

            for sig in filtered:
                signal_card(sig)
        else:
            st.info("No signals generated. The AI may have returned an unparseable response.")

        # Macro outlook
        if result.get("macro_outlook"):
            with st.expander("Macro Outlook"):
                st.markdown(result["macro_outlook"])

        # Risk warnings
        if result.get("risk_warnings"):
            with st.expander("Risk Warnings"):
                for w in result["risk_warnings"]:
                    st.markdown(f"- {w}")

        # Raw response (debug)
        if result.get("raw_text"):
            with st.expander("Raw AI Response"):
                st.text(result["raw_text"])

        # Timestamp
        ts = result.get("timestamp", "")
        if ts:
            st.markdown(f'<p class="status-text">Analysis generated at {ts[:19]}</p>', unsafe_allow_html=True)

    else:
        # Show past signals
        past = db.get_signals(user_id, 20)
        if past:
            st.markdown("### Recent Signals")
            for s in past:
                action = s.get("action", "")
                badge = f"badge-{action.lower()}" if action.lower() in ("buy", "sell", "hold", "watch") else "badge-watch"
                st.markdown(f"""
                <div class="signal-card signal-{action.lower() if action.lower() in ('buy','sell','hold','watch') else 'watch'}">
                    <span class="badge {badge}">{action}</span>
                    <strong>{s.get('ticker', '')}</strong> — {s.get('summary', '')}
                    <div class="status-text">{s.get('created_at', '')[:16]}</div>
                </div>
                """, unsafe_allow_html=True)


def page_news(user_id: str):
    positions = db.get_positions(user_id)

    st.markdown("### Market News Feed")

    col1, col2 = st.columns([3, 1])
    with col2:
        refresh = st.button("Refresh News")

    if refresh or "news_data" not in st.session_state:
        with st.spinner("Fetching news..."):
            st.session_state["news_data"] = nf.fetch_all_for_portfolio(positions) if positions else {
                "market": nf.fetch_market_news(8),
                "macro": nf.fetch_macro_news(5),
                "by_ticker": {},
                "by_sector": {},
            }

    news_data = st.session_state.get("news_data", {})

    # Market news
    if news_data.get("market"):
        st.markdown("#### Market Headlines")
        for item in news_data["market"][:10]:
            st.markdown(f"""
            <div class="metric-card" style="padding:12px 16px; margin-bottom:6px;">
                <div style="color:#7a8a7f; font-size:0.72rem;">{item['source']} {'| ' + item['published'][:10] if item.get('published') else ''}</div>
                <div style="color:#e0e0e0; font-size:0.88rem; font-weight:500;">
                    <a href="{item.get('url', '#')}" target="_blank" style="color:#e0e0e0; text-decoration:none;">{item['title']}</a>
                </div>
                {"<div style='color:#7a8a7f; font-size:0.8rem; margin-top:4px;'>" + item['summary'][:150] + "...</div>" if item.get('summary') else ""}
            </div>
            """, unsafe_allow_html=True)

    # Macro news
    if news_data.get("macro"):
        st.markdown("#### Central Banks & Macro")
        for item in news_data["macro"][:6]:
            st.markdown(f"""
            <div class="metric-card" style="padding:12px 16px; margin-bottom:6px;">
                <div style="color:#7a8a7f; font-size:0.72rem;">{item['source']}</div>
                <div style="color:#e0e0e0; font-size:0.88rem;">
                    <a href="{item.get('url', '#')}" target="_blank" style="color:#e0e0e0; text-decoration:none;">{item['title']}</a>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Per-ticker news
    if news_data.get("by_ticker"):
        st.markdown("#### Your Holdings")
        for ticker, items in news_data["by_ticker"].items():
            if items:
                with st.expander(f"{ticker} ({len(items)} articles)"):
                    for item in items[:5]:
                        st.markdown(f"- [{item['source']}] [{item['title']}]({item.get('url', '#')})")


def page_settings(user_id: str):
    st.markdown("### AI Provider Settings")
    st.markdown("Configure your LLM provider for investment analysis. All API calls are made directly from your browser — keys are stored locally.")

    # Current settings
    current_provider = st.session_state.get("llm_provider", "")
    current_key = st.session_state.get("llm_api_key", "")
    current_model = st.session_state.get("llm_model", "")

    provider = st.selectbox(
        "Provider",
        list(ai.PROVIDERS.keys()),
        index=list(ai.PROVIDERS.keys()).index(current_provider) if current_provider in ai.PROVIDERS else 0,
        format_func=lambda x: ai.PROVIDERS[x]["name"],
    )

    provider_info = ai.PROVIDERS[provider]

    api_key = st.text_input(
        f"API Key ({provider_info['env_key']})",
        value=current_key if current_provider == provider else "",
        type="password",
        help=f"Get your key from the {provider_info['name']} dashboard.",
    )

    model = st.selectbox(
        "Model",
        provider_info["models"],
        index=provider_info["models"].index(current_model) if current_model in provider_info["models"] else 0,
    )

    if st.button("Save Settings"):
        st.session_state["llm_provider"] = provider
        st.session_state["llm_api_key"] = api_key
        st.session_state["llm_model"] = model
        db.update_user_llm(user_id, provider, api_key, model)
        st.success("Settings saved.")

    # Provider guide
    st.markdown("---")
    st.markdown("### Provider Guide")
    guides = {
        "anthropic": "Get your API key at [console.anthropic.com](https://console.anthropic.com/). Pay-per-use, Sonnet is the best value.",
        "openai": "Get your API key at [platform.openai.com](https://platform.openai.com/api-keys). GPT-4o-mini is cheapest.",
        "google": "Get your API key at [aistudio.google.com](https://aistudio.google.com/app/apikey). Gemini Flash has a generous free tier.",
        "mistral": "Get your API key at [console.mistral.ai](https://console.mistral.ai/). Mistral Small is affordable.",
        "groq": "Get your API key at [console.groq.com](https://console.groq.com/). Free tier available, very fast.",
        "openrouter": "Get your API key at [openrouter.ai](https://openrouter.ai/keys). Access many models through one key.",
    }
    st.markdown(guides.get(provider, ""))

    # Load saved settings on first run
    if not current_provider:
        user = db.get_user(st.session_state.get("username", ""))
        if user and user.get("llm_provider"):
            st.session_state["llm_provider"] = user["llm_provider"]
            st.session_state["llm_api_key"] = user["llm_api_key"]
            st.session_state["llm_model"] = user["llm_model"]


# --- Sidebar Navigation ---

def main():
    if not check_auth():
        auth_page()
        return

    user_id = st.session_state["user_id"]
    username = st.session_state.get("username", "")

    # Load LLM settings from DB if not in session
    if "llm_provider" not in st.session_state or not st.session_state["llm_provider"]:
        user = db.get_user(username)
        if user:
            st.session_state["llm_provider"] = user.get("llm_provider", "")
            st.session_state["llm_api_key"] = user.get("llm_api_key", "")
            st.session_state["llm_model"] = user.get("llm_model", "")

    with st.sidebar:
        st.markdown("# Investment Watcher")
        st.markdown(f"Signed in as **{username}**")
        st.markdown("---")

        page = st.radio(
            "Navigation",
            ["Dashboard", "Portfolio", "AI Signals", "News", "Settings"],
            label_visibility="collapsed",
        )

        st.markdown("---")

        # Quick status
        positions = db.get_positions(user_id)
        st.markdown(f"Positions: **{len(positions)}**")
        provider = st.session_state.get("llm_provider", "")
        if provider:
            st.markdown(f"AI: **{ai.PROVIDERS.get(provider, {}).get('name', 'N/A')}**")
        else:
            st.markdown("AI: **Not configured**")

        st.markdown("---")
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Route
    if page == "Dashboard":
        st.markdown("## Dashboard")
        page_dashboard(user_id)
    elif page == "Portfolio":
        st.markdown("## Portfolio")
        page_portfolio(user_id)
    elif page == "AI Signals":
        st.markdown("## AI Signals")
        page_signals(user_id)
    elif page == "News":
        page_news(user_id)
    elif page == "Settings":
        page_settings(user_id)


if __name__ == "__main__":
    main()
