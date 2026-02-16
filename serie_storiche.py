# --- CORREZIONE LOGICA FETCH ONLINE ---
if not upload_file:
    from datetime import datetime
    start = datetime.now() - timedelta(days=years*365)
    all_s = {}
    
    with st.spinner("Scaricamento dati online..."):
        for t in tickers:
            # Scarichiamo i dati
            d = yf.download(t, start=start, progress=False)
            
            # VERIFICA CRITICA: I dati esistono? La colonna Close c'è?
            if not d.empty:
                col = 'Adj Close' if 'Adj Close' in d.columns else 'Close'
                # Squeeze serve a garantire che sia una Series, non un DF a colonna singola
                series = d[col].ffill()
                if isinstance(series, pd.DataFrame): # Caso raro con MultiIndex
                    series = series.iloc[:, 0]
                all_s[t] = series
            else:
                st.warning(f"⚠️ Ticker non trovato o senza dati: {t}")

    # VERIFICA FINALE PRIMA DI CREARE IL DATAFRAME
    if all_s:
        df_final = pd.DataFrame(all_s).dropna()
    else:
        st.error("❌ Errore: Non è stato possibile recuperare dati per nessuno dei ticker inseriti.")
        st.stop() # Blocca l'esecuzione qui per evitare il crash successivo
