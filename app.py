# app.py (diagnóstico mínimo)
import streamlit as st

# A PRIMEIRA LINHA DEVE SER set_page_config
st.set_page_config(
    page_title="OPERA LAB – Analyst Support (Diagnóstico)",
    page_icon="🧪",
    layout="wide",
)

# Guardas para capturar exceções e mostrar no front
def safe_block(title, func):
    with st.expander(f"Bloco: {title}", expanded=True):
        try:
            func()
        except Exception as e:
            st.error(f"Erro no bloco '{title}': {e}")

st.title("OPERA LAB – Analyst Support")
st.caption("Diagnóstico de renderização — se você está vendo este conteúdo, o front está ok.")

# Sidebar mínima
with st.sidebar:
    st.image("logo.png", caption="Logo (opcional)", use_column_width=True)
    matriz = st.selectbox("Matriz do lote", ["A", "AS", "ASub", "EFL", "S"])
    st.write(f"Matriz selecionada: **{matriz}**")

def bloco_layout():
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.metric("Itens no lote", 12)
    with c2:
        st.metric("Pendências", 2)
    with c3:
        st.metric("Última calibração", "2025‑12‑20")
    st.success("Render básico OK")

safe_block("Layout", bloco_layout)

# Evita CSS agressivo; apenas um estilo simples
st.markdown("""
<style>
/* estilo leve e seguro */
:root { --accent: #00A3FF; }
.block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# Logs de diagnóstico
st.write("Versão do Streamlit:", st.__version__)
st.write("Tema ativo (se houver) não deve causar tela preta.")

st.divider()
st.write("Se o seu app completo fica em tela preta, compare:")
st.code("""
1) st.set_page_config deve ser a PRIMEIRA chamada.
2) Evite CSS global que altere 'html, body' com overflow/height fixo.
3) Valide leitura de JSON antes de usar dados.
4) Use try/except e apresente st.error se algo falhar.
5) Teste sem .streamlit/config.toml para descartar tema.
""")
``
