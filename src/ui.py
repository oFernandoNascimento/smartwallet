# Arquivo: main.py
import streamlit as st
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import pytz
import os

# Imports Internos (Arquitetura Modular)
from src.database import RobustDatabase
from src.ai_engine import AIManager
from src.ui import UIManager
from src.utils import get_market_data, DocGenerator

# --- Configuração Inicial da Página ---
st.set_page_config(
    page_title="SmartWallet Enterprise",
    page_icon="💸", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.google.com',
        'Report a bug': "mailto:support@smartwallet.com",
        'About': "# SmartWallet v2.0 Enterprise\nGestão Financeira com IA."
    }
)

# --- Constantes de UI ---
FUSO_BR = pytz.timezone('America/Sao_Paulo')

def init_session_state():
    """Inicializa variáveis de estado globais de forma segura."""
    defaults = {
        'logged_in': False,
        'user': None,
        'audio_key': 0,
        'manual_form': {},
        'history_mkt': {},
        'show_confetti': False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def render_login_screen(db: RobustDatabase):
    """Renderiza a tela de login/registro com UX aprimorada."""
    c1, c2, c3 = st.columns([1, 1.2, 1])
    
    with c2:
        # Tenta carregar logo
        logo_files = ["logo.png", "logo.jpg", "logo.jpeg"]
        logo_path = next((f for f in logo_files if os.path.exists(f)), None)
        
        with st.container(border=True):
            if logo_path:
                st.image(logo_path, use_container_width=True)
            else:
                st.markdown("<h1 style='text-align:center;'>💸 SmartWallet</h1>", unsafe_allow_html=True)
            
            st.markdown("<p style='text-align:center;color:#888'>Gestão Financeira Inteligente</p>", unsafe_allow_html=True)
            
            tab_login, tab_register = st.tabs(["Acessar Conta", "Criar Nova Conta"])
            
            with tab_login:
                with st.form("frm_login"):
                    u = st.text_input("Usuário", placeholder="Seu user")
                    p = st.text_input("Senha", type="password", placeholder="••••••")
                    if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                        if db.login_user(u.strip(), p.strip()):
                            st.session_state.logged_in = True
                            st.session_state.user = u.strip()
                            # Processamento assíncrono de recorrências
                            n_rec = db.process_recurring_transactions(u.strip(), FUSO_BR)
                            if n_rec > 0:
                                st.toast(f"{n_rec} contas recorrentes lançadas automaticamente!", icon="🔄")
                            st.rerun()
                        else:
                            st.error("Credenciais inválidas.")

            with tab_register:
                with st.form("frm_register"):
                    nu = st.text_input("Escolha um Usuário")
                    np = st.text_input("Escolha uma Senha", type="password", help="Mínimo 8 caracteres, letras e números.")
                    npc = st.text_input("Confirme a Senha", type="password")
                    
                    if st.form_submit_button("Registrar", use_container_width=True):
                        if np != npc:
                            st.warning("As senhas não coincidem.")
                        else:
                            ok, msg = db.register_user(nu.strip(), np.strip())
                            if ok:
                                st.success(msg)
                                time.sleep(1)
                            else:
                                st.error(msg)

def render_sidebar(db: RobustDatabase, user: str) -> Tuple[date, date]:
    """Sidebar de navegação e filtros."""
    with st.sidebar:
        st.markdown(f"### 👤 {user}")
        st.caption("Status: Conectado")
        st.divider()
        
        st.markdown("### 📅 Período de Análise")
        mode = st.radio("Filtro de Data", ["Mês Atual", "Personalizado"], horizontal=True, label_visibility="collapsed")
        
        today = datetime.now(FUSO_BR).date()
        if mode == "Mês Atual":
            start_date = today.replace(day=1)
            # Lógica para pegar último dia do mês
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
            st.info(f"De: {start_date.strftime('%d/%m/%Y')}\nAté: {end_date.strftime('%d/%m/%Y')}")
        else:
            d_range = st.date_input("Selecione Intervalo", [today - timedelta(days=30), today], format="DD/MM/YYYY")
            if len(d_range) == 2:
                start_date, end_date = d_range
            else:
                start_date, end_date = today, today # Fallback
                
        st.divider()
        
        with st.expander("🛠️ Ferramentas"):
            if st.button("Limpar Cache"):
                st.cache_data.clear()
                st.rerun()
            if st.button("Sair (Logout)", type="primary"):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.rerun()
                
        return start_date, end_date

def render_dashboard(db: RobustDatabase, user: str, start: date, end: date):
    """Tab Dashboard Principal."""
    inc, exp = db.get_financial_summary(user, start, end)
    bal = inc - exp
    
    # KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("Entradas", UIManager.fmt_money(inc), delta="Recebido", delta_color="normal")
    k2.metric("Saídas", UIManager.fmt_money(exp), delta="-Gasto", delta_color="inverse")
    k3.metric("Saldo Líquido", UIManager.fmt_money(bal), delta="Resultado")
    
    st.divider()
    
    # Gráficos
    df = db.get_dataframe(user, start_date=start, end_date=end)
    
    if not df.empty:
        c1, c2 = st.columns([1.5, 1])
        
        with c1:
            st.subheader("Fluxo de Caixa Diário")
            daily = df.groupby(['date', 'type'])['amount'].sum().reset_index()
            fig = px.bar(daily, x='date', y='amount', color='type', barmode='group',
                        color_discrete_map={'Receita': '#4CAF50', 'Despesa': '#EF5350'})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.subheader("Gastos por Categoria")
            exp_df = df[df['type'] == 'Despesa']
            if not exp_df.empty:
                fig2 = px.pie(exp_df, values='amount', names='category', hole=0.5,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
                fig2.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0), height=300)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sem despesas no período.")
    else:
        st.warning("Nenhum dado encontrado para este período.")

