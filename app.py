# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io, re, json
from pathlib import Path

# =========================
# Config da página
# =========================
st.set_page_config(page_title="OPERA LAB - Analyst Support", layout="wide")

# =========================
# Cabeçalho compacto (sem logo)
# =========================
st.markdown(
    """
    <div style="display:flex;align-items:center;gap:8px;">
      <h1 style="margin:0;font-size:26px;line-height:1.05;">OPERA LAB - Analyst Support</h1>
    </div>
    <div style="height:2px;background:#00A3FF;border-radius:2px;margin-top:4px;"></div>
    <div style="margin-top:2px;opacity:0.85;font-size:14px;">
      Dissolvidos vs Totais • QC Ítrio • Duplicatas (%RPD) • Pré-avaliação por legislação/especificação • Decisão ICP • Calibração
    </div>
    """,
    unsafe_allow_html=True
)

# =========================
# Estado
# =========================
if "pasted" not in st.session_state:
    st.session_state["pasted"] = ""
if "spec_key" not in st.session_state:
    st.session_state["spec_key"] = None
if "matriz_lote" not in st.session_state:
    st.session_state["matriz_lote"] = "A"  # default água potável

# =========================
# Auxiliares (parse/normalização)
# =========================
def parse_val(val_str):
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

# =========================
# Catálogo de especificações (JSON externo)
# =========================
CAT_PATH = 'catalogo_especificacoes.json'

@st.cache_data(show_spinner=False)
def load_catalog():
    try:
        with open(CAT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

catalog = load_catalog()

ALIASES = {
    'Cromo': 'Crômio total',
    'Crômio': 'Crômio total',
    'Crômio total': 'Crômio total',
    'Cr+6': 'Crômio hexavalente',
    'Cr VI': 'Crômio hexavalente',
    'Cr3+': 'Crômio trivalente',
    'Chromium': 'Crômio total',
    'Pb': 'Chumbo',
    'Cd': 'Cádmio',
    'Ni': 'Níquel',
    'Hg': 'Mercúrio',
    'As': 'Arsênio'
}

# =========================
# Núcleo: Avaliar Dissolvidos vs Totais + QC Ítrio
# =========================

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
        D[['Id','Analito_base','Valor_mg_L','Censurado','Unidade de Medida','LQ - Limite Quantificação']],
        T[['Id','Analito_base','Valor_mg_L','Censurado','Unidade de Medida','LQ - Limite Quantificação']],
        on=['Id','Analito_base'], suffixes=('_diss','_tot'), how='outer'
    )

    out_rows = []
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

    # QC Ítrio % 70-130
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

    if has_nc_global:
        lote = 'REPROVADO'
    elif has_pot_global:
        lote = 'ATENÇÃO (potenciais não conformidades)'
    else:
        lote = 'APROVADO'

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

    return out_df, qc_out, lote, id_status, df

# =========================
# Duplicatas (%RPD)
# =========================

def rpd(x1, x2):
    if x1 is None or x2 is None:
        return None
    if (x1 + x2) == 0:
        return 0.0
    return abs(x1 - x2) / ((x1 + x2) / 2.0) * 100.0


def preparar_numerico(df):
    df = df.copy()
    df['Valor_num'], df['Censurado'] = zip(*df['Valor'].map(parse_val))
    df['Valor_mg_L'] = df.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
    df['Analito_base'] = df['Análise'].map(normalize_analito)
    return df


def comparar_duplicatas(df_raw, amostra1, amostra2, tolerancia_pct=20.0):
    df = preparar_numerico(df_raw)
    a1 = df[df['Nº Amostra'] == amostra1].copy()
    a2 = df[df['Nº Amostra'] == amostra2].copy()
    a1 = a1[~(a1['Unidade de Medida'].astype(str).str.strip() == '%')]
    a2 = a2[~(a2['Unidade de Medida'].astype(str).str.strip() == '%')]
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
            rpd_pct = rpd(v1, v2)
            status = 'Conforme' if (rpd_pct is not None and rpd_pct <= tolerancia_pct) else 'Não conforme'
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
    cat = pd.Categorical(out['Status'], categories=['Não conforme','INCONCLUSIVO','OK','Conforme','Sem dados'], ordered=True)
    out['__ord'] = cat
    out = out.sort_values(['__ord','Método de Análise','Analito']).drop(columns='__ord')
    return out

