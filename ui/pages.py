# ui/pages.py
# Interface principal: abas, carregamento de dados e integração com os módulos do core

import streamlit as st
import pandas as pd
import io

from core.dissolved_total import compare_dissolved_total
from core.qc import evaluate_qc_itrio
from core.duplicates import compare_duplicates
from core.legislation import apply_legislation
from ui.style import style_status


# ---------------------------------------------------------
# Função auxiliar para ler texto colado
# ---------------------------------------------------------

def try_read_pasted(text):
    seps = ["\t", ";", ",", "|"]
    for sep in seps:
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if len(df.columns) >= 4:
                return df
        except:
            pass
    return None


# ---------------------------------------------------------
# Página principal
# ---------------------------------------------------------

def render_pages(catalog):
    st.sidebar.header("Entrada de dados")

    file = st.sidebar.file_uploader("Enviar arquivo (Excel/CSV)", type=["xlsx", "xls", "csv"])

    pasted = st.sidebar.text_area("Ou cole a tabela aqui", height=150)
    btn_load = st.sidebar.button("Carregar dados")

    df_in = None

    if btn_load:
        if file is not None:
            try:
                if file.name.lower().endswith(".csv"):
                    df_in = pd.read_csv(file)
                else:
                    df_in = pd.read_excel(file, sheet_name=0, engine="openpyxl")
            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

        elif pasted.strip():
            df_in = try_read_pasted(pasted)
            if df_in is None:
                st.error("Não consegui interpretar o texto colado. Tente usar separador ';' ou TAB.")

    # ---------------------------------------------------------
    # Abas
    # ---------------------------------------------------------

    aba1, aba2, aba3, aba4 = st.tabs([
        "Avaliar Lote",
        "Legislação / Especificação",
        "Duplicatas",
        "Relatórios"
    ])

    # ---------------------------------------------------------
    # ABA 1 — Dissolvido vs Total + QC Ítrio
    # ---------------------------------------------------------

    with aba1:
        st.subheader("Avaliação: Dissolvidos vs Totais + QC Ítrio")

        if df_in is None:
            st.info("Carregue dados no menu lateral.")
        else:
            st.dataframe(df_in.head(20), use_container_width=True)

            if st.button("Rodar Avaliação do Lote", type="primary"):
                # Dissolvido vs Total
                out_dt, lote_status, id_status, df_num = compare_dissolved_total(df_in)

                # QC Ítrio
                qc_df, qc_id_status, qc_has_nc = evaluate_qc_itrio(df_num)

                # Integra status QC com status D/T
                for k, v in qc_id_status.items():
                    if v == "REPROVADO":
                        id_status[k] = "REPROVADO"

                # Status final do lote
                if any(v == "REPROVADO" for v in id_status.values()):
                    lote_status = "REPROVADO"

                # Exibe status do lote
                if lote_status == "APROVADO":
                    st.success(f"Status do Lote: {lote_status}")
                elif lote_status == "REPROVADO":
                    st.error(f"Status do Lote: {lote_status}")
                else:
                    st.warning(f"Status do Lote: {lote_status}")

                # Status por ID
                st.markdown("### Status por ID")
                for idv, stid in id_status.items():
                    st.write(f"• ID {idv}: {stid}")

                st.divider()

                # Tabela Dissolvido vs Total
                st.subheader("Comparação Dissolvido vs Total")
                st.dataframe(style_status(out_dt), use_container_width=True)

                # QC Ítrio
                st.subheader("QC Ítrio (70–130%)")
                if qc_df.empty:
                    st.info("Nenhuma linha de Ítrio em % encontrada.")
                else:
                    st.dataframe(style_status(qc_df), use_container_width=True)

                # Exportação
                st.subheader("Exportar Resultados")
                st.download_button(
                    "Baixar Dissolvido vs Total (CSV)",
                    out_dt.to_csv(index=False).encode("utf-8"),
                    file_name="dissolvido_vs_total.csv",
                    mime="text/csv"
                )

                if not qc_df.empty:
                    st.download_button(
                        "Baixar QC Ítrio (CSV)",
                        qc_df.to_csv(index=False).encode("utf-8"),
                        file_name="qc_itrio.csv",
                        mime="text/csv"
                    )

    # ---------------------------------------------------------
    # ABA 2 — Legislação / Especificação
    # ---------------------------------------------------------

    with aba2:
        st.subheader("Avaliação por Legislação / Especificação")

        if df_in is None:
            st.info("Carregue dados no menu lateral.")
        else:
            spec_keys = list(catalog.keys())

            filtro = st.text_input("Filtrar especificações por texto")
            if filtro:
                spec_keys = [k for k in spec_keys if filtro.lower() in k.lower()]

            spec_key = st.selectbox("Selecione a especificação", spec_keys)

            if st.button("Aplicar Especificação", type="primary"):
                spec_dict = catalog.get(spec_key, {})
                out_leg, resumo_leg = apply_legislation(df_in, spec_dict)

                if out_leg.empty:
                    st.info("Nenhum dado aplicável ou especificação sem limites.")
                else:
                    st.dataframe(style_status(out_leg), use_container_width=True)

                    if not resumo_leg.empty:
                        st.markdown("### Resumo por ID")
                        st.dataframe(resumo_leg, use_container_width=True)

                    st.download_button(
                        "Baixar Avaliação (CSV)",
                        out_leg.to_csv(index=False).encode("utf-8"),
                        file_name="avaliacao_legislacao.csv",
                        mime="text/csv"
                    )

    # ---------------------------------------------------------
    # ABA 3 — Duplicatas
    # ---------------------------------------------------------

    with aba3:
        st.subheader("Comparação de Duplicatas (%RPD)")

        if df_in is None:
            st.info("Carregue dados no menu lateral.")
        else:
            amostras = sorted(df_in["Nº Amostra"].dropna().astype(str).unique())

            col1, col2, col3 = st.columns(3)
            with col1:
                am1 = st.selectbox("Amostra 1", amostras)
            with col2:
                am2 = st.selectbox("Amostra 2", amostras)
            with col3:
                tol = st.number_input("Tolerância (%RPD)", min_value=0.0, max_value=100.0, value=20.0)

            if st.button("Comparar Duplicatas"):
                dup_df = compare_duplicates(df_in, am1, am2, tolerance_pct=tol)
                st.dataframe(style_status(dup_df), use_container_width=True)

                st.download_button(
                    "Baixar Duplicatas (CSV)",
                    dup_df.to_csv(index=False).encode("utf-8"),
                    file_name="duplicatas.csv",
                    mime="text/csv"
                )

    # ---------------------------------------------------------
    # ABA 4 — Relatórios (futuro)
    # ---------------------------------------------------------

    with aba4:
        st.subheader("Relatórios")
        st.info("Geração de PDF e relatórios consolidados será adicionada futuramente.")
