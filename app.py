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
    div.stButton > button:first-child { width: 100%; text-align: left; background-color: #1F2937; color: white; border: 1px solid #374151; }
    div.stButton > button:hover { background-color: #FF0000 !important; }
</style>""", unsafe_allow_html=True)

# --- FUNÇÕES TÉCNICAS ---
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
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    
    st.markdown("<h2 style='color:#FF0000;'>Data Support</h2><hr>", unsafe_allow_html=True)
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação"): st.session_state.pagina = "⚖️ Legislação"
    if st.button("👥 Duplicatas"): st.session_state.pagina = "👥 Duplicatas"

# --- PÁGINAS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados (LIMS)")
    pasted = st.text_area("Cole os dados aqui", height=250)
    if st.button("Processar Dados", type="primary"):
        df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python')
        df['V_num'], _ = zip(*df['Valor'].map(parse_val))
        # Cálculo interno em mg, mas preservamos a visualização original
        df['V_calculo_mg'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in str(r['Unidade de Medida']).lower() else r['V_num'], axis=1)
        df['key_busca'] = df['Análise'].map(limpar_texto)
        st.session_state["df_global"] = df
        st.success("Dados carregados com sucesso!")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação: Dissolvido vs Total")
    df = st.session_state["df_global"]
    if df is not None:
        D = df[df['Método de Análise'].str.contains('Diss', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Tot', case=False, na=False)].copy()
        if not D.empty and not T.empty:
            m = pd.merge(D, T, on=['Id', 'key_busca'], suffixes=('_D', '_T'))
            m['Status'] = np.where(m['V_calculo_mg_D'] > m['V_calculo_mg_T'], "❌ NÃO CONFORME", "✅ OK")
            res = m[['Id', 'Análise_D', 'Valor_D', 'Unidade de Medida_D', 'Valor_T', 'Unidade de Medida_T', 'Status']]
            res.columns = ['ID', 'Analito', 'Valor D', 'Unid D', 'Valor T', 'Unid T', 'Status']
            st.dataframe(res, use_container_width=True)

elif st.session_state.pagina == "⚖️ Legislação":
    st.title("⚖️ Conformidade Legal")
    catalog = load_catalog()
    df = st.session_state["df_global"]
    if df is not None:
        escolha = st.selectbox("Selecione a Legislação:", list(catalog.keys()))
        limites = {limpar_texto(k): v for k, v in catalog[escolha]['limits_mgL'].items()}
        
        df_l = df.copy()
        df_l['VMP_Legislação'] = df_l['key_busca'].map(limites)
        
        # Define a unidade da legislação baseado no nome da norma (Solo = mg/kg, Água/Efluente = mg/L)
        unid_leg = "mg/kg" if "Solo" in escolha or "Resíduos" in escolha else "mg/L"
        df_l['Unid_Leg'] = unid_leg
        
        df_l = df_l.dropna(subset=['VMP_Legislação'])
        df_l['Parecer'] = np.where(df_l['V_calculo_mg'] > df_l['VMP_Legislação'], "❌ REPROVADO", "✅ OK")
        
        # Tabela com as unidades do LIMS e da Legislação lado a lado
        res = df_l[['Id', 'Análise', 'Valor', 'Unidade de Medida', 'VMP_Legislação', 'Unid_Leg', 'Parecer']]
        res.columns = ['ID', 'Analito', 'Valor LIMS', 'Unid LIMS', 'VMP (mg)', 'Unid Leg.', 'Parecer']
        st.dataframe(res, use_container_width=True)

elif st.session_state.pagina == "👥 Duplicatas":
    st.title("👥 Controle de Precisão (RPD)")
    df = st.session_state["df_global"]
    if df is not None:
        amostras = df['Nº Amostra'].dropna().unique()
        c1, c2 = st.columns(2)
        a1 = c1.selectbox("Amostra Original", amostras)
        a2 = c2.selectbox("Duplicata", amostras)
        if a1 and a2:
            d1 = df[df['Nº Amostra'] == a1][['key_busca', 'V_calculo_mg', 'Análise', 'Valor', 'Unidade de Medida']]
            d2 = df[df['Nº Amostra'] == a2][['key_busca', 'V_calculo_mg', 'Valor', 'Unidade de Medida']]
            comp = pd.merge(d1, d2, on='key_busca', suffixes=('_Ori', '_Dup'))
            comp['RPD (%)'] = (abs(comp['V_calculo_mg_Ori'] - comp['V_calculo_mg_Dup']) / ((comp['V_calculo_mg_Ori'] + comp['V_calculo_mg_Dup'])/2)) * 100
            comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= 20 else "❌ FALHA")
            res = comp[['Análise', 'Valor_Ori', 'Unidade de Medida_Ori', 'Valor_Dup', 'Unidade de Medida_Dup', 'RPD (%)', 'Status']]
            st.dataframe(res, use_container_width=True)
