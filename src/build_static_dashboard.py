"""Build a self-contained old-money Vercel dashboard from the analytics CSV outputs."""
from __future__ import annotations

from pathlib import Path
import html
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DASHBOARD = ROOT / "dashboard"


def money_cr(value: float) -> str:
    return f"₹{value / 10_000_000:,.2f} Cr"


def money_lakh(value: float) -> str:
    return f"₹{value / 100_000:,.1f}L"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def svg_line(values, labels, width=920, height=260, color="#00f5ff") -> str:
    vals = list(map(float, values))
    mn, mx = min(vals), max(vals)
    pad = 28
    span = max(mx - mn, 1)
    pts = []
    for i, v in enumerate(vals):
        x = pad + i * (width - 2 * pad) / max(len(vals) - 1, 1)
        y = height - pad - ((v - mn) / span) * (height - 2 * pad)
        pts.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad},{height-pad} {poly} {width-pad},{height-pad}"
    ticks = []
    for idx in [0, len(labels)//4, len(labels)//2, 3*len(labels)//4, len(labels)-1]:
        x, _ = pts[idx]
        ticks.append(f'<text x="{x:.1f}" y="{height-5}" text-anchor="middle" class="axis">{html.escape(str(labels[idx]))}</text>')
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Revenue trend chart">
      <defs>
        <linearGradient id="lineGlow" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="0.38"/>
          <stop offset="100%" stop-color="#ff2bd6" stop-opacity="0.02"/>
        </linearGradient>
        <filter id="glow"><feGaussianBlur stdDeviation="3" result="coloredBlur"/><feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <polygon points="{area}" fill="url(#lineGlow)"/>
      <polyline points="{poly}" fill="none" stroke="{color}" stroke-width="4" filter="url(#glow)" stroke-linecap="round"/>
      {''.join(ticks)}
    </svg>"""


def bars(rows, label_key, value_key, max_items=8, color="#ff2bd6") -> str:
    rows = rows[:max_items]
    max_value = max(float(r[value_key]) for r in rows) if rows else 1
    out = []
    for r in rows:
        label = html.escape(str(r[label_key]))
        value = float(r[value_key])
        width = max(4, value / max_value * 100)
        out.append(f"""
        <div class="bar-row">
          <div class="bar-label">{label}</div>
          <div class="bar-track"><span style="width:{width:.1f}%; background:{color}"></span></div>
          <div class="bar-value">{money_cr(value) if value > 1_000_000 else f'{value:,.0f}'}</div>
        </div>""")
    return "\n".join(out)


def table_html(df: pd.DataFrame, columns: list[str], limit=8) -> str:
    head = "".join(f"<th>{html.escape(c.replace('_', ' ').title())}</th>" for c in columns)
    body = []
    for _, row in df.head(limit).iterrows():
        cells = []
        for c in columns:
            v = row[c]
            if isinstance(v, float):
                text = f"{v:,.2f}"
            else:
                text = str(v)
            cells.append(f"<td>{html.escape(text)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def main() -> None:
    orders = pd.read_csv(ROOT / "data/raw/orders.csv", parse_dates=["order_date", "promised_delivery_date", "actual_delivery_date"])
    customers = pd.read_csv(ROOT / "data/raw/customers.csv")
    products = pd.read_csv(ROOT / "data/raw/products.csv")
    monthly = pd.read_csv(ROOT / "data/processed/monthly_kpis.csv")
    segments = pd.read_csv(ROOT / "data/processed/customer_segments.csv")
    retention = pd.read_csv(ROOT / "data/processed/cohort_retention.csv")
    metrics = json.loads((ROOT / "models/model_metrics.json").read_text())

    valid_orders = orders[orders["order_status"] != "Cancelled"].copy()
    revenue = valid_orders["net_sales"].sum()
    profit = valid_orders["profit"].sum()
    margin = profit / revenue
    aov = valid_orders["net_sales"].mean()
    refunds = orders["refund_amount"].sum()
    refund_rate = (orders["refund_amount"] > 0).mean()
    delay_rate = orders["shipping_delay_flag"].mean()
    repeat_rate = (valid_orders.groupby("customer_id")["order_id"].nunique() > 1).mean()

    enriched = valid_orders.merge(products[["product_id", "category", "product_name"]], on="product_id").merge(
        customers[["customer_id", "region", "city", "loyalty_tier", "acquisition_channel"]], on="customer_id"
    )
    cat = enriched.groupby("category", as_index=False).agg(revenue=("net_sales", "sum"), profit=("profit", "sum"), orders=("order_id", "count"), returns=("refund_amount", lambda s: (s > 0).mean()))
    cat["margin"] = cat["profit"] / cat["revenue"]
    cat = cat.sort_values("revenue", ascending=False)
    region = enriched.groupby("region", as_index=False).agg(revenue=("net_sales", "sum"), delay=("shipping_delay_flag", "mean"), orders=("order_id", "count")).sort_values("revenue", ascending=False)
    campaigns = enriched.groupby("campaign", dropna=False, as_index=False).agg(revenue=("net_sales", "sum"), profit=("profit", "sum"), orders=("order_id", "count"))
    campaigns["campaign"] = campaigns["campaign"].fillna("Always-on / No Campaign")
    campaigns["margin"] = campaigns["profit"] / campaigns["revenue"]
    campaigns = campaigns.sort_values("revenue", ascending=False)
    top_products = enriched.groupby(["product_name", "category"], as_index=False).agg(revenue=("net_sales", "sum"), orders=("order_id", "count")).sort_values("revenue", ascending=False)
    seg_summary = segments.groupby("rfm_segment", as_index=False).agg(customers=("customer_id", "count"), revenue=("monetary", "sum"), avg_frequency=("frequency", "mean")).sort_values("revenue", ascending=False)

    monthly_labels = pd.to_datetime(monthly["order_month"]).dt.strftime("%b %y").tolist()
    line_chart = svg_line(monthly["revenue"].tolist(), monthly_labels)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>E-Commerce Sales & Customer Behavior Analytics | Old-Money BI</title>
  <meta name="description" content="Portfolio-grade e-commerce analytics platform with sales KPIs, customer segmentation, forecasting, churn prediction, SQL, and BI dashboard assets." />
  <style>
    :root {{ --bg:#05010d; --panel:#0d1022ee; --panel2:#121735; --cyan:#00f5ff; --pink:#ff2bd6; --lime:#9dff00; --amber:#ffd166; --text:#f4f7ff; --muted:#a7b1d8; --line:#29305f; }}
    * {{ box-sizing:border-box }}
    body {{ margin:0; color:var(--text); font-family:Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial; background: radial-gradient(circle at 15% 10%, #31105e 0, transparent 28%), radial-gradient(circle at 85% 5%, #003f5c 0, transparent 30%), linear-gradient(135deg,#03020a 0%,#09031b 48%,#020918 100%); min-height:100vh; }}
    body:before {{ content:""; position:fixed; inset:0; pointer-events:none; opacity:.22; background-image:linear-gradient(rgba(0,245,255,.14) 1px, transparent 1px), linear-gradient(90deg, rgba(255,43,214,.12) 1px, transparent 1px); background-size:42px 42px; mask-image:linear-gradient(to bottom, black, transparent 78%); }}
    .wrap {{ width:min(1440px, 94vw); margin:0 auto; padding:34px 0 70px; position:relative; }}
    .hero {{ padding:34px; border:1px solid #3b2a7d; border-radius:28px; background:linear-gradient(135deg, rgba(15,18,46,.92), rgba(8,11,28,.72)); box-shadow:0 0 48px rgba(0,245,255,.14), inset 0 0 60px rgba(255,43,214,.06); overflow:hidden; position:relative; }}
    .hero:after {{ content:""; position:absolute; width:520px; height:520px; right:-210px; top:-230px; background:radial-gradient(circle, rgba(255,43,214,.33), transparent 58%); }}
    .eyebrow {{ color:var(--cyan); letter-spacing:.22em; text-transform:uppercase; font-weight:800; font-size:12px; }}
    h1 {{ font-size:clamp(34px, 5vw, 78px); margin:10px 0; line-height:.95; text-shadow:0 0 22px rgba(0,245,255,.45); }}
    .gradient {{ background:linear-gradient(90deg,var(--cyan),var(--pink),var(--lime)); -webkit-background-clip:text; color:transparent; }}
    .sub {{ color:var(--muted); max-width:920px; font-size:18px; line-height:1.55; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:22px; }}
    .chip {{ border:1px solid #3850a5; color:#dfe7ff; padding:9px 13px; border-radius:999px; background:#0b1234cc; box-shadow:0 0 18px rgba(0,245,255,.08); }}
    .grid {{ display:grid; grid-template-columns:repeat(12,1fr); gap:18px; margin-top:18px; }}
    .card {{ grid-column:span 3; background:linear-gradient(180deg, rgba(18,23,53,.92), rgba(8,10,26,.9)); border:1px solid var(--line); border-radius:22px; padding:20px; box-shadow:0 18px 50px rgba(0,0,0,.34), 0 0 26px rgba(0,245,255,.06); }}
    .wide {{ grid-column:span 8 }} .side {{ grid-column:span 4 }} .half {{ grid-column:span 6 }} .full {{ grid-column:span 12 }}
    .label {{ color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.12em; }}
    .metric {{ font-size:clamp(26px,3vw,42px); font-weight:900; margin-top:8px; color:#fff; }}
    .metric.cyan {{ color:var(--cyan); text-shadow:0 0 20px rgba(0,245,255,.45) }} .metric.pink {{ color:var(--pink); text-shadow:0 0 20px rgba(255,43,214,.35) }} .metric.lime {{ color:var(--lime); text-shadow:0 0 20px rgba(157,255,0,.35) }}
    h2 {{ margin:0 0 14px; font-size:24px }} h3 {{ margin:14px 0 8px; color:#dfe7ff }}
    .chart-svg {{ width:100%; height:auto; min-height:220px; }} .axis {{ fill:#8f9bc7; font-size:12px; }}
    .bar-row {{ display:grid; grid-template-columns:150px 1fr 96px; gap:12px; align-items:center; margin:12px 0; }}
    .bar-label {{ color:#e9edff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }} .bar-value {{ color:var(--cyan); text-align:right; font-weight:800; font-size:13px }}
    .bar-track {{ height:12px; border-radius:999px; background:#080d25; overflow:hidden; border:1px solid #24305e; }} .bar-track span {{ display:block; height:100%; border-radius:999px; box-shadow:0 0 18px currentColor; }}
    table {{ width:100%; border-collapse:collapse; overflow:hidden; border-radius:16px; }} th,td {{ padding:11px 12px; border-bottom:1px solid #242b57; text-align:left; font-size:13px }} th {{ color:var(--cyan); background:#0a1131; text-transform:uppercase; letter-spacing:.08em }} td {{ color:#e5e9ff }}
    .insights {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }} .insight {{ border-left:3px solid var(--pink); background:#090f2c; padding:14px; border-radius:14px; color:#dfe7ff; }}
    .footer {{ color:#8d98c9; text-align:center; margin-top:30px; }}
    @media(max-width:900px) {{ .card,.wide,.side,.half {{ grid-column:span 12 }} .bar-row {{ grid-template-columns:1fr; gap:6px }} .insights {{ grid-template-columns:1fr }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">Portfolio BI System • SQL + Python + ML + Vercel</div>
      <h1>E-Commerce Sales & Customer Behavior <span class="gradient">Analytics Platform</span></h1>
      <p class="sub">A old-money executive analytics boardroom for a marketplace business: 58K synthetic transactions, 12K customers, advanced SQL, RFM, K-Means segmentation, churn prediction, forecasting assets, and BI-ready KPI layers.</p>
      <div class="chips"><span class="chip">Executive Summary</span><span class="chip">Sales Analytics</span><span class="chip">Customer Segmentation</span><span class="chip">Product Insights</span><span class="chip">Marketing Performance</span><span class="chip">Operational Analytics</span></div>
    </section>

    <section class="grid">
      <div class="card"><div class="label">Total Revenue</div><div class="metric cyan">{money_cr(revenue)}</div></div>
      <div class="card"><div class="label">Profit Margin</div><div class="metric lime">{pct(margin)}</div></div>
      <div class="card"><div class="label">Average Order Value</div><div class="metric pink">₹{aov:,.0f}</div></div>
      <div class="card"><div class="label">Transactions</div><div class="metric">{len(orders):,}</div></div>

      <div class="card wide"><h2>Revenue Pulse</h2>{line_chart}</div>
      <div class="card side"><h2>Operating KPIs</h2><div class="label">Refund %</div><div class="metric pink">{pct(refund_rate)}</div><div class="label">Shipping Delay %</div><div class="metric cyan">{pct(delay_rate)}</div><div class="label">Repeat Purchase Rate</div><div class="metric lime">{pct(repeat_rate)}</div><div class="label">Churn Model ROC-AUC</div><div class="metric">{metrics['roc_auc']:.2f}</div></div>

      <div class="card half"><h2>Category Revenue</h2>{bars(cat.to_dict('records'), 'category', 'revenue', 8, 'linear-gradient(90deg,#00f5ff,#00a7ff)')}</div>
      <div class="card half"><h2>Regional Heatmap Proxy</h2>{bars(region.to_dict('records'), 'region', 'revenue', 8, 'linear-gradient(90deg,#ff2bd6,#7c3cff)')}</div>

      <div class="card half"><h2>Customer Segments</h2>{table_html(seg_summary, ['rfm_segment','customers','revenue','avg_frequency'], 8)}</div>
      <div class="card half"><h2>Campaign Performance</h2>{table_html(campaigns, ['campaign','orders','revenue','margin'], 8)}</div>

      <div class="card full"><h2>Top Product Leaders</h2>{table_html(top_products, ['product_name','category','orders','revenue'], 10)}</div>

      <div class="card full"><h2>Business Insights</h2><div class="insights">
        <div class="insight"><strong>Revenue concentration:</strong> high-value customer cohorts materially outperform casual buyers; prioritize retention journeys and loyalty nudges.</div>
        <div class="insight"><strong>Discount tradeoff:</strong> promotional campaigns lift order velocity, but margin compression requires category-level guardrails.</div>
        <div class="insight"><strong>Operations:</strong> shipping delays and refunds are measurable leakage points; seller SLA dashboards should trigger weekly action reviews.</div>
        <div class="insight"><strong>Product strategy:</strong> electronics and fashion-style categories need separate return-rate playbooks because refund behavior varies by category.</div>
      </div></div>
    </section>
    <div class="footer">Built from Python-generated synthetic data • 35 advanced SQL queries • Streamlit app in repo • Static old-money dashboard deployed on Vercel</div>
  </main>
</body>
</html>"""
    PUBLIC.mkdir(exist_ok=True)
    DASHBOARD.mkdir(exist_ok=True)
    (PUBLIC / "index.html").write_text(html_doc)
    (DASHBOARD / "executive_dashboard.html").write_text(html_doc)
    print(f"Built {PUBLIC / 'index.html'} ({len(html_doc):,} chars)")


if __name__ == "__main__":
    main()
