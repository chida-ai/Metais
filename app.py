# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="OPERALAB - Gestão ICP", layout="wide")

# --- FUNÇÕES DE PARSE E CONVERSÃO ---
def parse_val(val_str):
    if pd.isna(val_str): return None, False
    s = str(val_str).strip().replace(',', '.')
    cens = s.startswith('<')
    s_clean = s.replace('<', '').strip()
    try:
        v = float(s_clean)
    except:
        v = None
    return v, cens

def to_mg_per_L(val, unit):
    if val is None or pd.isna(unit): return None
    u = str(unit).strip().lower()
    if u == 'mg/l': return val
    if u in ['µg/l', 'ug/l']: return val / 1000.0
    return val

def normalize_analito(name):
    if pd.isna(name): return None
    return re.sub(r"\s+Dissolvido$", "", str(name).strip(), flags=re.IGNORECASE)

# --- MOTOR DE INCERTEZA ---
def calcular_incerteza(valor, rsd_obs, p):
    if valor is None: return 0
    # incerteza combinada: sqrt(rsd² + u_calib² + u_pip² + u_dil²)
    uc_rel = np.sqrt(rsd_obs**2 + p['u_calib']**2 + p['u_pip']**2 + p['u_dil']**2)
    U = p['k'] * valor * (uc_rel / 100)
    return U

# --- CARREGAR CATÁLOGO ---
@st.cache_data
def load_catalog():
    try:
        with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

catalog = load_catalog()

# --- INTERFACE SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Configurações Lab")
    p = {
        'u_calib': st.number_input("u_Calibração (%)", 0.0, 5.0, 1.5),
        'u_pip': st.number_input("u_Pipetagem (%)", 0.0, 5.0, 2.5),
        'u_dil': st.number_input("u_Diluição (%)", 0.0, 5.0, 0.8),
        'k': st.number_input("Fator k (95%)", 1.0, 3.0, 2.0),
        'rpd_max': st.number_input("RPD Máx (%)", 1.0, 50.0, 20.0)
    }
    st.divider()
    uploaded_file = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])

# --- LÓGICA PRINCIPAL ---
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df_raw = pd.read_csv(uploaded_file)
    else:
        df_raw = pd.read_excel(uploaded_file)

    # Pré-processamento
    df_raw['Valor_num'], df_raw['Censurado'] = zip(*df_raw['Valor'].map(parse_val))
    df_raw['V_mgL'] = df_raw.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df_raw['Analito_base'] = df_raw['Análise'].map(normalize_analito)

    aba1, aba2, aba3 = st.tabs(["🧪 Validação Técnica", "⚖️ Legislação", "👥 Duplicatas"])

    with aba1:
        st.subheader("Dissolvido vs Total & QC Ítrio")
        # Comparação Dissolvido x Total
        D = df_raw[df_raw['Método de Análise'].str.contains('Dissolvidos', na=False)].copy()
        T = df_raw[df_raw['Método de Análise'].str.contains('Totais', na=False)].copy()
        merged = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
        
        merged['U_tot'] = merged['V_mgL_tot'].map(lambda x: calcular_incerteza(x, 2.0, p)) # assumindo RSD médio 2%
        merged['Status'] = np.where(merged['V_mgL_diss'] > (merged['V_mgL_tot'] + merged['U_tot']), 'NÃO CONFORME', 'OK')
        
        st.dataframe(merged[['Id', 'Analito_base', 'V_mgL_diss', 'V_mgL_tot', 'U_tot', 'Status']].style.apply(
            lambda x: ['background-color: #FF3B30' if v == 'NÃO CONFORME' else '' for v in x], axis=1, subset=['Status']
        ))

        # QC Ítrio
        itrio = df_raw[df_raw['Análise'].str.contains('ítrio|itrio', case=False, na=False)]
        if not itrio.empty:
            st.divider()
            st.subheader("Controle Padrão Interno (Ítrio)")
            itrio['Status_QC'] = itrio['Valor_num'].map(lambda x: 'OK' if 70 <= x <= 130 else 'NÃO CONFORME')
            st.dataframe(itrio[['Id', 'Nº Amostra', 'Análise', 'Valor_num', 'Status_QC']])

    with aba2:
        st.subheader("Avaliação por Legislação")
        spec_key = st.selectbox("Selecione a Portaria", options=list(catalog.keys()))
        if spec_key:
            limits = catalog[spec_key]['limits_mgL']
            # Filtra apenas o que tem limite e aplica regra de incerteza
            df_leg = df_raw[df_raw['Analito_base'].isin(limits.keys())].copy()
            df_leg['Limite'] = df_leg['Analito_base'].map(limits)
            df_leg['U'] = df_leg['V_mgL'].map(lambda x: calcular_incerteza(x, 3.0, p))
            
            def julgar(r):
                if r['V_mgL'] > r['Limite']: return "❌ NÃO CONFORME"
                if (r['V_mgL'] + r['U']) > r['Limite']: return "🔄 REANALISAR (Zona de Incerteza)"
                return "✅ CONFORME"
            
            df_leg['Parecer'] = df_leg.apply(julgar, axis=1)
            st.dataframe(df_leg[['Id', 'Analito_base', 'V_mgL', 'U', 'Limite', 'Parecer']])

    with aba3:
        st.subheader("Cálculo de RPD (Duplicatas)")
        amostras = df_raw['Nº Amostra'].unique()
        c1, c2 = st.columns(2)
        a1 = c1.selectbox("Amostra Original", amostras)
        a2 = c2.selectbox("Duplicata", amostras)
        
        if a1 and a2:
            res_a1 = df_raw[df_raw['Nº Amostra'] == a1][['Analito_base', 'V_mgL']]
            res_a2 = df_raw[df_raw['Nº Amostra'] == a2][['Analito_base', 'V_mgL']]
            comp = pd.merge(res_a1, res_a2, on='Analito_base', suffixes=('_1', '_2'))
            comp['RPD'] = abs(comp['V_mgL_1'] - comp['V_mgL_2']) / ((comp['V_mgL_1'] + comp['V_mgL_2'])/2) * 100
            comp['Status'] = comp['RPD'].map(lambda x: 'OK' if x <= p['rpd_max'] else 'EXCEDE LIMITE')
            st.dataframe(comp)

else:
    st.info("Aguardando upload de arquivo para iniciar as avaliações.")
