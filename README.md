# 💼 SmartWallet Portfolio

> Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).

O **SmartWallet** é uma aplicação Full-Stack desenvolvida em Python que utiliza Inteligência Artificial Generativa (Google Gemini) para transformar comandos de texto informais em registros financeiros estruturados.

![Status](https://img.shields.io/badge/Status-Concluído-success)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-red)

## 🚀 Funcionalidades Principais

* **🧠 Registro via NLP:** Digite *"Gastei 50 dólares em livros"* e o sistema identifica o valor, converte a moeda, categoriza e salva.
* **💹 Cotações em Tempo Real:** Monitoramento ao vivo de USD, EUR, GBP e BTC com atualização automática (Auto-Refresh).
* **🛡️ Arquitetura Robusta:** Sistema de fallback para IA e tratamento de erros de banco de dados (SQLite).
* **📊 Dashboard Interativo:** Gráficos dinâmicos com Plotly e análises de fluxo de caixa.
* **💡 Consultor IA:** Módulo que analisa seu histórico e gera diagnósticos financeiros racionais.

## 🛠️ Tecnologias Utilizadas

* **Frontend/Backend:** Streamlit
* **IA/LLM:** Google Gemini API (Modelo 2.5 Flash)
* **Banco de Dados:** SQLite3 (DAO Pattern)
* **Visualização:** Plotly Express & Pandas

## 📦 Como Rodar o Projeto

1. Clone o repositório:
```bash
git clone [https://github.com/SEU-USUARIO/smartwallet.git](https://github.com/SEU-USUARIO/smartwallet.git)