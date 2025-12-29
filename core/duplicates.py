# core/duplicates.py
# Comparação de duplicatas (%RPD) com lógica robusta e independente

import pandas as pd
from .parsing import parse_val
from .units import to_mg_per_L
from .normalize import normalize_analito


def rpd(v1, v2):
    """Calcula %RPD entre dois valores."""
    if v1 is None or v2 is None:
        return None
    if (v1 + v2) == 0:
        return 0.0
    return abs(v1 - v2) / ((v1 + v2) / 2.0) * 100.0


def prepare_numeric(df_raw):
    """Converte valores e normaliza analitos para comparação."""
    df = df_raw.copy()
    df["Valor_num"], df["Censurado"] = zip(*df["Valor"].map(parse_val))
    df["Valor_mg_L"] = df.apply(lambda r: to_mg_per_L(r["Valor_num"], r["Unidade de Medida"]), axis=1)
    df["Analito_norm"] = df["Análise"].map(normalize_analito)
    return df


def compare_duplicates(df_raw, sample1, sample2, tolerance_pct=20.0):
    """
    Compara duplicatas entre duas amostras.
    Retorna:
        - tabela final com %RPD
    """

    df = prepare_numeric(df_raw)

    # Filtra amostras
    a1 = df[df["Nº Amostra"].astype(str) == str(sample1)].copy()
    a2 = df[df["Nº Amostra"].astype(str) == str(sample2)].copy()

    # Remove unidades em %
    a1 = a1[a1["Unidade de Medida"].astype(str).str.strip() != "%"]
    a2 = a2[a2["Unidade de Medida"].astype(str).str.strip() != "%"]

    key_cols = ["Método de Análise", "Analito_norm"]
    cols_keep = key_cols + ["Unidade de Medida", "Valor_mg_L", "Censurado"]

    a1 = a1[cols_keep].rename(columns={
        "Unidade de Medida": "Unidade_1",
        "Valor_mg_L": "Valor_1",
        "Censurado": "Cens_1"
    })

    a2 = a2[cols_keep].rename(columns={
        "Unidade de Medida": "Unidade_2",
        "Valor_mg_L": "Valor_2",
        "Censurado": "Cens_2"
    })

    # Merge
    comp = pd.merge(a1, a2, on=key_cols, how="outer")

    rows = []

    for _, r in comp.iterrows():
        metodo = r["Método de Análise"]
        analito = r["Analito_norm"]

        v1 = r["Valor_1"]
        v2 = r["Valor_2"]

        c1 = bool(r["Cens_1"]) if pd.notna(r["Cens_1"]) else False
        c2 = bool(r["Cens_2"]) if pd.notna(r["Cens_2"]) else False

        unidade = r["Unidade_1"] if pd.notna(r["Unidade_1"]) else r["Unidade_2"]

        status = ""
        obs = ""
        rpd_pct = None

        # Casos especiais
        if v1 is None and v2 is None:
            status = "Sem dados"
            obs = "Valores ausentes"

        elif c1 and c2:
            status = "OK"
            obs = "Ambos <LQ"

        elif (c1 and not c2) or (c2 and not c1):
            status = "INCONCLUSIVO"
            obs = "Um <LQ"

        else:
            # Cálculo normal
            rpd_pct = rpd(v1, v2)
            status = "Conforme" if (rpd_pct is not None and rpd_pct <= tolerance_pct) else "Não conforme"

        rows.append({
            "Método de Análise": metodo,
            "Analito": analito,
            "Unidade": unidade,
            f"Valor ({sample1}) mg/L": v1,
            f"Valor ({sample2}) mg/L": v2,
            "%RPD": rpd_pct,
            "Status": status,
            "Observação": obs,
        })

    out = pd.DataFrame(rows)

    # Ordenação por severidade
    cat = pd.Categorical(
        out["Status"],
        categories=["Não conforme", "INCONCLUSIVO", "OK", "Conforme", "Sem dados"],
        ordered=True
    )
    out["__ord"] = cat
    out = out.sort_values(["__ord", "Método de Análise", "Analito"]).drop(columns="__ord")

    return out
