import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Caricamento Dati Processati
file_path = 'data/processed/COFFEE_MERGED.xlsx'
df = pd.read_excel(file_path)

# Pulizia da eventuali valori infiniti o nulli residui
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df.dropna(inplace=True)

# 2. Statistiche Descrittive
print("=== TABELLA 1: STATISTICHE DESCRITTIVE ===")
desc_stats = df[['Excess_Return_t_plus_1', 'SP_t', 'R_t']].describe().round(4)
print(desc_stats)
print("\n")

# 3. Test di Stazionarietà (Augmented Dickey-Fuller)
print("=== TEST DI STAZIONARIETA' ===")
def print_adf(series, name):
    result = adfuller(series)
    print(f"{name} -> Statistica ADF: {result[0]:.4f}, p-value: {result[1]:.4f}")
    if result[1] < 0.05:
        print(f"  [!] La serie {name} è STAZIONARIA (rifiutiamo H0)\n")
    else:
        print(f"  [!] La serie {name} ha una RADICE UNITARIA\n")

print_adf(df['Excess_Return_t_plus_1'], "Excess Return (t+1)")
print_adf(df['SP_t'], "Speculative Pressure (SP_t)")

# 4. Regressione OLS (Newey-West) - BASELINE
print("=== REGRESSIONE PREDITTIVA (FULL SAMPLE) ===")
# Omettiamo il Basis, manteniamo SP_t e R_t (momentum)
X = df[['SP_t', 'R_t']]
X = sm.add_constant(X)
y = df['Excess_Return_t_plus_1']

model = sm.OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags': 4})
print(model.summary())

# 5. Generazione Grafici
sns.set_theme(style="whitegrid")

# Grafico 1: Prezzo vs SP_t
fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot(pd.to_datetime(df['Date']), df['Price_c1'], color='#1f77b4', linewidth=1.5, label='Arabica Price (LHS)')
ax1.set_ylabel('Arabica Coffee Futures Price (USd/lb)', color='#1f77b4', fontweight='bold')
ax1.tick_params(axis='y', labelcolor='#1f77b4')

ax2 = ax1.twinx() 
ax2.plot(pd.to_datetime(df['Date']), df['SP_t'], color='#d62728', alpha=0.6, linewidth=1, label='Speculative Pressure (RHS)')
ax2.set_ylabel('Speculative Pressure ($SP_t$)', color='#d62728', fontweight='bold')
ax2.tick_params(axis='y', labelcolor='#d62728')

plt.title('Figure 1: Coffee Arabica Price vs Speculative Positioning', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('figure_1_price_vs_sp.png') # Salva l'immagine per GitHub

# 6. TEST DI ROBUSTEZZA (Shock Climatico Brasile 2021)
print("\n=== ROBUSTNESS TEST 1: SUB-SAMPLE DAL LUG 2021 (SHOCK REGIME) ===")
df_shock = df[df['Date'] >= pd.to_datetime('2021-06-01')].copy()

X_shock = df_shock[['SP_t', 'R_t']]
X_shock = sm.add_constant(X_shock)
y_shock = df_shock['Excess_Return_t_plus_1']

model_shock = sm.OLS(y_shock, X_shock).fit(cov_type='HAC', cov_kwds={'maxlags': 4})
print(f"Numero di osservazioni nel sub-sample: {len(df_shock)}")
print(model_shock.summary())

print("\nAnalisi completata. Grafici salvati nella cartella corrente.")