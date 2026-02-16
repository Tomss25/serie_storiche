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

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="AlphaTool Pro: Ultimate Edition", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    h3 { color: #58A6FF !important; }
    .stMetric { background-color: #161B22; border: 1px solid #30363D; border-radius: 10px; padding: 10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #161B22; border-radius: 5px; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 2. FUNZIONI CORE (LOGICA E STATISTICA) ---

def sanitize_csv(df):
    """Pulisce il CSV da sporcizia, trova le date e converte in numerico."""
    df = df.reset_index()
    date_col = None
    # Cerca una colonna che sembri una data
    for col in df.columns:
        if any(x in str(col).lower() for x in ['date', 'data', 'time', 'timestamp']):
            date_col = col
            break
    
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=True)
        df = df.dropna(subset=[date_col]).set_index(date_col)
    else:
        # Tenta di forzare l'indice attuale
        df.index = pd.to_datetime(df.index, errors='coerce', dayfirst=True)
        df = df[df.index.notnull()]

    # Filtra solo colonne numeriche e pulisce simboli strani
    df = df.apply(pd.to_numeric, errors='coerce')
    df = df.select_dtypes(include=[np.number]).dropna(axis=1, how='all')
    return df.ffill().dropna()

def get_robust_covariance(returns):
    """Shrinkage di Ledoit-Wolf per stabilità matematica."""
    shrunk_cov, shrinkage_coeff = ledoit_wolf(returns)
    return shrunk_cov * 252, shrinkage_coeff

def solve_frontier(mu, sigma, rf, min_w, max_w, num_points=25):
    """Genera i punti della Frontiera Efficiente."""
    n = len(mu)
    def get_vol(w): return np.sqrt(np.dot(w.T, np.dot(sigma, w)))
    bounds = tuple((min_w, max_w) for _ in range(n))
    
    # Trova rendimento min e max possibile
    res_min = minimize(lambda w: np.sum(mu * w), [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
    res_max = minimize(lambda w: -np.sum(mu * w), [1./n]*n, bounds=bounds, constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
    
    target_rets = np.linspace(np.sum(mu * res_min.x), np.sum(mu * res_max.x), num_points)
    vols = []
    for tr in target_rets:
        res = minimize(get_vol, [1./n]*n, bounds=bounds, 
                       constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}, 
                                    {'type': 'eq', 'fun': lambda x: np.sum(mu * x) - tr}])
        vols.append(res.fun if res.success else None)
    return target_rets, vols

# --- 3. SIDEBAR (INPUT UTENTE) ---
st.sidebar.header("🛡️ Configurazione Dati")
upload_file = st.sidebar.file_uploader("Opzionale: Carica CSV Serie Storiche", type=["csv"])
sep = st.sidebar.selectbox("Separatore CSV", [";", ","], index=0)

st.sidebar.markdown("---")
raw_input = st.sidebar.text_area("Asset List (Yahoo Finance / ISIN)", value="CSSPX.MI\nEIMI.MI\nGLD\nAAPL", height=100)
tickers = re.findall(r"[\w\.\-]+", raw_input.upper())

st.sidebar.markdown("---")
years = st.sidebar.slider("Orizzonte Storico (Anni)", 1, 15, 5)
min_w = st.sidebar.slider("Peso Minimo per Asset", 0.0, 0.2, 0.0)
max_w = st.sidebar.slider("Peso Massimo per Asset", 0.1, 1.0, 0.4)
rf_rate = st.sidebar.number_input("Tasso Risk Free %", 0.0, 10.0, 3.5) / 100

# --- 4. LOGICA DI ESECUZIONE ---
if st.sidebar.button("🚀 ESEGUI ANALISI PROFESSIONALE"):
    df_final = pd.DataFrame()

    # PRIORITÀ 1: CARICAMENTO CSV
    if upload_file is not None:
        try:
            df_raw = pd.read_csv(upload_file, sep=sep)
            df_final = sanitize_csv(df_raw)
            if df_final.empty:
                st.error("Il CSV caricato non contiene dati numerici validi o date riconoscibili.")
            else:
                st.success(f"✅ Analisi avviata su {len(df_final.columns)} asset da CSV.")
        except Exception as e:
            st.error(f"Errore nel processare il CSV: {e}")

    # PRIORITÀ 2: DOWNLOAD ONLINE
    elif tickers:
        start_date = datetime.now() - timedelta(days=years*365)
        all_s = {}
        with st.spinner("Recupero dati da Yahoo Finance..."):
            for t in tickers:
                try:
                    d = yf.download(t, start=start_date, progress=False)
                    if not d.empty:
                        col = 'Adj Close' if 'Adj Close' in d.columns else 'Close'
                        series = d[col].ffill()
                        # Gestione MultiIndex yfinance
                        if isinstance(series, pd.DataFrame): series = series.iloc[:, 0]
                        all_s[t] = series
                except: pass
            
            if all_s:
                df_final = pd.DataFrame(all_s).dropna()
            else:
                st.error("Nessun dato trovato per i ticker inseriti.")

    # --- 5. CALCOLI E VISUALIZZAZIONE ---
    if not df_final.empty:
        rets = df_final.pct_change().dropna()
        mu = rets.mean() * 252
        sigma, s_coeff = get_robust_covariance(rets)
        
        # Ottimizzazione Max Sharpe
        n = len(mu)
        def neg_sharpe(w):
            vol = np.sqrt(np.dot(w.T, np.dot(sigma, w)))
            ret = np.sum(mu * w)
            return -(ret - rf_rate) / vol

        res_opt = minimize(neg_sharpe, [1./n]*n, bounds=tuple((min_w, max_w) for _ in range(n)), 
                           constraints=[{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}])
        w_opt = res_opt.x

        # TABS
        tab1, tab2, tab3, tab4 = st.tabs(["📉 Frontiera Efficiente", "🛡️ Rischio & Shrinkage", "📊 Allocazione", "🌊 Drawdown"])

        with tab1:
            st.subheader("Ottimizzazione Media-Varianza")
            f_rets, f_vols = solve_frontier(mu, sigma, rf_rate, min_w, max_w)
            p_vol_opt = np.sqrt(np.dot(w_opt.T, np.dot(sigma, w_opt)))
            p_ret_opt = np.sum(mu * w_opt)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=f_vols, y=f_rets, mode='lines', name='Frontiera Robusta', line=dict(color='#58A6FF', width=4)))
            fig.add_trace(go.Scatter(x=[p_vol_opt], y=[p_ret_opt], mode='markers', name='MAX SHARPE', marker=dict(size=15, color='red', symbol='star')))
            fig.update_layout(template="plotly_dark", xaxis_title="Rischio (Volatilità)", yaxis_title="Rendimento Atteso")
            st.plotly_chart(fig, use_container_width=True)
            

        with tab2:
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Shrinkage Intensity", f"{s_coeff:.2%}")
                st.info("Un valore alto indica che i dati storici erano instabili e il modello Ledoit-Wolf ha dovuto correggerli pesantemente.")
            with col_b:
                rc = (w_opt * np.dot(sigma, w_opt)) / (p_vol_opt**2)
                st.write("### Risk Contribution per Asset")
                st.bar_chart(pd.DataFrame({'Rischio': rc}, index=mu.index))
            

        with tab3:
            st.write("### Pesi Ottimali di Portafoglio")
            df_w = pd.DataFrame({'Allocazione': w_opt}, index=mu.index).sort_values('Allocazione', ascending=False)
            st.table(df_w.style.format("{:.2%}"))

        with tab4:
            st.subheader("Analisi dello Stress Storico")
            p_rets = (rets * w_opt).sum(axis=1)
            cum_rets = (1 + p_rets).cumprod()
            max_inv = cum_rets.cummax()
            dd = (cum_rets - max_inv) / max_inv
            
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(x=dd.index, y=dd*100, fill='tozeroy', name='Drawdown %', line=dict(color='red')))
            fig_dd.update_layout(template="plotly_dark", title="Underwater Chart", yaxis_title="Perdita %")
            st.plotly_chart(fig_dd, use_container_width=True)
            st.metric("Massimo Drawdown Storico", f"{dd.min():.2%}")
            

    else:
        st.warning("In attesa di dati validi. Carica un file o controlla i ticker nella sidebar.")

else:
    st.info("👈 Configura i parametri nella sidebar e clicca su 'Esegui Analisi Professionale'.")
