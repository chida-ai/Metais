
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="operalab_validador_metais", layout="wide")
st.title("operalab_validador_metais")
st.caption("Validador: Metais Dissolvidos vs Totais + QC Ítrio (70–130%)")

# ----------------------
# Estado inicial (para colagem)
# ----------------------
if "pasted" not in st.session_state:
    st.session_state["pasted"] = ""

# ----------------------
# Funções auxiliares
# ----------------------
def parse_val(val_str):
    """Retorna (valor_float, censurado_bool) a partir de strings como '0,009' ou '< 0,006'."""
    if pd.isna(val_str):
        return None, False
    s = str(val_str).strip()
    cens = s.startswith('<')
    s_clean = s.replace('<','').strip()
    s_clean = s_clean.replace('.', '')
    s_clean = s_clean.replace(',', '.')
    try:
        v = float(s_clean)
    except ValueError:
        v = None
    return v, cens

def to_mg_per_L(val, unit):
    """Converte para mg/L quando unit é 'mg/L' ou 'µg/L'. Demais unidades retornam None."""
    if val is None or pd.isna(unit):
        return None
    u = str(unit).strip().lower()
    if u == 'mg/l':
        return val
    if u in ['µg/l','ug/l']:
        return val/1000.0
    return None

def normalize_analito(name):
    if pd.isna(name):
        return None
    s = str(name).strip()
    s = re.sub(r"\s+Dissolvido$", "", s, flags=re.IGNORECASE)
    return s

def try_read_pasted(text):
    seps = ['\t', ';', ',', '|']
    for sep in seps:
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if len(df.columns) >= 6:
                return df
        except Exception:
            pass
    return None

# ----------------------
# Avaliação (retorna por lote e por ID)
# ----------------------
def avaliar(df):
    df = df.copy()
    if 'LQ - Limite Quantificação' not in df.columns:
        df['LQ - Limite Quantificação'] = None

    # Parsing numérico e normalização
    df['Valor_num'], df['Censurado'] = zip(*df['Valor'].map(parse_val))
    df['Valor_mg_L'] = df.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df['Analito_base'] = df['Análise'].map(normalize_analito)

    # Separar dissolvidos e totais
    D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
    T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()

    # Ignorar % (mantém só mg/L)
    D = D[D['Valor_mg_L'].notna()].copy()
    T = T[T['Valor_mg_L'].notna()].copy()

    # Merge outer
    merged = pd.merge(
        D[['Id','Analito_base','Valor_mg_L','Censurado','LQ - Limite Quantificação']],
        T[['Id','Analito_base','Valor_mg_L','Censurado','LQ - Limite Quantificação']],
        on=['Id','Analito_base'], suffixes=('_diss','_tot'), how='outer'
    )

    out_rows = []
    # Acumuladores globais
    has_nc_global = False
    has_pot_global = False

    # Acumuladores por ID
    id_has_nc = {}   # True se ID tem N.C.
    id_has_pot = {}  # True se ID tem potencial N.C.

    for _, r in merged.iterrows():
        idv = r['Id']
        analito = r['Analito_base']
        d_val = r['Valor_mg_L_diss']
        t_val = r['Valor_mg_L_tot']
        d_cens = bool(r['Censurado_diss']) if pd.notna(r['Censurado_diss']) else False
        t_cens = bool(r['Censurado_tot']) if pd.notna(r['Censurado_tot']) else False

        status = ''
        obs = ''

        if pd.isna(d_val) and pd.isna(t_val):
            status = 'Sem dados válidos'
            obs = 'Unidade não suportada ou valor ausente'
        elif pd.isna(d_val) and pd.notna(t_val):
            status = 'Sem par para comparação'
            obs = 'Apenas Total disponível'
        elif pd.notna(d_val) and pd.isna(t_val):
            status = 'Sem par para comparação'
            obs = 'Apenas Dissolvido disponível'
        else:
            if not d_cens and not t_cens:
                status = 'NÃO CONFORME' if d_val > t_val else 'OK'
            elif not d_cens and t_cens:
                lq_tot = r['LQ - Limite Quantificação_tot']
                lq_num, _ = parse_val(lq_tot)
                lq_mg = lq_num if lq_num is not None else None
                if lq_mg is None:
                    status = 'INCONCLUSIVO'
                    obs = 'Total <LQ; LQ não informado'
                else:
                    status = 'POTENCIAL NÃO CONFORME' if d_val > lq_mg else 'OK'
            elif d_cens and not t_cens:
                status = 'OK' if (d_val is None or d_val <= t_val) else 'INCONCLUSIVO'
                obs = 'Dissolvido <LQ'
            else:
                status = 'OK'
                obs = 'Ambos <LQ'

        # Atualiza flags globais e por ID
        if status == 'NÃO CONFORME':
            has_nc_global = True
            id_has_nc[idv] = True
        elif status == 'POTENCIAL NÃO CONFORME':
            has_pot_global = True
            if idv not in id_has_nc:  # só marca potencial se ainda não N.C.
                id_has_pot[idv] = True

        out_rows.append({
            'Id': idv,
            'Analito': analito,
            'Dissolvido (mg/L)': d_val,
            'Total (mg/L)': t_val,
            'Dissolvido é <LQ?': 'Sim' if d_cens else 'Não',
            'Total é <LQ?': 'Sim' if t_cens else 'Não',
            'Status': status,
            'Observação': obs,
        })

    out_df = pd.DataFrame(out_rows)

    # QC ÍTRIO: unidade '%' (recuperação 70–130)
    qc_df = df.copy()
    qc_df['analise_lower'] = qc_df['Análise'].str.lower()
    mask_itrio = qc_df['analise_lower'].str.contains('ítrio') | qc_df['analise_lower'].str.contains('itrio')
    mask_pct = qc_df['Unidade de Medida'].astype(str).str.strip() == '%'
    qc_df = qc_df[mask_itrio & mask_pct].copy()

    qc_rows = []
    for _, r in qc_df.iterrows():
        rec_num, _ = parse_val(r['Valor'])
        status = 'OK'
        obs = ''
        if rec_num is None:
            status = 'Sem dado'
            obs = 'Valor de recuperação ausente ou inválido'
        else:
            if rec_num < 70.0 or rec_num > 130.0:
                status = 'NÃO CONFORME'
                obs = 'Recuperação fora de 70–130%'
                has_nc_global = True
                id_has_nc[r['Id']] = True  # reprova o ID na QC
            else:
                status = 'OK'
                obs = 'Recuperação dentro de 70–130%'
        qc_rows.append({
            'Id': r['Id'],
            'Nº Amostra': r['Nº Amostra'],
            'Método de Análise': r['Método de Análise'],
            'Análise': r['Análise'],
            'Recuperação (%)': rec_num,
            'Status': status,
            'Observação': obs,
        })
    qc_out = pd.DataFrame(qc_rows)

    # Status global do lote
    if has_nc_global:
        lote = 'REPROVADO'
    elif has_pot_global:
        lote = 'ATENÇÃO (potenciais não conformidades)'
    else:
        lote = 'APROVADO'

    # Status por ID: REPROVADO > ATENÇÃO > APROVADO
    id_status = {}
    ids_encontrados = pd.concat([merged['Id'], qc_out.get('Id', pd.Series(dtype='object'))], axis=0).dropna().unique()
    for idv in ids_encontrados:
        if idv in id_has_nc and id_has_nc[idv]:
            id_status[idv] = 'REPROVADO'
        elif idv in id_has_pot and id_has_pot[idv]:
            id_status[idv] = 'ATENÇÃO'
        else:
            id_status[idv] = 'APROVADO'

    return out_df, qc_out, lote, id_status

