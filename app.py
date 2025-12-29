# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, unicodedata
from pathlib import Path

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

# --- CSS DARK ---
st.markdown("""<style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #374151; }
    .stButton button { width: 100%; text-align: left; }
</style>""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_texto(t):
    if pd.isna(t): return ""
    t = str(t).strip().lower()
    t = re.sub(r"\s+(total|dissolvido|lixiviado|solubilizado)$", "", t)
    nfkd = unicodedata.normalize('NFKD', t)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def parse_val(v):
    if pd.isna(v): return None, False
    s = str(v).replace('<','').replace('.', '').replace(',', '.')
    try: return float(s), str(v).startswith('<')
    except: return None, False

def load_catalog():
    try:
        with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

# --- ESTADO DE SESSÃO ---
if "df_global" not in st.session_state: st.session_state["df_global"] = None
if "pagina" not in st.session_state: st.session_state["pagina"] = "📥 Inserir Dados"

# --- SIDEBAR ---
with st.sidebar:
    st.title("Data Support")
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação & U"): st.session_state.pagina = "⚖️ Legislação & U"

# --- PÁGINAS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados")
    pasted = st.text_area("Cole as colunas do LIMS", height=200)
    if st.button("Processar Dados", type="primary"):
        df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python')
        df['V_num'], _ = zip(*df['Valor'].map(parse_val))
        
        # LOGICA DE UNIDADE EXPLICITA
        df['Unidade_Original'] = df['Unidade de Medida'].astype(str)
        df['Conversão'] = df['Unidade_Original'].apply(lambda x: "÷ 1000" if 'ug' in x.lower() else "x 1")
        df['V_mg'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in r['Unidade_Original'].lower() else r['V_num'], axis=1)
        
        df['key_busca'] = df['Análise'].map(limpar_texto)
        st.session_state["df_global"] = df
        st.success("Dados processados com memória de unidade.")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Conferência: Dissolvido vs Total")
    df = st.session_state["df_global"]
    if df is not None:
        D = df[df['Método de Análise'].str.contains('Diss', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Tot', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            m = pd.merge(D, T, on=['Id', 'key_busca'], suffixes=('_D', '_T'))
            m['Status'] = np.where(m['V_mg_D'] > m['V_mg_T'], "❌ D > T", "✅ OK")
            
            # Mostrando as unidades originais para sua segurança
            res = m[['Id', 'Análise_D', 'V_num_D', 'Unidade_Original_D', 'V_num_T', 'Unidade_Original_T', 'Status']]
            res.columns = ['ID', 'Analito', 'Valor D', 'Unid D', 'Valor T', 'Unid T', 'Avaliação']
            st.dataframe(res, use_container_width=True)

elif st.session_state.pagina == "⚖️ Legislação & U":
    st.title("⚖️ Verificação de Limites")
    catalog = load_catalog()
    df = st.session_state["df_global"]
    if df is not None:
        escolha = st.selectbox("Norma:", list(catalog.keys()))
        limites = {limpar_texto(k): v for k, v in catalog[escolha]['limits_mgL'].items()}
        
        df_l = df.copy()
        df_l['VMP_mg'] = df_l['key_busca'].map(limites)
        df_l = df_l.dropna(subset=['VMP_mg'])
        
        df_l['Parecer'] = np.where(df_l['V_mg'] > df_l['VMP_mg'], "❌ REPROVADO", "✅ OK")
        
        # Aqui você vê o valor original, a unidade e o valor já convertido
        res = df_l[['Id', 'Análise', 'V_num', 'Unidade_Original', 'V_mg', 'VMP_mg', 'Parecer']]
        res.columns = ['ID', 'Analito', 'Valor LIMS', 'Unid. LIMS', 'Valor (mg)', 'VMP (mg)', 'Parecer']
        st.dataframe(res, use_container_width=True)
