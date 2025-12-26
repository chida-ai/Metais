# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="operalab_validador_metais", layout="wide")
st.title("operalab_validador_metais")
st.caption("Validador: Metais Dissolvidos vs Totais + QC Ítrio (70–130%)")

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

REQUIRED_COLS = ['Id','Nº Amostra','Método de Análise','Análise','Valor','Unidade de Medida']


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


def avaliar(df):
    df = df.copy()
    if 'LQ - Limite Quantificação' not in df.columns:
        df['LQ - Limite Quantificação'] = None

    df['Valor_num'], df['Censurado'] = zip(*df['Valor'].map(parse_val))
    df['Valor_mg_L'] = df.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df['Analito_base'] = df['Análise'].map(normalize_analito)

    D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
    T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()

    D = D[D['Valor_mg_L'].notna()].copy()
    T = T[T['Valor_mg_L'].notna()].copy()

    merged = pd.merge(
        D[['Id','Analito_base','Valor_mg_L','Censurado','LQ - Limite Quantificação']],
        T[['Id','Analito_base','Valor_mg_L','Censurado','LQ - Limite Quantificação']],
        on=['Id','Analito_base'], suffixes=('_diss','_tot'), how='outer'
    )

    out_rows = []
    nao_conformes = []
    potenciais = []
    sem_par = []

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
            sem_par.append((idv, analito, 'Sem dados válidos'))
        elif pd.isna(d_val) and pd.notna(t_val):
            status = 'Sem par para comparação'
            obs = 'Apenas Total disponível'
            sem_par.append((idv, analito, 'Apenas Total'))
        elif pd.notna(d_val) and pd.isna(t_val):
            status = 'Sem par para comparação'
            obs = 'Apenas Dissolvido disponível'
            sem_par.append((idv, analito, 'Apenas Dissolvido'))
        else:
            if not d_cens and not t_cens:
                status = 'NÃO CONFORME' if d_val > t_val else 'OK'
                if d_val > t_val:
                    nao_conformes.append((idv, analito, d_val, t_val, 'Dissolvido > Total'))
            elif not d_cens and t_cens:
                lq_tot = r['LQ - Limite Quantificação_tot']
                lq_num, _ = parse_val(lq_tot)
                lq_mg = lq_num if lq_num is not None else None
                if lq_mg is None:
                    status = 'INCONCLUSIVO'
                    obs = 'Total <LQ; LQ não informado'
                else:
                    status = 'POTENCIAL NÃO CONFORME' if d_val > lq_mg else 'OK'
                    if d_val > lq_mg:
                        potenciais.append((idv, analito, d_val, lq_mg, 'Dissolvido > LQ do Total'))
            elif d_cens and not t_cens:
                status = 'OK' if (d_val is None or d_val <= t_val) else 'INCONCLUSIVO'
                obs = 'Dissolvido <LQ'
            else:
                status = 'OK'
                obs = 'Ambos <LQ'

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

    # QC ÍTRIO: unidade '%', aceitar 70–130
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

    has_nc = (out_df['Status'] == 'NÃO CONFORME').any() or (qc_out['Status'] == 'NÃO CONFORME').any()
    has_pot = (out_df['Status'] == 'POTENCIAL NÃO CONFORME').any()

    if has_nc:
        lote = 'REPROVADO'
    elif has_pot:
        lote = 'ATENÇÃO (potenciais não conformidades)'
    else:
        lote = 'APROVADO'

    return out_df, qc_out, lote

# ----------------------
# UI
# ----------------------
with st.sidebar:
    st.header("Dados de Entrada")
    file = st.file_uploader("Enviar arquivo (Excel/CSV)", type=["xlsx","xls","csv"]) 
    st.markdown("Ou cole a tabela abaixo (csv/tsv com cabeçalhos):")
    pasted = st.text_area("Colar dados", height=180)
    btn = st.button("Avaliar Lote", type="primary")

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
elif pasted:
    df_in = try_read_pasted(pasted)
    if df_in is None:
        st.error("Não consegui interpretar o texto colado. Tente usar separador ';' ou TAB.")

if df_in is not None:
    st.subheader("Pré-visualização dos dados")
    st.dataframe(df_in.head(20), use_container_width=True)

if btn:
    if df_in is None:
        st.error("Informe os dados (arquivo ou colagem) antes de avaliar.")
    else:
        out_df, qc_out, lote = avaliar(df_in)

        if lote.startswith('APROVADO'):
            st.success(f"Status do Lote: {lote}")
        elif lote.startswith('REPROVADO'):
            st.error(f"Status do Lote: {lote}")
        else:
            st.warning(f"Status do Lote: {lote}")

        st.subheader("Resultado - Comparação Dissolvido vs Total")
        st.dataframe(out_df, use_container_width=True)

        st.subheader("QC Ítrio (Recuperação 70–130%)")
        if qc_out.empty:
            st.info("Nenhuma linha de Ítrio em % encontrada.")
        else:
            st.dataframe(qc_out, use_container_width=True)

        st.divider()
        st.subheader("Exportar")
        csv_out = out_df.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar Resultado (CSV)", csv_out, file_name="resultado_comparacao.csv", mime="text/csv")
        if not qc_out.empty:
            csv_qc = qc_out.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar QC Ítrio (CSV)", csv_qc, file_name="qc_itrio.csv", mime="text/csv")

st.caption("© {} | operalab_validador_metais".format(pd.Timestamp.now().year))
