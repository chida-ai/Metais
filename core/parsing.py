# core/parsing.py
# Funções robustas para interpretar valores numéricos e censurados

import pandas as pd
import unicodedata

def normalize_text(s: str) -> str:
    """Remove acentos e normaliza unicode."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c))


def parse_val(raw):
    """
    Converte valores como:
    - "< 0,3"
    - "<0.3"
    - "1.200,5"
    - "0,05"
    Retorna (valor_float, censurado_bool)
    """
    if pd.isna(raw):
        return None, False

    s = str(raw).strip()
    cens = s.startswith("<")

    # Remove "<"
    s = s.replace("<", "").strip()

    # Remove milhar
    s = s.replace(".", "")

    # Troca vírgula por ponto
    s = s.replace(",", ".")

    try:
        v = float(s)
    except:
        v = None

    return v, cens
