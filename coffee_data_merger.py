import pandas as pd
import numpy as np
import yfinance as yf
from datetime import timedelta
import os

print("Avvio del processo di Data Merging per il progetto Coffee Futures...")

# =======================================================
# 1. SETUP DEI PERCORSI
# =======================================================
percorso_prezzi = 'data/raw/Dati_Storici_Coffee_C_Futures.xlsx'
cartella_cftc = 'data/raw/CFTC/'  # La cartella dove hai messo TUTTI i file .txt
percorso_output = 'data/processed/COFFEE_MERGED.xlsx'

# Assicuriamoci che la cartella processed esista, altrimenti la creiamo
os.makedirs('data/processed', exist_ok=True)

# =======================================================
# 2. ELABORAZIONE DATI PREZZI (Investing.com)
# =======================================================
print("Elaborazione prezzi da Investing.com...")
try:
    df_prezzi = pd.read_excel(percorso_prezzi)
except FileNotFoundError:
    print(f"ERRORE: Non trovo il file dei prezzi in {percorso_prezzi}")
    exit()

df_prezzi = df_prezzi.rename(columns={'Data': 'Date', 'Ultimo': 'Price_c1'})

# Pulizia formato europeo (es. 259,33 -> 259.33)
df_prezzi['Price_c1'] = df_prezzi['Price_c1'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.').astype(float)
df_prezzi['Date'] = pd.to_datetime(df_prezzi['Date'], format='%d.%m.%Y')
df_prezzi = df_prezzi.sort_values('Date').reset_index(drop=True)

# Filtriamo solo i Venerdì (Day of week = 4)
df_prezzi_venerdi = df_prezzi[df_prezzi['Date'].dt.dayofweek == 4].copy()

# =======================================================
# 3. ELABORAZIONE DATI CFTC (Lettura Batch)
# =======================================================
# =======================================================
# 3. ELABORAZIONE DATI CFTC (Lettura Batch e Fix Date Dinamico)
# =======================================================
print("Lettura e fusione automatica dei file CFTC...")

lista_df_cftc = []
file_letti = 0

# Scansiona tutti i file nella cartella CFTC
for nome_file in os.listdir(cartella_cftc):
    if nome_file.endswith('.txt') or nome_file.endswith('.csv'):
        percorso_completo = os.path.join(cartella_cftc, nome_file)
        print(f" - Leggendo {nome_file}...")
        try:
            df_temp = pd.read_csv(percorso_completo, low_memory=False)
            lista_df_cftc.append(df_temp)
            file_letti += 1
        except Exception as e:
             print(f"   Errore nella lettura di {nome_file}: {e}")

if file_letti == 0:
    print(f"ERRORE: Nessun file trovato nella cartella {cartella_cftc}")
    exit()

# Unisce tutti i dataframe in uno solo
df_cftc_completo = pd.concat(lista_df_cftc, ignore_index=True)

print("Filtraggio per il mercato Arabica e allineamento date...")
# Filtro specifico per l'Arabica (COFFEE C)
df_coffee_cot = df_cftc_completo[df_cftc_completo['Market_and_Exchange_Names'].str.contains('COFFEE C', na=False, case=False)].copy()

# =======================================================
# LA MAGIA DEL DATA ENGINEERING: FIX DINAMICO DELLE DATE
# Trova tutte le colonne che assomigliano a una data e le unisce,
# risolvendo il cambio di formato della CFTC dal 2013 in poi.
colonne_date = [c for c in df_coffee_cot.columns if 'Report_Date_as' in c]
df_coffee_cot['Report_Date_Raw'] = df_coffee_cot[colonne_date[0]]
if len(colonne_date) > 1:
    for col in colonne_date[1:]:
        df_coffee_cot['Report_Date_Raw'] = df_coffee_cot['Report_Date_Raw'].fillna(df_coffee_cot[col])

df_coffee_cot['Report_Date'] = pd.to_datetime(df_coffee_cot['Report_Date_Raw'])
# =======================================================

# Calcolo Pressione Speculativa (SP_t) usando le minuscole corrette '_All'
df_coffee_cot['SP_t'] = (df_coffee_cot['M_Money_Positions_Long_All'] - df_coffee_cot['M_Money_Positions_Short_All']) / df_coffee_cot['Open_Interest_All']

# Allineamento temporale (Martedì -> Venerdì)
df_coffee_cot['Date'] = df_coffee_cot['Report_Date'] + timedelta(days=3)

# Print di diagnostica fondamentale
print(f" > Dati CFTC estratti con successo dal {df_coffee_cot['Date'].min().date()} al {df_coffee_cot['Date'].max().date()}")

# Teniamo solo le colonne che ci servono davvero per la fusione finale (con le maiuscole/minuscole corrette)
colonne_da_tenere_cftc = [
    'Date', 'Open_Interest_All', 'M_Money_Positions_Long_All', 'M_Money_Positions_Short_All', 'SP_t'
]
df_coffee_cot = df_coffee_cot[colonne_da_tenere_cftc]

# =======================================================
# 4. DOWNLOAD TASSO RISK-FREE (yfinance)
# =======================================================
print("Download tasso Risk-Free (US 3-Month T-Bill)...")
irx = yf.download('^IRX', start='2010-01-01', end='2026-12-31', progress=False)

if isinstance(irx.columns, pd.MultiIndex):
    rf_series = irx['Close']['^IRX']
else:
    rf_series = irx['Close']

df_rf = rf_series.reset_index()
df_rf = df_rf.rename(columns={'Close': 'RF_Annual_Pct', '^IRX': 'RF_Annual_Pct'})

# De-annualizzazione (Tasso settimanale)
df_rf['RF_Weekly'] = (1 + df_rf['RF_Annual_Pct'] / 100) ** (1/52) - 1
df_rf['Date'] = pd.to_datetime(df_rf['Date']).dt.tz_localize(None)

# =======================================================
# 5. MERGE E CALCOLO RENDIMENTI
# =======================================================
# =======================================================
# 5. MERGE E CALCOLO RENDIMENTI
# =======================================================
print("Fusione finale dei dataset...")

# Merge 1: Prezzi + CFTC
df_merged = pd.merge(df_prezzi_venerdi, df_coffee_cot, on='Date', how='inner')

# ---> AGGIUNGI QUESTE DUE RIGHE QUI <---
# Forziamo le date allo stesso identico formato (nanosecondi) per evitare il MergeError
df_merged['Date'] = df_merged['Date'].astype('datetime64[ns]')
df_rf['Date'] = df_rf['Date'].astype('datetime64[ns]')
# --------------------------------------

# Merge 2: Aggiunta Risk-Free (backward fill per i festivi)
df_merged = df_merged.sort_values('Date')
df_rf = df_rf.sort_values('Date')
df_merged = pd.merge_asof(df_merged, df_rf[['Date', 'RF_Weekly']], on='Date', direction='backward')

# ... il resto del codice rimane identico ...
df_merged['RF_Weekly'] = df_merged['RF_Weekly'].ffill()

# Calcoli Log-Return ed Excess Return
df_merged['Weekly_Return'] = np.log(df_merged['Price_c1'] / df_merged['Price_c1'].shift(1))
df_merged['R_t'] = df_merged['Weekly_Return'] - df_merged['RF_Weekly']
df_merged['Excess_Return_t_plus_1'] = df_merged['R_t'].shift(-1)

# Pulizia finale
df_merged.dropna(subset=['Excess_Return_t_plus_1', 'R_t'], inplace=True)

colonne_finali = [
    'Date', 'Price_c1', 'SP_t', 'R_t', 'Excess_Return_t_plus_1', 
    'Open_Interest_All', 'M_Money_Positions_Long_All', 'M_Money_Positions_Short_All'
]
df_finale = df_merged[colonne_finali]

# =======================================================
# 6. ESPORTAZIONE
# =======================================================
df_finale.to_excel(percorso_output, index=False)
print(f"\n✅ FATTO! Dataset salvato con successo in: {percorso_output}")
print(f"Dimensioni del dataset: {df_finale.shape[0]} settimane analizzabili.")