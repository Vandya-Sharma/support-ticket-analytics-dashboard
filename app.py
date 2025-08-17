import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt
from helpers import load_data, compute_metrics, plot_overall_satisfaction_pie, compute_csat_dsat
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# 1) Must come first
st.set_page_config(
    page_title="Support Ticket SLA Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
plt.style.use('dark_background')
sns.set_style("dark", {
    "axes.facecolor": "#222222",
    "figure.facecolor": "#121212",
    "grid.color": "#444444",
    "text.color": "white",
    "xtick.color": "white",
    "ytick.color": "white",
    "axes.labelcolor": "white"
})

# Load data
df = load_data("customer_support_tickets_clean.csv")

# --------------------- SIDEBAR FILTERS ---------------------
st.sidebar.header("Filters")

channels = st.sidebar.multiselect(
    "Select Channels",
    options=sorted(df['Ticket Channel'].dropna().unique()),
    default=sorted(df['Ticket Channel'].dropna().unique())
)

priorities = st.sidebar.multiselect(
    "Select Priorities",
    options=sorted(df['Ticket Priority'].dropna().unique()),
    default=sorted(df['Ticket Priority'].dropna().unique())
)

# Date range (based on created_at)
df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
date_min = df['created_at'].min().date()
date_max = df['created_at'].max().date()

date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max
)

# Issue category selector (for trend chart)
issue_category = st.sidebar.selectbox(
    "Select Issue Category",
    options=["Ticket Type", "Ticket Subject", "Product Purchased"],
    index=1
)

# Instructions in sidebar
st.sidebar.markdown("""
---
### How to use this dashboard:
- Select Channels, Priorities and Date Range using the filters above.
- Use **Issue Category** to drill down trends (Monthly).
- Hover on each element to view exact values.
""")

# --------------------- FILTER APPLICATION ---------------------
filtered = df.copy()

if channels:
    filtered = filtered[filtered['Ticket Channel'].isin(channels)]

if priorities:
    filtered = filtered[filtered['Ticket Priority'].isin(priorities)]

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered = filtered[
        (filtered['created_at'].dt.date >= start_date) &
        (filtered['created_at'].dt.date <= end_date)
    ]

# --------------------- KPI METRICS ---------------------
csat, dsat = compute_csat_dsat(filtered)
ch_metrics = compute_metrics(filtered, 'Ticket Channel')
# Merge priority back to enable hover
temp = filtered[['Ticket Channel','Ticket Priority']].drop_duplicates()
ch_metrics = ch_metrics.merge(temp, on='Ticket Channel', how='left')

st.title("Support Ticket SLA Dashboard")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Max Breach Rate (%)", f"{ch_metrics['sla_breach_rate'].max():.2f}")
k2.metric("Avg Resolution (hrs)", f"{ch_metrics['avg_resolution'].mean():.2f}")
k3.metric("Total Tickets", len(filtered))
k4.metric("CSAT (%)", f"{csat:.2f}")
k5.metric("DSAT (%)", f"{dsat:.2f}")

# --------------------- TODAY'S SIMULATION SECTION ---------------------
latest_date = df['created_at'].dt.date.max()
df_today = df[df['created_at'].dt.date == latest_date]
df_today['Hour'] = df_today['created_at'].dt.hour

st.metric("Total Tickets Today", len(df_today))

hourly_tickets = df_today.groupby('Hour').size().reset_index(name='Ticket Count')
fig_hour = px.bar(hourly_tickets, x='Hour', y='Ticket Count',
                  title="Tickets Received by Hour (Today)",
                  labels={'Hour': 'Hour of Day', 'Ticket Count': 'Number of Tickets'})
st.plotly_chart(fig_hour)

fig_type = px.pie(df_today, names='Ticket Type', title="Ticket Type Distribution (Today)", hole=0.4)
st.plotly_chart(fig_type)

