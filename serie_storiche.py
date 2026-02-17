import streamlit as st
import yfinance as yf
import mstarpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE PAGINA E STILE CSS ---
st.set_page_config(page_title="Asset Historical Data Engine", layout="wide")

st.markdown("""
<style>
    /* SFONDO GENERALE APP - Grigio Scuro Professionale */
    .stApp { background-color: #0E1117; color: #FAFAFA; }

    /* SIDEBAR - Tonalità leggermente più chiara */
    section[data-testid="stSidebar"] { background-color: #161B22; border-right: 1px solid #30363D; }
    
    /* TESTI SIDEBAR BIANCHI */
    section[data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* INPUT TEXT AREA - Stile Dark */
    .stTextArea textarea { background-color: #21262D; color: #FFFFFF !important; border: 1px solid #30363D; border-radius: 10px; }
    .stTextArea textarea:focus { border-color: #3B82F6; box-shadow: 0 0 0 1px #3B82F6; }

    /* BOTTONI - Sfumatura Blu */
    div.stButton > button {
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        color: white; border: none; padding: 0.5rem 1rem; border-radius: 12px; font-weight: 600;
        transition: all 0.3s ease; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); width: 100%;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #1E40AF 0%, #60A5FA 100%);
        transform: translateY(-2px); box-shadow: 0 6px 8px rgba(0, 0, 0, 0.4); border-color: #60A5FA;
    }

    /* DATAFRAME E TABELLE */
    div[data-testid="stDataFrame"] { border: 1px solid #30363D; border-radius: 10px; overflow: hidden; }
    
    /* TAB STYLING */
    button[data-baseweb="tab"] { color: #58A6FF; font-weight: bold; }
    
    /* TITOLI HEADER */
    h1, h2, h3 { color: #58A6FF !important; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("📊 AlphaTool Pro: Hybrid Engine")
st.markdown("Analisi finanziaria professionale multi-sorgente (Yahoo + Morningstar).")
st.markdown("---")

# --- CREAZIONE TAB ---
tab_analisi, tab_codici = st.tabs(["📉 ANALISI & GRAFICI", "📋 CODICI UTILI (Copia/Incolla)"])

# --- SIDEBAR: CONFIGURAZIONE (SEMPRE VISIBILE) ---
st.sidebar.header("⚙️ Configurazione")

raw_input = st.sidebar.text_area(
    "Lista Tickers / ISIN", 
    value="SP500\nSWDA.MI\nLU1287022708\nGOLD", 
    height=150,
    help="Inserisci i codici qui. Vedi la tab 'Codici Utili' per suggerimenti."
)

# --- INTELLIGENZA ALIAS ---
ALIAS_MAP = {
    "SP500": "^GSPC", "S&P500": "^GSPC", "NASDAQ": "^NDX", "NASDAQ100": "^NDX",
    "DOWJONES": "^DJI", "DAX": "^GDAXI", "CAC40": "^FCHI", "ESTX50": "^STOXX50E",
    "EUROSTOXX": "^STOXX50E", "VIX": "^VIX", "GOLD": "GC=F", "OIL": "CL=F",
    "BITCOIN": "BTC-USD", "BTC": "BTC-USD", "EURUSD": "EURUSD=X"
}

raw_tokens = re.findall(r"[\w\.\-\^\=]+", raw_input.upper())
tickers_input = []
for t in raw_tokens:
    if t in ALIAS_MAP: tickers_input.append(ALIAS_MAP[t])
    else: tickers_input.append(t)

years = st.sidebar.selectbox("Orizzonte Temporale", [1, 3, 5, 10, 20], index=1)
freq_options = {"Giornaliero": "D", "Settimanale": "W", "Mensile": "ME"}
selected_freq_label = st.sidebar.selectbox("Frequenza Dati", list(freq_options.keys()))
selected_freq_code = freq_options[selected_freq_label]

start_date = datetime.now() - timedelta(days=years*365)
end_date = datetime.now()

# --- FUNZIONI DI ESTRAZIONE ---
def get_data_yahoo(ticker, start_dt):
    try:
        df = yf.download(ticker, start=start_dt, progress=False)
        if not df.empty:
            col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            series = df[col].squeeze()
            if isinstance(series, pd.Series): return series.ffill()
    except: return None
    return None

def get_data_morningstar(isin, start_dt, end_dt):
    try:
        fund = mstarpy.Funds(term=isin, country="it")
        history = fund.nav(start_date=start_dt, end_date=end_dt, frequency="daily")
        if history:
            df = pd.DataFrame(history)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            series = df['nav']
            series.index = series.index.normalize().tz_localize(None)
            return series
    except: return None
    return None

# =========================================================
# TAB 1: ESECUZIONE ANALISI (Tutto il programma originale)
# =========================================================
with tab_analisi:
    if st.sidebar.button("🔥 ESEGUI ANALISI"):
        if not tickers_input:
            st.error("Inserisci dei codici validi.")
        else:
            all_series = {}
            
            with st.spinner('Ricerca in corso...'):
                for t in tickers_input:
                    series = None
                    # 1. YAHOO
                    series = get_data_yahoo(t, start_date)
                    # 2. MORNINGSTAR
                    if series is None:
                        series = get_data_morningstar(t, start_date, end_date)

                    if series is not None:
                        series.name = t 
                        all_series[t] = series
                    else:
                        st.warning(f"⚠️ Dati non trovati per {t}")

            if all_series:
                df_daily = pd.DataFrame(all_series).ffill().dropna()
                
                if selected_freq_code == "D":
                    df_final = df_daily
                    ann_factor = 252
                else:
                    df_final = df_daily.resample(selected_freq_code).last()
                    ann_factor = 52 if selected_freq_code == "W" else 12

                metrics = []
                for col in df_final.columns:
                    s = df_final[col]
                    if len(s) > 1:
                        returns = s.pct_change().dropna()
                        tot_ret = ((s.iloc[-1] / s.iloc[0]) - 1) * 100
                        vol = returns.std() * np.sqrt(ann_factor) * 100
                        roll_max = s.cummax()
                        drawdown = (s - roll_max) / roll_max
                        max_dd = drawdown.min() * 100
                        
                        metrics.append({
                            "Ticker": col,
                            "Prezzo": round(s.iloc[-1], 2),
                            "Rend %": round(tot_ret, 2),
                            "Volat %": round(vol, 2),
                            "Max DD %": round(max_dd, 2)
                        })

                st.subheader(f"📅 Serie Storiche ({selected_freq_label})")
                st.dataframe(df_final.sort_index(ascending=False).round(2), use_container_width=True, height=500)
                
                st.markdown("---")

                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader("📈 Performance (Base 100)")
                    if not df_final.empty:
                        df_b100 = (df_final / df_final.iloc[0]) * 100
                        st.line_chart(df_b100)
                
                with col2:
                    st.subheader("🏆 Analisi")
                    st.dataframe(pd.DataFrame(metrics).set_index("Ticker"), use_container_width=True)

                st.markdown("---")
                
                st.subheader("🔗 Matrice di Correlazione")
                if len(df_final.columns) > 1:
                    corr = df_final.pct_change().corr()
                    plt.style.use("dark_background")
                    fig, ax = plt.subplots(figsize=(10, 4))
                    sns.heatmap(corr, annot=True, cmap="RdYlGn", fmt=".2f", vmin=-1, vmax=1, ax=ax, cbar_kws={'label': 'Corr'})
                    st.pyplot(fig)

                st.markdown("### 📥 Download")
                df_final.index.name = "Data"
                csv = df_final.to_csv(sep=";", decimal=",", encoding="utf-8-sig")
                st.download_button(
                    label=f"SCARICA CSV ({selected_freq_label.upper()})", 
                    data=csv, 
                    file_name=f"Analisi_{selected_freq_label}.csv", 
                    mime="text/csv"
                )
            else:
                st.error("Nessun dato valido estratto.")
    else:
        st.info("👈 Configura i parametri nella Sidebar e premi 'ESEGUI ANALISI' per iniziare.")

# =========================================================
# TAB 2: CODICI UTILI (CHEAT SHEET)
# =========================================================
with tab_codici:
    st.header("📋 Codici Pronti all'Uso")
    st.markdown("Copia questi codici e incollali nella barra laterale. Hanno il tasto copia integrato.")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("🇺🇸 Indici USA")
        st.caption("S&P 500")
        st.code("^GSPC", language="text")
        st.caption("NASDAQ 100")
        st.code("^NDX", language="text")
        st.caption("Dow Jones Industrial")
        st.code("^DJI", language="text")
        st.caption("VIX (Volatilità)")
        st.code("^VIX", language="text")

        st.subheader("🇪🇺 Indici Europa")
        st.caption("FTSE MIB (Italia)")
        st.code("FTSEMIB.MI", language="text")
        st.caption("DAX (Germania)")
        st.code("^GDAXI", language="text")
        st.caption("CAC 40 (Francia)")
        st.code("^FCHI", language="text")
        st.caption("Euro Stoxx 50")
        st.code("^STOXX50E", language="text")

    with col_b:
        st.subheader("🛢️ Materie Prime")
        st.caption("Oro (Gold Futures)")
        st.code("GC=F", language="text")
        st.caption("Petrolio (Crude Oil)")
        st.code("CL=F", language="text")
        st.caption("Argento (Silver)")
        st.code("SI=F", language="text")

        st.subheader("₿ Crypto & Valute")
        st.caption("Bitcoin (USD)")
        st.code("BTC-USD", language="text")
        st.caption("Ethereum (USD)")
        st.code("ETH-USD", language="text")
        st.caption("Cambio Euro/Dollaro")
        st.code("EURUSD=X", language="text")
        
    st.markdown("---")
    st.subheader("🇮🇹 Esempi ETF & Azioni (Milano)")
    st.caption("Per Milano usare sempre il suffisso **.MI**")
    st.code("SWDA.MI", language="text")
    st.code("EIMI.MI", language="text")
    st.code("ENEL.MI", language="text")
    st.code("ISP.MI", language="text")

