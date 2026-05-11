import pandas as pd

def calculate_kpis(df: pd.DataFrame) -> dict:
    revenue = df["net_sales"].sum()
    orders = df["order_id"].nunique()
    return {
        "total_revenue": revenue,
        "profit_margin": df["profit"].sum() / revenue if revenue else 0,
        "average_order_value": revenue / orders if orders else 0,
        "return_rate": (df["order_status"] == "Returned").mean(),
        "shipping_delay_pct": df["shipping_delay_flag"].mean(),
    }
