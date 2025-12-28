# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from pathlib import Path
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Data Support - Dashboard", layout="wide")

# --- CSS PARA ESTILIZAÇÃO DOS BOTÕES E TABELAS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    div.stButton > button:first-child {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #f0f2f6;
        border: 1px solid #d1d5db;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #FF0000;
        color: white;
        border: 1px solid #FF0000;
    }
    .status-aprovado { color: #34C759; font-weight: bold; }
    .status-reprovado { color: #FF3B30; font-weight: bold; }
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

# --- SIDEBAR (LOGO E CABEÇALHO) ---
with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), use_container_width=True)
    
    st.markdown("""
        <div style="text-align: left; margin-bottom: 20px;">
            <h1 style="margin:0; font-size: 32px; color: #1e293b;">Data Support</h1>
            <div style="height:4px; background:#FF0000; width:100%; margin-top:2px;"></div>
            <p style="color: #FF0000; font-size: 16px; font-weight: bold; margin-top:4px;">
                Avaliação de Resultados
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    st.subheader("Navegação")
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação & Incerteza"): st.session_state.pagina = "⚖️ Legislação & Incerteza"
    if st.button("👥 Duplicatas (RPD)"): st.session_state.pagina = "👥 Duplicatas (RPD)"
    
    st.divider()
    if st.session_state["df_global"] is not None:
        st.success(f"Lote ativo: {len(st.session_state['df_global'])} registros")

# --- MÓDULOS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.header("📥 Carregamento de Amostras")
    col1, col2 = st.columns(2)
    with col1:
        file = st.file_uploader("Arraste seu arquivo Excel/CSV", type=["xlsx", "csv"])
    with col2:
        pasted = st.text_area("Ou cole os dados do sistema aqui", height=150, placeholder="ID | Amostra | Analito | Valor...")
    
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
            st.success("✅ Dados carregados com sucesso!")
            st.balloons()
        else: st.error("❌ Formato não reconhecido.")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.header("🧪 Avaliação Química do Lote")
    if st.session_state["df_global"] is None: st.info("Aguardando dados...")
    else:
        df = st.session_state["df_global"]
        
        # Dissolvido x Total
        st.subheader("Comparação Dissolvidos vs Totais")
        D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            merged = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
            merged['Avaliação'] = np.where(merged['V_mgL_diss'] > (merged['V_mgL_tot'] * 1.05), "❌ NÃO CONFORME", "✅ OK")
            
            # Renomeando para exibição
            disp = merged[['Id', 'Analito_base', 'V_mgL_diss', 'V_mgL_tot', 'Avaliação']].copy()
            disp.columns = ['ID', 'Analito', 'Conc. Dissolvido (mg/L)', 'Conc. Total (mg/L)', 'Status']
            st.dataframe(disp.style.apply(lambda x: ['background-color: #FF3B30; color: white' if v == "❌ NÃO CONFORME" else '' for v in x], axis=1, subset=['Status']), use_container_width=True)
        
        # QC Ítrio
        st.divider()
        st.subheader("Controle de Recuperação (Ítrio)")
        itrio = df[df['Análise'].str.contains('itrio|ítrio', case=False, na=False)]
        if not itrio.empty:
            it_disp = itrio[['Id', 'Nº Amostra', 'Análise', 'Valor_num']].copy()
            it_disp['Recuperação (%)'] = it_disp['Valor_num']
            it_disp['Resultado'] = it_disp['Recuperação (%)'].apply(lambda x: "✅ OK" if 70 <= x <= 130 else "❌ REPROVADO")
            st.table(it_disp[['ID', 'Nº Amostra', 'Recuperação (%)', 'Resultado']])

elif st.session_state.pagina == "⚖️ Legislação & Incerteza":
    st.header("⚖️ Avaliação Normativa + Incerteza")
    if st.session_state["df_global"] is None: st.info("Aguardando dados...")
    else:
        with st.expander("🛠️ Configurar Incerteza do Método (U)", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            p = {
                'u_cal': c1.number_input("u_Calib (%)", 0.0, 5.0, 1.5),
                'u_pip': c2.number_input("u_Pipet (%)", 0.0, 5.0, 2.5),
                'u_dil': c3.number_input("u_Dilu (%)", 0.0, 5.0, 0.8),
                'k': c4.number_input("Fator k", 1.0, 3.0, 2.0),
                'rsd': st.slider("RSD do Equipamento (%)", 0.1, 10.0, 2.0)
            }
        
        catalog = load_catalog()
        spec_key = st.selectbox("Selecione a Legislação de Referência:", options=list(catalog.keys()))
        
        if spec_key:
            limits = catalog[spec_key]['limits_mgL']
            df_leg = st.session_state["df_global"].copy()
            df_leg = df_leg[df_leg['Analito_base'].isin(limits.keys())].copy()
            df_leg['Limite'] = df_leg['Analito_base'].map(limits)
            df_leg['U_exp'] = df_leg['V_mgL'].apply(lambda x: calc_U(x, p))
            
            def julgar(r):
                if r['V_mgL'] > r['Limite']: return "❌ REPROVADO"
                if (r['V_mgL'] + r['U_exp']) > r['Limite']: return "🔄 REANALISAR"
                return "✅ CONFORME"
            
            df_leg['Parecer'] = df_leg.apply(julgar, axis=1)
            
            # Renomeando para o usuário
            leg_disp = df_leg[['Id', 'Analito_base', 'V_mgL', 'U_exp', 'Limite', 'Parecer']].copy()
            leg_disp.columns = ['ID', 'Elemento', 'Resultado (mg/L)', 'Incerteza U (±)', 'Limite Normativo (mg/L)', 'Parecer Técnico']
            st.dataframe(leg_disp, use_container_width=True)

elif st.session_state.pagina == "👥 Duplicatas (RPD)":
    st.header("👥 Verificação de Precisão (Duplicatas)")
    if st.session_state["df_global"] is None: st.info("Aguardando dados...")
    else:
        df = st.session_state["df_global"]
        amostras = df['Nº Amostra'].dropna().unique()
        col1, col2, col3 = st.columns(3)
        a1 = col1.selectbox("Amostra Original", amostras)
        a2 = col2.selectbox("Duplicata", amostras)
        tol = col3.number_input("Tolerância RPD (%)", 1, 100, 20)
        
        if a1 and a2:
            a1_d = df[df['Nº Amostra'] == a1][['Analito_base', 'V_mgL']]
            a2_d = df[df['Nº Amostra'] == a2][['Analito_base', 'V_mgL']]
            comp = pd.merge(a1_d, a2_d, on='Analito_base', suffixes=('_A', '_B'))
            comp['RPD (%)'] = abs(comp['V_mgL_A'] - comp['V_mgL_B']) / ((comp['V_mgL_A'] + comp['V_mgL_B'])/2) * 100
            comp['Avaliação'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= tol else "❌ REPROVADO")
            
            comp.columns = ['Analito', 'Conc. Original (mg/L)', 'Conc. Duplicata (mg/L)', 'RPD (%)', 'Status']
            st.dataframe(comp, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption(f"Logado como Analista • {datetime.now().strftime('%d/%m/%Y')}")
