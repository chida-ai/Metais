# operalab_validador_metais

Validador online de **Metais Dissolvidos vs Totais** com **QC Ítrio (70–130%)**, feito em Streamlit.

## Como publicar (Streamlit Community Cloud)
1. Crie um repositório GitHub com estes arquivos (`app.py`, `requirements.txt`, `README.md`).
2. Acesse o painel **Streamlit Community Cloud** e conecte seu GitHub.
3. Clique em **Create app**, selecione seu repositório e o arquivo principal `app.py`.
4. Clique em **Deploy** e pegue a URL pública.

Referências oficiais:
- Guia de deploy: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
- Quickstart (Cloud): https://github.com/streamlit/docs/blob/main/content/deploy/community-cloud/get-started/quickstart.md

## Como publicar (Hugging Face Spaces)
1. Crie um Space (SDK **Streamlit**).
2. Suba `app.py` e `requirements.txt`.
3. Aguarde o build e use a URL do Space.

Documentação Spaces (Streamlit): https://huggingface.co/docs/hub/en/spaces-sdks-streamlit

## Uso
- Cole dados ou envie **CSV/Excel** com cabeçalhos: `Id, Nº Amostra, Método de Análise, Análise, Valor, Unidade de Medida, (opcional) LQ - Limite Quantificação`.
- Clique **Avaliar Lote**.
- Veja status do lote, tabelas e baixe CSVs.

## Critérios
- **NÃO CONFORME**: Dissolvido > Total.
- **POTENCIAL NÃO CONFORME**: Total < LQ e Dissolvido > LQ(Total).
- **QC Ítrio**: OK se 70–130%; fora disso = NÃO CONFORME.
