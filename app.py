# -*- coding: utf-8 -*-
"""
Validador de Metais: Dissolvidos vs Totais + QC Ítrio
Uso:
    python validador_metais.py Template_Comparacao_Metais_v2.xlsx

- Lê a aba 'Dados'
- Gera/atualiza:
   * 'Resultado' com a comparação por ID+Analito
   * 'QC_Ítrio' com verificação de recuperação (70% a 130%)
"""
import sys
import pandas as pd
import re

if len(sys.argv) < 2:
    print("Uso: python validador_metais.py <arquivo.xlsx>")
    sys.exit(1)

xlsx_path = sys.argv[1]

# Ler dados
df = pd.read_excel(xlsx_path, sheet_name='Dados', engine='openpyxl')

# Selecionar colunas necessárias
cols = ['Id','Nº Amostra','Método de Análise','Análise','Valor','Unidade de Medida','LQ - Limite Quantificação']
for c in cols:
    if c not in df.columns:
        raise ValueError(f"Coluna obrigatória ausente: {c}")

# Funções auxiliares

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
    if pd.isna(unit):
        return None
    u = str(unit).strip()
    if u == 'mg/L':
        return val
    elif u == 'µg/L' or u.lower() == 'ug/l':
        return val/1000.0 if val is not None else None
    else:
        return None  # ignore % etc

# Preparar dataframe
df['Valor_num'], df['Censurado'] = zip(*df['Valor'].map(parse_val))
df['Valor_mg_L'] = df.apply(lambda r: to_mg_per_L(r['Valor_num'], r['Unidade de Medida']), axis=1)
# Padronizar analito (remove sufixo ' Dissolvido')
df['Analito_base'] = df['Análise'].str.replace(r"\s+Dissolvido$", '', regex=True)

# Separar Dissolvidos e Totais
D = df[df['Método de Análise'].str.contains('Dissolvidos', case=False, na=False)].copy()
T = df[df['Método de Análise'].str.contains('Totais', case=False, na=False)].copy()

# Filtrar apenas mg/L
D = D[D['Valor_mg_L'].notna()].copy()
T = T[T['Valor_mg_L'].notna()].copy()

# Merge (outer para sinalizar casos sem par)
merged = pd.merge(
    D[['Id','Analito_base','Valor_mg_L','Censurado','LQ - Limite Quantificação']],
    T[['Id','Analito_base','Valor_mg_L','Censurado','LQ - Limite Quantificação']],
    on=['Id','Analito_base'], suffixes=('_diss','_tot'), how='outer'
)

# Aplicar regras de comparação
out_rows = []
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
            # comparar com LQ do total, se disponível
            lq_tot = r['LQ - Limite Quantificação_tot']
            lq_num, _ = parse_val(lq_tot)
            # LQ fornecido já deve estar em mg/L na coluna; se vier em string numérica, usamos diretamente
            lq_mg = lq_num if lq_num is not None else t_val
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

# =====================
# QC ÍTRIO (70% a 130%)
# =====================
qc_df = df.copy()
# normalizar grafia de Ítrio/Itrio
qc_df['Analise_lower'] = qc_df['Análise'].str.lower()
mask_itrio = qc_df['Analise_lower'].str.contains('ítrio') | qc_df['Analise_lower'].str.contains('itrio')
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

# Escrever nas abas Resultado e QC_Ítrio
with pd.ExcelWriter(xlsx_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
    out_df.to_excel(writer, sheet_name='Resultado', index=False)
    qc_out.to_excel(writer, sheet_name='QC_Ítrio', index=False)

print(f"Processado: {xlsx_path}. Linhas Resultado={len(out_df)} | Linhas QC_Ítrio={len(qc_out)}")
