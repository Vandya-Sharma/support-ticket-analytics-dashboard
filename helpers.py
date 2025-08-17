import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    for col in ['First Response Time','Time to Resolution','Date of Purchase']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    df['created_at'] = df['Date of Purchase']
    df['response_after_creation_hrs'] = ((df['First Response Time'] - df['Date of Purchase']).dt.total_seconds()/3600).astype(int)
    df['resolution_after_response_hrs'] = ((df['Time to Resolution'] - df['First Response Time']).dt.total_seconds()/3600).astype(int)

    sla_map = {'Critical':4,'High':24,'Medium':48,'Low':72}
    df['sla_threshold_hrs'] = df['Ticket Priority'].map(sla_map).fillna(72)
    df['sla_breach'] = np.where(df['resolution_after_response_hrs'] > df['sla_threshold_hrs'],1,0)

    return df[df['resolution_after_response_hrs'] >= 0].copy()

def compute_metrics(df, by):
    m = df.groupby(by).agg(
        avg_resolution=('resolution_after_response_hrs','mean'),
        sla_breach_rate=('sla_breach','mean'),
        total_tickets=(by,'count')
    ).reset_index()
    m['sla_breach_rate'] = (m['sla_breach_rate']*100).round(2)
    m['avg_resolution'] = m['avg_resolution'].round(2)
    return m

def compute_csat_dsat(df):
    total_responses = df['Customer Satisfaction Rating'].notnull().sum()
    csat_count = df[df['Customer Satisfaction Rating'] >= 4].shape[0]
    dsat_count = df[df['Customer Satisfaction Rating'] <= 2].shape[0]
    csat_percent = (csat_count/total_responses)*100 if total_responses else 0
    dsat_percent = (dsat_count/total_responses)*100 if total_responses else 0
    return csat_percent, dsat_percent

def plot_overall_satisfaction_pie(df):
    total = len(df)
    csat = len(df[df['Customer Satisfaction Rating'].isin([4,5])]) / total * 100
    dsat = len(df[df['Customer Satisfaction Rating'].isin([1,2])]) / total * 100
    neutral = len(df[df['Customer Satisfaction Rating'] == 3]) / total * 100
    labels  = ['Satisfied (4-5)', 'Neutral (3)', 'Dissatisfied (1-2)']
    values  = [csat, neutral, dsat]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.5,
        textinfo='label+percent',
        hovertemplate='%{label}: %{percent:.1f}%<extra></extra>'
    ))
    fig.update_layout(template='plotly_dark', height=400,
                      title="Overall Customer Satisfaction Breakdown")
    return fig
