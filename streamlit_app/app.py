import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="E-Commerce Analytics Platform", page_icon="🛒", layout="wide")
st.markdown("""
<style>
.stApp {background: #0B1020; color: #EAF0FF;}
[data-testid="stMetricValue"] {font-size: 28px; color: #7CFFCB;}
.block-container {padding-top: 1.5rem;}
</style>
""", unsafe_allow_html=True)

BASE = Path(__file__).resolve().parents[1]
@st.cache_data
def load():
    orders = pd.read_csv(BASE/'data/processed/orders_enriched.csv', parse_dates=['order_date'])
    rfm = pd.read_csv(BASE/'data/processed/customer_segments.csv')
    monthly = pd.read_csv(BASE/'data/processed/monthly_kpis.csv')
    cohort = pd.read_csv(BASE/'data/processed/cohort_retention.csv')
    return orders, rfm, monthly, cohort
orders, rfm, monthly, cohort = load()

st.title("🛒 E-Commerce Sales & Customer Behavior Analytics Platform")
st.caption("Portfolio-grade BI app: sales, products, customer segmentation, forecasting, operations, and retention analytics.")

with st.sidebar:
    st.header("Filters")
    categories = st.multiselect("Category", sorted(orders.category.unique()), default=sorted(orders.category.unique()))
    regions = st.multiselect("Region", sorted(orders.region.unique()), default=sorted(orders.region.unique()))
    campaigns = st.multiselect("Campaign", sorted(orders.campaign.unique()), default=sorted(orders.campaign.unique()))
    date_range = st.date_input("Order date range", [orders.order_date.min(), orders.order_date.max()])

mask = orders.category.isin(categories) & orders.region.isin(regions) & orders.campaign.isin(campaigns)
if len(date_range)==2:
    mask &= orders.order_date.dt.date.between(date_range[0], date_range[1])
df = orders[mask].copy()

revenue = df.net_sales.sum(); profit = df.profit.sum(); orders_n = df.order_id.nunique(); customers = df.customer_id.nunique()
cols = st.columns(5)
cols[0].metric("Total Revenue", f"₹{revenue/1e7:.2f} Cr")
cols[1].metric("Profit Margin", f"{profit/revenue:.1%}" if revenue else "0%")
cols[2].metric("AOV", f"₹{revenue/orders_n:,.0f}" if orders_n else "₹0")
cols[3].metric("Customers", f"{customers:,}")
cols[4].metric("Return Rate", f"{(df.order_status.eq('Returned').mean()):.1%}" if len(df) else "0%")

tabs = st.tabs(["Executive", "Sales", "Customers", "Products", "Marketing", "Operations", "Forecast", "Downloads"])
with tabs[0]:
    c1,c2 = st.columns([1.5,1])
    month = df.groupby(df.order_date.dt.to_period('M').astype(str)).agg(revenue=('net_sales','sum'),profit=('profit','sum')).reset_index()
    c1.plotly_chart(px.line(month, x='order_date', y=['revenue','profit'], template='plotly_dark', title='Revenue and Profit Trend'), use_container_width=True)
    cat = df.groupby('category').net_sales.sum().reset_index().sort_values('net_sales', ascending=False)
    c2.plotly_chart(px.pie(cat, names='category', values='net_sales', hole=.55, template='plotly_dark', title='Revenue Mix'), use_container_width=True)
    st.info("Key insight: high-value repeat customers and festival campaigns drive revenue, but margin discipline and return reduction create the biggest profit upside.")
with tabs[1]:
    c1,c2 = st.columns(2)
    sales = df.groupby(['order_month','region']).net_sales.sum().reset_index()
    c1.plotly_chart(px.area(sales, x='order_month', y='net_sales', color='region', template='plotly_dark', title='Regional Revenue'), use_container_width=True)
    aov = df.groupby('loyalty_tier').net_sales.mean().reset_index()
    c2.plotly_chart(px.bar(aov, x='loyalty_tier', y='net_sales', template='plotly_dark', title='AOV by Loyalty Tier'), use_container_width=True)
with tabs[2]:
    merged = rfm.merge(df[['customer_id','region','acquisition_channel']].drop_duplicates('customer_id'), on='customer_id', how='left')
    c1,c2 = st.columns(2)
    c1.plotly_chart(px.scatter(merged, x='recency_days', y='monetary', color='kmeans_segment', size='frequency', template='plotly_dark', title='K-Means Customer Segments'), use_container_width=True)
    seg = merged.groupby('rfm_segment').agg(customers=('customer_id','count'), revenue=('monetary','sum')).reset_index()
    c2.plotly_chart(px.bar(seg, x='rfm_segment', y='revenue', color='customers', template='plotly_dark', title='RFM Segment Value'), use_container_width=True)
with tabs[3]:
    prod = df.groupby(['product_name','category']).agg(revenue=('net_sales','sum'), orders=('order_id','count'), return_rate=('is_returned','mean')).reset_index().sort_values('revenue', ascending=False).head(25)
    st.plotly_chart(px.bar(prod, x='revenue', y='product_name', color='category', orientation='h', template='plotly_dark', title='Top Products'), use_container_width=True)
    st.dataframe(prod, use_container_width=True)
with tabs[4]:
    camp = df.groupby('campaign').agg(orders=('order_id','count'), revenue=('net_sales','sum'), profit=('profit','sum'), discount=('discount_amount','sum')).reset_index()
    camp['margin_pct']=camp.profit/camp.revenue
    st.plotly_chart(px.scatter(camp, x='discount', y='revenue', size='orders', color='margin_pct', template='plotly_dark', title='Campaign Revenue vs Discount Investment'), use_container_width=True)
    st.dataframe(camp.sort_values('revenue', ascending=False), use_container_width=True)
with tabs[5]:
    c1,c2 = st.columns(2)
    ship = df.groupby('shipping_mode').agg(delay_rate=('shipping_delay_flag','mean'), fulfillment=('fulfillment_days','mean')).reset_index()
    c1.plotly_chart(px.bar(ship, x='shipping_mode', y='delay_rate', template='plotly_dark', title='Shipping Delay %'), use_container_width=True)
    geo = df.groupby(['city','state','region']).agg(revenue=('net_sales','sum'), delay=('shipping_delay_flag','mean')).reset_index()
    c2.plotly_chart(px.scatter(geo, x='revenue', y='delay', color='region', hover_name='city', template='plotly_dark', title='Geo Operations Hotspots'), use_container_width=True)
with tabs[6]:
    m = df.groupby(df.order_date.dt.to_period('M').astype(str)).net_sales.sum().reset_index(name='revenue')
    m['t']=np.arange(len(m))
    model=LinearRegression().fit(m[['t']], m.revenue)
    fut = pd.DataFrame({'t':np.arange(len(m), len(m)+6)})
    fut['revenue']=model.predict(fut[['t']])
    last = pd.Period(m.order_date.iloc[-1], freq='M')
    fut['order_date']=[str(last+i) for i in range(1,7)]
    plot = pd.concat([m[['order_date','revenue']].assign(type='Actual'), fut[['order_date','revenue']].assign(type='Forecast')])
    st.plotly_chart(px.line(plot, x='order_date', y='revenue', color='type', template='plotly_dark', title='6-Month Revenue Forecast'), use_container_width=True)
with tabs[7]:
    st.download_button('Download filtered orders CSV', df.to_csv(index=False), 'filtered_orders.csv')
    st.download_button('Download customer segments CSV', rfm.to_csv(index=False), 'customer_segments.csv')
