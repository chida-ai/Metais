# core/dissolved_total.py
# Comparação Dissolvido vs Total com lógica científica completa

import pandas as pd
from .parsing import parse_val
from .units import to_mg_per_L
from .normalize import normalize_analito


def compare_dissolved_total(df_raw):
    """
    Compara Dissolvido vs Total para cada ID + Analito.
    Retorna:
        - tabela detalhada
        - status global do lote
        - status por ID
        - dataframe numérico completo
    """

    df = df_raw.copy()

    # Garante coluna LQ
    if "LQ - Limite Quantificação" not in df.columns:
        df["LQ - Limite Quantificação"] = None

    # Parsing e conversão
    df["Valor_num"], df["Censurado"] = zip(*df["Valor"].map(parse_val))
    df["Valor_mg_L"] = df.apply(lambda r: to_mg_per_L(r["Valor_num"], r["Unidade de Medida"]), axis=1)
    df["Analito_norm"] = df["Análise"].map(normalize_analito)

    # Separa Dissolvidos e Totais
    D = df[df["Método de Análise"].str.contains("Dissolvidos", case=False, na=False)].copy()
    T = df[df["Método de Análise"].str.contains("Totais", case=False, na=False)].copy()

    # Remove valores inválidos
    D = D[D["Valor_mg_L"].notna()].copy()
    T = T[T["Valor_mg_L"].notna()].copy()

    # Merge Dissolvido × Total
    merged = pd.merge(
        D[["Id", "Analito_norm", "Valor_mg_L", "Censurado", "Unidade de Medida", "LQ - Limite Quantificação"]],
        T[["Id", "Analito_norm", "Valor_mg_L", "Censurado", "Unidade de Medida", "LQ - Limite Quantificação"]],
        on=["Id", "Analito_norm"],
        suffixes=("_diss", "_tot"),
        how="outer"
    )

    out_rows = []
    has_nc_global = False
    has_pot_global = False
    id_nc = {}
    id_pot = {}

    for _, r in merged.iterrows():
        idv = r["Id"]
        analito = r["Analito_norm"]

        d_val = r["Valor_mg_L_diss"]
        t_val = r["Valor_mg_L_tot"]

        d_cens = bool(r["Censurado_diss"]) if pd.notna(r["Censurado_diss"]) else False
        t_cens = bool(r["Censurado_tot"]) if pd.notna(r["Censurado_tot"]) else False

        status = ""
        obs = ""

        # Casos sem dados
        if pd.isna(d_val) and pd.isna(t_val):
            status = "Sem dados válidos"
            obs = "Unidade não suportada ou valor ausente"

        elif pd.isna(d_val) and pd.notna(t_val):
            status = "Sem par para comparação"
            obs = "Apenas Total disponível"

        elif pd.notna(d_val) and pd.isna(t_val):
            status = "Sem par para comparação"
            obs = "Apenas Dissolvido disponível"

        else:
            # Ambos presentes
            if not d_cens and not t_cens:
                status = "NÃO CONFORME" if d_val > t_val else "OK"

            elif not d_cens and t_cens:
                # Total < LQ → comparar Dissolvido com LQ
                lq_num, _ = parse_val(r["LQ - Limite Quantificação_tot"])
                lq_unit = r["Unidade de Medida_tot"]
                lq_mg = to_mg_per_L(lq_num, lq_unit)

                if lq_mg is None:
                    status = "INCONCLUSIVO"
                    obs = "Total <LQ; LQ não informado ou unidade não suportada"
                else:
                    status = "POTENCIAL NÃO CONFORME" if d_val > lq_mg else "OK"

            elif d_cens and not t_cens:
                status = "OK" if (d_val is None or d_val <= t_val) else "INCONCLUSIVO"
                obs = "Dissolvido <LQ"

            else:
                status = "OK"
                obs = "Ambos <LQ"

        # Marca status global
        if status == "NÃO CONFORME":
            has_nc_global = True
            id_nc[idv] = True

        elif status == "POTENCIAL NÃO CONFORME":
            has_pot_global = True
            if idv not in id_nc:
                id_pot[idv] = True

        out_rows.append({
            "Id": idv,
            "Analito": analito,
            "Dissolvido (mg/L)": d_val,
            "Total (mg/L)": t_val,
            "Dissolvido <LQ?": "Sim" if d_cens else "Não",
            "Total <LQ?": "Sim" if t_cens else "Não",
            "Status": status,
            "Observação": obs,
        })

    out_df = pd.DataFrame(out_rows)

    # Status global do lote
    if has_nc_global:
        lote_status = "REPROVADO"
    elif has_pot_global:
        lote_status = "ATENÇÃO (potenciais não conformidades)"
    else:
        lote_status = "APROVADO"

    # Status por ID
    id_status = {}
    ids = merged["Id"].dropna().unique()

    for idv in ids:
        if idv in id_nc:
            id_status[idv] = "REPROVADO"
        elif idv in id_pot:
            id_status[idv] = "ATENÇÃO"
        else:
            id_status[idv] = "APROVADO"

    return out_df, lote_status, id_status, df
