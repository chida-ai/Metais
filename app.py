# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, unicodedata
from pathlib import Path

# --- FUNÇÕES DE TRATAMENTO ---
def limpar_texto(t):
    if pd.isna(t): return ""
    t = str(t).strip().lower()
    t = re.sub(r"\s+(total|dissolvido|lixiviado|solubilizado)$", "", t)
    nfkd = unicodedata.normalize('NFKD', t)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def parse_val(v):
    if pd.isna(v): return None, False
    s_orig = str(v).strip()
    is_less_than = '<' in s_orig
    
    # Se o valor for "< 0,3", ele remove o "<", 
    # troca a vírgula por ponto e vira o número 0.3
    s_limpo = s_orig.replace('<', '').replace(' ', '').replace(',', '.')
    
    try: 
        return float(s_limpo), is_less_than
    except: 
        return None, False
# --- INTERFACE ---
st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

if "df_global" not in st.session_state: st.session_state["df_global"] = None
if "pagina" not in st.session_state: st.session_state["pagina"] = "📥 Inserir Dados"

with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists(): st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown("<h2 style='color:#FF0000;'>Data Support</h2><hr>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#FF0000;'>Data Support</h2><hr>", unsafe_allow_html=True)
    if st.button("📥 Inserir Dados"): st.session_state.pagina = "📥 Inserir Dados"
    if st.button("🧪 Avaliação de Lote (QC)"): st.session_state.pagina = "🧪 Avaliação de Lote"
    if st.button("⚖️ Legislação"): st.session_state.pagina = "⚖️ Legislação"

# --- PÁGINAS ---

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados (LIMS)")
    pasted = st.text_area("Cole os dados aqui", height=200)
    if st.button("Processar Dados", type="primary"):
        df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python')
        
        # 1. Extrai número e sinal <
        df['V_num'], df['V_menor_que'] = zip(*df['Valor'].map(parse_val))
        
        # 2. CONVERSÃO CRÍTICA: Se for ug, divide por 1000 para virar mg
        df['V_mg'] = df.apply(lambda r: r['V_num']/1000 if 'ug' in str(r['Unidade de Medida']).lower() else r['V_num'], axis=1)
        
        df['key_busca'] = df['Análise'].map(limpar_texto)
        st.session_state["df_global"] = df
        st.success("Dados processados com conversão automática de unidades.")

elif st.session_state.pagina == "⚖️ Legislação":
    st.title("⚖️ Conformidade Legal")
    df = st.session_state["df_global"]
    if df is not None:
        try:
            with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            
            escolha = st.selectbox("Selecione a Legislação:", list(catalog.keys()))
            limites = {limpar_texto(k): v for k, v in catalog[escolha]['limits_mgL'].items()}
            
            df_l = df.copy()
            df_l['VMP_mg'] = df_l['key_busca'].map(limites)
            df_l = df_l.dropna(subset=['VMP_mg'])

            # LÓGICA DE AVALIAÇÃO CORRIGIDA
            def avaliar(row):
                # Se o valor é < 0,3 ug/L, row['V_mg'] será 0,0003 mg/L
                if row['V_menor_que']:
                    return "✅ OK" if row['V_mg'] <= row['VMP_mg'] else "❌ FORA (LD > VMP)"
                else:
                    return "❌ FORA" if row['V_mg'] > row['VMP_mg'] else "✅ OK"

            df_l['Parecer'] = df_l.apply(avaliar, axis=1)

            # Exibição clara para auditoria
            res = df_l[['Id', 'Análise', 'Valor', 'Unidade de Medida', 'V_mg', 'VMP_mg', 'Parecer']]
            res.columns = ['ID', 'Analito', 'Valor LIMS', 'Unid LIMS', 'Resultado (mg)', 'VMP (mg)', 'Parecer']
            st.dataframe(res, use_container_width=True)
            
        except Exception as e:
            st.error(f"Erro ao carregar legislação: {e}")
