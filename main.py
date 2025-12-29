# main.py
# Ponto de entrada do aplicativo Streamlit

import streamlit as st
import json
from ui.layout import render_header, render_footer
from ui.pages import render_pages
from pathlib import Path


# ---------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------

st.set_page_config(
    page_title="OPERALAB - Avaliação de Resultados",
    layout="wide"
)

# Ano para rodapé
st.session_state["year"] = 2025


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

render_header()


# ---------------------------------------------------------
# Carrega catálogo de especificações
# ---------------------------------------------------------

CAT_PATH = Path("catalogo_especificacoes.json")

if CAT_PATH.exists():
    try:
        with open(CAT_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    except Exception as e:
        st.error(f"Erro ao carregar catálogo: {e}")
        catalog = {}
else:
    st.warning("Arquivo 'catalogo_especificacoes.json' não encontrado.")
    catalog = {}


# ---------------------------------------------------------
# Renderiza páginas
# ---------------------------------------------------------

render_pages(catalog)


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

render_footer()
