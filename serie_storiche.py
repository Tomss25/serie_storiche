import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Data Extractor Pro", layout="wide")

st.title("🚀 Financial Data Extractor")

# --- SIDEBAR ---
st.sidebar.header("Parametri")
input_data = st.sidebar.text_input("Inserisci Tickers (es: SWDA.MI, AAPL)", "SWDA.MI, AAPL")
tickers = [t.strip().upper() for t in input_data.split(",")]
years = st.sidebar.selectbox("Anni", [3, 5, 10, 15], index=1)
interval_map = {"Daily": "1d", "Weekly": "1wk", "Monthly": "1mo", "Yearly": "1y"}
tf_display = st.sidebar.selectbox("Timeframe", list(interval_map.keys()))

if st.sidebar.button("Estrai Serie Storiche"):
    start_date = datetime.now() - timedelta(days=years*365)
    
    try:
        # Download con auto_adjust=True per evitare problemi di nomi colonne
        data = yf.download(tickers, start=start_date, interval=interval_map[tf_display])
        
        if data.empty:
            st.error("Dati non trovati. Verifica i Tickers.")
        else:
            # GESTIONE ERRORE 'Adj Close': 
            # Selezioniamo solo i prezzi di chiusura indipendentemente dalla struttura
            if 'Adj Close' in data.columns:
                df_final = data['Adj Close']
            else:
                df_final = data['Close']

            # Se scarichi UN SOLO ticker, Pandas restituisce una Serie. La trasformiamo in DataFrame.
            if isinstance(df_final, pd.Series):
                df_final = df_final.to_frame(name=tickers[0])

            # Formattazione indice data
            df_final.index = df_final.index.strftime('%Y-%m-%d')
            
            st.subheader("Anteprima Serie Storiche")
            st.dataframe(df_final, use_container_width=True)

            # Preparazione CSV con separatore | come richiesto
            csv = df_final.to_csv(sep="|")

            st.download_button(
                label="📥 Scarica in CSV",
                data=csv,
                file_name=f"estrazione_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
            
    except Exception as e:
        st.error(f"Errore tecnico: {str(e)}")
