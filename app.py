# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from pathlib import Path

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Data Support - Gestão Laboratorial", layout="wide")

# --- ESTADO DE SESSÃO ---
if "df_global" not in st.session_state:
    st.session_state["df_global"] = None

# --- AUXILIARES TÉCNICOS (Baseados no seu código original) ---
def parse_val(val_str):
    if pd.isna(val_str): return None, False
    s = str(val_str).strip()
    cens = s.startswith('<')
    s_clean = s.replace('<','').replace('.', '').replace(',', '.')
    try: v = float(s_clean)
    except: v = None
    return v, cens

def to_mg_per_L(val, unit):
    if val is None or pd.isna(unit): return None
    u = str(unit).strip().lower()
    if u in ['µg/l','ug/l']: return val/1000.0
    return val

def normalize_analito(name):
    if pd.isna(name): return None
    return re.sub(r"\s+Dissolvido$", "", str(name).strip(), flags=re.IGNORECASE)

def calc_U(val, p):
    if val is None: return 0
    uc_rel = np.sqrt(p['rsd']**2 + p['u_cal']**2 + p['u_pip']**2 + p['u_dil']**2)
    return p['k'] * val * (uc_rel / 100)

@st.cache_data
def load_catalog():
    try:
        with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

# --- SIDEBAR: LOGO, TÍTULO E NAVEGAÇÃO ---
with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    
    # Cabeçalho Data Support
    st.markdown("""
        <div style="text-align: left; margin-bottom: 20px;">
            <h1 style="margin:0; font-size: 28px;">Data Support</h1>
            <div style="height:3px; background:#FF0000; width:100%; margin-top:5px;"></div>
            <p style="color: #FF0000; font-size: 14px; font-weight: bold; margin-top:5px;">
                Avaliação de Resultados
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    modulo = st.radio(
        "Selecione o Módulo:",
        ["📥 Inserir Dados", "🧪 Avaliação Técnica (Lote)", "⚖️ Legislação & Incerteza", "👥 Duplicatas"]
    )
    st.divider()
    st.caption("v1.0 • © OPERALAB")

# --- MÓDULO 0: INSERIR DADOS ---
if modulo == "📥 Inserir Dados":
    st.header("Entrada de Dados do Lote")
    col1, col2 = st.columns(2)
    with col1:
        file = st.file_uploader("Upload de Excel ou CSV", type=["xlsx", "csv"])
    with col2:
        pasted = st.text_area("Cole os dados aqui (TAB ou ';')", height=150)
    
    if st.button("Carregar Dados", type="primary"):
        df_temp = None
        if file:
            df_temp = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        elif pasted:
            for sep in ['\t', ';', ',']:
                try:
                    df_check = pd.read_csv(io.StringIO(pasted), sep=sep)
                    if len(df_check.columns) >= 3:
                        df_temp = df_check
                        break
                except: pass
        
        if df_temp is not None:
            # Pré-processamento (Parseando valores e unidades)
            df_temp['Valor_num'], df_temp['Censurado'] = zip(*df_temp['Valor'].map(parse_val))
            df_temp['V_mgL'] = df_temp.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
            df_temp['Analito_base'] = df_temp['Análise'].map(normalize_analito)
            st.session_state["df_global"] = df_temp
            st.success("Dados carregados com sucesso!")
            st.dataframe(df_temp.head(10))
        else:
            st.error("Erro: Não foi possível interpretar o formato dos dados.")

# --- MÓDULO 1: AVALIAÇÃO TÉCNICA (Lote, Diss x Tot, Ítrio) ---
elif modulo == "🧪 Avaliação Técnica (Lote)":
    st.header("Avaliação de Lote: Dissolvidos, Totais e Ítrio")
    if st.session_state["df_global"] is None:
        st.info("Por favor, carregue os dados no módulo 'Inserir Dados'.")
    else:
        df = st.session_state["df_global"]
        
        # Comparação Dissolvido x Total
        st.subheader("1. Comparação Dissolvidos vs Totais")
        D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            merged = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
            merged['Avaliação'] = np.where(merged['V_mgL_diss'] > (merged['V_mgL_tot'] * 1.05), "❌ NÃO CONFORME", "✅ OK")
            st.dataframe(merged[['Id', 'Analito_base', 'V_mgL_diss', 'V_mgL_tot', 'Avaliação']].style.apply(
                lambda x: ['background-color: #FF3B30; color: white' if v == "❌ NÃO CONFORME" else '' for v in x], axis=1, subset=['Avaliação']
            ))
        
        # Ítrio
        st.divider()
        st.subheader("2. Controle de Qualidade Ítrio (%)")
        itrio = df[df['Análise'].str.contains('itrio|ítrio', case=False, na=False)]
        if not itrio.empty:
            itrio['Status_QC'] = itrio['Valor_num'].apply(lambda x: "✅ OK" if 70 <= x <= 130 else "❌ REPROVADO")
            st.table(itrio[['Id', 'Nº Amostra', 'Análise', 'Valor_num', 'Status_QC']])

# --- MÓDULO 2: LEGISLAÇÃO E INCERTEZA ---
elif modulo == "⚖️ Legislação & Incerteza":
    st.header("Avaliação por Legislação com Incerteza Expandida")
    if st.session_state["df_global"] is None:
        st.info("Por favor, carregue os dados no módulo 'Inserir Dados'.")
    else:
        # Parâmetros de Incerteza (Visíveis apenas aqui)
        with st.expander("⚙️ Parâmetros de Incerteza Laboratorial", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            p = {
                'u_cal': col1.number_input("u_Calib (%)", 0.0, 5.0, 1.5),
                'u_pip': col2.number_input("u_Pipet (%)", 0.0, 5.0, 2.5),
                'u_dil': col3.number_input("u_Dilu (%)", 0.0, 5.0, 0.8),
                'k': col4.number_input("Fator k", 1.0, 3.0, 2.0),
                'rsd': st.slider("RSD Instrumental (%)", 0.1, 10.0, 2.0)
            }
        
        catalog = load_catalog()
        spec_key = st.selectbox("Selecione a Legislação:", options=list(catalog.keys()))
        
        if spec_key:
            limits = catalog[spec_key]['limits_mgL']
            df_leg = st.session_state["df_global"].copy()
            df_leg = df_leg[df_leg['Analito_base'].isin(limits.keys())].copy()
            df_leg['Limite'] = df_leg['Analito_base'].map(limits)
            df_leg['U_exp'] = df_leg['V_mgL'].apply(lambda x: calc_U(x, p))
            
            def julgar(r):
                if r['V_mgL'] > r['Limite']: return "❌ REPROVADO"
                if (r['V_mgL'] + r['U_exp']) > r['Limite']: return "⚠️ REANALISAR"
                return "✅ CONFORME"
            
            df_leg['Parecer'] = df_leg.apply(julgar, axis=1)
            st.dataframe(df_leg[['Id', 'Analito_base', 'V_mgL', 'U_exp', 'Limite', 'Parecer']])

# --- MÓDULO 3: DUPLICATAS ---
elif modulo == "👥 Duplicatas":
    st.header("Comparação de Duplicatas e Cálculo de RPD")
    if st.session_state["df_global"] is None:
        st.info("Por favor, carregue os dados no módulo 'Inserir Dados'.")
    else:
        df = st.session_state["df_global"]
        amostras = df['Nº Amostra'].dropna().unique()
        c1, c2, c3 = st.columns(3)
        am1 = c1.selectbox("Original", amostras)
        am2 = c2.selectbox("Duplicata", amostras)
        tol = c3.number_input("Tolerância RPD (%)", 1, 100, 20)
        
        if am1 and am2:
            a1_data = df[df['Nº Amostra'] == am1][['Analito_base', 'V_mgL']]
            a2_data = df[df['Nº Amostra'] == am2][['Analito_base', 'V_mgL']]
            comp = pd.merge(a1_data, a2_data, on='Analito_base', suffixes=('_Ori', '_Dup'))
            comp['RPD (%)'] = abs(comp['V_mgL_Ori'] - comp['V_mgL_Dup']) / ((comp['V_mgL_Ori'] + comp['V_mgL_Dup'])/2) * 100
            comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= tol else "❌ FALHA")
            st.dataframe(comp)
