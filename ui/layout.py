# ui/layout.py
# Layout visual do aplicativo (header, footer, barras, etc.)

import streamlit as st
from pathlib import Path


def render_header():
    """Renderiza o cabeçalho com logo, título e barra azul."""
    LOGO_PATH = Path("assets/operalab_logo.png")

    cols = st.columns([0.9, 6])

    with cols[0]:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=160)
        else:
            st.caption("Logo não encontrado em: assets/operalab_logo.png")

    with cols[1]:
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:12px;">
                <h1 style="margin:0;">OPERALAB&nbsp;&nbsp;-&nbsp;&nbsp;Avaliação de Resultados</h1>
            </div>

            <div style="height:4px;background:#00A3FF;border-radius:2px;margin-top:8px;"></div>

            <div style="margin-top:6px;opacity:0.85;">
                Dissolvidos vs Totais • QC Ítrio • Duplicatas (%RPD) • Avaliação por Legislação
            </div>
            """,
            unsafe_allow_html=True
        )


def render_footer():
    """Renderiza o rodapé padrão."""
    st.markdown(
        f"""
        <div style="margin-top:40px;text-align:center;opacity:0.6;font-size:13px;">
            © {st.session_state.get("year", "")} OPERALAB — Sistema de Avaliação de Resultados
        </div>
        """,
        unsafe_allow_html=True
    )
