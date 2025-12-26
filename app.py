# --- Cabeçalho com logo e título ---
from pathlib import Path

LOGO_PATH = Path("assets/operalab_logo.png")

# Cria duas colunas: logo (esq.) e título (dir.)
header_cols = st.columns([0.9, 6])

with header_cols[0]:
    if LOGO_PATH.exists():
        # Ajuste o tamanho do logo aqui (300 se quiser bem grande; 120–160 costuma ficar equilibrado)
        st.image(str(LOGO_PATH), width=300)
    else:
        st.caption("Adicione o arquivo do logo em: assets/operalab_logo.png")

with header_cols[1]:
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;">
          <h1 style="margin:0;">OPERATORLAB&nbsp;&nbsp;-&nbsp;&nbsp;Avaliador de Resultados</h1>
        </div>
        <div style="height:4px;background:#00A3FF;border-radius:2px;margin-top:8px;"></div>
        <div style="margin-top:6px;opacity:0.85;">
          Dissolvidos vs Totais • QC Ítrio • Duplicatas (%RPD) • Pré‑avaliação por legislação/especificação
        </div>
        """,
        unsafe_allow_html=True
    )

# ----------------------
# Estado
# ----------------------
if "pasted" not in st.session_state:
    st.session_state["pasted"] = ""

# ----------------------
# Auxiliares
# ----------------------

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

# ----------------------
# Especificações — catálogo externo (JSON)
# ----------------------
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
}

# ----------------------
# Núcleo: avaliação Dissolvido vs Total + QC Ítrio
# ----------------------

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

# ----------------------
# Duplicatas (%RPD)
# ----------------------

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

# ----------------------
# Engine: pré‑avaliação por especificação
# ----------------------

def style_status(df):
    def color_row(s):
        c = 'white'
        bg = '#222'
        if s.get('Status') == 'Não conforme':
            bg = '#FF3B30'
        elif s.get('Status') == 'Conforme' or s.get('Status') == 'OK':
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

# ----------------------
# UI com abas
# ----------------------
with st.sidebar:
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

# carregar df
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

aba1, aba2, aba3, aba4 = st.tabs(["Avaliar Lote", "Legislação/Especificação", "Duplicatas", "Relatórios"])

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

with aba2:
    st.subheader("Pré‑avaliação por legislação / especificação")
    if df_in is None:
        st.info("Carregue dados no sidebar.")
    else:
        df_num = preparar_numerico(df_in)
        st.session_state['df_num_full'] = df_num
        spec_keys = list(catalog.keys())
        filtro = st.text_input("Filtrar lista por texto (ex.: 'Portaria 888' ou 'CONAMA 357')")
        if filtro:
            spec_keys = [k for k in spec_keys if filtro.lower() in k.lower()]
        spec_key = st.selectbox("Selecione a especificação", options=spec_keys, index=0 if spec_keys else None)
        meta = catalog.get(spec_key, {})
        st.markdown(f"**Descrição:** {meta.get('title','')}  ")
        st.markdown(f"**Matriz:** {', '.join(meta.get('matrices', []))}")
        if st.button("Rodar pré‑avaliação", type="primary") and spec_key:
            pre_df, pre_resumo = aplicar_especificacao(df_num, spec_key)
            if pre_df.empty:
                st.info("Sem dados aplicáveis ou especificação sem limites carregados.")
            else:
                st.dataframe(style_status(pre_df), use_container_width=True)
                if not pre_resumo.empty:
                    st.caption("Resumo por ID:")
                    st.dataframe(pre_resumo, use_container_width=True)
                csv_pre = pre_df.to_csv(index=False).encode('utf-8')
                st.download_button("Baixar pré‑avaliação (CSV)", csv_pre, file_name="pre_avaliacao_especificacao.csv", mime="text/csv")

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

with aba4:
    st.subheader("Relatórios (em breve)")
    st.info("Geração de PDF e planilhas consolidadas — futuro incremento.")

st.caption("© {} | operalab_validador_metais".format(pd.Timestamp.now().year))