# =========================
# Pré-avaliação por especificação (tabelas com cor)
# =========================

def style_status(df):
    def color_row(s):
        c = 'white'
        bg = '#222'
        if s.get('Status') == 'Não conforme':
            bg = '#FF3B30'
        elif s.get('Status') in ('Conforme','OK'):
            bg = '#34C759'
        elif s.get('Status') == 'INCONCLUSIVO':
            bg = '#FFCC00'
        return [f'background-color: {bg}; color: {c}' for _ in s]
    return df.style.apply(color_row, axis=1)


def aplicar_especificacao(df_num, spec_key):
    spec = catalog.get(spec_key)
    if not spec:
        return pd.DataFrame(), pd.DataFrame()
    limites = spec.get('limits_mgL', {})
    usar_totais = spec.get('prefer_total', True)
    df = df_num.copy()
    df['Analito_norm'] = df['Analito_base'].map(lambda x: ALIASES.get(x, x))
    D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
    T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()
    if usar_totais:
        base = pd.concat([T, D[~D['Analito_base'].isin(T['Analito_base'])]], ignore_index=True)
    else:
        base = pd.concat([D, T[~T['Analito_base'].isin(D['Analito_base'])]], ignore_index=True)

    rows = []
    for _, r in base.iterrows():
        anal = r['Analito_norm']
        idv = r['Id']
        val = r['Valor_mg_L']
        lim = limites.get(anal)
        if lim is None or val is None:
            status = 'Sem limite / Sem dado'
        else:
            status = 'Conforme' if val <= lim else 'Não conforme'
        rows.append({'Id': idv, 'Analito': r['Analito_base'], 'Valor (mg/L)': val, 'Limite (mg/L)': lim, 'Status': status})

    out = pd.DataFrame(rows)
    resumo = pd.DataFrame()
    if not out.empty:
        resumo = out.groupby('Id')['Status'].apply(lambda s: 'REPROVADO' if (s=='Não conforme').any() else 'APROVADO').reset_index(name='Pré-avaliação (especificação)')
    return out, resumo

# =========================
# Sidebar (logo + matriz + parâmetros + entrada de dados)
# =========================
with st.sidebar:
    # Logo na sidebar
    LOGO_PATH = Path("assets/operalab_logo.png")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_column_width=True)
    else:
        st.caption("Adicione o logo em: assets/operalab_logo.png")
    st.markdown("<hr style='margin:6px 0;border-color:#333'>", unsafe_allow_html=True)

    # Matriz do lote
    st.subheader("🧪 Matriz do lote")
    matriz_opcoes = {
        "Água potável (A)": "A",
        "Água superficial (AS)": "AS",
        "Água subterrânea (ASub)": "ASub",
        "Efluente (EFL)": "EFL",
        "Solo (S)": "S"
    }
    matriz_label = st.selectbox("Selecione a matriz", list(matriz_opcoes.keys()), index=0)
    st.session_state["matriz_lote"] = matriz_opcoes[matriz_label]
    st.markdown("<hr style='margin:6px 0;border-color:#333'>", unsafe_allow_html=True)

    # Parâmetros do Lab (ICP) com persistência
    def init_params():
        if "lab_params" not in st.session_state:
            st.session_state["lab_params"] = {
                "u_calib": 0.015,
                "u_pip": 0.025,
                "u_dil": 0.008,
                "k": 2.0,
                "rsd_max": 5.0,
                "rec_min": 90.0,
                "rec_max": 110.0
            }
        return st.session_state["lab_params"]

    params = init_params()
    st.subheader("⚙️ Parâmetros do Lab")
    params["u_calib"] = st.number_input("u_calib (%)", 0.005, 0.050, params["u_calib"], 0.001)
    params["u_pip"]   = st.number_input("u_pipetagem (%)", 0.005, 0.050, params["u_pip"],   0.001)
    params["u_dil"]   = st.number_input("u_diluição (%)", 0.002, 0.050, params["u_dil"],   0.001)
    params["k"]       = st.number_input("k (95%)", 1.90, 2.58, params["k"], 0.01)

    st.markdown("<hr style='margin:6px 0;border-color:#333'>", unsafe_allow_html=True)

    # Entrada de dados
    st.header("Entrada de dados")
    file = st.file_uploader("Enviar arquivo (Excel/CSV)", type=["xlsx","xls","csv"]) 
    st.markdown("Ou cole a tabela abaixo (csv/tsv com cabeçalhos):")
    st.session_state["pasted"] = st.text_area("Colar dados", value=st.session_state.get("pasted",""), height=150)
    c1, c2 = st.columns(2)
    with c1:
        btn_limpar = st.button("Limpar")
    with c2:
        btn_carregar = st.button("Carregar")
    if btn_limpar:
        st.session_state["pasted"] = ""
        st.toast("Área de colagem limpa.")

