import streamlit as st
import yfinance as yf
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Data Extractor Pro", layout="wide")

st.title("🚀 Financial Data Extractor")

# --- SIDEBAR ---
st.sidebar.header("Parametri di Estrazione")

# Input flessibile: accetta virgole, spazi, invii a capo
raw_input = st.sidebar.text_area("Inserisci Tickers o ISIN", 
                                 value="SWDA.MI AAPL\nCSSX5.MI", 
                                 help="Puoi incollarli separati da spazio, virgola o invio a capo.")

# Regex per estrarre parole (ticker/isin) ignorando la punteggiatura
tickers = re.findall(r"[\w\.\-]+", raw_input.upper())

years = st.sidebar.selectbox("Orizzonte Temporale (Anni)", [3, 5, 10, 15], index=1)
interval_map = {"Daily": "1d", "Weekly": "1wk", "Monthly": "1mo", "Yearly": "1y"}
tf_display = st.sidebar.selectbox("Timeframe", list(interval_map.keys()))

if st.sidebar.button("Estrai Serie Storiche"):
    if not tickers:
        st.error("Inserisci almeno un Ticker o ISIN valido.")
    else:
        start_date = datetime.now() - timedelta(days=years*365)
        
        try:
            with st.spinner('Scaricamento dati in corso...'):
                data = yf.download(tickers, start=start_date, interval=interval_map[tf_display])
            
            if data.empty:
                st.error("Nessun dato trovato per i codici inseriti.")
            else:
                # Gestione colonna prezzi (Adj Close o Close)
                if 'Adj Close' in data.columns:
                    df_final = data['Adj Close']
                else:
                    df_final = data['Close']

                # Forza DataFrame se è un singolo ticker
                if isinstance(df_final, pd.Series):
                    df_final = df_final.to_frame(name=tickers[0])

                # ARROTONDAMENTO A 2 CIFRE DECIMALI
                df_final = df_final.round(2)

                # Pulizia Indice Data
                df_final.index = df_final.index.strftime('%Y-%m-%d')
                
                st.subheader("Anteprima Dati (Arrotondati)")
                st.dataframe(df_final, use_container_width=True)

                # Export CSV con separatore | e virgola per i decimali (formato IT)
                # Sostituiamo il punto con la virgola per Excel italiano
                csv = df_final.to_csv(sep="|", decimal=",")

                st.download_button(
                    label="📥 Scarica in CSV (Formato Excel IT)",
                    data=csv,
                    file_name=f"estrazione_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                )
                
        except Exception as e:
            st.error(f"Errore tecnico: {str(e)}")