# --------------------- SLA BREACH RATE BY CHANNEL ---------------------
fig_plotly = px.bar(
    ch_metrics,
    x='Ticket Channel',
    y='sla_breach_rate',
    color='Ticket Channel',
    hover_data=['total_tickets', 'Ticket Priority'],
    labels={'sla_breach_rate': "SLA Breach Rate (%)"},
    title="SLA Breach Rate by Channel"
)
st.plotly_chart(fig_plotly, use_container_width=True)

# --------------------- RESOLUTION TIME BY CHANNEL ---------------------
fig_resolution = px.bar(
    ch_metrics,
    x='Ticket Channel',
    y='avg_resolution',
    color='Ticket Channel',
    hover_data={'Ticket Channel': True, 'avg_resolution': ':.2f'},
    title="Average Resolution Time by Channel"
)
st.plotly_chart(fig_resolution, use_container_width=True)

# --------------------- RESPONSE vs RESOLUTION (SCATTER) ---------------------
fig_scatter = px.scatter(
    filtered,
    x='response_after_creation_hrs',
    y='resolution_after_response_hrs',
    color='Ticket Priority',
    hover_data=[
        'Ticket ID','Customer Name','Ticket Priority',
        'Ticket Status','Ticket Channel','Customer Satisfaction Rating'
    ],
    title="Response vs Resolution Time by Priority"
)
st.plotly_chart(fig_scatter, use_container_width=True)

# --------------------- TIME-BASED TREND (DAILY) ---------------------
filtered['first_response_time'] = pd.to_datetime(filtered['First Response Time'], errors='coerce')
filtered['first_response_delay_hrs'] = (
    (filtered['first_response_time'] - filtered['created_at']).dt.total_seconds() / 3600
)
df_time = filtered[filtered['first_response_delay_hrs'] >= 0].copy()

volumes = df_time.set_index('created_at').resample('D').size().rename('ticket_count')
volumes_rolling = volumes.rolling(window=7).mean()

fig_daily = go.Figure()
fig_daily.add_trace(go.Scatter(x=volumes.index, y=volumes.values, mode='lines+markers', name='Daily Volume'))
fig_daily.add_trace(go.Scatter(x=volumes.index, y=volumes_rolling.values, mode='lines', name='7-day Rolling Avg'))

fig_daily.update_layout(
    title="Daily Ticket Volume (with Rolling Average)",
    xaxis_title="Date",
    yaxis_title="Number of Tickets",
    hovermode="x unified"
)
st.plotly_chart(fig_daily, use_container_width=True)

# --------------------- CSAT/DSAT PIE ---------------------
st.plotly_chart(plot_overall_satisfaction_pie(filtered), use_container_width=True)

# --------------------- MONTHLY ISSUE CATEGORY TREND ---------------------
filtered['month'] = filtered['created_at'].dt.to_period('M').dt.to_timestamp()
trend_data = (
    filtered.groupby(['month', issue_category]).size().reset_index(name='ticket_count')
)
fig_trend = px.area(
    trend_data,
    x='month', y='ticket_count',
    color=issue_category,
    labels={'month':'Month', 'ticket_count':'Number of Tickets'},
    title=f"Monthly Ticket Volume by {issue_category}"
)
st.plotly_chart(fig_trend, use_container_width=True)

# --------------------- TOP 5 RECURRING CATEGORIES ---------------------
category_counts = (
    filtered.groupby(issue_category).size().reset_index(name='ticket_count')
    .sort_values(by='ticket_count', ascending=False).head(5)
)
category_counts['percentage'] = (category_counts['ticket_count']/category_counts['ticket_count'].sum()*100).round(2)

fig_top = px.bar(
    category_counts,
    x=issue_category,
    y='ticket_count',
    color='ticket_count',
    hover_data={'ticket_count':True, 'percentage':':.2f'},
    title=f"Top 5 Recurring {issue_category}s"
)
st.plotly_chart(fig_top, use_container_width=True)

# --------------------- RAW DATA VIEW ---------------------
with st.expander("Show Raw Ticket Data"):
    st.dataframe(filtered, use_container_width=True)
