# app.py (OPERA LAB – Analyst Support, versão segura e ASCII-safe)
import json
from pathlib import Path
import pandas as pd
import streamlit as st

# =============================
# 1) Configuração da página
# =============================
st.set_page_config(
    page_title="OPERA LAB – Analyst Support",
    page_icon="🧪",
    layout="wide",
)

# =============================
# 2) Utilitários seguros
# =============================

def safe_error(msg, exc=None):
    """Apresenta erro no front sem quebrar renderização."""
    if exc:
        st.error(f"{msg}: {exc}")
    else:
        st.error(msg)


def load_json_safe(path: Path):
    """Lê JSON com tratamento de erros e retorna dict vazio em falha."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        safe_error(f"Arquivo não encontrado: {path}", e)
    except json.JSONDecodeError as e:
        safe_error(f"JSON inválido em {path}", e)
    except Exception as e:
        safe_error(f"Falha ao ler {path}", e)
    return {}


@st.cache_data(show_spinner=False)
def load_catalogo(path: Path):
    data = load_json_safe(path)
    if isinstance(data, dict) and "normas" in data and isinstance(data["normas"], list):
        return data
    if data:
        safe_error("Estrutura do catalogo_especificacoes.json não possui chave 'normas' (lista).")
    return {"normas": []}


def filtrar_normas_por_matriz(catalogo_dict, matriz_sel):
    normas = catalogo_dict.get("normas", [])
    # Espera: cada norma com campos: nome, codigo, aplicavel_matrizes (lista), itens (lista)
    return [n for n in normas if matriz_sel in n.get("aplicavel_matrizes", [])]


def calc_rpd(v1: float, v2: float) -> float:
    """Calcula %RPD com proteção para soma zero."""
    denom = (v1 + v2) / 2.0
    if denom == 0:
        return 0.0
    return abs(v1 - v2) / denom * 100.0


def calc_U(u: float, k: float) -> float:
    """Incerteza expandida U = k * u."""
    return k * u


# =============================
# 3) Sidebar e navegação
# =============================
with st.sidebar:
    st.header("OPERA LAB")
    st.caption("Analyst Support")
    # Matrizes conforme preferência do Alexandre: A, AS, ASub, EFL, S
    matriz = st.selectbox("Matriz do lote", ["A", "AS", "ASub", "EFL", "S"], index=0)
    st.divider()
    st.write("Seções")
    go_normas = st.button("Legislação/Especificação")
    go_icp = st.button("Decisão ICP")
    go_diss_tot = st.button("Dissolvidos vs Totais + QC Ítrio")
    go_dup = st.button("Duplicatas (%RPD)")
    go_cal = st.button("Calibração semanal")

# =============================
# 4) Cabeçalho
# =============================
st.title("OPERA LAB – Analyst Support")
st.caption(f"Matriz selecionada: {matriz}")

# =============================
# 5) Carregar catálogo
# =============================
CATALOGO_PATH = Path("catalogo_especificacoes.json")
catalogo = load_catalogo(CATALOGO_PATH)

# =============================
# 6) Seções
# =============================

def sec_legislacao():
    st.subheader("Legislação/Especificação")
    normas = filtrar_normas_por_matriz(catalogo, matriz)
    if not normas:
        st.info("Nenhuma norma aplicável encontrada para esta matriz. Verifique o JSON.")
        st.code(
            """
Estrutura esperada por norma:
{
  "nome": "Portaria GM/MS 888/2021",
  "codigo": "GM/MS 888/2021",
  "aplicavel_matrizes": ["A"],
  "itens": [
    {"analisito": "Pb", "limite": 10, "unidade": "µg/L", "tipo": "potabilidade"}
  ]
}
            """
        )
        return
    for n in normas:
        with st.expander(f"{n.get('nome','(sem nome)')} — {n.get('codigo','')}", expanded=False):
            df = pd.DataFrame(n.get("itens", []))
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("Norma sem itens preenchidos.")


def sec_decisao_icp():
    st.subheader("Decisão ICP")
    st.caption("Cálculo de U (incerteza expandida), RSD, recuperação (spike), checklist, gráfico e log CSV.")
    col1, col2 = st.columns(2)
    with col1:
        u = st.number_input("Incerteza padrão (u)", min_value=0.0, value=0.5, step=0.01)
        k = st.number_input("Fator de cobertura (k)", min_value=1.0, value=2.0, step=0.5)
        rsd = st.number_input("RSD (%)", min_value=0.0, value=3.0, step=0.1)
        rec = st.number_input("Recuperação (%)", min_value=0.0, value=95.0, step=0.1)
    with col2:
        usar_catalogo = st.checkbox("Usar limites do catálogo", value=True)
        limite_manual = st.text_input("Limite manual (opcional)", value="")
        st.write("Incerteza expandida U:", f"{calc_U(u, k):.3f}")
        st.write("RSD informado:", f"{rsd:.2f}%")
        st.write("Recuperação informada:", f"{rec:.2f}%")
    st.info("Implemente aqui os cálculos detalhados e gráficos. Use st.download_button para exportar CSV do log.")


def sec_dissolvidos_totais():
    st.subheader("Dissolvidos vs Totais + QC Ítrio")
    st.caption("Avaliação comparativa e controle de qualidade (Ítrio).")
    st.info("Placeholders. Faça upload dos dados do lote e compare dissolvidos vs totais. Inserir regra do QC Ítrio.")


def sec_duplicatas():
    st.subheader("Duplicatas (%RPD)")
    st.caption("Cálculo do %RPD para amostras duplicatas.")
    v1 = st.number_input("Valor A", min_value=0.0, value=10.0)
    v2 = st.number_input("Valor B", min_value=0.0, value=12.0)
    if v1 == 0 and v2 == 0:
        st.warning("Valores ambos zero — RPD indefinido.")
    else:
        rpd = calc_rpd(v1, v2)
        st.metric("%RPD", f"{rpd:.2f}%")


def sec_calibracao():
    st.subheader("Calibração semanal")
    st.caption("Roteiro e validação em lote.")
    st.write("- Preparar padrões, verificar linearidade, ajustar curva, validar em lote.")
    st.info("Adicione checklist e upload de arquivos para validar automaticamente.")

# =============================
# 7) Render com navegação
# =============================
try:
    if go_normas:
        sec_legislacao()
    elif go_icp:
        sec_decisao_icp()
    elif go_diss_tot:
        sec_dissolvidos_totais()
    elif go_dup:
        sec_duplicatas()
    elif go_cal:
        sec_calibracao()
    else:
        st.success("Selecione uma seção na barra lateral para começar.")
        sec_legislacao()
except Exception as e:
    safe_error("Falha na renderização de seção", e)

# =============================
# 8) CSS leve e seguro (opcional)
# =============================
st.markdown(
    """
<style>
:root { --accent: #00A3FF; }
.block-container { padding-top: 1.1rem; }
</style>
    """,
    unsafe_allow_html=True,
)
