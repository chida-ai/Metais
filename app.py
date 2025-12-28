# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from pathlib import Path
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="OPERALAB - Gestão de Qualidade", layout="wide")

# --- ESTADOS DE SESSÃO ---
if "df_global" not in st.session_state:
    st.session_state["df_global"] = None

# --- AUXILIARES TÉCNICOS ---
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

@st.cache_data
def load_catalog():
    try:
        with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

# --- SIDEBAR (LOGO E NAVEGAÇÃO) ---
with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True) # Logo maior no topo
    else:
        st.title("OPERALAB")
    
    st.divider()
    st.subheader("Menu de Funcionalidades")
    modulo = st.radio(
        "Selecione a operação:",
        ["📥 Carregar Dados", "📊 Avaliação de Resultados", "⚖️ Legislação & Incerteza"]
    )
    
    st.divider()
    if st.session_state["df_global"] is not None:
        st.success("Dados carregados em memória.")
    else:
        st.info("Aguardando upload de dados.")

# --- MÓDULO 0: CARREGAMENTO ---
if modulo == "📥 Carregar Dados":
    st.header("Entrada de Dados")
    col1, col2 = st.columns(2)
    with col1:
        file = st.file_uploader("Upload de arquivo (Excel/CSV)", type=["xlsx","csv"])
    with col2:
        pasted = st.text_area("Ou cole aqui (separado por TAB ou ponto-e-vírgula)", height=150)
    
    if st.button("Processar e Armazenar Dados", type="primary"):
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
            # Preparação de colunas técnicas
            df_temp['Valor_num'], df_temp['Censurado'] = zip(*df_temp['Valor'].map(parse_val))
            df_temp['V_mgL'] = df_temp.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
            df_temp['Analito_base'] = df_temp['Análise'].map(normalize_analito)
            st.session_state["df_global"] = df_temp
            st.success("Dados processados com sucesso!")
            st.dataframe(df_temp.head())
        else:
            st.error("Falha ao interpretar os dados.")

# --- MÓDULO 1: AVALIAÇÃO DE RESULTADOS (Química e Controle) ---
elif modulo == "📊 Avaliação de Resultados":
    st.header("Avaliação Técnica de Resultados")
    if st.session_state["df_global"] is None:
        st.warning("Carregue os dados primeiro no menu ao lado.")
    else:
        df = st.session_state["df_global"]
        
        # Sub-modulo A: Totais x Dissolvidos
        st.subheader("1. Comparação Totais vs Dissolvidos")
        D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            merged = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
            # Avaliação direta (sem incerteza neste módulo conforme pedido)
            merged['Avaliação'] = np.where(merged['V_mgL_diss'] > (merged['V_mgL_tot'] * 1.1), "❌ ERRO: Diss > Tot", "✅ OK")
            st.dataframe(merged[['Id', 'Analito_base', 'V_mgL_diss', 'V_mgL_tot', 'Avaliação']].style.apply(
                lambda x: ['background-color: #FF3B30' if v == "❌ ERRO: Diss > Tot" else '' for v in x], axis=1, subset=['Avaliação']
            ))
        else:
            st.info("Não foram encontrados pares Totais/Dissolvidos para comparação.")

        # Sub-modulo B: Duplicatas
        st.divider()
        st.subheader("2. Comparação de Duplicatas (RPD)")
        amostras = df['Nº Amostra'].dropna().unique()
        c1, c2, c3 = st.columns(3)
        a1 = c1.selectbox("Amostra A", amostras, key="dup1")
        a2 = c2.selectbox("Amostra B (Duplicata)", amostras, key="dup2")
        tol = c3.number_input("Tolerância RPD (%)", 1.0, 50.0, 20.0)
        
        if a1 and a2:
            res_a = df[df['Nº Amostra'] == a1][['Analito_base', 'V_mgL']]
            res_b = df[df['Nº Amostra'] == a2][['Analito_base', 'V_mgL']]
            comp = pd.merge(res_a, res_b, on='Analito_base', suffixes=('_A', '_B'))
            comp['RPD (%)'] = abs(comp['V_mgL_A'] - comp['V_mgL_B']) / ((comp['V_mgL_A'] + comp['V_mgL_B'])/2) * 100
            comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= tol else "❌ FORA")
            st.dataframe(comp)

        # Sub-modulo C: QC Ítrio
        st.divider()
        st.subheader("3. QC Ítrio (Padrão Interno)")
        itrio = df[df['Análise'].str.contains('itrio|ítrio', case=False, na=False)]
        if not itrio.empty:
            itrio['Status_QC'] = itrio['Valor_num'].apply(lambda x: "✅ OK" if 70 <= x <= 130 else "❌ FALHA")
            st.dataframe(itrio[['Id', 'Nº Amostra', 'Análise', 'Valor_num', 'Status_QC']])
        else:
            st.info("Nenhum dado de Ítrio detectado.")

