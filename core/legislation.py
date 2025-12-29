# core/legislation.py
# Avaliação por legislação / especificação usando catálogo JSON

import pandas as pd
from .normalize import normalize_analito, apply_alias
from .units import to_mg_per_L
from .parsing import parse_val


def prepare_numeric(df_raw):
    """Converte valores e normaliza analitos para uso em legislação."""
    df = df_raw.copy()
    df["Valor_num"], df["Censurado"] = zip(*df["Valor"].map(parse_val))
    df["Valor_mg_L"] = df.apply(lambda r: to_mg_per_L(r["Valor_num"], r["Unidade de Medida"]), axis=1)
    df["Analito_norm"] = df["Análise"].map(normalize_analito)
    df["Analito_alias"] = df["Analito_norm"].map(apply_alias)
    return df


def apply_legislation(df_raw, spec_dict):
    """
    Aplica uma legislação/especificação.
    spec_dict deve conter:
        - limits_mgL: {analito: limite}
        - prefer_total: True/False
    Retorna:
        - tabela detalhada
        - resumo por ID
    """

    if not spec_dict:
        return pd.DataFrame(), pd.DataFrame()

    limits = spec_dict.get("limits_mgL", {})
    prefer_total = spec_dict.get("prefer_total", True)

    df = prepare_numeric(df_raw)

    # Separa Dissolvidos e Totais
    D = df[df["Método de Análise"].str.contains("Dissolvidos", case=False, na=False)].copy()
    T = df[df["Método de Análise"].str.contains("Totais", case=False, na=False)].copy()

    # Escolha da base conforme especificação
    if prefer_total:
        # Usa Totais; se não houver, usa Dissolvidos
        base = pd.concat([
            T,
            D[~D["Analito_alias"].isin(T["Analito_alias"])]
        ], ignore_index=True)
    else:
        # Usa Dissolvidos; se não houver, usa Totais
        base = pd.concat([
            D,
            T[~T["Analito_alias"].isin(D["Analito_alias"])]
        ], ignore_index=True)

    rows = []

    for _, r in base.iterrows():
        anal = r["Analito_alias"]
        idv = r["Id"]
        val = r["Valor_mg_L"]
        lim = limits.get(anal)

        if lim is None:
            status = "Sem limite"
        elif val is None:
            status = "Sem dado"
        else:
            status = "Conforme" if val <= lim else "Não conforme"

        rows.append({
            "Id": idv,
            "Analito": r["Analito_norm"],
            "Analito (alias)": anal,
            "Valor (mg/L)": val,
            "Limite (mg/L)": lim,
            "Status": status
        })

    out = pd.DataFrame(rows)

    # Resumo por ID
    if out.empty:
        resumo = pd.DataFrame()
    else:
        resumo = (
            out.groupby("Id")["Status"]
            .apply(lambda s: "REPROVADO" if (s == "Não conforme").any() else "APROVADO")
            .reset_index(name="Status (Legislação)")
        )

    return out, resumo
