# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, unicodedata
from pathlib import Path

st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

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

if "df_global" not in st.session_state: st.session_state["df_global"] = None
if "pagina" not in st.session_state: st.session_state["pagina"] = "📥 Inserir Dados"

# --- SIDEBAR ---
with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), use_container_width=True)
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
        df['V_calculo_mg'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in str(r['Unidade de Medida']).lower() else r['V_num'], axis=1)
        df['key_busca'] = df['Análise'].map(limpar_texto)
        st.session_state["df_global"] = df
        st.success("Dados carregados!")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação: Dissolvido vs Total")
    df = st.session_state["df_global"]
    if df is not None:
        # Tabela de QC (Ítrio)
        qc_df = df[df['key_busca'].str.contains('itrio', na=False)]
        if not qc_df.empty:
            st.subheader("🔍 Controle de Qualidade (Ítrio)")
            st.dataframe(qc_df[['Id', 'Análise', 'Valor', 'Unidade de Medida']], use_container_width=True)

        D = df[df['Método de Análise'].str.contains('Diss', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Tot', case=False, na=False)].copy()
        if not D.empty and not T.empty:
            st.subheader("📊 Comparação D vs T")
            m = pd.merge(D, T, on=['Id', 'key_busca'], suffixes=('_D', '_T'))
            m['Status'] = np.where(m['V_calculo_mg_D'] > m['V_calculo_mg_T'], "❌ D > T", "✅ OK")
            
            # Resumo por ID
            for id_amostra in m['Id'].unique():
                status_final = "❌ REPROVADO" if any(m[m['Id']==id_amostra]['Status'] == "❌ D > T") else "✅ APROVADO"
                st.write(f"**Amostra {id_amostra}:** {status_final}")

            res = m[['Id', 'Análise_D', 'Valor_D', 'Unidade de Medida_D', 'Valor_T', 'Unidade de Medida_T', 'Status']]
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
        unid_leg = "mg/kg" if "Solo" in escolha or "Resíduos" in escolha else "mg/L"
        df_l['Unid_Leg'] = unid_leg
        df_l = df_l.dropna(subset=['VMP_Legislação'])
        df_l['Parecer'] = np.where(df_l['V_calculo_mg'] > df_l['VMP_Legislação'], "❌ FORA", "✅ OK")

        # Resumo de Aprovação por ID
        st.subheader("📝 Resumo Final por Amostra")
        c1, c2 = st.columns(2)
        for i, id_amostra in enumerate(df_l['Id'].unique()):
            total_params = df_l[df_l['Id']==id_amostra]
            status_amostra = "❌ REPROVADA" if any(total_params['Parecer'] == "❌ FORA") else "✅ APROVADA"
            col = c1 if i % 2 == 0 else c2
            col.info(f"ID: {id_amostra} -> {status_amostra}")

        st.subheader("📋 Detalhamento dos Analitos")
        res = df_l[['Id', 'Análise', 'Valor', 'Unidade de Medida', 'VMP_Legislação', 'Unid_Leg', 'Parecer']]
        res.columns = ['ID', 'Analito', 'Valor LIMS', 'Unid LIMS', 'VMP Leg.', 'Unid Leg.', 'Parecer']
        st.dataframe(res, use_container_width=True)

elif st.session_state.pagina == "👥 Duplicatas":
    st.title("👥 Controle de Precisão (RPD)")
    df = st.session_state["df_global"]
    
    if df is None: 
        st.warning("Aguardando dados...")
    else:
        # Interface de Configuração
        with st.expander("⚙️ Configurações do Controle de Qualidade", expanded=True):
            c1, c2, c3 = st.columns([1, 1, 1])
            amostras = sorted(df['Nº Amostra'].dropna().unique())
            
            orig = c1.selectbox("Selecione a Amostra ORIGINAL", amostras)
            dupl = c2.selectbox("Selecione a Amostra DUPLICATA", amostras)
            limite_rpd = c3.number_input("Limite Máximo Aceitável de RPD (%)", value=20, step=5)

        if orig == dupl:
            st.error("⚠️ Selecione amostras diferentes para comparar.")
        else:
            # Filtragem e Cruzamento
            d1 = df[df['Nº Amostra'] == orig][['key_busca', 'Análise', 'Valor', 'Unidade de Medida', 'V_calculo_mg']]
            d2 = df[df['Nº Amostra'] == dupl][['key_busca', 'Valor', 'Unidade de Medida', 'V_calculo_mg']]
            
            comp = pd.merge(d1, d2, on='key_busca', suffixes=('_Ori', '_Dup'))
            
            if comp.empty:
                st.info("Não foram encontrados analitos em comum entre estas duas amostras.")
            else:
                # Cálculo do RPD
                # Fórmula: |V1 - V2| / ((V1 + V2)/2) * 100
                comp['RPD (%)'] = comp.apply(
                    lambda x: (abs(x['V_calculo_mg_Ori'] - x['V_calculo_mg_Dup']) / 
                              ((x['V_calculo_mg_Ori'] + x['V_calculo_mg_Dup']) / 2)) * 100 
                    if (x['V_calculo_mg_Ori'] + x['V_calculo_mg_Dup']) > 0 else 0, axis=1
                )
                
                comp['Situação'] = comp['RPD (%)'].apply(lambda x: "✅ DENTRO" if x <= limite_rpd else "❌ FALHA")
                
                # Exibição
                st.subheader(f"📊 Resultado: Amostra {orig} vs {dupl}")
                
                # Resumo Final do RPD
                falhas = comp[comp['Situação'] == "❌ FALHA"].shape[0]
                if falhas == 0:
                    st.success(f"Controle de Qualidade aprovado para o par selecionado (Limite: {limite_rpd}%)")
                else:
                    st.error(f"Controle de Qualidade falhou em {falhas} analito(s) (Limite: {limite_rpd}%)")

                res = comp[['Análise', 'Valor_Ori', 'Unidade de Medida_Ori', 'Valor_Dup', 'Unidade de Medida_Dup', 'RPD (%)', 'Situação']]
                res.columns = ['Analito', f'Valor ({orig})', 'Unid.', f'Valor ({dupl})', 'Unid.', 'RPD %', 'Resultado']
                
                st.dataframe(res.style.format({'RPD %': '{:.2f}'}), use_container_width=True)