# Carregar df
df_in = None
if btn_carregar or True:
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

# =========================
# Abas
# =========================
aba1, aba2, aba3, aba4, aba5 = st.tabs(["Avaliar Lote", "Legislação/Especificação", "Duplicatas", "Relatórios", "Decisão ICP"])

# --- Aba 1: Avaliar Lote ---
with aba1:
    st.subheader("Avaliação: Dissolvidos vs Totais + QC Ítrio")
    if df_in is None:
        st.info("Carregue dados no sidebar.")
    else:
        st.dataframe(df_in.head(20), use_container_width=True)
        if st.button("Avaliar Lote", type="primary"):
            out_df, qc_out, lote, id_status, df_num_full = avaliar(df_in)
            if lote.startswith('APROVADO'):
                st.success(f"Status do Lote: {lote}")
            elif lote.startswith('REPROVADO'):
                st.error(f"Status do Lote: {lote}")
            else:
                st.warning(f"Status do Lote: {lote}")
            st.markdown("**Status por ID**")
            order_map = {'REPROVADO':0,'ATENÇÃO':1,'APROVADO':2}
            for idv, stid in sorted(id_status.items(), key=lambda x: (order_map.get(x[1],9), x[0])):
                st.write(f"• ID {idv}: {stid}")
            st.divider()
            st.subheader("Comparação Dissolvido vs Total")
            st.dataframe(style_status(out_df), use_container_width=True)
            st.subheader("QC Ítrio (70–130%)")
            if qc_out.empty:
                st.info("Nenhuma linha de Ítrio em % encontrada.")
            else:
                st.dataframe(style_status(qc_out), use_container_width=True)
            st.subheader("Exportar")
            csv_out = out_df.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar Resultado (CSV)", csv_out, file_name="resultado_comparacao.csv", mime="text/csv")
            if not qc_out.empty:
                csv_qc = qc_out.to_csv(index=False).encode('utf-8')
                st.download_button("Baixar QC Ítrio (CSV)", csv_qc, file_name="qc_itrio.csv", mime="text/csv")
            st.session_state['df_num_full'] = df_num_full

# --- Aba 2: Legislação/Especificação ---
with aba2:
    st.subheader("Pré-avaliação por legislação / especificação")
    if df_in is None:
        st.info("Carregue dados no sidebar.")
    else:
        df_num = preparar_numerico(df_in)
        st.session_state['df_num_full'] = df_num
        matriz = st.session_state.get("matriz_lote")
        spec_keys = [k for k, v in catalog.items() if matriz in v.get("matrices", [])]
        filtro = st.text_input("Filtrar lista por texto (ex.: 'Portaria 888' ou 'CONAMA 357')")
        if filtro:
            spec_keys = [k for k in spec_keys if filtro.lower() in k.lower()]
        if not spec_keys:
            st.warning("Nenhuma especificação disponível no catálogo para esta matriz.")
        else:
            spec_key = st.selectbox("Selecione a especificação", options=spec_keys, index=0)
            st.session_state["spec_key"] = spec_key
            meta = catalog.get(spec_key, {})
            st.markdown(f"**Descrição:** {meta.get('title','')}  ")
            st.markdown(f"**Matriz:** {', '.join(meta.get('matrices', []))}")
            is_conama357 = isinstance(spec_key, str) and (spec_key.startswith("CONAMA 357/2005") or spec_key == "CONAMA 357/2005 – Classes (selecionar)")
            if is_conama357:
                classe = st.selectbox("Classe (1, 2, 3 ou 4)", options=["1","2","3","4"], index=0)
                ambiente = st.selectbox("Ambiente", options=["água doce – lótico","água doce – intermediário","água salobra","água salina"], index=0)
                st.caption(f"Perfil selecionado: Classe {classe} ({ambiente})")
                st.info("Os limites digitais dependem do perfil de classe/ambiente da 357/2005. Vou carregar os valores oficiais na próxima atualização.")
            if st.button("Rodar pré-avaliação", type="primary"):
                pre_df, pre_resumo = aplicar_especificacao(df_num, spec_key)
                if pre_df.empty:
                    st.info("Sem dados aplicáveis ou especificação sem limites carregados.")
                else:
                    st.dataframe(style_status(pre_df), use_container_width=True)
                    if not pre_resumo.empty:
                        st.caption("Resumo por ID:")
                        st.dataframe(pre_resumo, use_container_width=True)
                    csv_pre = pre_df.to_csv(index=False).encode('utf-8')
                    st.download_button("Baixar pré-avaliação (CSV)", csv_pre, file_name="pre_avaliacao_especificacao.csv", mime="text/csv")

