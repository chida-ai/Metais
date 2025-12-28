# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from pathlib import Path
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

# --- CSS PARA TEMA DARK PROFISSIONAL ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    
    /* Botões Laterais Estilizados */
    div.stButton > button:first-child {
        width: 100%;
        border-radius: 4px;
        height: 3em;
        background-color: #1F2937;
        color: #FFFFFF !important;
        border: 1px solid #374151;
        font-weight: 500;
        transition: all 0.2s;
        text-align: left;
        padding-left: 15px;
    }
    
    div.stButton > button:hover {
        background-color: #FF0000 !important;
        color: white !important;
        border: 1px solid #FF0000;
    }

    /* Botão de Ação Principal (Sóbrio) */
    .stButton button[kind="primary"] {
        background-color: #374151 !important;
        border: 1px solid #4B5563 !important;
        color: white !important;
        width: auto !important;
        padding: 0.5rem 2rem !important;
    }
    
    .stButton button[kind="primary"]:hover {
        background-color: #FF0000 !important;
        border-color: #FF0000 !important;
    }

    /* Sidebar e Headers */
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #374151; }
    h1, h2, h3 { color: #F3F4F6; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADO DE SESSÃO ---
if "df_global" not in st.session_state: st.session_state["df_global"] = None
if "pagina" not in st.session_state: st.session_state["pagina"] = "📥 Inserir Dados"

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

# --- SIDEBAR ---
with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), use_container_width=True)
    
    st.markdown("""
        <div style="text-align: left; margin-bottom: 30px;">
            <h1 style="margin:0; font-size: 28px; color: #FFFFFF;">Data Support</h1>
            <div style="height:3px; background:#FF0000; width:100%; margin-top:2px;"></div>
            <p style="color: #FF0000; font-size: 13px; font-weight: bold; margin-top:4px;">
                AVALIAÇÃO DE DADOS AMBIENTAIS
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação & U"): st.session_state.pagina = "⚖️ Legislação & U"
    if st.button("👥 Duplicatas"): st.session_state.pagina = "👥 Duplicatas"
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.caption(f"Log: {datetime.now().strftime('%H:%M:%S')}")

# --- MÓDULOS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Amostras")
    col1, col2 = st.columns(2)
    with col1:
        file = st.file_uploader("Upload Planilha (Excel/CSV)", type=["xlsx", "csv"])
    with col2:
        pasted = st.text_area("Colagem Direta do Sistema", height=150)
    
    if st.button("Processar Lote", type="primary"):
        df_temp = None
        if file: df_temp = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        elif pasted:
            for sep in ['\t', ';', ',']:
                try:
                    df_check = pd.read_csv(io.StringIO(pasted), sep=sep)
                    if len(df_check.columns) >= 3:
                        df_temp = df_check
                        break
                except: pass
        
        if df_temp is not None:
            df_temp['Valor_num'], df_temp['Censurado'] = zip(*df_temp['Valor'].map(parse_val))
            df_temp['V_mgL'] = df_temp.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
            df_temp['Analito_base'] = df_temp['Análise'].map(normalize_analito)
            st.session_state["df_global"] = df_temp
            st.success("Dados carregados com sucesso.")
        else: st.error("Erro na leitura dos dados.")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação Técnica")
    if st.session_state["df_global"] is None: st.warning("Aguardando dados...")
    else:
        df = st.session_state["df_global"]
        
        st.subheader("📊 Dissolvidos vs Totais")
        D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            merged = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
            merged['Avaliação'] = np.where(merged['V_mgL_diss'] > (merged['V_mgL_tot'] * 1.05), "❌ NÃO CONFORME", "✅ OK")
            
            res_disp = merged[['Id', 'Analito_base', 'V_mgL_diss', 'V_mgL_tot', 'Avaliação']].copy()
            res_disp.columns = ['ID Amostra', 'Analito', 'Conc. Diss (mg/L)', 'Conc. Total (mg/L)', 'Parecer']
            st.dataframe(res_disp, use_container_width=True)
        
        st.divider()
        st.subheader("🎯 Recuperação de Ítrio (%)")
        itrio = df[df['Análise'].str.contains('itrio|ítrio', case=False, na=False)]
        if not itrio.empty:
            it_disp = itrio[['Id', 'Nº Amostra', 'Valor_num']].copy()
            it_disp['Parecer'] = it_disp['Valor_num'].apply(lambda x: "✅ OK" if 70 <= x <= 130 else "❌ REPROVADO")
            it_disp.columns = ['ID', 'Nº Amostra', 'Recuperação (%)', 'Status Técnico']
            st.table(it_disp)

elif st.session_state.pagina == "⚖️ Legislação & U":
    st.title("⚖️ Conformidade Legal & Incerteza")
    if st.session_state["df_global"] is None: st.warning("Aguardando dados...")
    else:
        with st.expander("🛠️ Parâmetros de Incerteza", expanded=False):
            c1, c2, c3 = st.columns(3)
            p = {'u_cal': c1.number_input("U_Cal (%)", 0.0, 5.0, 1.5),
                 'u_pip': c2.number_input("U_Vol (%)", 0.0, 5.0, 2.5),
                 'u_dil': c3.number_input("U_Dil (%)", 0.0, 5.0, 0.8),
                 'k': 2.0, 'rsd': 2.0}
        
        catalog = load_catalog()
        spec_key = st.selectbox("Legislação de Referência:", options=list(catalog.keys()))
        
        if spec_key:
            lims = catalog[spec_key]['limits_mgL']
            df_leg = st.session_state["df_global"].copy()
            df_leg = df_leg[df_leg['Analito_base'].isin(lims.keys())].copy()
            df_leg['Limite'] = df_leg['Analito_base'].map(lims)
            df_leg['U'] = df_leg['V_mgL'].apply(lambda x: calc_U(x, p))
            
            def julgar(r):
                if r['V_mgL'] > r['Limite']: return "❌ REPROVADO"
                if (r['V_mgL'] + r['U']) > r['Limite']: return "🔄 REANALISAR"
                return "✅ CONFORME"
            
            df_leg['Parecer'] = df_leg.apply(julgar, axis=1)
            final = df_leg[['Id', 'Analito_base', 'V_mgL', 'U', 'Limite', 'Parecer']].copy()
            final.columns = ['ID', 'Analito', 'Resultado (mg/L)', 'Incerteza (±)', 'VMP (mg/L)', 'Status Final']
            st.dataframe(final, use_container_width=True)

elif st.session_state.pagina == "👥 Duplicatas":
    st.title("👥 Controle de Precisão (RPD)")
    if st.session_state["df_global"] is None: st.warning("Aguardando dados...")
    else:
        df = st.session_state["df_global"]
        amostras = df['Nº Amostra'].dropna().unique()
        col1, col2 = st.columns(2)
        a1 = col1.selectbox("Amostra Original", amostras)
        a2 = col2.selectbox("Duplicata", amostras)
        
        if a1 and a2:
            a1_d = df[df['Nº Amostra'] == a1][['Analito_base', 'V_mgL']]
            a2_d = df[df['Nº Amostra'] == a2][['Analito_base', 'V_mgL']]
            comp = pd.merge(a1_d, a2_d, on='Analito_base', suffixes=('_A', '_B'))
            comp['RPD (%)'] = abs(comp['V_mgL_A'] - comp['V_mgL_B']) / ((comp['V_mgL_A'] + comp['V_mgL_B'])/2) * 100
            comp['Avaliação'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= 20 else "❌ FALHA")
            
            # --- PADRONIZAÇÃO DAS COLUNAS SOLICITADA ---
            comp_final = comp.copy()
            comp_final.columns = ['Analito', 'Conc. Original (mg/L)', 'Conc. Duplicata (mg/L)', 'RPD (%)', 'Status']
            st.dataframe(comp_final, use_container_width=True)
