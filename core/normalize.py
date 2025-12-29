# core/normalize.py
# Normalização robusta de nomes de analitos para uso em:
# - Dissolvido vs Total
# - QC Ítrio
# - Duplicatas
# - Legislação / especificações

import unicodedata
import re
import pandas as pd


def strip_accents(s: str) -> str:
    """Remove acentos preservando caracteres ASCII."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c))


def normalize_analito(name: str) -> str:
    """
    Normaliza nomes de analitos sem destruir informações essenciais.
    Mantém:
        - 'total'
        - 'dissolvido'
        - 'hexavalente'
        - 'trivalente'
    Remove:
        - acentos
        - espaços duplicados
    """
    if name is None or pd.isna(name):
        return ""

    s = strip_accents(name).strip().lower()

    # Remove espaços duplicados
    s = re.sub(r"\s+", " ", s)

    # Mantém total/dissolvido (não remover!)
    # Exemplo: "chumbo total", "chumbo dissolvido"

    return s


# -----------------------------
# Aliases para legislação
# -----------------------------

ALIASES = {
    # Cromo
    "cromo": "cromo total",
    "cromio": "cromo total",
    "cromio total": "cromo total",
    "cr+6": "cromo hexavalente",
    "cr6": "cromo hexavalente",
    "cr vi": "cromo hexavalente",
    "crvi": "cromo hexavalente",
    "cr 6": "cromo hexavalente",
    "cr iii": "cromo trivalente",
    "cr3+": "cromo trivalente",

    # Ítrio
    "itrio": "itrio",
    "itrio total": "itrio total",

    # Metais comuns
    "chumbo": "chumbo total",
    "pb": "chumbo total",
    "arsenio": "arsenio total",
    "cadmio": "cadmio total",
    "mercurio": "mercurio total",
}


def apply_alias(name: str) -> str:
    """
    Aplica alias após normalização.
    """
    if not name:
        return ""
    n = normalize_analito(name)
    return ALIASES.get(n, n)
