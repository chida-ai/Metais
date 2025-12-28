# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from pathlib import Path

st.set_page_config(page_title="OPERALAB - Avaliação com Incerteza", layout="wide")

# --- ESTILIZAÇÃO E CABEÇALHO ---
LOGO_PATH = Path("assets/operalab_logo.png")
header_cols = st.columns([0.9, 6])
with header_cols[0]:
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), width=160)
    else: st.caption("Logo em: assets/operalab_logo.png")
with header_cols[1]:
    st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;">
          <h1 style="margin:0;">OPERALAB&nbsp;&nbsp;-&nbsp;&nbsp;Avaliação de Resultados v3.0</h1>
        </div>
        <div style="height:4px;background:#00A3FF;border-radius:2px;margin-top:8px;"></div>
        <div style="margin-top:6px;opacity:0.85;">
          Dissolvidos vs Totais • QC Ítrio • Duplicatas (%RPD) • <b>Módulo de Incerteza Expandida (U)</b>
        </div>
        """, unsafe_allow_html=True)

# --- MOTOR DE INCERTEZA ---
def calc_incerteza(valor, rsd_obs, p):
    if valor is None or valor == 0: return 0
    # uc_rel = sqrt(rsd² + u_calib² + u_pip² + u_dil²)
    uc_rel = np.sqrt(rsd_obs**2 + p['u_calib']**2 + p['u_pip']**2 + p['u_dil']**2)
    U = p['k'] * valor * (uc_rel / 100)
    return U

# --- AUXILIARES DE PARSE (Sua versão otimizada) ---
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

# --- CARREGAR ESPECIFICAÇÕES ---
@st.cache_data
def load_catalog():
    try:
        with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

catalog = load_catalog()

# --- SIDEBAR: PARÂMETROS DE INCERTEZA ---
with st.sidebar:
    st.header("⚙️ Parâmetros Metrológicos")
    p = {
        'u_calib': st.number_input("u_calib (%)", 0.0, 5.0, 1.5),
        'u_pip': st.number_input("u_pipetagem (%)", 0.0, 5.0, 2.5),
        'u_dil': st.number_input("u_diluição (%)", 0.0, 5.0, 0.8),
        'k': st.number_input("Fator k (95% Conf.)", 1.0, 3.0, 2.0),
        'rsd_padrao': st.number_input("RSD Médio ICP (%)", 0.1, 10.0, 2.0),
        'rpd_max': st.number_input("Tolerância RPD (%)", 1.0, 50.0, 20.0)
    }
    st.divider()
    st.header("Entrada de Dados")
    file = st.file_uploader("Arquivo (Excel/CSV)", type=["xlsx","csv"])
    pasted = st.text_area("Ou cole a tabela aqui", height=100)

# --- PROCESSAMENTO ---
df_in = None
if file:
    df_in = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
elif pasted:
    for sep in ['\t', ';', ',']:
        try:
            df_temp = pd.read_csv(io.StringIO(pasted), sep=sep)
            if len(df_temp.columns) >= 3:
                df_in = df_temp
                break
        except: pass

if df_in is not None:
    # Preparação Global
    df_in['Valor_num'], df_in['Censurado'] = zip(*df_in['Valor'].map(parse_val))
    df_in['V_mgL'] = df_in.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df_in['Analito_base'] = df_in['Análise'].map(normalize_analito)
    df_in['U_exp'] = df_in['V_mgL'].apply(lambda x: calc_incerteza(x, p['rsd_padrao'], p))

    aba1, aba2, aba3 = st.tabs(["🔍 Avaliação de Lote (Diss x Tot)", "⚖️ Legislação", "👥 Duplicatas"])

    with aba1:
        st.subheader("Dissolvido vs Total (Com Incerteza)")
        D = df_in[df_in['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
        T = df_in[df_in['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()
        merged = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
        
        # Regra: Diss > (Total + U) = ERRO. Se Diss > Total mas dentro de U = OK (variabilidade).
        def check_diss(r):
            if r['V_mgL_diss'] > (r['V_mgL_tot'] + r['U_exp_tot']): return "❌ NÃO CONFORME"
            if r['V_mgL_diss'] > r['V_mgL_tot']: return "⚠️ ALERTA (Variabilidade)"
            return "✅ OK"
        
        merged['Avaliação'] = merged.apply(check_diss, axis=1)
        st.dataframe(merged[['Id', 'Analito_base', 'V_mgL_diss', 'V_mgL_tot', 'U_exp_tot', 'Avaliação']].style.apply(
            lambda x: ['background-color: #FF3B30' if v == "❌ NÃO CONFORME" else '' for v in x], axis=1, subset=['Avaliação']
        ))

        # QC Ítrio
        st.divider()
        st.subheader("QC Ítrio (70-130%)")
        itrio = df_in[df_in['Análise'].str.contains('itrio|ítrio', case=False, na=False)]
        if not itrio.empty:
            itrio['QC'] = itrio['Valor_num'].apply(lambda x: "✅ OK" if 70 <= x <= 130 else "❌ FALHA")
            st.table(itrio[['Id', 'Nº Amostra', 'Análise', 'Valor_num', 'QC']])

    with aba2:
        st.subheader("Pré-avaliação por Legislação")
        spec_key = st.selectbox("Selecione a Legislação", options=list(catalog.keys()))
        if spec_key:
            limits = catalog[spec_key]['limits_mgL']
            df_leg = df_in[df_in['Analito_base'].isin(limits.keys())].copy()
            df_leg['Limite'] = df_leg['Analito_base'].map(limits)
            
            def parecer_final(r):
                if r['V_mgL'] > r['Limite']: return "❌ NÃO CONFORME"
                if (r['V_mgL'] + r['U_exp']) > r['Limite']: return "🔄 REANALISAR (Incerteza)"
                return "✅ CONFORME"
            
            df_leg['Parecer'] = df_leg.apply(parecer_final, axis=1)
            st.dataframe(df_leg[['Id', 'Analito_base', 'V_mgL', 'U_exp', 'Limite', 'Parecer']])

    with aba3:
        st.subheader("Duplicatas e RPD")
        amostras = df_in['Nº Amostra'].dropna().unique()
        c1, c2 = st.columns(2)
        am1 = c1.selectbox("Amostra 1", amostras)
        am2 = c2.selectbox("Amostra 2 (Duplicata)", amostras)
        
        if am1 and am2:
            a1_data = df_in[df_in['Nº Amostra'] == am1][['Analito_base', 'V_mgL']]
            a2_data = df_in[df_in['Nº Amostra'] == am2][['Analito_base', 'V_mgL']]
            comp = pd.merge(a1_data, a2_data, on='Analito_base', suffixes=('_A', '_B'))
            comp['RPD (%)'] = abs(comp['V_mgL_A'] - comp['V_mgL_B']) / ((comp['V_mgL_A'] + comp['V_mgL_B'])/2) * 100
            comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= p['rpd_max'] else "❌ FORA")
            st.dataframe(comp)

else:
    st.info("💡 Carregue um arquivo ou cole os dados para iniciar.")

st.caption(f"© {datetime.now().year} | OPERALAB - Gestão de Qualidade Metrológica")
