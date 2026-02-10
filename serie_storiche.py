import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
from datetime import datetime, timedelta

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="ESTRAZIONE SERIE STORICHE", layout="wide")

st.title("📊 CDG Tool Pro: Estrazione serie storiche")
st.markdown("---")

# --- SIDEBAR: INPUT E PARAMETRI ---
st.sidebar.header("⚙️ Configurazione")

# Area di testo libera per inserire i codici
raw_input = st.sidebar.text_area(
    "Lista Tickers / ISIN", 
    value="SWDA.MI\nEIMI.MI\nAAPL\nGLUX.MI", 
    height=150,
    help="Incolla qui i tuoi codici. Il tool ignora spazi, virgole e testo inutile."
)

# Regex per pulire l'input e trovare solo i codici validi
tickers_input = re.findall(r"[\w\.\-]+", raw_input.upper())

# Selezione Orizzonte Temporale
years = st.sidebar.selectbox("Orizzonte Temporale (Anni)", [1, 3, 5, 10, 15], index=1)

# Selezione Frequenza Dati
interval_map = {"Giornaliero": "1d", "Settimanale": "1wk", "Mensile": "1mo"}
tf_key = st.sidebar.selectbox("Frequenza", list(interval_map.keys()))
interval = interval_map[tf_key]

# Tasto di avvio
if st.sidebar.button("🔥 ESEGUI ANALISI COMPLETA"):
    if not tickers_input:
        st.error("⚠️ Inserisci almeno un codice valido per iniziare.")
    else:
        start_date = datetime.now() - timedelta(days=years*365)
        all_series = {}
        metrics = []

        # --- FASE 1: DOWNLOAD E ELABORAZIONE ---
        with st.spinner('Accesso ai server finanziari e calcolo metriche...'):
            for t in tickers_input:
                try:
                    # Download singolo per evitare conflitti Multi-Index
                    df = yf.download(t, start=start_date, interval=interval, progress=False)
                    
                    if not df.empty:
                        # Gestione dinamica della colonna prezzi (Adj Close vs Close)
                        col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
                        
                        # .squeeze() trasforma il DataFrame (se singola colonna) in Series
                        series = df[col].squeeze()
                        
                        # Verifica che sia effettivamente una Series temporale
                        if isinstance(series, pd.Series):
                            # Pulizia dati mancanti (fill forward)
                            series = series.ffill()
                            all_series[t] = series
                            
                            # --- CALCOLO KPI FINANZIARI ---
                            # Rendimenti percentuali
                            returns = series.pct_change().dropna()
                            
                            # Rendimento Totale Periodo
                            if len(series) > 0:
                                total_ret = ((series.iloc[-1] / series.iloc[0]) - 1) * 100
                                
                                # CAGR (Compound Annual Growth Rate)
                                years_actual = (series.index[-1] - series.index[0]).days / 365.25
                                if years_actual > 0:
                                    cagr = (((series.iloc[-1] / series.iloc[0]) ** (1/years_actual)) - 1) * 100
                                else:
                                    cagr = 0
                            else:
                                total_ret = 0
                                cagr = 0

                            # Volatilità Annualizzata
                            # 252 giorni trading, 52 settimane, 12 mesi
                            ann_factor = 252 if interval == "1d" else (52 if interval == "1wk" else 12)
                            vol = returns.std() * np.sqrt(ann_factor) * 100
                            
                            # Max Drawdown
                            roll_max = series.cummax()
                            drawdown = (series - roll_max) / roll_max
                            max_dd = drawdown.min() * 100
                            
                            # Sharpe Ratio (Semplificato, Risk Free = 2%)
                            sharpe = (cagr - 2) / vol if vol > 0 else 0
                            
                            metrics.append({
                                "Ticker": t,
                                "Ultimo Prezzo": round(series.iloc[-1], 2),
                                "Rend. Tot %": round(total_ret, 2),
                                "CAGR %": round(cagr, 2),
                                "Volatilità %": round(vol, 2),
                                "Max DD %": round(max_dd, 2),
                                "Sharpe Ratio": round(sharpe, 2)
                            })
                    else:
                        st.warning(f"⚠️ Nessun dato trovato per: {t}")
                except Exception as e:
                    st.error(f"❌ Errore critico su {t}: {str(e)}")

        # --- FASE 2: VISUALIZZAZIONE RISULTATI ---
        if all_series:
            # Creazione DataFrame Unico allineato sulle date
            df_final = pd.DataFrame(all_series)
            
            # Ordiniamo per data decrescente (più recente in alto)
            df_display = df_final.sort_index(ascending=False).round(2)
            # Formattiamo la data come stringa per visualizzazione pulita
            df_display.index = df_display.index.strftime('%Y-%m-%d')

            # ---------------------------------------------------------
            # 1. TABELLA SERIE STORICHE (SPOSTATA IN CIMA COME RICHIESTO)
            # ---------------------------------------------------------
            st.subheader("📅 Serie Storiche (Prezzi)")
            st.dataframe(df_display, use_container_width=True, height=500)
            
            st.markdown("---")

            # ---------------------------------------------------------
            # 2. GRAFICI E METRICHE (SPOSTATI SOTTO)
            # ---------------------------------------------------------
            col_chart, col_kpi = st.columns([2, 1])

            with col_chart:
                st.subheader("📈 Performance Comparata (Base 100)")
                # Normalizzazione a base 100 per confronto equo
                df_b100 = (df_final / df_final.iloc[0]) * 100
                st.line_chart(df_b100)
            
            with col_kpi:
                st.subheader("🏆 Classifica Performance")
                # Creiamo un DataFrame dalle metriche per visualizzarlo bene
                df_metrics = pd.DataFrame(metrics).set_index("Ticker")
                # Evidenziamo i valori massimi
                st.dataframe(df_metrics.style.highlight_max(axis=0, color='#90EE90'), use_container_width=True)

            st.markdown("---")

            # ---------------------------------------------------------
            # 3. MATRICE DI CORRELAZIONE (IN CODA)
            # ---------------------------------------------------------
            st.subheader("🔗 Matrice di Correlazione")
            if len(df_final.columns) > 1:
                corr = df_final.pct_change().corr()
                fig, ax = plt.subplots(figsize=(10, 5))
                sns.heatmap(corr, annot=True, cmap="RdYlGn", fmt=".2f", vmin=-1, vmax=1, ax=ax)
                st.pyplot(fig)
            else:
                st.info("Necessari almeno 2 titoli per calcolare la correlazione.")

            # --- FASE 3: EXPORT CSV PER EXCEL ITALIANO ---
            st.markdown("### 📥 Area Download")
            
            # Preparazione CSV
            # 1. Impostiamo il nome indice
            df_final.index.name = "Data"
            # 2. Formattazione Data per il CSV
            # Nota: uso una copia per non rovinare l'indice originale se servisse per altri calcoli futuri
            df_csv = df_final.copy()
            df_csv.index = df_csv.index.strftime('%d/%m/%Y')
            
            # 3. Conversione in CSV con ; come separatore e , come decimale
            csv = df_csv.to_csv(sep=";", decimal=",", encoding="utf-8-sig")
            
            st.download_button(
                label="SCARICA FILE EXCEL (.csv)",
                data=csv,
                file_name=f"Analisi_Portafoglio_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                help="Formattato con colonne separate (;) e decimali con virgola (,) per Excel Italiano."
            )

        else:
            st.error("La ricerca non ha prodotto risultati validi. Controlla i Ticker inseriti.")