# --- MÓDULO 2: LEGISLAÇÃO & INCERTEZA ---
elif modulo == "⚖️ Legislação & Incerteza":
    st.header("Avaliação Normativa com Incerteza Expandida")
    if st.session_state["df_global"] is None:
        st.warning("Carregue os dados primeiro no menu ao lado.")
    else:
        # Interface de Cálculo de Incerteza (Modulo à parte dentro da legislação)
        with st.expander("🛠️ Parâmetros de Incerteza (Configurar para Avaliação)", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            u_cal = col1.number_input("u_Calibração (%)", 0.0, 5.0, 1.5)
            u_pip = col2.number_input("u_Pipetagem (%)", 0.0, 5.0, 2.5)
            u_dil = col3.number_input("u_Diluição (%)", 0.0, 5.0, 0.8)
            k_fat = col4.number_input("Fator k", 1.0, 3.0, 2.0)
            rsd_i = st.slider("RSD Instrumental Médio (%)", 0.1, 10.0, 2.0)

        catalog = load_catalog()
        spec_key = st.selectbox("Selecione a Portaria/Legislação", options=list(catalog.keys()))
        
        if spec_key:
            limits = catalog[spec_key]['limits_mgL']
            df_leg = st.session_state["df_global"].copy()
            df_leg = df_leg[df_leg['Analito_base'].isin(limits.keys())].copy()
            df_leg['Limite_Legal'] = df_leg['Analito_base'].map(limits)
            
            # Cálculo da Incerteza Expandida (U)
            def calc_U(val):
                if val is None: return 0
                uc_rel = np.sqrt(rsd_i**2 + u_cal**2 + u_pip**2 + u_dil**2)
                return k_fat * val * (uc_rel / 100)
            
            df_leg['U_expandida'] = df_leg['V_mgL'].apply(calc_U)
            
            # Regra de Decisão com Incerteza
            def julgar_conformidade(r):
                if r['V_mgL'] > r['Limite_Legal']: 
                    return "❌ NÃO CONFORME"
                elif (r['V_mgL'] + r['U_expandida']) > r['Limite_Legal']: 
                    return "🔄 REANALISAR (Zona de Incerteza)"
                else: 
                    return "✅ CONFORME"
            
            df_leg['Parecer'] = df_leg.apply(julgar_conformidade, axis=1)
            
            st.subheader(f"Resultado: {spec_key}")
            st.dataframe(df_leg[['Id', 'Analito_base', 'V_mgL', 'U_expandida', 'Limite_Legal', 'Parecer']].style.apply(
                lambda x: [
                    'background-color: #FF3B30' if v == "❌ NÃO CONFORME" else 
                    'background-color: #FFCC00; color: black' if v == "🔄 REANALISAR (Zona de Incerteza)" else 
                    'background-color: #34C759' if v == "✅ CONFORME" else '' for v in x
                ], axis=1, subset=['Parecer']
            ))

st.sidebar.markdown("---")
st.sidebar.caption(f"© {datetime.now().year} OPERALAB v3.1")
