import streamlit as st
import yfinance as yf
import mstarpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
from datetime import datetime, timedelta

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="AlphaTool Pro Hybrid", layout="wide")
st.title("📊 AlphaTool Pro: Hybrid Engine (Yahoo Priority)")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configurazione")
raw_input = st.sidebar.text_area(
    "Lista Tickers / ISIN", 
    value="SWDA.MI\nLU1287022708\nAAPL", 
    height=150,
    help="Inserisci i codici. Il sistema cercherà prima su Yahoo, poi su Morningstar."
)
tickers_input = re.findall(r"[\w\.\-]+", raw_input.upper())

years = st.sidebar.selectbox("Orizzonte Temporale", [1, 3, 5, 10], index=1)
# Calcoliamo la data di inizio una volta sola
start_date = datetime.now() - timedelta(days=years*365)
end_date = datetime.now()

# --- FUNZIONI DI ESTRAZIONE ---

def get_data_yahoo(ticker, start_dt):
    """Tentativo 1: Yahoo Finance (Veloce)"""
    try:
        df = yf.download(ticker, start=start_dt, progress=False)
        if not df.empty:
            col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            series = df[col].squeeze()
            if isinstance(series, pd.Series):
                # Pulizia base
                series = series.ffill()
                return series
    except:
        return None
    return None

def get_data_morningstar(isin, start_dt, end_dt):
    """Tentativo 2: Morningstar (Lento ma profondo)"""
    try:
        # Cerca il fondo per ISIN o Nome
        fund = mstarpy.Funds(term=isin, country="it")
        # Scarica storico NAV
        history = fund.nav(start_date=start_dt, end_date=end_dt, frequency="daily")
        
        if history:
            df = pd.DataFrame(history)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            series = df['nav']
            # Rimuove timezone se presente per allinearsi con Yahoo
            series.index = series.index.normalize().tz_localize(None)
            return series
    except:
        return None
    return None

# --- ESECUZIONE ---
if st.sidebar.button("🔥 ESEGUI ANALISI"):
    if not tickers_input:
        st.error("Inserisci dei codici.")
    else:
        all_series = {}
        metrics = []
        
        with st.spinner('Ricerca in corso (Priorità: Yahoo -> Fallback: Morningstar)...'):
            for t in tickers_input:
                series = None
                source = "N/A"
                
                # 1. PRIMO TENTATIVO: YAHOO FINANCE
                series = get_data_yahoo(t, start_date)
                
                if series is not None:
                    source = "Yahoo"
                else:
                    # 2. SECONDO TENTATIVO: MORNINGSTAR (SOLO SE YAHOO FALLISCE)
                    # Morningstar lavora meglio con ISIN puliti, quindi proviamo
                    series = get_data_morningstar(t, start_date, end_date)
                    if series is not None:
                        source = "Morningstar"

                # --- ELABORAZIONE DATI TROVATI ---
                if series is not None:
                    series.name = t
                    all_series[t] = series
                    
                    # Calcolo Metriche
                    returns = series.pct_change().dropna()
                    if len(series) > 0:
                        tot_ret = ((series.iloc[-1] / series.iloc[0]) - 1) * 100
                        vol = returns.std() * np.sqrt(252) * 100
                        
                        # Max Drawdown
                        roll_max = series.cummax()
                        drawdown = (series - roll_max) / roll_max
                        max_dd = drawdown.min() * 100
                        
                        metrics.append({
                            "Ticker": t,
                            "Fonte": source,
                            "Prezzo": round(series.iloc[-1], 2),
                            "Rend %": round(tot_ret, 2),
                            "Volat %": round(vol, 2),
                            "Max DD %": round(max_dd, 2)
                        })
                else:
                    st.warning(f"⚠️ Dati non trovati per {t} (Né su Yahoo, né su Morningstar)")

        # --- VISUALIZZAZIONE ---
        if all_series:
            # Creazione DataFrame Unico
            df_final = pd.DataFrame(all_series).ffill().dropna()
            
            # ORDINAMENTO GRAFICO: PRIMA I DATI
            st.subheader("📅 Serie Storiche (Prezzi)")
            st.dataframe(df_final.sort_index(ascending=False).round(2), use_container_width=True, height=500)
            
            st.markdown("---")

            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📈 Performance (Base 100)")
                if not df_final.empty:
                    df_b100 = (df_final / df_final.iloc[0]) * 100
                    st.line_chart(df_b100)
                else:
                    st.info("Dati insufficienti per il grafico (date non allineate).")
            
            with col2:
                st.subheader("🏆 Analisi")
                st.dataframe(pd.DataFrame(metrics).set_index("Ticker"), use_container_width=True)

            st.markdown("---")
            
            # MATRICE DI CORRELAZIONE
            st.subheader("🔗 Matrice di Correlazione")
            if len(df_final.columns) > 1:
                corr = df_final.pct_change().corr()
                fig, ax = plt.subplots(figsize=(10, 4))
                sns.heatmap(corr, annot=True, cmap="RdYlGn", fmt=".2f", vmin=-1, vmax=1, ax=ax)
                st.pyplot(fig)

            # EXPORT
            st.markdown("### 📥 Download")
            df_final.index.name = "Data"
            # Formattazione per Excel Italiano (Sep=; Dec=,)
            csv = df_final.to_csv(sep=";", decimal=",", encoding="utf-8-sig")
            st.download_button("SCARICA CSV COMPLETO", csv, "Analisi_Hybrid.csv", "text/csv")
        else:
            st.error("Nessun dato valido estratto.")
