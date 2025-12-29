# core/units.py
# Conversão robusta de unidades ambientais (mg/L, µg/L, μg/L, ug/L)

import unicodedata
import pandas as pd


def normalize_unit(u: str) -> str:
    """
    Normaliza unidades para formato seguro:
    - Remove acentos
    - Converte µ e μ para 'u'
    - Remove espaços
    - Converte tudo para minúsculas
    """
    if u is None or pd.isna(u):
        return ""

    s = str(u).strip().lower()

    # Normaliza unicode (µ, μ → u)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))

    # Converte explicitamente micro para 'u'
    s = s.replace("µ", "u").replace("μ", "u")

    # Remove espaços
    s = s.replace(" ", "")

    return s


def to_mg_per_L(value: float, unit: str):
    """
    Converte qualquer unidade suportada para mg/L.
    Suporta:
    - mg/L
    - ug/L, µg/L, μg/L
    - mg/l, ug/l, etc.
    """
    if value is None:
        return None

    u = normalize_unit(unit)

    # mg/L → mg/L
    if u in ["mg/l", "mg/l.", "mg"]:
        return value

    # µg/L → mg/L
    if u in ["ug/l", "ug", "µg/l", "μg/l"]:
        return value / 1000.0

    # Caso não reconheça a unidade
    return None


def is_supported_unit(unit: str) -> bool:
    """Retorna True se a unidade é reconhecida pelo sistema."""
    u = normalize_unit(unit)
    return u in ["mg/l", "ug/l", "ug", "µg/l", "μg/l"]
