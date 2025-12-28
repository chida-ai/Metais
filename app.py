# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json
from pathlib import Path
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

# --- CSS DARK PROFISSIONAL (SÓBRIO) ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    
    /* Botões Laterais */
    div.stButton > button:first-child {
        width: 100%; border-radius: 4px; height: 3em;
        background-color: #1F2937; color: #FFFFFF !important;
        border: 1px solid #374151; font-weight: 500;
        text-align: left; padding-left: 15px;
    }
    div.stButton > button:hover {
        background-color: #FF0000 !important; border: 1px solid #FF0000;
    }

    /* Botão de Processamento Principal */
    .stButton button[kind="primary"] {
        background-color: #374151 !important; color: white !important;
        padding: 0.5rem 2rem !important; border: 1px solid #4B5563 !important;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #FF0000 !important; border-color: #FF0000 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #374151; }
    h1, h2, h3 { color: #F3F4F6; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES TÉCNICAS ---
def parse_val(val_str):
    if pd.isna(val_str): return None, False
    s = str(val_str).strip()
    cens = s.startswith('<')
    s_clean = s.replace('<','').replace('.', '').replace(',', '.')
    try: v = float(s_clean)
    except: v = None
    return v, cens

def padronizar_unidade(val, unit):
    if val is None or pd.isna(unit): return None
    u = str(unit).strip().lower()
    if 'µg' in u or 'ug' in u:
        return val / 1000.0
    return val

def normalize_analito(name):
    if pd.isna(name): return None
    # Remove "Dissolvido" ou "Total" do nome para conseguir cruzar os dados
    name_clean = re.sub(r"\s+(Dissolvido|Total)$", "", str(name).strip(), flags=re.IGNORECASE)
    return name_clean

# --- ESTADO DE SESSÃO ---
if "df_global" not in st.session_state: st.session_state["df_global"] = None
if "pagina" not in st.session_state: st.session_state["pagina"] = "📥 Inserir Dados"

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
        <div style="text-align: left; margin-bottom: 30px;">
            <h1 style="margin:0; font-size: 28px; color: #FFFFFF;">Data Support</h1>
            <div style="height:3px; background:#FF0000; width:100%; margin-top:2px;"></div>
            <p style="color: #FF0000; font-size: 13px; font-weight: bold; margin-top:4px;">AVALIAÇÃO DE DADOS LIMS</p>
        </div>
        """, unsafe_allow_html=True)
    
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação & U"): st.session_state.pagina = "⚖️ Legislação & U"
    if st.button("👥 Duplicatas"): st.session_state.pagina = "👥 Duplicatas"

# --- MÓDULOS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados (LIMS)")
    pasted = st.text_area("Cole aqui as colunas do LIMS (Id, Análise, Valor, Unidade de Medida, Nº Amostra, Método de Análise)", height=300)
    
    if st.button("Processar Dados", type="primary"):
        if pasted:
            try:
                # Tenta ler com TAB (comum em colagens de sistemas/excel)
                df_temp = pd.read_csv(io.StringIO(pasted), sep='\t')
                if len(df_temp.columns) < 3: # Se falhar, tenta ponto e vírgula
                    df_temp = pd.read_csv(io.StringIO(pasted), sep=';')
                
                df_temp['V_num'], df_temp['Cens'] = zip(*df_temp['Valor'].map(parse_val))
                df_temp['V_padrao'] = df_temp.apply(lambda r: padronizar_unidade(r['V_num'], r['Unidade de Medida']), axis=1)
                df_temp['Analito_base'] = df_temp['Análise'].map(normalize_analito)
                
                st.session_state["df_global"] = df_temp
                st.success(f"Sucesso! {len(df_temp)} registros importados.")
            except Exception as e:
                st.error(f"Erro ao processar: Verifique se os cabeçalhos das colunas estão corretos.")
        else:
            st.warning("Cole os dados antes de processar.")

elif st.session_state.pagina == "🧪 Avaliação de Lote":
    st.title("🧪 Avaliação Técnica")
    if st.session_state["df_global"] is None: st.warning("Aguardando dados...")
    else:
        df = st.session_state["df_global"]
        
        # --- REGRA: DISSOLVIDO X TOTAL (SEM TOLERÂNCIA) ---
        st.subheader("📊 Dissolvidos vs Totais")
        D = df[df['Método de Análise'].str.contains('Dissolvidos|Dissolvido', case=False, na=False)].copy()
        T = df[df['Método de Análise'].str.contains('Totais|Total', case=False, na=False)].copy()
        
        if not D.empty and not T.empty:
            m = pd.merge(D, T, on=['Id', 'Analito_base'], suffixes=('_diss', '_tot'))
            # Regra: Se Dissolvido > Total = Erro
            m['Status'] = np.where(m['V_padrao_diss'] > m['V_padrao_tot'], "❌ NÃO CONFORME (D > T)", "✅ OK")
            
            res = m[['Id', 'Analito_base', 'V_padrao_diss', 'V_padrao_tot', 'Status']].copy()
            res.columns = ['ID Amostra', 'Analito', 'Conc. Diss (mg)', 'Conc. Total (mg)', 'Avaliação']
            st.dataframe(res, use_container_width=True)
        else:
            st.info("Nenhum par de 'Dissolvido' e 'Total' encontrado para o mesmo ID e Analito.")

elif st.session_state.pagina == "👥 Duplicatas":
    st.title("👥 Controle de Precisão (RPD)")
    if st.session_state["df_global"] is None: st.warning("Aguardando dados...")
    else:
        df = st.session_state["df_global"]
        amostras = df['Nº Amostra'].dropna().unique()
        c1, c2 = st.columns(2)
        a1 = c1.selectbox("Amostra Original", amostras)
        a2 = c2.selectbox("Duplicata (D)", amostras)
        
        if a1 and a2:
            d1 = df[df['Nº Amostra'] == a1][['Analito_base', 'V_padrao']]
            d2 = df[df['Nº Amostra'] == a2][['Analito_base', 'V_padrao']]
            comp = pd.merge(d1, d2, on='Analito_base', suffixes=('_Ori', '_Dup'))
            
            # Cálculo de RPD
            comp['RPD (%)'] = (abs(comp['V_padrao_Ori'] - comp['V_padrao_Dup']) / ((comp['V_padrao_Ori'] + comp['V_padrao_Dup'])/2)) * 100
            comp['Avaliação'] = comp['RPD (%)'].apply(lambda x: "✅ OK" if x <= 20 else "❌ FALHA (>20%)")
            
            comp.columns = ['Analito', 'Original (mg)', 'Duplicata (mg)', 'RPD (%)', 'Status']
            st.dataframe(comp, use_container_width=True)
