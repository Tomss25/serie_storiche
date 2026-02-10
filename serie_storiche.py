import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Data Extractor Pro", layout="wide")

st.title("🚀 Financial Data Extractor")
st.markdown("Smetti di dipendere da piattaforme chiuse. Estrai i tuoi dati in autonomia.")

# --- SIDEBAR PER INPUT ---
st.sidebar.header("Parametri di Estrazione")

# Input ISIN / Tickers
input_data = st.sidebar.text_input("Inserisci Tickers o ISIN (separati da virgola)", "CSSX5.MI, SWDA.MI, AAPL")
tickers = [t.strip().upper() for t in input_data.split(",")]

# Selezione Orizzonte Temporale
years = st.sidebar.selectbox("Orizzonte Temporale (Anni)", [3, 5, 10, 15], index=1)

# Selezione Timeframe
interval_map = {
    "Daily": "1d",
    "Weekly": "1wk",
    "Monthly": "1mo",
    "Yearly": "1y"
}
tf_display = st.sidebar.selectbox("Timeframe", list(interval_map.keys()))
interval = interval_map[tf_display]

if st.sidebar.button("Estrai Serie Storiche"):
    start_date = datetime.now() - timedelta(days=years*365)
    
    try:
        # Download dati
        data = yf.download(tickers, start=start_date, interval=interval)['Adj Close']
        
        if data.empty:
            st.error("Nessun dato trovato. Controlla i Ticker inseriti.")
        else:
            # Formattazione richiesta: DATA | NOME | (Multi-colonna)
            # Pulizia per il formato specifico
            df_final = data.copy()
            df_final.index = df_final.index.strftime('%Y-%m-%d')
            
            st.subheader(f"Anteprima Dati ({tf_display})")
            st.dataframe(df_final, use_container_width=True)

            # Preparazione CSV conforme alla tua richiesta
            # CSV Standard: Data come prima colonna, nomi asset come header
            csv = df_final.to_csv(sep="|")

            st.download_button(
                label="📥 Scarica Serie Storiche in CSV",
                data=csv,
                file_name=f"serie_storiche_{years}y.csv",
                mime="text/csv",
            )
            
    except Exception as e:
        st.error(f"Errore tecnico: {e}")

else:
    st.info("Configura i parametri a sinistra e clicca su 'Estrai'")