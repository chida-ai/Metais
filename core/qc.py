# core/qc.py
# Avaliação de QC Ítrio (70–130%) com detecção robusta

import pandas as pd
from .parsing import parse_val
from .normalize import strip_accents


def evaluate_qc_itrio(df_raw):
    """
    Avalia QC Ítrio com faixa 70–130%.
    Retorna:
        - tabela QC
        - status por ID
        - flag se há NC global
    """

    df = df_raw.copy()

    # Normalização para busca
    df["analise_norm"] = df["Análise"].astype(str).apply(strip_accents).str.lower()
    df["unidade_norm"] = df["Unidade de Medida"].astype(str).str.strip().str.lower()

    # Seleciona apenas Ítrio em %
    mask_itrio = df["analise_norm"].str.contains("itrio")
    mask_pct = df["unidade_norm"] == "%"

    qc_df = df[mask_itrio & mask_pct].copy()

    out_rows = []
    id_status = {}
    has_nc_global = False

    for _, r in qc_df.iterrows():
        idv = r["Id"]
        rec_num, _ = parse_val(r["Valor"])

        if rec_num is None:
            status = "Sem dado"
            obs = "Valor de recuperação ausente ou inválido"

        else:
            if 70.0 <= rec_num <= 130.0:
                status = "OK"
                obs = "Recuperação dentro de 70–130%"
            else:
                status = "NÃO CONFORME"
                obs = "Recuperação fora de 70–130%"
                has_nc_global = True
                id_status[idv] = "REPROVADO"

        # Se não marcou NC, marca OK
        if idv not in id_status:
            id_status[idv] = "APROVADO"

        out_rows.append({
            "Id": idv,
            "Nº Amostra": r.get("Nº Amostra", ""),
            "Método de Análise": r["Método de Análise"],
            "Análise": r["Análise"],
            "Recuperação (%)": rec_num,
            "Status": status,
            "Observação": obs,
        })

    out_df = pd.DataFrame(out_rows)

    return out_df, id_status, has_nc_global