# --- Aba 3: Duplicatas ---
with aba3:
    st.subheader("Comparação de duplicatas (%RPD)")
    if df_in is None:
        st.info("Carregue dados no sidebar.")
    else:
        amostras = sorted(df_in['Nº Amostra'].dropna().astype(str).unique()) if 'Nº Amostra' in df_in.columns else []
        c = st.columns(3)
        with c[0]:
            am1 = st.selectbox("Amostra 1", options=amostras, index=0 if amostras else None)
        with c[1]:
            am2 = st.selectbox("Amostra 2", options=amostras, index=1 if len(amostras)>1 else None)
        with c[2]:
            tol = st.number_input("Tolerância (%RPD)", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
        if st.button("Comparar duplicatas", type="secondary"):
            res_dup = comparar_duplicatas(df_in, am1, am2, tolerancia_pct=tol)
            st.dataframe(style_status(res_dup), use_container_width=True)
            n_nc = (res_dup['Status'] == 'Não conforme').sum()
            n_ok = ((res_dup['Status'] == 'Conforme') | (res_dup['Status'] == 'OK')).sum()
            n_inc = (res_dup['Status'] == 'INCONCLUSIVO').sum()
            st.caption(f"Resumo: Não conformes = {n_nc} | Conforme/OK = {n_ok} | Inconclusivos = {n_inc}")
            csv_dup = res_dup.to_csv(index=False).encode('utf-8')
            st.download_button("Baixar duplicatas (CSV)", csv_dup, file_name="comparacao_duplicatas.csv", mime="text/csv")

# --- Aba 4: Relatórios (placeholder) ---
with aba4:
    st.subheader("Relatórios (em breve)")
    st.info("Geração de PDF e planilhas consolidadas — futuro incremento.")

# =========================
# DECISÃO ICP (Aba 5)
# =========================

def calcular_incerteza(resultado, rsd_pct, params):
    uc_rel_pct = np.sqrt(rsd_pct**2 + params["u_calib"]**2 + params["u_pip"]**2 + params["u_dil"]**2)
    U = params["k"] * resultado * uc_rel_pct / 100.0
    return uc_rel_pct, U


def gerar_decisao(resultado, limite, U, rsd_pct, recuperacao, checklist_ok, params):
    inferior = resultado - U
    superior = resultado + U
    motivos, acoes = [], []
    if inferior <= limite:
        decisao = "✅ CONFORME"
        motivos.append(f"Intervalo [{inferior:.3f}-{superior:.3f}] cobre o limite {limite:.3f} mg/L")
    elif superior <= limite * 1.10:
        decisao = "🔄 REANALISAR"
        motivos.append("Resultado próximo (±10% do limite); incerteza sugere possível conformidade")
        if rsd_pct > 5:
            motivos.append("❌ RSD >5%: variabilidade elevada")
            acoes.append("🔧 Verificar pipetagem/reagentes")
    else:
        decisao = "❌ NÃO CONFORME"
        motivos.append(f"Resultado + U ({superior:.3f}) excede o limite {limite:.3f} mg/L")
        acoes.append("📤 Relatar não conformidade")
    if rsd_pct > params["rsd_max"]:
        acoes.append("⚠️ RSD alto: refazer réplicas")
    if not (params["rec_min"] <= recuperacao <= params["rec_max"]):
        acoes.append("⚠️ Recuperação fora (spike): verificar matriz/método")
    if not checklist_ok:
        acoes.append("📋 Checklist incompleto: complete antes da decisão")
    return decisao, motivos, acoes


def parse_replicas(texto):
    vals = []
    for piece in str(texto).split(','):
        s = piece.strip().replace('.', '').replace(',', '.')
        if s:
            try:
                vals.append(float(s))
            except:
                pass
    return vals

with aba5:
    st.subheader("🎯 Decisão ICP — Incerteza, RSD e Recuperação")
    # Recupera params do sidebar
    def init_params():
        if "lab_params" not in st.session_state:
            st.session_state["lab_params"] = {
                "u_calib": 0.015,
                "u_pip": 0.025,
                "u_dil": 0.008,
                "k": 2.0,
                "rsd_max": 5.0,
                "rec_min": 90.0,
                "rec_max": 110.0
            }
        return st.session_state["lab_params"]
    params = init_params()

    fonte_limite = st.radio("Fonte do limite para decisão", ["Usar especificação selecionada", "Informar limite manual"], horizontal=True)
    metal = st.text_input("Metal/Analito (ex.: Pb, Cd, Crômio total)", value="Pb")

    limite = None
    spec_sel = st.session_state.get("spec_key")
    if fonte_limite == "Usar especificação selecionada":
        if not spec_sel:
            st.warning("Selecione uma especificação na aba 'Legislação/Especificação'.")
        else:
            alias = ALIASES.get(metal, metal)
            limite = catalog.get(spec_sel, {}).get("limits_mgL", {}).get(alias)
            if limite is None:
                st.error(f"Limite não encontrado para '{alias}' em '{spec_sel}'. Informe manualmente ou escolha outro metal.")
    else:
        limite = st.number_input("Limite legal (mg/L)", min_value=0.0001, max_value=1000.0, value=0.010, step=0.001)

    colA, colB = st.columns([1,1])
    with colA:
        resultado = st.number_input("Resultado médio (mg/L)", min_value=0.00001, max_value=1000.0, value=0.012, step=0.001)
        replicas_str = st.text_input("Réplicas (vírgula)", value="0.012, 0.011, 0.013")
        replicas = parse_replicas(replicas_str)
        rsd = (np.std(replicas)/np.mean(replicas)*100.0) if (len(replicas)>1 and np.mean(replicas)!=0) else 0.0
    with colB:
        recuperacao = st.number_input("Recuperação Spiked (%)", min_value=50.0, max_value=150.0, value=95.0, step=0.5)
        st.subheader("✅ Checklist Diário")
        blank_ok    = st.checkbox("Blank < LOQ", value=True)
        calib_ok    = st.checkbox("R² > 0.999", value=True)
        matriz_ok   = st.checkbox("Matching de matriz", value=True)
        interfer_ok = st.checkbox("Modo colisão OK", value=True)
        checklist_ok = blank_ok and calib_ok and matriz_ok and interfer_ok

    if st.button("🚀 ANALISAR & DECIDIR", type="primary"):
        if limite is None:
            st.error("Defina o limite (via especificação ou manual).")
        else:
            uc_rel, U = calcular_incerteza(resultado, rsd, params)
            decisao, motivos, acoes = gerar_decisao(resultado, limite, U, rsd, recuperacao, checklist_ok, params)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Resultado", f"{resultado:.3f} mg/L")
            c2.metric("U expandida", f"{U:.3f} mg/L")
            c3.metric("RSD", f"{rsd:.1f}%")
            c4.metric("Recuperação", f"{recuperacao:.1f}%")

            st.markdown(f"### 🎯 **{decisao}**")
            st.info("**📝 Motivos técnicos:**")
            for m in motivos:
                st.write(f"• {m}")
            if acoes:
                st.warning("**🎯 Ações imediatas:**")
                for a in acoes:
                    st.markdown(a)

            df_resumo = pd.DataFrame({
                "Critério": ["Resultado", "Limite", "Inferior (U)", "Superior (U)", "RSD", "Recuperação", "Checklist", "Decisão"],
                "Valor": [f"{resultado:.3f}", f"{limite:.3f}", f"{resultado-U:.3f}", f"{resultado+U:.3f}",
                          f"{rsd:.1f}%", f"{recuperacao:.1f}%", "✅" if checklist_ok else "❌", decisao]
            })
            st.table(df_resumo)

            fig = px.line(x=[resultado-U, resultado, resultado+U], y=[1,1,1],
                          labels={'x':'Concentração (mg/L)'}, title="Intervalo de Confiança vs Limite")
            fig.add_hline(y=1, line_dash="dash", line_color="red", annotation_text=f"Limite: {limite:.3f} mg/L")
            st.plotly_chart(fig, use_container_width=True)

            log_data = {
                'data_hora': pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
                'matriz': st.session_state.get("matriz_lote"),
                'especificacao': spec_sel if spec_sel else "manual",
                'metal': metal, 'resultado': resultado, 'limite': limite, 'U': U,
                'rsd': rsd, 'recuperacao': recuperacao, 'checklist_ok': checklist_ok,
                'decisao': decisao, 'motivos': '; '.join(motivos), 'acoes': '; '.join(acoes)
            }
            st.download_button(
                label="💾 Salvar Log CSV",
                data=pd.DataFrame([log_data]).to_csv(index=False),
                file_name=f"ICP_log_{metal}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )

    # =========================
    # Calibração semanal (com roteiro)
    # =========================
    st.markdown("---")
    st.subheader("🔧 Calibração semanal (30 min)")

    with st.expander("📋 Roteiro passo a passo (30min)", expanded=False):
        st.markdown(
            """
            **Responsável**: Operador ICP + Analista Sênior  
            **Passo 1 – Coletar (5min)**: copie `data, metal, resultado, réplicas, recuperação, U_lab, decisao_experta` (20 linhas) no CSV.  
            **Passo 2 – Rodar validação (5min)**: upload CSV → ver **Bias (%)**, **Acordo (%)**.  
            **Passo 3 – Decidir ajuste (5–10min)**:  
            • **Bias >10%?** → aumentar `u_pip`  
            • **Acordo <95%?** → checklist mais rígido.  
            **Passo 4 – Atualizar (5min)**: aplique ajuste sugerido e salve.  
            **Passo 5 – Log (5min)**: exporte CSV e arquive.
            """
        )

    template = pd.DataFrame(columns=['data','metal','resultado','replicas','recuperacao','U_lab','decisao_experta'])
    st.download_button("📥 Baixar template calibração", template.to_csv(index=False), "template_validacao.csv")

    uploaded_csv = st.file_uploader("📁 Upload CSV validação (20 linhas)")
    if uploaded_csv:
        df_val = pd.read_csv(uploaded_csv)
        U_calc, bias_list = [], []
        for _, row in df_val.iterrows():
            reps = parse_replicas(row.get('replicas',''))
            rsd_val = (np.std(reps)/np.mean(reps)*100.0) if (len(reps)>1 and np.mean(reps)!=0) else 0.0
            uc_rel2, U_val = calcular_incerteza(row.get('resultado',0.0), rsd_val, params)
            U_calc.append(U_val)
            U_lab = row.get('U_lab', np.nan)
            bias_list.append(abs(U_val - U_lab)/U_lab*100.0 if (U_lab and U_lab!=0) else np.nan)

        df_val['U_calc'] = U_calc
        df_val['bias_%'] = bias_list
        bias_medio = float(pd.to_numeric(df_val['bias_%'], errors='coerce').dropna().mean())
        acordo = float((df_val['decisao_experta'].astype(str) == 'Conforme').mean()*100.0) if 'decisao_experta' in df_val.columns else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Bias médio", f"{bias_medio:.1f}%")
        c2.metric("Acordo especialista", f"{acordo:.0f}%")
        c3.metric("Linhas validadas", len(df_val))

        st.dataframe(df_val[['metal','resultado','U_lab','U_calc','bias_%']].round(3), use_container_width=True)

        import math
        if (not math.isnan(bias_medio)) and (bias_medio > 10.0):
            ajuste_pip = params['u_pip'] + 0.005 * (bias_medio/10.0)
            st.warning(f"🔧 Ajuste recomendado: u_pip → {ajuste_pip:.3f}%")
            if st.button("✅ Aplicar ajuste automaticamente"):
                params['u_pip'] = ajuste_pip
                st.success("✅ Parâmetros atualizados! (persistem na sessão)")
                st.rerun()
        else:
            st.success("🎉 Calibração OK! Bias ≤ 10%")

# Rodapé
st.caption("© {} | OPERA LAB - Analyst Support".format(pd.Timestamp.now().year))
