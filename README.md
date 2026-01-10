# 💼 SmartWallet Portfolio (V3.0)

> Sistema de Gestão Financeira Inteligente com Autenticação Segura e IA.

O **SmartWallet** é uma aplicação Full-Stack desenvolvida em Python que utiliza Inteligência Artificial Generativa (Google Gemini) para transformar comandos de texto informais em registros financeiros estruturados.

Esta versão conta com **Múltiplos Usuários**, **Criptografia de Senhas** e **Persistência em Banco de Dados**.

![Status](https://img.shields.io/badge/Status-Concluído-success)
![Security](https://img.shields.io/badge/Security-SHA256-green)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-red)

## 🚀 Novas Funcionalidades (v3.0)

* **🔐 Login & Segurança:** Sistema de autenticação robusto. Senhas salvas com criptografia (Hash SHA-256).
* **💾 Banco de Dados SQLite:** Persistência total dos dados. Cada usuário acessa apenas sua própria carteira (Multi-tenancy).
* **🧠 Registro via NLP:** Digite *"Gastei 50 dólares em livros"* e o sistema identifica o valor, converte a moeda e salva.
* **🛡️ Zero Erros UX:** Interface otimizada para evitar conflitos de preenchimento automático.
* **📊 Dashboard Interativo:** Gráficos dinâmicos com Plotly e análises de fluxo de caixa.

## 🛠️ Tecnologias Utilizadas

* **Core:** Python 3.10+
* **Frontend:** Streamlit (com tema personalizado Dark/Green)
* **AI/LLM:** Google Gemini API (Modelo 2.5 Flash)
* **Database:** SQLite3 (DAO Pattern)
* **Security:** Hashlib (SHA-256 Encryption)

## 📦 Como Rodar o Projeto

1. Clone o repositório:
```bash
git clone [https://github.com/oFernandoNascimento/smartwallet.git](https://github.com/oFernandoNascimento/smartwallet.git)
cd smartwallet
