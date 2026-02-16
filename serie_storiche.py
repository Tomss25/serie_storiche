import streamlit as st
import yfinance as yf
import mstarpy
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from scipy.optimize import minimize
import plotly.graph_objects as go
from sklearn.covariance import ledoit_wolf

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="AlphaTool Pro: Full Professional", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h3 { color: #58A6FF !important; }
    .stMetric { background-color: #161B22; border: 1px solid #30363D; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FUNZIONI DI SERVIZIO ---

def sanitize_csv(df):
    df = df.reset_index()
    date_col = None
    for col in df.columns:
        if any(x in str(col).lower() for x in ['date', 'data', 'time', 'timestamp']):
            date_col = col
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
        df = df.dropna(subset=[date_col]).set_index(date_col)
    else:
        df.index = pd.to_datetime(df.index, errors='coerce', dayfirst=True)
        df = df[df.index.notnull()]
    df = df.apply(pd.to_numeric, errors='coerce').select_dtypes(include=[np.number]).dropna(axis=1, how='all')
    return df.ffill().dropna()

def get_robust_covariance(returns):
    shrunk_cov, shrinkage_coeff = ledoit_wolf(returns)
    return shrunk_cov * 252, shrinkage_coeff

def solve_frontier(mu, sigma, rf, min_w, max_w, num_points=25):
    n = len(mu)
    def get_vol(w): return np.sqrt(np.dot(w.T, np.dot(sigma, w)))
    bounds = tuple((min_w, max_w) for _ in range(n))
    res_min = minimize(lambda w: np.sum(mu * w), [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
    res_max = minimize(lambda w: -np.sum(mu * w), [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
    target_returns = np.linspace(np.sum(mu * res_min.x), np.sum(mu * res_max.x), num_points)
    vols = []
    for tr in target_returns:
        res = minimize(get_vol, [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}, {'type': 'eq', 'fun': lambda x: np.sum(mu * x) - tr}])
        vols.append(res.fun if res.success else None)
    return target_returns, vols

# --- SIDEBAR ---
st.sidebar.header("🛡️ Data Ingestion")
upload_file = st.sidebar.file_uploader("Carica CSV", type=["csv"])
sep = st.sidebar.selectbox("Separatore", [";", ","], index=0)
raw_input = st.sidebar.text_area("Fallback Tickers", value="CSSPX.MI\nEIMI.MI\nGLD\nAAPL", height=80)
tickers = re.findall(r"[\w\.\-]+", raw_input.upper())
years = st.sidebar.slider("Orizzonte Storico", 1, 15, 5)
min_w = st.sidebar.slider("Min Peso", 0.0, 0.2, 0.0)
max_w = st.sidebar.slider("Max Peso", 0.1, 1.0, 0.4)
rf_rate = st.sidebar.number_input("Risk Free %", 0.0, 10.0, 3.5) / 100

# --- LOGICA ---
if st.sidebar.button("🚀 ESEGUI ANALISI COMPLETA"):
    if upload_file:
        df_final = sanitize_csv(pd.read_csv(upload_file, sep=sep))
    else:
        start = datetime.now() - timedelta(days=years*365)
        all_s = {}
        for t in tickers:
            d = yf.download(t, start=start, progress=False)
            if not d.empty: all_s[t] = d['Adj Close' if 'Adj Close' in d.columns else 'Close'].ffill()
        df_final = pd.DataFrame(all_s).dropna()

    if not df_final.empty:
        rets = df_final.pct_change().dropna()
        mu = rets.mean() * 252
        sigma, s_coeff = get_robust_covariance(rets)
        
        # Ottimizzazione Max Sharpe
        n = len(mu)
        res_opt = minimize(lambda w: -(np.sum(mu * w) - rf_rate) / np.sqrt(np.dot(w.T, np.dot(sigma, w))), 
                           [1./n]*n, bounds=tuple((min_w, max_w) for _ in range(n)), 
                           constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
        w_opt = res_opt.x

        tab1, tab2, tab3, tab4 = st.tabs(["📉 Frontiera", "🛡️ Rischio", "📊 Allocazione", "🌊 Drawdown"])

        with tab1:
            f_rets, f_vols = solve_frontier(mu, sigma, rf_rate, min_w, max_w)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=f_vols, y=f_rets, mode='lines', name='Frontiera Robusta', line=dict(color='#58A6FF', width=3)))
            p_vol_opt = np.sqrt(np.dot(w_opt.T, np.dot(sigma, w_opt)))
            p_ret_opt = np.sum(mu * w_opt)
            fig.add_trace(go.Scatter(x=[p_vol_opt], y=[p_ret_opt], mode='markers', name='Max Sharpe', marker=dict(size=15, color='red', symbol='star')))
            fig.update_layout(template="plotly_dark", xaxis_title="Rischio", yaxis_title="Rendimento")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.metric("Shrinkage Intensity (Ledoit-Wolf)", f"{s_coeff:.2%}")
            rc = (w_opt * np.dot(sigma, w_opt)) / (p_vol_opt**2)
            risk_df = pd.DataFrame({'Asset': mu.index, 'Peso': w_opt, 'Risk Contrib': rc})
            st.bar_chart(risk_df.set_index('Asset'))

        with tab3:
            st.table(pd.DataFrame({'Peso': w_opt}, index=mu.index).style.format("{:.2%}"))

        with tab4:
            st.subheader("Analisi Storica dei Drawdown")
            # Calcolo Equity Line del portafoglio ottimo
            portfolio_rets = (rets * w_opt).sum(axis=1)
            equity_line = (1 + portfolio_rets).cumprod()
            running_max = equity_line.cummax()
            drawdown = (equity_line - running_max) / running_max
            
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(x=drawdown.index, y=drawdown * 100, fill='tozeroy', name="Drawdown %", line=dict(color='red')))
            fig_dd.update_layout(template="plotly_dark", title="Underwater Chart (Drawdown %)", yaxis_title="Perdita dal Picco %")
            st.plotly_chart(fig_dd, use_container_width=True)
            
            
            
            max_dd = drawdown.min()
            st.metric("Massimo Drawdown Storico", f"{max_dd:.2%}")
            st.info("💡 Un Drawdown elevato indica che l'ottimizzazione storica potrebbe essere stata 'fortunata'. Se il Max DD supera la tua tolleranza, riduci il peso massimo degli asset rischiosi.")
            
    else: st.error("Dati non disponibili.")
