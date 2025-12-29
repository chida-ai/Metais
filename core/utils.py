# core/utils.py
# Funções auxiliares compartilhadas entre módulos

import pandas as pd


# -----------------------------
# Ordenação de severidade
# -----------------------------

STATUS_ORDER = [
    "NÃO CONFORME",
    "Não conforme",
    "POTENCIAL NÃO CONFORME",
    "INCONCLUSIVO",
    "Sem dados",
    "Sem limite",
    "ATENÇÃO",
    "OK",
    "Conforme",
    "APROVADO"
]


def sort_by_status(df, status_col="Status"):
    """
    Ordena um dataframe por severidade de status.
    """
    if status_col not in df.columns:
        return df

    cat = pd.Categorical(df[status_col], categories=STATUS_ORDER, ordered=True)
    df["__ord"] = cat
    df = df.sort_values("__ord").drop(columns="__ord")
    return df


# -----------------------------
# Cores para UI (usado pelo style.py)
# -----------------------------

STATUS_COLORS = {
    "NÃO CONFORME": "#FF3B30",
    "Não conforme": "#FF3B30",
    "POTENCIAL NÃO CONFORME": "#FF9500",
    "INCONCLUSIVO": "#FFCC00",
    "Sem dados": "#555555",
    "Sem limite": "#555555",
    "ATENÇÃO": "#FF9500",
    "OK": "#34C759",
    "Conforme": "#34C759",
    "APROVADO": "#34C759",
}
