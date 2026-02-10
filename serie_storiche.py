import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Data Extractor Pro v2", layout="wide")

st.title("🚀 Financial Data Extractor & Analyzer")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("Configurazione")
raw_input = st.sidebar.text_area("Inserisci Tickers o ISIN", 
                                 value="SWDA.MI\nAAPL\nCSSX5.MI", 
                                 height=150,
                                 help="Incolla liberamente. Gestisce spazi, virgole e invii a capo.")

# Regex avanzata per catturare correttamente i ticker (incluso punti e trattini)
tickers_input = re.findall(r"[\w\.\-]+", raw_input.upper())

years = st.sidebar.selectbox("Orizzonte Temporale (Anni)", [3, 5, 10, 15], index=1)
interval_map = {"Daily": "1d", "Weekly": "1wk", "Monthly": "1mo"}
tf_key = st.sidebar.selectbox("Frequenza Dati", list(interval_map.keys()))
interval = interval_map[tf_key]

if st.sidebar.button("Estrai ed Analizza"):
    if not tickers_input:
        st.error("Inserisci almeno un codice valido.")
    else:
        start_date = datetime.now() - timedelta(days=years*365)
        all_series = {}
        metrics = []

        with st.spinner('Scarico i dati da Yahoo Finance...'):
            for t in tickers_input:
                try:
                    # Scarico singolarmente per evitare conflitti di Multi-Index
                    df = yf.download(t, start=start_date, interval=interval, progress=False)
                    
                    if not df.empty:
                        # Selezione dinamica della colonna prezzi
                        col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
                        # Appiattiamo il dataframe se yfinance restituisce multi-index
                        series = df[col].squeeze() 
                        
                        if isinstance(series, pd.Series):
                            series.name = t
                            all_series[t] = series.round(2)
                            
                            # CALCOLO METRICHE BASE
                            returns = series.pct_change().dropna()
                            total_ret = ((series.iloc[-1] / series.iloc[0]) - 1) * 100
                            # Volatilità annua (approssimata)
                            ann_vol = returns.std() * np.sqrt(252) * 100 if tf_key == "Daily" else 0
                            
                            metrics.append({
                                "Ticker": t,
                                "Ultimo Prezzo": f"{series.iloc[-1]:.2f}",
                                "Rendimento Tot %": f"{total_ret:.2f}%",
                                "Volatilità Ann. %": f"{ann_vol:.2f}%" if ann_vol > 0 else "N/A"
                            })
                    else:
                        st.warning(f"⚠️ Nessun dato trovato per: {t}")
                except Exception as e:
                    st.error(f"❌ Errore su {t}: {str(e)}")

        if all_series:
            # Creazione Tabella Finale
            df_final = pd.DataFrame(all_series)
            # Ordiniamo per data decrescente per l'anteprima
            df_preview = df_final.sort_index(ascending=False)
            df_preview.index = df_preview.index.strftime('%Y-%m-%d')

            # --- VISUALIZZAZIONE ---
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Serie Storiche")
                st.dataframe(df_preview, use_container_width=True)
            
            with col2:
                st.subheader("Analisi Rapida")
                st.table(pd.DataFrame(metrics).set_index("Ticker"))

            # --- DOWNLOAD ---
            st.markdown("---")
            csv = df_final.to_csv(sep="|", decimal=",")
            st.download_button(
                label="📥 Scarica CSV (DATA | NOME1 | NOME2)",
                data=csv,
                file_name=f"analisi_portafoglio_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.error("La ricerca non ha prodotto risultati. Verifica i ticker su Yahoo Finance.")
