Entendido! Fiz os ajustes finais para que a ferramenta fique 100% operacional para o seu laboratório.

O que foi corrigido:

Ítrio Isolado: Na aba "Avaliação de Lote", o Ítrio agora é filtrado e excluído da comparação Dissolvido vs Total, aparecendo apenas no quadro de QC.

Módulo Duplicata Restaurado: O código foi reestruturado para garantir que a aba de Duplicatas apareça corretamente no menu lateral.

RPD Customizável: Mantive a opção de você escolher a % de desvio.

Aqui está o código completo e corrigido:

Python

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
        st.success("Dados carregados com sucesso!")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação: Dissolvido vs Total")
    df = st.session_state["df_global"]
    if df is not None:
        # 1. QC ÍTRIO (Isolado)
        qc_itrio = df[df['key_busca'].str.contains('itrio', na=False)]
        if not qc_itrio.empty:
            st.subheader("🔍 Controle de Qualidade (Ítrio)")
            st.dataframe(qc_itrio[['Id', 'Análise', 'Valor', 'Unidade de Medida']], use_container_width=True)

        # 2. COMPARATIVO D vs T (Removendo o Ítrio da conta)
        df_analitos = df[~df['key_busca'].str.contains('itrio', na=False)].copy()
        
        D = df_analitos[df_analitos['Método de Análise'].str.contains('Diss', case=False, na=False)].copy()
        T = df_analitos[df_analitos['Método de Análise'].str.contains('Tot', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            st.subheader("📊 Comparação de Metais (D vs T)")
            m = pd.merge(D, T, on=['Id', 'key_busca'], suffixes=('_D', '_T'))
            
            # Margem de segurança de 10% comum em laboratórios para variação analítica
            m['Status'] = np.where(m['V_calculo_mg_D'] > (m['V_calculo_mg_T'] * 1.1), "❌ D > T", "✅ OK")
            
            for id_amostra in m['Id'].unique():
                temp = m[m['Id']==id_amostra]
                status_final = "❌ REPROVADO" if any(temp['Status'] == "❌ D > T") else "✅ APROVADO"
                st.write(f"**Amostra {id_amostra}:** {status_final}")

            res = m[['Id', 'Análise_D', 'Valor_D', 'Valor_T', 'Status']]
            st.dataframe(res, use_container_width=True)

elif st.session_state.pagina == "⚖️ Legislação":
    st.title("⚖️ Conformidade Legal")
    catalog = load_catalog()
    df = st.session_state["df_global"]
    if df is not None:
        escolha = st.selectbox("Selecione a Legislação:", list(catalog.keys()))
        limites = {limpar_texto(k): v for k, v in catalog[escolha]['limits_mgL'].items()}
        
        df_l = df[~df['key_busca'].str.contains('itrio', na=False)].copy()
        df_l['VMP_Legislação'] = df_l['key_busca'].map(limites)
        df_l = df_l.dropna(subset=['VMP_Legislação'])
        df_l['Parecer'] = np.where(df_l['V_calculo_mg'] > df_l['VMP_Legislação'], "❌ FORA", "✅ OK")

        st.subheader("📝 Resumo por Amostra")
        for id_amostra in df_l['Id'].unique():
            status = "❌ REPROVADA" if any(df_l[df_l['Id']==id_amostra]['Parecer'] == "❌ FORA") else "✅ APROVADA"
            st.info(f"ID: {id_amostra} -> {status}")

        st.dataframe(df_l[['Id', 'Análise', 'Valor', 'VMP_Legislação', 'Parecer']], use_container_width=True)

elif st.session_state.pagina == "👥 Duplicatas":
    st.title("👥 Controle de Precisão (RPD)")
    df = st.session_state["df_global"]
    if df is not None:
        st.info("O RPD é calculado apenas para analitos presentes em ambas as amostras (Original e Duplicata).")
        
        with st.expander("⚙️ Configurar Comparação", expanded=True):
            c1, c2, c3 = st.columns(3)
            amostras = sorted(df['Nº Amostra'].dropna().unique())
            a1 = c1.selectbox("Amostra Original", amostras)
            a2 = c2.selectbox("Duplicata", amostras)
            limite_rpd = c3.number_input("Limite Máximo RPD (%)", value=20)

        if a1 and a2 and a1 != a2:
            d1 = df[df['Nº Amostra'] == a1][['key_busca', 'V_calculo_mg', 'Análise', 'Valor']]
            d2 = df[df['Nº Amostra'] == a2][['key_busca', 'V_calculo_mg', 'Valor']]
            
            comp = pd.merge(d1, d2, on='key_busca', suffixes=('_Ori', '_Dup'))
            
            # Cálculo RPD: |V1-V2| / Média * 100
            comp['RPD (%)'] = (abs(comp['V_calculo_mg_Ori'] - comp['V_calculo_mg_Dup']) / 
                              ((comp['V_calculo_mg_Ori'] + comp['V_calculo_mg_Dup'])/2)) * 100
            
            comp['Status'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= limite_rpd else "❌ FALHA")
            
            st.subheader(f"Resultado RPD: {a1} vs {a2}")
            st.dataframe(comp[['Análise', 'Valor_Ori', 'Valor_Dup', 'RPD (%)', 'Status']], use_container_width=True)
        elif a1 == a2:
            st.warning("Selecione amostras diferentes para calcular o RPD.")