def main():
    UIManager.inject_global_css()
    init_session_state()
    
    db = RobustDatabase() # Instancia DB (Conexão Singleton)
    AIManager.configure() # Configura IA
    
    # Roteamento de Estado (Login vs App)
    if not st.session_state.logged_in:
        render_login_screen(db)
        return

    # App Logado
    user = st.session_state.user
    start_date, end_date = render_sidebar(db, user)
    
    # Header com Ticker de Mercado
    mkt = get_market_data()
    UIManager.render_market_ticker(mkt)
    
    # Abas Principais
    t1, t2, t3, t4, t5 = st.tabs(["📊 Dashboard", "➕ Lançamentos", "🤖 Assistente IA", "🎯 Metas", "📋 Extrato"])
    
    # Tab 1: Dashboard
    with t1:
        render_dashboard(db, user, start_date, end_date)
        
    # Tab 2: Lançamentos Manuais
    with t2:
        c1, c2 = st.columns(2)
        cats = db.get_user_categories(user)
        
        with c1:
            l_tipo = st.radio("Tipo", ["Despesa", "Receita"], horizontal=True)
            l_val = st.number_input("Valor (R$)", min_value=0.01, step=10.0)
            l_date = st.date_input("Data", datetime.now(FUSO_BR))
            
        with c2:
            l_cat = st.selectbox("Categoria", cats)
            l_desc = st.text_input("Descrição", placeholder="Ex: Mercado Semanal")
            l_file = st.file_uploader("Comprovante (Opcional)", type=['png', 'jpg', 'pdf'])
            
        l_rec = st.checkbox("Tornar Recorrente (Todo mês)")
        
        if st.button("Salvar Lançamento", type="primary", use_container_width=True):
            if db.add_transaction(user, l_date, l_val, l_cat, l_desc, l_tipo, l_file, l_file.name if l_file else None):
                if l_rec:
                    db.add_recurring(user, l_cat, l_val, l_desc, l_tipo, l_date.day)
                st.toast("Lançamento salvo com sucesso!", icon="✅")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Erro ao salvar.")
                
    # Tab 3: Assistente IA (Onde ocorria o erro 404)
    with t3:
        st.markdown("### 🤖 IA Generativa Financeira")
        st.info("Dica: Use comandos de voz ou texto como 'Gastei 100 reais no Outback'. A IA categoriza e converte moedas automaticamente.")
        
        col_ia_1, col_ia_2 = st.columns([4, 1])
        with col_ia_1:
            txt_ia = st.text_input("Comando de Texto", placeholder="Digite aqui...")
        with col_ia_2:
            # Incremento key para resetar componente
            aud_ia = st.audio_input("Voz", key=f"rec_{st.session_state.audio_key}")
            
        if st.button("Processar IA", type="primary"):
            cats = db.get_user_categories(user)
            res = None
            
            with st.spinner("🧠 Analisando..."):
                if aud_ia:
                    res = AIManager.process_audio_nlp(aud_ia, mkt, cats)
                    st.session_state.audio_key += 1
                elif txt_ia:
                    res = AIManager.process_nlp(txt_ia, mkt, cats)
            
            if res:
                if "error" in res:
                    st.error(res['error'])
                else:
                    # Confirmação antes de salvar
                    with st.expander("Confirme os dados extraídos", expanded=True):
                        c_edit_1, c_edit_2 = st.columns(2)
                        n_amt = c_edit_1.number_input("Valor", value=float(res['amount']))
                        n_cat = c_edit_2.selectbox("Categoria", cats, index=cats.index(res['category']) if res['category'] in cats else 0)
                        n_desc = st.text_input("Descrição", value=res['description'])
                        
                        if st.button("Confirmar e Salvar"):
                            db.add_transaction(user, datetime.now(FUSO_BR), n_amt, n_cat, n_desc, res['type'])
                            st.success("Salvo!")
                            time.sleep(1)
                            st.rerun()

    # Tab 4: Metas
    with t4:
        metas_df = db.get_budgets(user)
        # (Código de visualização de metas similar ao original, mas usando db robusto)
        # Para brevidade, inserindo lógica simplificada mas funcional
        c_add, c_view = st.columns([1, 2])
        with c_add:
            st.markdown("#### Definir Meta")
            m_cat = st.selectbox("Categoria", db.get_user_categories(user), key="m_cat")
            m_val = st.number_input("Limite Mensal", min_value=1.0)
            if st.button("Salvar Meta"):
                db.upsert_budget(user, m_cat, m_val)
                st.rerun()
                
        with c_view:
            if not metas_df.empty and start_date and end_date:
                curr_df = db.get_dataframe(user, start_date=start_date, end_date=end_date)
                spending = curr_df[curr_df['type']=='Despesa'].groupby('category')['amount'].sum()
                
                for _, r in metas_df.iterrows():
                    cat, lim = r['category'], r['limit_amount']
                    spent = spending.get(cat, 0.0)
                    pct = (spent / lim) * 100 if lim > 0 else 0
                    st.write(f"**{cat}** (R$ {spent:.0f} / R$ {lim:.0f})")
                    st.progress(min(pct/100, 1.0), text=f"{pct:.1f}%")

    # Tab 5: Extrato
    with t5:
        df_ex = db.get_dataframe(user, start_date=start_date, end_date=end_date, limit=100)
        if not df_ex.empty:
            # Grid interativo simples
            st.dataframe(
                df_ex[['date', 'type', 'category', 'description', 'amount']],
                column_config={
                    "amount": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Exportação
            csv = df_ex.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar CSV", csv, "extrato.csv", "text/csv")
            
            # Ação de Excluir
            st.divider()
            del_id = st.number_input("ID para excluir", min_value=0, step=1)
            if st.button("🗑️ Excluir Item pelo ID"):
                if db.delete_transaction(del_id, user):
                    st.success("Item apagado.")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("Sem lançamentos.")

if __name__ == "__main__":
    main()