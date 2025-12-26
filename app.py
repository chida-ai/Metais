# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="operalab_validador_metais", layout="wide")
st.title("operalab_validador_metais")
st.caption("Validador: Metais Dissolvidos vs Totais + QC Ítrio (70–130%) + Comparação de duplicatas (%RPD)")

# ----------------------
# Estado inicial
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
    # Em pt-BR, vírgula é decimal; ponto pode ser milhar
    s_clean = s_clean.replace('.', '')
    s_clean = s_clean.replace(',', '.')
    try:
        v = float(s_clean)
    except ValueError:
        v = None
    return v, cens


def to_mg_per_L(val, unit):
    """Converte para mg/L quando unit é 'mg/L' ou 'µg/L'/'ug/L'. Demais unidades retornam None."""
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
    """Tenta ler texto colado com separador TAB, ponto-e-vírgula, vírgula ou pipe."""
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
# Núcleo: avaliação Dissolvido vs Total + QC Ítrio
# ----------------------

def avaliar(df):
    df = df.copy()
    if 'LQ - Limite Quantificação' not in df.columns:
        df['LQ - Limite Quantificação'] = None

    # Parsing numérico e normalização
    df['Valor_num'], df['Censurado'] = zip(*df['Valor'].map(parse_val))
    df['Valor_mg_L'] = df.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df['Analito_base'] = df['Análise'].map(normalize_analito)

    # Separar dissolvidos e totais (robusto a sufixos como "- ug/L")
    D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
    T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()

    # Ignorar % (Ítrio) na comparação; manter apenas mg/L
    D = D[D['Valor_mg_L'].notna()].copy()
    T = T[T['Valor_mg_L'].notna()].copy()

    # Merge outer para identificar sem par; levar unidade e LQ do Total para a conversão correta
    merged = pd.merge(
        D[['Id','Analito_base','Valor_mg_L','Censurado','Unidade de Medida','LQ - Limite Quantificação']],
        T[['Id','Analito_base','Valor_mg_L','Censurado','Unidade de Medida','LQ - Limite Quantificação']],
        on=['Id','Analito_base'], suffixes=('_diss','_tot'), how='outer'
    )

    out_rows = []
    # Acumuladores globais e por ID
    has_nc_global = False
    has_pot_global = False
    id_has_nc = {}
    id_has_pot = {}

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
                # Total está censurado (<LQ). Comparar Dissolvido com o LQ do Total (convertido pela UNIDADE do Total)
                lq_num, _ = parse_val(r['LQ - Limite Quantificação_tot'])
                lq_unit = r['Unidade de Medida_tot']
                lq_mg = to_mg_per_L(lq_num, lq_unit)
                if lq_mg is None:
                    status = 'INCONCLUSIVO'
                    obs = 'Total <LQ; LQ não informado ou unidade não suportada'
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
            if idv not in id_has_nc:
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

    # QC ÍTRIO (recuperação em %): aceitar 70–130
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
                id_has_nc[r['Id']] = True
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
    ids_encontrados = pd.concat([
        merged['Id'],
        qc_out['Id'] if not qc_out.empty else pd.Series(dtype='object')
    ], axis=0).dropna().unique()

    for idv in ids_encontrados:
        if idv in id_has_nc and id_has_nc[idv]:
            id_status[idv] = 'REPROVADO'
        elif idv in id_has_pot and id_has_pot[idv]:
            id_status[idv] = 'ATENÇÃO'
        else:
            id_status[idv] = 'APROVADO'

    return out_df, qc_out, lote, id_status

# ----------------------
# Comparação de duplicatas (%RPD)
# ----------------------

def rpd(x1, x2):
    """Relative Percent Difference (%): |x1-x2| / ((x1+x2)/2) * 100."""
    if x1 is None or x2 is None:
        return None
    if (x1 + x2) == 0:
        return 0.0
    return abs(x1 - x2) / ((x1 + x2) / 2.0) * 100.0


