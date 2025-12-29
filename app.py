# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io, re, json, unicodedata
from pathlib import Path

# ============================================================
# 🔧 FUNÇÕES DE TRATAMENTO
# ============================================================

def limpar_texto(t):
    if pd.isna(t): 
        return ""
    t = str(t).strip().lower()
    t = re.sub(r"\s+(total|dissolvido|lixiviado|solubilizado)$", "", t)
    nfkd = unicodedata.normalize('NFKD', t)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_unidade(u):
    if pd.isna(u): 
        return ""
    u = unicodedata.normalize("NFKD", str(u).lower())
    return "".join(c for c in u if not unicodedata.combining(c))


def parse_val(v):
    if pd.isna(v):
        return None, False

    s = str(v).strip()
    is_less = s.startswith("<")

    s = s.replace("<", "")
    s = s.replace(" ", "")
    s = s.replace(".", "")   # remove milhar
    s = s.replace(",", ".")  # decimal

    try:
        return float(s), is_less
    except:
        return None, is_less


# ============================================================
# 🎨 INTERFACE
# ============================================================

st.set_page_config(page_title="Data Support - Lab Ambiental", layout="wide")

if "df_global" not in st.session_state:
    st.session_state["df_global"] = None

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "📥 Inserir Dados"

with st.sidebar:
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)

    st.markdown("<h2 style='color:#FF0000;'>Data Support</h2><hr>", unsafe_allow_html=True)

    if st.button("📥 Inserir Dados"):
        st.session_state.pagina = "📥 Inserir Dados"

    if st.button("🧪 Avaliação de Lote (QC)"):
        st.session_state.pagina = "🧪 Avaliação de Lote"

    if st.button("⚖️ Legislação"):
        st.session_state.pagina = "⚖️ Legislação"


# ============================================================
# 📥 PÁGINA 1 — INSERIR DADOS
# ============================================================

if st.session_state.pagina == "📥 Inserir Dados":
    st.title("📥 Entrada de Dados (LIMS)")

    pasted = st.text_area("Cole os dados aqui", height=200)

    if st.button("Processar Dados", type="primary"):
        df = pd.read_csv(io.StringIO(pasted), sep=None, engine='python', decimal=",")

        # Extrai número e sinal "<"
        df['V_num'], df['V_menor_que'] = zip(*df['Valor'].map(parse_val))

        # Converte unidades
        df['Unid_norm'] = df['Unidade de Medida'].map(normalizar_unidade)

        df['V_mg'] = df.apply(
            lambda r: r['V_num']/1000 if "ug" in r['Unid_norm'] else r['V_num'],
            axis=1
        )

        df['key_busca'] = df['Análise'].map(limpar_texto)

        st.session_state["df_global"] = df
        st.success("Dados processados com sucesso, incluindo conversão automática de unidades.")


# ============================================================
# ⚖️ PÁGINA 2 — LEGISLAÇÃO
# ============================================================

