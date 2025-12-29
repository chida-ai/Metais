# ui/style.py
# Estilos visuais para tabelas no Streamlit

import pandas as pd
from core.utils import STATUS_COLORS


def style_status(df, status_col="Status"):
    """
    Aplica cores de fundo conforme o status.
    Pode ser usado em:
        - Dissolvido vs Total
        - QC Ítrio
        - Duplicatas
        - Legislação
    """

    def color_row(row):
        status = row.get(status_col, "")
        bg = STATUS_COLORS.get(status, "#222222")  # fallback
        fg = "white"
        return [f"background-color: {bg}; color: {fg}" for _ in row]

    return df.style.apply(color_row, axis=1)