# ----------------------
# UI (Sidebar com limpar + status por ID)
# ----------------------
with st.sidebar:
    st.header("Dados de Entrada")

    file = st.file_uploader("Enviar arquivo (Excel/CSV)", type=["xlsx","xls","csv"])
    st.markdown("Ou cole a tabela abaixo (csv/tsv com cabeçalhos):")

    # Text area vinculado ao session_state para permitir 'Limpar'
    st.session_state["pasted"] = st.text_area("Colar dados", value=st.session_state.get("pasted",""), height=180)

    col_btn = st.columns(2)
    with col_btn[0]:
        btn_avaliar = st.button("Avaliar Lote", type="primary")
    with col_btn[1]:
        btn_limpar = st.button("Limpar")

    # Limpar conteúdo colado
    if btn_limpar:
        st.session_state["pasted"] = ""
        st.toast("Área de colagem limpa.")

# Carregar dados
df_in = None
if file is not None:
    try:
        if file.name.lower().endswith('.csv'):
            df_in = pd.read_csv(file)
        else:
            df_in = pd.read_excel(file, sheet_name=0, engine='openpyxl')
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
elif st.session_state["pasted"]:
    df_in = try_read_pasted(st.session_state["pasted"])
    if df_in is None:
        st.error("Não consegui interpretar o texto colado. Tente usar separador ';' ou TAB.")

# Preview
if df_in is not None:
    st.subheader("Pré-visualização dos dados")
    st.dataframe(df_in.head(20), use_container_width=True)

# Avaliação
if btn_avaliar:
    if df_in is None:
        st.error("Informe os dados (arquivo ou colagem) antes de avaliar.")
    else:
        out_df, qc_out, lote, id_status = avaliar(df_in)

        # Status do lote na sidebar (com IDs e seus status)
        with st.sidebar:
            st.header("Status do Lote")
            if lote.startswith('APROVADO'):
                st.success(f"{lote}")
            elif lote.startswith('REPROVADO'):
                st.error(f"{lote}")
            else:
                st.warning(f"{lote}")

            st.subheader("Status por ID")
            # Lista os IDs encontrados
            for idv, stid in sorted(id_status.items(), key=lambda x: (x[1], x[0])):
                if stid == "REPROVADO":
                    st.error(f"ID {idv}: {stid}")
                elif stid == "ATENÇÃO":
                    st.warning(f"ID {idv}: {stid}")
                else:
                    st.success(f"ID {idv}: {stid}")

        # Tabelas de saída
        st.subheader("Resultado - Comparação Dissolvido vs Total")
        st.dataframe(out_df, use_container_width=True)

        st.subheader("QC Ítrio (Recuperação 70–130%)")
        if qc_out.empty:
            st.info("Nenhuma linha de Ítrio em % encontrada.")
        else:
            st.dataframe(qc_out, use_container_width=True)

        # Exportar
        st.divider()
        st.subheader("Exportar")
        csv_out = out_df.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar Resultado (CSV)", csv_out, file_name="resultado_comparacao.csv", mime="text/csv")
        if not qc_out.empty:
            csv_qc = qc_out.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar QC Ítrio (CSV)", csv_qc, file_name="qc_itrio.csv", mime="text/csv")

st.caption("© {} | operalab_validador_metais".format(pd.Timestamp.now().year))
