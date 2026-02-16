import streamlit as st
import yfinance as yf
import mstarpy
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from scipy.optimize import minimize
import altair as alt
import plotly.graph_objects as go
from sklearn.covariance import ledoit_wolf # <--- L'ingrediente segreto

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="AlphaTool Pro: Indestructible Edition", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stMetric { background-color: #161B22; border: 1px solid #30363D; padding: 10px; border-radius: 10px; }
    h3 { color: #58A6FF !important; }
</style>
""", unsafe_allow_html=True)

# --- MOTORE STATISTICO AVANZATO ---

def get_robust_covariance(returns):
    """
    Applica lo Shrinkage di Ledoit-Wolf. 
    Invece di usare la covarianza campionaria pura (instabile), 
    calcola una miscela ottimale tra i dati e una matrice target.
    """
    # Ledoit-Wolf ritorna la matrice shrunk e il coefficiente di shrinkage usato
    shrunk_cov, shrinkage_coeff = ledoit_wolf(returns)
    return shrunk_cov * 252, shrinkage_coeff

def calculate_risk_contribution(weights, sigma):
    portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(sigma, weights)))
    marginal_risk = np.dot(sigma, weights) / portfolio_vol
    risk_contribution = weights * marginal_risk
    return risk_contribution / portfolio_vol

def solve_frontier(mu, sigma, rf, min_w, max_w, num_points=25):
    n = len(mu)
    def get_vol(w): return np.sqrt(np.dot(w.T, np.dot(sigma, w)))
    bounds = tuple((min_w, max_w) for _ in range(n))
    
    # Trova il range di rendimento possibile con i vincoli dati
    res_min = minimize(lambda w: np.sum(mu * w), [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
    res_max = minimize(lambda w: -np.sum(mu * w), [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
    
    target_returns = np.linspace(np.sum(mu * res_min.x), np.sum(mu * res_max.x), num_points)
    frontier_vols = []
    
    for tr in target_returns:
        cons = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                {'type': 'eq', 'fun': lambda x: np.sum(mu * x) - tr}]
        res = minimize(get_vol, [1./n]*n, bounds=bounds, constraints=cons)
        frontier_vols.append(res.fun if res.success else None)
    return target_returns, frontier_vols

# --- LOGICA DATI (FUSA) ---

def fetch_data(tickers, years):
    start_dt = datetime.now() - timedelta(days=years*365)
    end_dt = datetime.now()
    all_series = {}
    for t in tickers:
        try:
            df = yf.download(t, start=start_dt, end=end_dt, progress=False)
            if not df.empty:
                all_series[t] = df['Adj Close' if 'Adj Close' in df.columns else 'Close'].ffill().squeeze()
                continue
        except: pass
        try:
            fund = mstarpy.Funds(term=t, country="it")
            history = fund.nav(start_date=start_dt, end_date=end_dt, frequency="daily")
            if history:
                df = pd.DataFrame(history)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True).sort_index()
                all_series[t] = df['nav'].squeeze()
        except: pass
    return pd.DataFrame(all_series).ffill().dropna()

# --- SIDEBAR ---
st.sidebar.header("🛡️ Robust Engine")
upload_file = st.sidebar.file_uploader("Carica CSV (Prioritario)", type=["csv"])
raw_input = st.sidebar.text_area("Asset List (Yahoo/ISIN)", value="CSSPX.MI\nEIMI.MI\nAAPL\nGLD", height=80)
tickers = re.findall(r"[\w\.\-]+", raw_input.upper())

st.sidebar.markdown("---")
years = st.sidebar.slider("Orizzonte Storico", 1, 15, 5)
min_w = st.sidebar.slider("Min Peso Asset", 0.0, 0.2, 0.0)
max_w = st.sidebar.slider("Max Peso Asset", 0.1, 1.0, 0.4)
rf_rate = st.sidebar.number_input("Risk Free Rate %", 0.0, 10.0, 3.5) / 100

if st.sidebar.button("🚀 ESEGUI OTTIMIZZAZIONE ROBUSTA"):
    if upload_file:
        df_raw = pd.read_csv(upload_file, sep=None, engine='python', index_col=0, parse_dates=True)
        df_final = df_raw.select_dtypes(include=[np.number]).ffill().dropna()
    else:
        df_final = fetch_data(tickers, years)

    if not df_final.empty:
        rets = df_final.pct_change().dropna()
        mu = rets.mean() * 252
        
        # APPLICAZIONE LEDOIT-WOLF
        sigma, s_coeff = get_robust_covariance(rets)
        
        # Ottimizzazione Max Sharpe
        n = len(mu)
        def neg_sharpe(w):
            p_ret = np.sum(mu * w)
            p_vol = np.sqrt(np.dot(w.T, np.dot(sigma, w)))
            return -(p_ret - rf_rate) / p_vol
        
        res_opt = minimize(neg_sharpe, [1./n]*n, bounds=tuple((min_w, max_w) for _ in range(n)), 
                           constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
        w_opt = res_opt.x

        # --- UI ---
        st.title("🛡️ AlphaTool Pro: Frontier & Risk Decomposition")
        
        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            st.metric("Shrinkage Intensity", f"{s_coeff:.2%}", help="Indica quanto il modello ha dovuto 'correggere' i tuoi dati per renderli stabili. Più è alto, più i tuoi dati storici erano rumorosi/pericolosi.")
        
        tab1, tab2, tab3 = st.tabs(["📉 Frontiera Efficiente", "🛡️ Analisi del Rischio", "📊 Metriche Dettagliate"])

        with tab1:
            f_rets, f_vols = solve_frontier(mu, sigma, rf_rate, min_w, max_w)
            fig = go.Figure()
            # Frontiera
            fig.add_trace(go.Scatter(x=f_vols, y=f_rets, mode='lines', name='Frontiera Robusta (Ledoit-Wolf)', line=dict(color='#58A6FF', width=4)))
            # Portafoglio Max Sharpe
            p_vol_opt = np.sqrt(np.dot(w_opt.T, np.dot(sigma, w_opt)))
            p_ret_opt = np.sum(mu * w_opt)
            fig.add_trace(go.Scatter(x=[p_vol_opt], y=[p_ret_opt], mode='markers', name='MAX SHARPE', marker=dict(size=18, color='red', symbol='star')))
            
            fig.update_layout(template="plotly_dark", xaxis_title="Rischio Annualizzato (Volatilità)", yaxis_title="Rendimento Atteso Annualizzato")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            rc = calculate_risk_contribution(w_opt, sigma)
            risk_df = pd.DataFrame({'Asset': mu.index, 'Peso (%)': w_opt*100, 'Contribuzione Rischio (%)': rc*100})
            
            c1, c2 = st.columns([1, 1])
            with c1:
                st.write("### Confronto Peso vs Rischio")
                st.dataframe(risk_df.style.format("{:.2f}"))
            with c2:
                st.write("### Risk Distribution")
                st.bar_chart(risk_df.set_index('Asset')['Contribuzione Rischio (%)'])
            
            st.warning("⚠️ Se un asset ha una Contribuzione al Rischio molto superiore al suo Peso, significa che è il 'motore' della volatilità del portafoglio.")

        with tab3:
            st.write("### Pesi Ottimali del Portafoglio")
            df_weights = pd.DataFrame({'Allocazione': w_opt}, index=mu.index).sort_values('Allocazione', ascending=False)
            st.table(df_weights.style.format("{:.2%}"))
            
            st.markdown("---")
            st.write("### Serie Storiche Utilizzate")
            st.dataframe(df_final.tail(10), use_container_width=True)

    else:
        st.error("Dati insufficienti o asset non trovati. Controlla i Ticker o il file CSV.")