def preparar_numerico(df):
    """Normaliza valores para mg/L, remove sufixo 'Dissolvido' e retorna DF pronto."""
    df = df.copy()
    df['Valor_num'], df['Censurado'] = zip(*df['Valor'].map(parse_val))
    df['Valor_mg_L'] = df.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df['Analito_base'] = df['Análise'].map(normalize_analito)
    return df


def comparar_duplicatas(df_raw, amostra1, amostra2, tolerancia_pct=20.0):
    """Compara duas amostras (Nº Amostra) e calcula %RPD por método+analito.
    Regras:
    - Ignora entradas em % (ex.: Ítrio).
    - Se ambos censurados (<LQ): status = OK (comparação não aplicável), obs='Ambos <LQ'.
    - Se um censurado e outro quantificado: status = INCONCLUSIVO, obs='Um <LQ'.
    - Se ambos quantificados: RPD calculado; status = Conforme se RPD <= tolerância, caso contrário Não conforme.
    """
    df = preparar_numerico(df_raw)

    # Filtrar amostras selecionadas
    a1 = df[df['Nº Amostra'] == amostra1].copy()
    a2 = df[df['Nº Amostra'] == amostra2].copy()

    # Remover linhas de % (ex.: Ítrio em %)
    a1 = a1[~(a1['Unidade de Medida'].astype(str).str.strip() == '%')]
    a2 = a2[~(a2['Unidade de Medida'].astype(str).str.strip() == '%')]

    # Chave de comparação: Método + Analito_base
    key_cols = ['Método de Análise','Analito_base']
    cols_keep = key_cols + ['Unidade de Medida','Valor_mg_L','Censurado']

    a1 = a1[cols_keep].rename(columns={'Unidade de Medida':'Unidade_1','Valor_mg_L':'Valor_1','Censurado':'Cens_1'})
    a2 = a2[cols_keep].rename(columns={'Unidade de Medida':'Unidade_2','Valor_mg_L':'Valor_2','Censurado':'Cens_2'})

    comp = pd.merge(a1, a2, on=key_cols, how='outer')

    rows = []
    for _, r in comp.iterrows():
        metodo = r['Método de Análise']
        analito = r['Analito_base']
        v1 = r['Valor_1']
        v2 = r['Valor_2']
        c1 = bool(r['Cens_1']) if pd.notna(r['Cens_1']) else False
        c2 = bool(r['Cens_2']) if pd.notna(r['Cens_2']) else False
        unidade = r['Unidade_1'] if pd.notna(r['Unidade_1']) else r['Unidade_2']

        status = ''
        obs = ''
        rpd_pct = None

        if (v1 is None) and (v2 is None):
            status = 'Sem dados'
            obs = 'Valores ausentes'
        elif c1 and c2:
            status = 'OK'
            obs = 'Ambos <LQ'
        elif (c1 and not c2) or (c2 and not c1):
            status = 'INCONCLUSIVO'
            obs = 'Um <LQ'
        else:
            # ambos quantificados
            rpd_pct = rpd(v1, v2)
            if rpd_pct is None:
                status = 'Sem dados'
            else:
                status = 'Conforme' if rpd_pct <= tolerancia_pct else 'Não conforme'

        rows.append({
            'Método de Análise': metodo,
            'Analito': analito,
            'Unidade': unidade,
            f'Valor ({amostra1}) mg/L': v1,
            f'Valor ({amostra2}) mg/L': v2,
            '%RPD': rpd_pct,
            'Status': status,
            'Observação': obs,
        })

    out = pd.DataFrame(rows)
    # Ordena: Não conforme > INCONCLUSIVO > OK/Conforme
    cat = pd.Categorical(out['Status'], categories=['Não conforme','INCONCLUSIVO','OK','Conforme','Sem dados'], ordered=True)
    out['__ord'] = cat
    out = out.sort_values(['__ord','Método de Análise','Analito']).drop(columns='__ord')

    return out

