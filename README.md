# 💲 SmartWallet Personal Pro

> **Seu dinheiro, sob controle. Sem fricção, com Inteligência Artificial.**

O **SmartWallet** é uma plataforma de gestão financeira pessoal *Enterprise-Grade* desenvolvida para eliminar a barreira de entrada no controle de gastos. Diferente de planilhas manuais, ele utiliza um **Motor Híbrido de IA** que entende linguagem natural (texto e áudio) para registrar, categorizar e analisar transações automaticamente.

O projeto sofreu uma **Refatoração Arquitetural Completa**, evoluindo de um script linear para uma aplicação modular, segura e escalável, seguindo princípios de **Clean Architecture** e **DDD (Domain Driven Design)**.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Binary-336791?style=flat&logo=postgresql&logoColor=white)
![Google Gemini](https://img.shields.io/badge/AI-Gemini%202.0-8E75B2?style=flat&logo=google&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=flat&logo=docker&logoColor=white)

---

## 🚀 Principais Inovações (v2.0)

Esta versão traz mudanças drásticas em relação ao projeto original:

### 🧠 1. Cérebro de IA Avançado (RAG + Contexto)
* **RAG (Retrieval-Augmented Generation):** O sistema agora lê a pasta `assets/` para estudar PDFs e apostilas financeiras, usando esse conhecimento para responder dúvidas no Chat (Ex: "O que diz a apostila sobre Reserva de Emergência?").
* **Coach Financeiro Inteligente:** A IA agora diferencia matematicamente o que é **Renda Mensal** (Salário) do que é **Patrimônio Acumulado** (Investimentos), evitando alucinações nas recomendações de investimento.
* **Output Sanitization:** Filtros automáticos removem formatações de código indesejadas (Markdown/LaTeX) para garantir uma resposta visualmente limpa ao usuário.

### 🛡️ 2. UX/UI Defensiva e Segura
* **Janelas de Confirmação (Pop-ups):** Implementação de travas de segurança (`@st.dialog`) para todas as ações destrutivas (excluir transação, resetar conta, limpar chat).
* **Visualização de Investimentos:** Lógica de cores semântica na carteira:
    * 🟢 **Verde:** Saldo/Rendimento.
    * 🟠 **Laranja:** Aportes (Saída de caixa para ativo).
    * 🔵 **Azul:** Resgates.

### ⚙️ 3. Engenharia de Software Robusta
* **Fail-Fast & Guard Clauses:** O código foi blindado para falhar cedo em caso de erros (ex: senhas fracas, valores negativos), protegendo a integridade do banco.
* **Idempotência:** O sistema de banco de dados e processamento de contas recorrentes pode rodar múltiplas vezes sem duplicar dados ou quebrar a aplicação.

---

## 🎯 Funcionalidades Detalhadas

-   **Processamento Híbrido (NLP):**
    -   ⚡ **Motor Local (Regex):** Processa transações simples ("Gastei 50 no Uber") em milissegundos, custo zero.
    -   🧠 **Motor LLM (Gemini):** Acionado para inferências complexas, áudios e categorização contextual.
-   **Multi-Moeda Global:** Conversão em tempo real de USD, EUR, GBP (Libra corrigida), BTC e ETH para BRL no momento do registro.
-   **Gestão de Documentos:** Upload de comprovantes (PDF/Imagem) salvos diretamente no banco (BYTEA).
-   **Recorrência Inteligente:** Sistema automático para lançar contas fixas mensais.
-   **Relatórios Profissionais:** Exportação de extratos auditáveis em **Excel (.xlsx)** estilizado e **PDF**.
-   **Segurança:** Hashing SHA-256 com Salt dinâmico via variáveis de ambiente.

📱  **ACESSE A APLICAÇÃO ONLINE:** [SmartWallet - Carteira Inteligente](https://smartwallet-carteirateligente.streamlit.app/)

---

## 📸 Galeria

| Dashboard Interativo | IA & NLP (Texto/Voz) |
| :---: | :---: |
| ![Dashboard](assets/Dashboard%20view.png) | ![IA Demo](assets/ai_demo.png) |

---

## 🏗️ Arquitetura do Projeto

A estrutura de arquivos foi organizada para facilitar a manutenção e testes:

```text
smartwallet/
├── .github/
│   └── workflows/tests.yml # CI/CD: Pipeline de testes automáticos
├── assets/                 # Base de conhecimento (PDFs) para o RAG
├── src/
│   ├── ai_engine.py        # Cérebro: Lógica Híbrida, RAG e Coach Financeiro
│   ├── auth.py             # Segurança: Hash, Salt e Validação de Senhas
│   ├── database.py         # Persistência: PostgreSQL com Singleton e Migrations
│   ├── ui.py               # Frontend: Injeção de CSS e Componentes Visuais
│   └── utils.py            # Domínio: Validadores, Cotações e Gerador de Docs
├── tests/                  # Testes Unitários (QA)
├── main.py                 # Orquestrador da Aplicação
├── Dockerfile              # Containerização
└── requirements.txt        # Dependências Otimizadas