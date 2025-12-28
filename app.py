# app.py (OPERA LAB – Analyst Support)
import json
from pathlib import Path
import io
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
    if exc:
        st.error(f"{msg}: {exc}")
    else:
        st.error(msg)


def load_json_safe(path: Path):
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
    return [n for n in normas if matriz_sel in n.get("aplicavel_matrizes", [])]


def calc_rpd(v1: float, v2: float) -> float:
    denom = (v1 + v2) / 2.0
    if denom == 0:
        return 0.0
    return abs(v1 - v2) / denom * 100.0


def calc_U(u: float, k: float) -> float:
    return k * u


# =============================
# 3) Estado de navegação persistente
# =============================
PAGES = {
    "Legislação/Especificação": "normas",
    "Decisão ICP": "icp",
    "Dissolvidos vs Totais + QC Ítrio": "diss_tot",
    "Duplicatas (%RPD)": "duplicatas",
    "Calibração semanal": "calibracao",
}

if "page" not in st.session_state:
    st.session_state.page = "normas"  # página inicial

# =============================
# 4) Sidebar e navegação
# =============================
with st.sidebar:
    st.header("OPERA LAB")
    st.caption("Analyst Support")
    matriz = st.selectbox("Matriz do lote", ["A", "AS", "ASub", "EFL", "S"], index=0)
    st.divider()
    st.write("Seções")
    # Botões que atualizam session_state.page
    if st.button("Legislação/Especificação"):
        st.session_state.page = "normas"
    if st.button("Decisão ICP"):
        st.session_state.page = "icp"
    if st.button("Dissolvidos vs Totais + QC Ítrio"):
        st.session_state.page = "diss_tot"
    if st.button("Duplicatas (%RPD)"):
        st.session_state.page = "duplicatas"
    if st.button("Calibração semanal"):
        st.session_state.page = "calibracao"

# =============================
# 5) Cabeçalho
# =============================
st.title("OPERA LAB – Analyst Support")
st.caption(f"Matriz selecionada: {matriz}")

# =============================
# 6) Dados e catálogo
# =============================
CATALOGO_PATH = Path("catalogo_especificacoes.json")
catalogo = load_catalogo(CATALOGO_PATH)

# Upload opcional de dados do lote (CSV/XLSX)
with st.expander("Dados do lote (upload opcional)", expanded=False):
    up = st.file_uploader("CSV ou XLSX", type=["csv", "xlsx"])
    df_lote = None
    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                df_lote = pd.read_csv(up)
            else:
                df_lote = pd.read_excel(up, engine="openpyxl")
            st.success(f"Arquivo carregado: {up.name}")
            st.dataframe(df_lote.head(50), use_container_width=True)
        except Exception as e:
            safe_error("Falha ao ler dados do lote", e)

# =============================
# 7) Seções
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
        st.metric("Incerteza expandida U", f"{calc_U(u, k):.3f}")
        st.metric("RSD", f"{rsd:.2f}%")
        st.metric("Recuperação", f"{rec:.2f}%")

    # Log simples (em memória) e export
    log_rows = [
        {"u": u, "k": k, "U": calc_U(u, k), "RSD(%)": rsd, "Rec(%)": rec, "matriz": matriz}
    ]
    log_df = pd.DataFrame(log_rows)
    st.dataframe(log_df, use_container_width=True)
    csv_bytes = log_df.to_csv(index=False).encode("utf-8")
    st.download_button("Exportar log CSV", data=csv_bytes, file_name="log_icp.csv", mime="text/csv")


def sec_dissolvidos_totais():
    st.subheader("Dissolvidos vs Totais + QC Ítrio")
    st.caption("Comparação e controle de qualidade (Ítrio). Use dados do lote para análise.")
    st.info("Exemplo: informe pares de resultados para o mesmo analito (Dissolvido vs Total).")
    colA, colB = st.columns(2)
    with colA:
        vd = st.number_input("Valor Dissolvido", min_value=0.0, value=10.0)
    with colB:
        vt = st.number_input("Valor Total", min_value=0.0, value=12.0)
    if vt == 0:
        st.warning("Valor Total zero — razão D/T indefinida.")
    else:
        razao = vd / vt
        st.metric("Razão Dissolvido/Total", f"{razao:.3f}")
    st.info("QC Ítrio: implemente aqui critério específico do seu método (placeholder).")


def sec_duplicatas():
    st.subheader("Duplicatas (%RPD)")
    st.caption("Cálculo do %RPD para amostras duplicatas.")
    v1 = st.number_input("Valor A", min_value=0.0, value=10.0)
    v2 = st.number_input("Valor B", min_value=0.0, value=12.0)
    rpd = calc_rpd(v1, v2)
    st.metric("%RPD", f"{rpd:.2f}%")
    st.info("Regra típica: aceitar se %RPD <= 20% (ajuste conforme seu método).")


def sec_calibracao():
    st.subheader("Calibração semanal")
    st.caption("Roteiro e validação em lote.")
    st.write("- Preparar padrões, verificar linearidade (R²), faixa, pontos e resíduos.")
    st.write("- Validar em lote: critérios de recuperação, RSD, branco, controle.")
    # Placeholder: upload de resultados de calibração
    up_cal = st.file_uploader("Curva de calibração (CSV)", type=["csv"], key="up_cal")
    if up_cal is not None:
        try:
            dfc = pd.read_csv(up_cal)
            st.dataframe(dfc, use_container_width=True)
            st.success("Curva carregada — implemente aqui validação (linearidade, resíduos, faixa).")
        except Exception as e:
            safe_error("Falha ao ler curva de calibração", e)

# =============================
# 8) Router de páginas
# =============================
try:
    page = st.session_state.page
    if page == "normas":
        sec_legislacao()
    elif page == "icp":
        sec_decisao_icp()
    elif page == "diss_tot":
        sec_dissolvidos_totais()
    elif page == "duplicatas":
        sec_duplicatas()
    elif page == "calibracao":
        sec_calibracao()
    else:
        st.warning("Página desconhecida. Voltando para Legislação.")
        st.session_state.page = "normas"
        sec_legislacao()
except Exception as e:
    safe_error("Falha na renderização de seção", e)

# =============================
# 9) CSS leve e seguro
# =============================
st.markdown(
    """
<style>
:root { --accent: #00A3FF; }
.block-container { padding-top: 1.0rem; }
</style>
    """,
    unsafe_allow_html=True,
)