# ----------------------
# UI (Sidebar)
# ----------------------
with st.sidebar:
    st.header("Dados de Entrada")
    file = st.file_uploader("Enviar arquivo (Excel/CSV)", type=["xlsx","xls","csv"]) 
    st.markdown("Ou cole a tabela abaixo (csv/tsv com cabeçalhos):")
    st.session_state["pasted"] = st.text_area("Colar dados", value=st.session_state.get("pasted",""), height=180)

    c1, c2 = st.columns(2)
    with c1:
        btn_avaliar = st.button("Avaliar Lote", type="primary")
    with c2:
        btn_limpar = st.button("Limpar")

    if btn_limpar:
        st.session_state["pasted"] = ""
        st.toast("Área de colagem limpa.")

# Carregar dados de entrada
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

# Pré-visualização
if df_in is not None:
    st.subheader("Pré-visualização dos dados")
    st.dataframe(df_in.head(20), use_container_width=True)

# Avaliação do lote
if btn_avaliar:
    if df_in is None:
        st.error("Informe os dados (arquivo ou colagem) antes de avaliar.")
    else:
        out_df, qc_out, lote, id_status = avaliar(df_in)

        # Status do lote e por ID no sidebar
        with st.sidebar:
            st.header("Status do Lote")
            if lote.startswith('APROVADO'):
                st.success(f"{lote}")
            elif lote.startswith('REPROVADO'):
                st.error(f"{lote}")
            else:
                st.warning(f"{lote}")

            st.subheader("Status por ID")
            # Ordena IDs por gravidade: REPROVADO > ATENÇÃO > APROVADO
            order_map = {'REPROVADO':0,'ATENÇÃO':1,'APROVADO':2}
            for idv, stid in sorted(id_status.items(), key=lambda x: (order_map.get(x[1],9), x[0])):
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

# ----------------------
# Comparação de duplicatas (UI)
# ----------------------
if df_in is not None:
    st.divider()
    st.subheader("Comparação de duplicatas (%RPD)")
    st.markdown("Selecione **duas amostras** (campo 'Nº Amostra') e defina a **tolerância** em %.")

    amostras = sorted(df_in['Nº Amostra'].dropna().astype(str).unique()) if 'Nº Amostra' in df_in.columns else []
    col_dup = st.columns(3)
    with col_dup[0]:
        am1 = st.selectbox("Amostra 1", options=amostras, index=0 if amostras else None)
    with col_dup[1]:
        am2 = st.selectbox("Amostra 2", options=amostras, index=1 if len(amostras)>1 else None)
    with col_dup[2]:
        tol = st.number_input("Tolerância (%RPD)", min_value=0.0, max_value=100.0, value=20.0, step=1.0)

    btn_comp = st.button("Comparar duplicatas", type="secondary")

    if btn_comp:
        if not amostras or am1 is None or am2 is None:
            st.error("Dados insuficientes ou amostras não selecionadas.")
        elif am1 == am2:
            st.warning("Selecione amostras diferentes para comparação.")
        else:
            res_dup = comparar_duplicatas(df_in, am1, am2, tolerancia_pct=tol)
            st.dataframe(res_dup, use_container_width=True)

            # Resumo
            n_nc = (res_dup['Status'] == 'Não conforme').sum()
            n_ok = ((res_dup['Status'] == 'Conforme') | (res_dup['Status'] == 'OK')).sum()
            n_inc = (res_dup['Status'] == 'INCONCLUSIVO').sum()
            st.caption(f"Resumo: Não conformes = {n_nc} | Conforme/OK = {n_ok} | Inconclusivos = {n_inc}")

            # Download
            csv_dup = res_dup.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar comparação de duplicatas (CSV)", csv_dup, file_name="comparacao_duplicatas.csv", mime="text/csv")

# Rodapé
st.caption("© {} | operalab_validador_metais".format(pd.Timestamp.now().year))
