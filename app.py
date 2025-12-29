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
    if st.button("🧪 Avaliação de Lote (QC)"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação"): st.session_state.pagina = "⚖️ Legislação"

# --- PÁGINAS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados (LIMS)")
    pasted = st.text_area("Cole os dados aqui (Colunas: Id, Nº Amostra, Análise, Método de Análise, Valor, Unidade de Medida)", height=250)
    if st.button("Processar Dados", type="primary"):
        df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python')
        df['V_num'], _ = zip(*df['Valor'].map(parse_val))
        df['V_calculo_mg'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in str(r['Unidade de Medida']).lower() else r['V_num'], axis=1)
        df['key_busca'] = df['Análise'].map(limpar_texto)
        st.session_state["df_global"] = df
        st.success("Dados carregados com sucesso!")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação Técnica e Controle de Qualidade")
    df = st.session_state["df_global"]
    
    if df is not None:
        # 1. QC ÍTRIO (Regra 70-130%)
        qc_itrio = df[df['key_busca'].str.contains('itrio', na=False)].copy()
        if not qc_itrio.empty:
            st.subheader("🔍 1. Controle de Qualidade (Ítrio)")
            # Aplicando a regra técnica
            qc_itrio['Status QC'] = qc_itrio['V_num'].apply(lambda x: "✅ CONFORME" if 70 <= x <= 130 else "❌ NÃO CONFORME")
            
            res_itrio = qc_itrio[['Id', 'Análise', 'Valor', 'Unidade de Medida', 'Status QC']]
            st.dataframe(res_itrio, use_container_width=True)
            
            if any(qc_itrio['Status QC'] == "❌ NÃO CONFORME"):
                st.error("Atenção: Existem recuperações de Ítrio fora do intervalo de 70-130%!")

        st.divider()

        # 2. COMPARATIVO D vs T (Excluindo Ítrio)
        df_analitos = df[~df['key_busca'].str.contains('itrio', na=False)].copy()
        D = df_analitos[df_analitos['Método de Análise'].str.contains('Diss', case=False, na=False)].copy()
        T = df_analitos[df_analitos['Método de Análise'].str.contains('Tot', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            st.subheader("📊 2. Comparação Metais (Dissolvido vs Total)")
            m = pd.merge(D, T, on=['Id', 'key_busca'], suffixes=('_D', '_T'))
            # Critério: D não pode ser maior que T (com margem de 5% de variabilidade analítica)
            m['Status'] = np.where(m['V_calculo_mg_D'] > (m['V_calculo_mg_T'] * 1.05), "❌ D > T", "✅ OK")
            
            for id_amostra in m['Id'].unique():
                temp = m[m['Id']==id_amostra]
                status_final = "❌ REPROVADO" if any(temp['Status'] == "❌ D > T") else "✅ APROVADO"
                st.write(f"**Amostra {id_amostra}:** {status_final}")

            st.dataframe(m[['Id', 'Análise_D', 'Valor_D', 'Unidade de Medida_D', 'Valor_T', 'Unidade de Medida_T', 'Status']], use_container_width=True)

        st.divider()

        # 3. DUPLICATAS (RPD)
        st.subheader("👥 3. Controle de Precisão (RPD)")
        amostras_list = sorted(df['Nº Amostra'].dropna().unique())
        
        if len(amostras_list) >= 2:
            c1, c2, c3 = st.columns(3)
            a1 = c1.selectbox("Amostra Original", amostras_list)
            a2 = c2.selectbox("Duplicata", amostras_list)
            limite_rpd = c3.number_input("Limite RPD (%)", value=20)

            if a1 != a2:
                d1 = df[df['Nº Amostra'] == a1][['key_busca', 'V_calculo_mg', 'Análise', 'Valor', 'Unidade de Medida']]
                d2 = df[df['Nº Amostra'] == a2][['key_busca', 'V_calculo_mg', 'Valor', 'Unidade de Medida']]
                
                comp = pd.merge(d1, d2, on='key_busca', suffixes=('_Ori', '_Dup'))
                if not comp.empty:
                    comp['RPD (%)'] = (abs(comp['V_calculo_mg_Ori'] - comp['V_calculo_mg_Dup']) / 
                                      ((comp['V_calculo_mg_Ori'] + comp['V_calculo_mg_Dup'])/2)) * 100
                    comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= limite_rpd else "❌ FALHA")
                    
                    st.dataframe(comp[['Análise', 'Valor_Ori', 'Unidade de Medida_Ori', 'Valor_Dup', 'Unidade de Medida_Dup', 'RPD (%)', 'Status']], use_container_width=True)
                else:
                    st.info("Nenhum parâmetro em comum para calcular RPD.")
        else:
            st.info("Necessário colunas com 'Nº Amostra' diferentes para avaliar duplicatas.")

elif st.session_state.pagina == "⚖️ Legislação":
    # (Mantido conforme versão anterior)
    st.title("⚖️ Conformidade Legal")
    catalog = load_catalog()
    df = st.session_state["df_global"]
    if df is not None:
        escolha = st.selectbox("Selecione a Legislação:", list(catalog.keys()))
        limites = {limpar_texto(k): v for k, v in catalog[escolha]['limits_mgL'].items()}
        
        df_l = df[~df['key_busca'].str.contains('itrio', na=False)].copy()
        df_l['VMP_Legislação'] = df_l['key_busca'].map(limites)
        unid_leg = "mg/kg" if "Solo" in escolha or "Resíduos" in escolha else "mg/L"
        df_l['Unid_Leg'] = unid_leg
        
        df_l = df_l.dropna(subset=['VMP_Legislação'])
        df_l['Parecer'] = np.where(df_l['V_calculo_mg'] > df_l['VMP_Legislação'], "❌ FORA", "✅ OK")

        st.subheader("📝 Resumo por Amostra")
        for id_amostra in df_l['Id'].unique():
            status = "❌ REPROVADA" if any(df_l[df_l['Id']==id_amostra]['Parecer'] == "❌ FORA") else "✅ APROVADA"
            st.info(f"ID: {id_amostra} -> {status}")

        st.dataframe(df_l[['Id', 'Análise', 'Valor', 'Unidade de Medida', 'VMP_Legislação', 'Unid_Leg', 'Parecer']], use_container_width=True)
