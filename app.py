# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, unicodedata
from pathlib import Path

st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

# --- CSS DARK ---
st.markdown("""<style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    div.stButton > button:first-child { width: 100%; background-color: #1F2937; color: white !important; text-align: left; }
    div.stButton > button:hover { background-color: #FF0000 !important; }
</style>""", unsafe_allow_html=True)

# --- FUNÇÃO DE LIMPEZA UNIVERSAL ---
def limpar_texto(t):
    if pd.isna(t): return ""
    t = str(t).strip().lower()
    # Remove "Total", "Dissolvido", etc.
    t = re.sub(r"\s+(total|dissolvido|lixiviado|solubilizado|as|pb|cd|cr|cu|ni|zn|hg|ba)$", "", t)
    # Remove acentos
    return "".join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c))

def parse_val(v):
    if pd.isna(v): return None, False
    s = str(v).replace('<','').replace('.', '').replace(',', '.')
    try: return float(s), str(v).startswith('<')
    except: return None, False

def load_catalog():
    try:
        with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.sidebar.error(f"Erro no JSON: {e}")
        return {}

# --- ESTADO E SIDEBAR ---
if "df_global" not in st.session_state: st.session_state["df_global"] = None
if "pagina" not in st.session_state: st.session_state["pagina"] = "📥 Inserir Dados"

with st.sidebar:
    st.title("Data Support")
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("⚖️ Legislação"): st.session_state.pagina = "⚖️ Legislação"

# --- PÁGINAS ---
if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados")
    pasted = st.text_area("Cole os dados do LIMS aqui", height=250)
    if st.button("Processar", type="primary"):
        df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python')
        df['V_num'], _ = zip(*df['Valor'].map(parse_val))
        df['V_padrao'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in str(r['Unidade de Medida']).lower() else r['V_num'], axis=1)
        # Criamos a chave de busca limpa
        df['key_busca'] = df['Análise'].map(limpar_texto)
        st.session_state["df_global"] = df
        st.success("Dados carregados!")

elif st.session_state.pagina == "⚖️ Legislação":
    st.title("⚖️ Conformidade")
    catalog = load_catalog()
    if st.session_state["df_global"] is None: st.warning("Sem dados.")
    else:
        escolha = st.selectbox("Selecione a Norma:", list(catalog.keys()))
        if escolha:
            # Prepara os limites do JSON para busca limpa
            limites_json = catalog[escolha]['limits_mgL']
            limites_limpos = {limpar_texto(k): v for k, v in limites_json.items()}
            
            df = st.session_state["df_global"].copy()
            # Filtra apenas o que bate com o JSON
            df['Limite'] = df['key_busca'].map(limites_limpos)
            
            # Mostra o diagnóstico se não bater nada
            if df['Limite'].isnull().all():
                st.error("Nenhum analito coincidiu.")
                st.write("Detectado no LIMS:", list(df['key_busca'].unique()))
                st.write("Esperado no JSON:", list(limites_limpos.keys()))
            else:
                df = df.dropna(subset=['Limite'])
                df['Status'] = np.where(df['V_padrao'] > df['Limite'], "❌ REPROVADO", "✅ OK")
                st.dataframe(df[['Id', 'Análise', 'V_padrao', 'Limite', 'Status']])
