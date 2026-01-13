# 💲 SmartWallet

O SmartWallet é um gerenciador financeiro pessoal focado em **reduzir a fricção** no registro de despesas. Em vez de preencher formulários manuais, o usuário envia comandos de texto ou áudio (ex: *"Gastei 50 reais no Uber"*), e o sistema processa, categoriza e salva automaticamente.

O projeto utiliza uma arquitetura híbrida de processamento: **Regex Local** para transações simples (custo zero e latência nula) e **Google Gemini (LLM)** para interpretação de contextos complexos, conversão de moedas e análise de comprovantes.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Binary-336791?style=flat&logo=postgresql&logoColor=white)

## 🎯 Funcionalidades

-   **Processamento Híbrido (NLP):**
    -   ⚡ **Motor Local:** Detecta padrões simples via Regex instantaneamente.
    -   🧠 **Motor LLM:** Aciona a API do Gemini apenas para áudios ou frases complexas que requerem inferência.
-   **Multi-Moeda:** Conversão automática de valores (USD, EUR, BTC, ETH) para BRL no momento do registro, utilizando cotações em tempo real.
-   **Gestão de Comprovantes:** Upload e armazenamento de arquivos (PDF/Imagens) vinculados à transação no banco de dados.
-   **Recorrência Inteligente:** Sistema para lançar automaticamente contas fixas mensais.
-   **Relatórios e Exportação:** Dashboard interativo com Plotly e exportação de extratos formatados em Excel (.xlsx) e PDF.
-   **Segurança:** Autenticação com Hashing (SHA-256) e Salt dinâmico via variáveis de ambiente.

## 📸 Galeria do Projeto

### 📊 Dashboard Interativo
Visão geral das finanças com gráficos dinâmicos e KPIs em tempo real.
![Dashboard](assets/Dashboard%20view.png)

### 🤖 Inteligência Artificial (NLP)
Registro de despesas via comando de texto natural ou voz.
![IA Demo](assets/ai_demo.png)

### 📑 Relatórios e Extratos
Gerenciamento completo com exportação profissional para Excel e PDF.
![Relatórios](assets/reports_view.png)

## 🏗️ Arquitetura do Projeto

O projeto foi refatorado para seguir princípios de **Clean Architecture** e **DDD (Domain Driven Design)**, separando responsabilidades:

```text
smartwallet/
├── src/
│   ├── ai_engine.py    # Lógica híbrida (Regex/Gemini) e fallback de modelos
│   ├── auth.py         # Gerenciamento de Hash, Salt e validação de senhas
│   ├── database.py     # Camada de persistência (PostgreSQL) com padrão Singleton
│   ├── ui.py           # Componentes visuais e injeção de CSS
│   └── utils.py        # Validadores de domínio e integrações externas (APIs)
├── main.py             # Ponto de entrada e orquestração do Streamlit
└── requirements.txt    # Dependências