elif st.session_state.pagina == "⚖️ Legislação":
    st.title("⚖️ Conformidade Legal")

    df = st.session_state["df_global"]

    if df is not None:
        try:
            with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
                catalog = json.load(f)

            escolha = st.selectbox("Selecione a Legislação:", list(catalog.keys()))

            # NOVO: % de desvio permitido
            desvio = st.slider("Desvio permitido (%)", 0, 100, 0)

            limites = {
                limpar_texto(k): v 
                for k, v in catalog[escolha]['limits_mgL'].items()
            }

            df_l = df.copy()
            df_l['VMP_mg'] = df_l['key_busca'].map(limites)

            # Aviso para analitos não encontrados
            nao_encontrados = df_l[df_l['VMP_mg'].isna()]['Análise'].unique()
            if len(nao_encontrados) > 0:
                st.warning(f"Analitos sem VMP encontrado: {list(nao_encontrados)}")

            df_l = df_l.dropna(subset=['VMP_mg'])

            # Aplica desvio
            df_l['VMP_ajustado'] = df_l['VMP_mg'] * (1 + desvio/100)

            # Avaliação
            def avaliar(row):
                if row['V_menor_que']:
                    return "✅ OK" if row['V_mg'] <= row['VMP_ajustado'] else "❌ FORA (LD > VMP)"
                else:
                    return "❌ FORA" if row['V_mg'] > row['VMP_ajustado'] else "✅ OK"

            df_l['Parecer'] = df_l.apply(avaliar, axis=1)

            # Exibição final com unidades
            res = df_l[[
                'Id', 'Análise', 'Valor', 'Unidade de Medida',
                'V_mg', 'VMP_mg', 'VMP_ajustado', 'Parecer'
            ]]

            res.columns = [
                'ID', 'Analito', 'Valor LIMS', 'Unidade LIMS',
                'Resultado (mg/L)', 'VMP (mg/L)', f'VMP Ajustado (+{desvio}%)', 'Parecer'
            ]

            st.dataframe(res, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao carregar legislação: {e}")

# ============================================================
# 📊 PÁGINA 3 — COMPARAR LEGISLAÇÕES
# ============================================================

elif st.session_state.pagina == "📊 Comparar Legislações":
    st.title("📊 Comparação de Legislações")

    df = st.session_state["df_global"]

    if df is not None:
        try:
            with open('catalogo_especificacoes.json', 'r', encoding='utf-8') as f:
                catalog = json.load(f)

            colA, colB = st.columns(2)
            with colA:
                legA = st.selectbox("Legislação A:", list(catalog.keys()))
            with colB:
                legB = st.selectbox("Legislação B:", list(catalog.keys()))

            # Normaliza limites
            limitesA = {limpar_texto(k): v for k, v in catalog[legA]['limits_mgL'].items()}
            limitesB = {limpar_texto(k): v for k, v in catalog[legB]['limits_mgL'].items()}

            df_c = df.copy()
            df_c['VMP_A'] = df_c['key_busca'].map(limitesA)
            df_c['VMP_B'] = df_c['key_busca'].map(limitesB)

            # Remove analitos sem correspondência
            df_c = df_c.dropna(subset=['VMP_A', 'VMP_B'])

            # Diferenças
            df_c['Diferença (mg/L)'] = df_c['VMP_A'] - df_c['VMP_B']
            df_c['Diferença (%)'] = (df_c['Diferença (mg/L)'] / df_c['VMP_B']) * 100

            # Qual é mais restritiva?
            df_c['Mais Restritiva'] = df_c.apply(
                lambda r: legA if r['VMP_A'] < r['VMP_B'] else legB,
                axis=1
            )

            # Parecer frente às duas legislações
            def avaliar(v, vmp, menor):
                if menor:
                    return "OK" if v <= vmp else "FORA"
                return "FORA" if v > vmp else "OK"

            df_c['Parecer A'] = df_c.apply(lambda r: avaliar(r['V_mg'], r['VMP_A'], r['V_menor_que']), axis=1)
            df_c['Parecer B'] = df_c.apply(lambda r: avaliar(r['V_mg'], r['VMP_B'], r['V_menor_que']), axis=1)

            # Parecer combinado
            def combinado(a, b):
                if a == "OK" and b == "OK":
                    return "OK nas duas"
                if a == "OK" and b == "FORA":
                    return f"OK apenas em {legA}"
                if a == "FORA" and b == "OK":
                    return f"OK apenas em {legB}"
                return "FORA em ambas"

            df_c['Parecer Geral'] = df_c.apply(lambda r: combinado(r['Parecer A'], r['Parecer B']), axis=1)

            # Exibição
            res = df_c[[
                'Id', 'Análise', 'V_mg',
                'VMP_A', 'VMP_B',
                'Diferença (mg/L)', 'Diferença (%)',
                'Mais Restritiva',
                'Parecer A', 'Parecer B', 'Parecer Geral'
            ]]

            res.columns = [
                'ID', 'Analito', 'Resultado (mg/L)',
                f'VMP - {legA} (mg/L)', f'VMP - {legB} (mg/L)',
                'Diferença (mg/L)', 'Diferença (%)',
                'Mais Restritiva',
                f'Parecer {legA}', f'Parecer {legB}', 'Parecer Geral'
            ]

            st.dataframe(res, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao comparar legislações: {e}")
