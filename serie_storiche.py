import streamlit as st
import yfinance as yf
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

st.set_page_config(page_title="Data Extractor Pro", layout="wide")

st.title("🚀 Financial Data Extractor (Versione Multi-Sorgente)")

# --- LOGICA DI RICERCA FALLBACK PER ISIN ---
def get_data_from_yahoo(ticker, start_date, interval):
    df = yf.download(ticker, start=start_date, interval=interval, progress=False)
    if not df.empty:
        col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        return df[col]
    return None

# Funzione per tentare di recuperare dati se il ticker secco fallisce
def try_alternative_sources(isin, start_date):
    # Qui potresti aggiungere API a pagamento o scraping specifico
    # Per ora, proviamo a suggerire all'utente il ticker corretto di Yahoo
    # Molti fondi LU... su Yahoo finiscono con .MI (Milano) o .PA (Parigi)
    suffixes = ["", ".MI", ".PA", ".DE"]
    for s in suffixes:
        test_ticker = f"{isin}{s}"
        data = get_data_from_yahoo(test_ticker, start_date, "1d")
        if data is not None:
            return data, test_ticker
    return None, None

# --- INTERFACCIA ---
st.sidebar.header("Parametri")
raw_input = st.sidebar.text_area("Inserisci Tickers o ISIN", value="LU1287022708 SWDA.MI")
tickers_input = re.findall(r"[\w\.\-]+", raw_input.upper())
years = st.sidebar.selectbox("Anni", [3, 5, 10, 15], index=1)
interval_map = {"Daily": "1d", "Weekly": "1wk", "Monthly": "1mo"}
interval = interval_map[st.sidebar.selectbox("Timeframe", list(interval_map.keys()))]

if st.sidebar.button("Estrai Serie Storiche"):
    start_date = datetime.now() - timedelta(days=years*365)
    all_data = []
    
    for t in tickers_input:
        with st.spinner(f'Ricerca {t}...'):
            # Primo tentativo: Yahoo diretto
            data = get_data_from_yahoo(t, start_date, interval)
            
            # Secondo tentativo: Fallback con suffissi comuni
            if data is None:
                data, found_ticker = try_alternative_sources(t, start_date)
                if found_ticker:
                    st.info(f"💡 {t} trovato come {found_ticker}")

            if data is not None:
                data.name = t
                all_data.append(data)
            else:
                st.error(f"❌ Impossibile trovare dati per: {t}")

    if all_data:
        df_final = pd.concat(all_data, axis=1).round(2)
        df_final.index = df_final.index.strftime('%Y-%m-%d')
        st.dataframe(df_final, use_container_width=True)
        csv = df_final.to_csv(sep="|", decimal=",")
        st.download_button("📥 Scarica in CSV", data=csv, file_name="export.csv")
