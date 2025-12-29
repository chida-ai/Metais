# OPERALAB – Sistema de Avaliação de Resultados

O **OPERALAB** é um sistema profissional desenvolvido em **Python + Streamlit** para avaliação automatizada de resultados laboratoriais ambientais.  
Ele unifica o melhor das versões anteriores do sistema, agora com uma arquitetura modular, robusta e fácil de manter.

---

## 🚀 Funcionalidades Principais

### **1. Comparação Dissolvido vs Total**
- Conversão de unidades totalmente robusta (mg/L, µg/L, μg/L, ug/L)
- Tratamento de valores censurados (<LQ)
- Avaliação automática:
  - **OK**
  - **NÃO CONFORME**
  - **POTENCIAL NÃO CONFORME**
  - **INCONCLUSIVO**
- Status por ID e status global do lote

---

### **2. QC Ítrio (70–130%)**
- Detecção automática de linhas de Ítrio
- Avaliação de recuperação (%)
- Status por ID
- Integração com o status final do lote

---

### **3. Comparação de Duplicatas (%RPD)**
- Cálculo automático de %RPD
- Tratamento de censura
- Exclusão automática de unidades em %
- Avaliação conforme tolerância configurável

---

### **4. Avaliação por Legislação / Especificação**
- Compatível com catálogo JSON externo
- Aliases para analitos (Cr+6, Cr VI, etc.)
- Seleção automática entre Totais e Dissolvidos
- Tabela detalhada + resumo por ID

---

### **5. Interface Moderna**
- Layout profissional com logo
- Abas organizadas
- Upload de arquivos ou colagem direta
- Exportação de resultados em CSV
- Estilização por severidade (cores)

---

## 🧱 Arquitetura do Projeto

