# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, unicodedata
from pathlib import Path

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

# --- CSS DARK PROFISSIONAL ---
st.markdown("""<style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    div.stButton > button:first-child { 
        width: 100%; border-radius: 4px; height: 3em;
        background-color: #1F2937; color: white !important;
        border: 1px solid #374151; text-align: left; padding-left: 15px;
    }
    div.stButton > button:hover { background-color: #FF0000 !important; border: 1px solid #FF0000; }
    .stButton button[kind="primary"] { background-color: #374151 !important; color: white !important; }
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #374151; }
</style>""", unsafe_allow_html=True)

# --- FUNÇÕES TÉCNICAS BLINDADAS ---
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

# --- SIDEBAR COM LOGO ---
with st.sidebar:
    # Busca o logo na pasta assets
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    
    st.markdown("""
        <div style="text-align: left; margin-bottom: 25px;">
            <h2 style="margin:0; font-size: 24px; color: #FFFFFF;">Data Support</h2>
            <div style="height:3px; background:#FF0000; width:100%; margin-top:2px;"></div>
            <p style="color: #FF0000; font-size: 12px; font-weight: bold; margin-top:4px;">LAB AMBIENTAL</p>
        </div>
        """, unsafe_allow_html=True)
    
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação & U"): st.session_state.pagina = "⚖️ Legislação & U"
    if st.button("👥 Duplicatas"): st.session_state.pagina = "👥 Duplicatas"

# --- MÓDULOS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados (LIMS)")
    pasted = st.text_area("Cole as colunas do LIMS aqui (Id, Análise, Valor, Unidade, Nº Amostra...)", height=250)
    if st.button("Processar Dados", type="primary"):
        if pasted:
            df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python')
            df['V_num'], _ = zip(*df['Valor'].map(parse_val))
            df['V_padrao'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in str(r['Unidade de Medida']).lower() else r['V_num'], axis=1)
            df['key_busca'] = df['Análise'].map(limpar_texto)
            st.session_state["df_global"] = df
            st.success("Dados carregados e padronizados!")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação Técnica (D vs T)")
    df = st.session_state["df_global"]
    if df is None: st.warning("Aguardando dados...")
    else:
        D = df[df['Método de Análise'].str.contains('Dissolvidos|Dissolvido', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Totais|Total', case=False, na=False)].copy()
        if not D.empty and not T.empty:
            m = pd.merge(D, T, on=['Id', 'key_busca'], suffixes=('_diss', '_tot'))
            # REGRA: Dissolvido > Total = Não Conforme
            m['Status'] = np.where(m['V_padrao_diss'] > m['V_padrao_tot'], "❌ NÃO CONFORME (D > T)", "✅ OK")
            res = m[['Id', 'Análise_diss', 'V_padrao_diss', 'V_padrao_tot', 'Status']]
            res.columns = ['ID', 'Analito', 'Conc. Diss (mg)', 'Conc. Total (mg)', 'Avaliação']
            st.dataframe(res, use_container_width=True)
        else: st.info("Não foram encontrados pares de Dissolvido/Total para este lote.")

elif st.session_state.pagina == "⚖️ Legislação & U":
    st.title("⚖️ Conformidade Legal")
    catalog = load_catalog()
    df = st.session_state["df_global"]
    if df is None: st.warning("Aguardando dados...")
    else:
        escolha = st.selectbox("Selecione a Legislação:", list(catalog.keys()))
        if escolha:
            limites_limpos = {limpar_texto(k): v for k, v in catalog[escolha]['limits_mgL'].items()}
            df_leg = df.copy()
            df_leg['Limite'] = df_leg['key_busca'].map(limites_limpos)
            df_leg = df_leg.dropna(subset=['Limite'])
            if df_leg.empty:
                st.error("Nenhum analito bateu com os nomes desta legislação.")
            else:
                df_leg['Status'] = np.where(df_leg['V_padrao'] > df_leg['Limite'], "❌ REPROVADO", "✅ OK")
                res = df_leg[['Id', 'Análise', 'V_padrao', 'Limite', 'Status']]
                res.columns = ['ID', 'Analito', 'Resultado (mg)', 'VMP (mg)', 'Parecer']
                st.dataframe(res, use_container_width=True)

elif st.session_state.pagina == "👥 Duplicatas":
    st.title("👥 Controle de Precisão (RPD)")
    df = st.session_state["df_global"]
    if df is None: st.warning("Aguardando dados...")
    else:
        amostras = df['Nº Amostra'].dropna().unique()
        c1, c2 = st.columns(2)
        a1 = c1.selectbox("Amostra Original", amostras)
        a2 = c2.selectbox("Duplicata", amostras)
        if a1 and a2:
            d1 = df[df['Nº Amostra'] == a1][['key_busca', 'V_padrao', 'Análise']]
            d2 = df[df['Nº Amostra'] == a2][['key_busca', 'V_padrao']]
            comp = pd.merge(d1, d2, on='key_busca', suffixes=('_Ori', '_Dup'))
            comp['RPD (%)'] = (abs(comp['V_padrao_Ori'] - comp['V_padrao_Dup']) / ((comp['V_padrao_Ori'] + comp['V_padrao_Dup'])/2)) * 100
            comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= 20 else "❌ FALHA")
            res = comp[['Análise', 'V_padrao_Ori', 'V_padrao_Dup', 'RPD (%)', 'Status']]
            res.columns = ['Analito', 'Original (mg)', 'Duplicata (mg)', 'RPD (%)', 'Situação']
            st.dataframe(res, use_container_width=True)
