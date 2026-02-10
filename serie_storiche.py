import streamlit as st
import yfinance as yf
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Data Extractor Pro", layout="wide")

st.title("🚀 Financial Data Extractor")

# --- SIDEBAR ---
st.sidebar.header("Parametri di Estrazione")

raw_input = st.sidebar.text_area("Inserisci Tickers o ISIN", 
                                 value="SWDA.MI AAPL CSSX5.MI", 
                                 help="Incolla liberamente i codici (spazi, virgole o invii a capo).")

# Estrazione pulita dei codici
tickers_input = re.findall(r"[\w\.\-]+", raw_input.upper())

years = st.sidebar.selectbox("Orizzonte Temporale (Anni)", [3, 5, 10, 15], index=1)
interval_map = {"Daily": "1d", "Weekly": "1wk", "Monthly": "1mo", "Yearly": "1y"}
tf_display = st.sidebar.selectbox("Timeframe", list(interval_map.keys()))

if st.sidebar.button("Estrai Serie Storiche"):
    if not tickers_input:
        st.error("Inserisci almeno un codice valido.")
    else:
        start_date = datetime.now() - timedelta(days=years*365)
        all_data = []
        missing_tickers = []

        with st.spinner('Estrazione in corso...'):
            for t in tickers_input:
                try:
                    # Scarico il singolo ticker
                    df = yf.download(t, start=start_date, interval=interval_map[tf_display], progress=False)
                    
                    if df.empty:
                        missing_tickers.append(t)
                    else:
                        # Seleziono il prezzo (Adj Close o Close)
                        col_name = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
                        series = df[col_name].copy()
                        
                        # Rinonimo la serie con il nome del Ticker/ISIN
                        series.name = t
                        all_data.append(series)
                except Exception:
                    missing_tickers.append(t)

        # GESTIONE ERRORI
        if missing_tickers:
            for m in missing_tickers:
                st.warning(f"⚠️ ISIN/Ticker non trovato o non disponibile: {m}")

        # COSTRUZIONE TABELLA FINALE
        if all_data:
            # Unisco tutte le serie sulla colonna Data (Join)
            df_final = pd.concat(all_data, axis=1)
            
            # Arrotondamento e pulizia data
            df_final = df_final.round(2)
            df_final.index = df_final.index.strftime('%Y-%m-%d')
            
            # Mostro la tabella a schermo: DATA | NOME1 | NOME2...
            st.subheader("Tabella Serie Storiche")
            st.dataframe(df_final, use_container_width=True)

            # Export CSV con separatore | e decimale ,
            csv = df_final.to_csv(sep="|", decimal=",")

            st.download_button(
                label="📥 Scarica in CSV",
                data=csv,
                file_name=f"export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.error("Nessun dato recuperato per i codici inseriti.")
