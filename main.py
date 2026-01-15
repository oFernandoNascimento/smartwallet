import streamlit as st
import sys
import os

# Adiciona o diretório raiz ao path do Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import locale

from src.database import RobustDatabase
from src.ai_engine import AIManager
from src.ui import UIManager
from src.utils import get_market_data, DocGenerator
from src.services.transaction_service import TransactionService

# Configuração de Localização
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try: locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except: pass

# Configuração da Página
st.set_page_config(
    page_title="SmartWallet Personal Pro",
    page_icon="💲", 
    layout="wide",
    initial_sidebar_state="expanded"
)

FUSO_BR = pytz.timezone('America/Sao_Paulo')
CATEGORIAS_BASE = ["Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", "Salário", "Investimentos", "Educação", "Viagem", "Compras", "Assinaturas", "Presentes", "Outros"]

@st.fragment(run_every=10) 
def header_relogio(mkt):
    """Componente de cabeçalho com relógio e status de conexão."""
    now = datetime.now(FUSO_BR)
    d_str = now.strftime("%A, %d de %B de %Y").title()
    
    t_map = {
        "Monday":"Segunda","Tuesday":"Terça","Wednesday":"Quarta","Thursday":"Quinta","Friday":"Sexta","Saturday":"Sábado","Sunday":"Domingo",
        "January":"Janeiro","February":"Fevereiro","March":"Março","April":"Abril","May":"Maio","June":"Junho","July":"Julho","August":"Agosto","September":"Setembro","October":"Outubro","November":"Novembro","December":"Dezembro"
    }
    if "Monday" in d_str or "January" in d_str or "," in d_str: 
        for en, pt in t_map.items(): d_str = d_str.replace(en, pt)
    
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"### {d_str} | {now.strftime('%H:%M:%S')}")
    st_ico = "🟢" if "online" in mkt.get('status', 'offline') else "🔴"
    c2.caption(f"{st_ico} Conexão: {mkt.get('status', 'OFFLINE').upper()}")

def main():
    UIManager.inject_global_css()
    
    db = RobustDatabase()
    try:
        service = TransactionService()
    except Exception as e:
        st.error(f"Erro ao iniciar serviços: {e}")
        return
    
    AIManager.configure()
    
    # Inicialização de estado da sessão
    if 'audio_key' not in st.session_state: st.session_state.audio_key = 0
    if 'history_mkt' not in st.session_state: st.session_state.history_mkt = {}
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'user' not in st.session_state: st.session_state.user = None
    if 'manual_form' not in st.session_state: st.session_state.manual_form = {}
    if 'chat_history' not in st.session_state: st.session_state.chat_history = []

    # Tela de Login
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            with st.container(border=True):
                logo_path = None
                for file in ["logo.png", "logo.jpg", "logo.jpeg"]:
                    if os.path.exists(file): logo_path = file; break
                if logo_path:
                    cl, cm, cr = st.columns([1, 1, 1])
                    with cm: st.image(logo_path, use_container_width=True)
                
                st.markdown('<h2 style="text-align: center; color: #4CAF50;">SmartWallet Personal</h2>', unsafe_allow_html=True)
                st.markdown('<p style="text-align: center; color: #888;">Seu dinheiro, sob controle.</p>', unsafe_allow_html=True)
                
                with st.form("login"):
                    u = st.text_input("Usuário")
                    p = st.text_input("Senha", type="password")
                    if st.form_submit_button("Entrar no Sistema", use_container_width=True):
                        if db.login(u.strip(), p.strip()):
                            st.session_state.logged_in = True
                            st.session_state.user = u.strip()
                            rec_count = db.process_recurring_items(u.strip())
                            if rec_count > 0: st.toast(f"{rec_count} contas processadas!", icon="🔄")
                            st.rerun()
                        else: st.error("Dados incorretos.")
            with st.expander("Primeiro acesso?"):
                nu, np = st.text_input("Criar Usuário"), st.text_input("Criar Senha", type="password")
                if st.button("Registrar Conta"): 
                    ok, msg = db.register(nu.strip(), np.strip()); 
                    if ok: st.success(msg) 
                    else: st.error(msg)
        return

    # Área Logada
    user = st.session_state.user
    user_cats = db.get_categories(user)
    
    with st.sidebar:
        logo_path = None
        for file in ["logo.png", "logo.jpg", "logo.jpeg"]:
            if os.path.exists(file): logo_path = file; break
        if logo_path: st.logo(logo_path, icon_image=logo_path)
        else: st.title("💲 SmartWallet")
            
        st.info(f"Olá, **{user}**!")
        st.divider()
        
        st.markdown("### 📅 Filtro de Período")
        filter_mode = st.radio("Modo", ["Mês Atual", "Personalizado"], horizontal=True)
        start_date, end_date = None, None
        
        if filter_mode == "Mês Atual":
            today = datetime.now(FUSO_BR).date()
            start_date = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
            st.caption(f"De: {start_date.strftime('%d/%m')} até {end_date.strftime('%d/%m')}")
        else:
            d_range = st.date_input("Selecione o intervalo", [], format="DD/MM/YYYY")
            if len(d_range) == 2: start_date, end_date = d_range
            else: st.warning("Selecione data inicial e final.")

        st.divider()
        with st.expander("⚙️ Gerenciar Categorias"):
            new_cat = st.text_input("Nova Categoria")
            if st.button("Adicionar"):
                if db.add_category(user, new_cat): st.success(f"'{new_cat}' OK!"); time.sleep(1); st.rerun()
            
            del_cat = st.selectbox("Excluir Categoria", [c for c in user_cats if c not in CATEGORIAS_BASE])
            
            @st.dialog("Excluir Categoria?")
            def confirm_del_cat(cat_name):
                st.write(f"Tem certeza que deseja apagar a categoria **{cat_name}**?")
                c1, c2 = st.columns(2)
                if c1.button("Sim, Excluir", type="primary", key="s_cat"):
                    db.delete_category(user, cat_name)
                    st.rerun()
                if c2.button("Cancelar", key="n_cat"): st.rerun()

            if st.button("Excluir"):
                confirm_del_cat(del_cat)

        st.divider()
        if st.button("Sair da Conta"): st.session_state.logged_in = False; st.rerun()

    mkt = get_market_data()
    header_relogio(mkt)
    
    # Ticker de Mercado
    mc1, mc2, mc3, mc4 = st.columns(4)
    assets = [("USD", "Dólar", "$"), ("EUR", "Euro", "€"), ("GBP", "Libra", "£"), ("BTC", "Bitcoin", "₿")]
    for i, (k, n, s) in enumerate(assets):
        val = mkt.get(k, 0.0)
        prev_val = st.session_state.history_mkt.get(k, val)
        is_up = val >= prev_val 
        st.session_state.history_mkt[k] = val 
        trend_class = "up-trend" if is_up else "down-trend"
        with [mc1, mc2, mc3, mc4][i]:
            svg = UIManager.get_svg_chart(is_up)
            st.markdown(f"""<div class="market-card {trend_class}">{svg}<div class="label-coin">{n}</div><div class="value-coin">{s} {UIManager.format_money(val).replace('R$ ','')}</div></div>""", unsafe_allow_html=True)
    st.divider()

    # Carregamento de Dados Globais
    try:
        df_global = service.get_statement(user, limit=None)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        df_global = pd.DataFrame()
    
    if not df_global.empty:
        df_global['date'] = pd.to_datetime(df_global['date'], errors='coerce')
        df_global = df_global.sort_values('date', ascending=False)
    
    tabs = st.tabs(["🤖 IA Rápida", "✍️ Manual", "📊 Dashboard", "💰 Investimentos", "🎯 Metas", "📑 Extrato", "🧠 Coach"])

    # Aba 1: IA Rápida
    with tabs[0]:
        st.markdown("""<div style="margin-bottom: 20px;"><h2 style="font-weight: 600; color: #fff;">💬 Assistente Financeiro</h2><p style="color: #888; font-size: 14px;">Digite ou grave um áudio.</p></div>""", unsafe_allow_html=True)
        with st.container(border=True):
            st.info("💡 **Dicas:** 'Gastei 50 no Uber', 'Recebi 2000 de pix', 'Comprei mouse por 25 dolares'")
            c_input, c_mic = st.columns([5, 1], vertical_alignment="bottom")
            with c_input:
                with st.form("ia_text", clear_on_submit=True):
                    txt = st.text_input("O que aconteceu?", placeholder="Digite aqui...", label_visibility="collapsed")
                    submitted_text = st.form_submit_button("Enviar Texto", type="primary", use_container_width=True)
            with c_mic:
                audio_val = st.audio_input("🎙️ Gravar", label_visibility="visible", key=f"audio_{st.session_state.audio_key}")

            if audio_val:
                with st.spinner("🎙️ Processando áudio..."):
                    res = AIManager.process_audio_nlp(audio_val, mkt, user_cats, history_df=df_global)
                    if "error" not in res:
                        result = service.register_transaction(user, datetime.now(FUSO_BR), res['amount'], res['category'], res['description'], res['type'])
                        
                        if result.is_success:
                            st.toast(f"{res['type']} de R$ {res['amount']} registrada!", icon="✅"); st.session_state.audio_key += 1; time.sleep(1.0); st.rerun()
                        else:
                            st.error(result.error)
                    else: st.error(res['error'])
            elif submitted_text and txt:
                with st.spinner("🤖 Lendo texto..."):
                    res = AIManager.process_nlp(txt, mkt, user_cats, history_df=df_global)
                    if "error" not in res:
                        result = service.register_transaction(user, datetime.now(FUSO_BR), res['amount'], res['category'], res['description'], res['type'])
                        
                        if result.is_success:
                            ico = "🚀" if res.get('source') == "Local/Regex" else "✨"
                            st.toast(f"{res['type']} de R$ {res['amount']} registrada!", icon=ico)
                            time.sleep(1.5); st.rerun()
                        else:
                            st.error(result.error)
                    else: st.error(res['error'])

    # Aba 2: Manual
    with tabs[1]:
        c1, c2 = st.columns(2)
        default_val = st.session_state.manual_form.get('amount', 0.01)
        default_desc = st.session_state.manual_form.get('desc', "")
        default_cat = st.session_state.manual_form.get('cat', user_cats[0])
        if default_cat not in user_cats: default_cat = user_cats[0]
        with c1:
            tp = st.radio("Tipo", ["Despesa", "Receita"], horizontal=True)
            vl = st.number_input("Valor (R$)", min_value=0.01, value=max(0.01, float(default_val)))
        with c2:
            ct = st.selectbox("Categoria", user_cats, index=user_cats.index(default_cat))
            ds = st.text_input("Descrição", value=default_desc)
        uploaded_file = st.file_uploader("Anexar Comprovante", type=['png', 'jpg', 'jpeg', 'pdf'])
        is_rec = st.checkbox("🔄 Repetir todo mês")
        
        l_date = st.date_input("Data do Registro", datetime.now(FUSO_BR), format="DD/MM/YYYY")

        if st.button("Salvar Registro"):
            result = service.register_transaction(
                user_id=user,
                date_val=datetime.combine(l_date, datetime.now(FUSO_BR).time()),
                amount=vl,
                category=ct,
                description=ds,
                type_=tp,
                proof_file=uploaded_file
            )
            
            if result.is_success:
                if is_rec: db.add_recurring(user, ct, vl, ds, tp, l_date.day)
                st.toast(result.data, icon="💾") 
                st.session_state.manual_form = {}
                time.sleep(1)
                st.rerun()
            else:
                st.error(result.error)

    # Aba 3: Dashboard
    with tabs[2]:
        if start_date and end_date:
            c_tit, c_eye = st.columns([6, 1])
            c_tit.subheader(f"Visão Geral: {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}")
            priv = c_eye.toggle("👁️", value=False)
            
            inc, exp, bal = service.get_balance_view(user, start_date, end_date)
            
            k1, k2, k3 = st.columns(3)
            with k1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Entrou</div><div class="kpi-value" style="color:#4CAF50">{UIManager.format_money(inc, priv)}</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Saiu</div><div class="kpi-value" style="color:#F44336">{UIManager.format_money(exp, priv)}</div></div>', unsafe_allow_html=True)
            with k3: 
                cor = "#4CAF50" if bal >= 0 else "#F44336"
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">Saldo</div><div class="kpi-value" style="color:{cor}">{UIManager.format_money(bal, priv)}</div></div>', unsafe_allow_html=True)
            st.divider()
            
            if not df_global.empty:
                mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
                df_dash = df_global.loc[mask]
            else:
                df_dash = pd.DataFrame(columns=df_global.columns)

            if not df_dash.empty:
                df_exp = df_dash[df_dash['type']=='Despesa']
                if not df_exp.empty:
                    c_ch, c_li = st.columns([1.5, 1])
                    with c_ch:
                        grp = df_exp.groupby('category')['amount'].sum().reset_index()
                        grp['fmt'] = grp['amount'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        fig = px.pie(grp, values='amount', names='category', hole=0.6, color_discrete_sequence=px.colors.qualitative.Pastel, custom_data=['fmt'])
                        fig.update_traces(hovertemplate='<b>%{label}</b><br>Gasto: %{customdata[0]}<br>(%{percent})<extra></extra>')
                        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white", height=350, margin=dict(t=20, b=20))
                        st.plotly_chart(fig, use_container_width=True)
                    with c_li:
                        st.markdown("##### 🏆 Top Gastos")
                        top = df_exp.groupby('category')['amount'].sum().sort_values(ascending=False).head(5)
                        for c, v in top.items(): st.write(f"**{c}**"); st.progress(min(v/exp, 1.0) if exp>0 else 0, text=f"{UIManager.format_money(v, priv)}")
                else: st.info("Sem despesas.")
            else: st.warning("Sem dados.")
        else: st.info("👈 Selecione um período.")

    # Aba 4: Investimentos
    with tabs[3]:
        st.subheader("💰 Carteira de Investimentos")
        df_all = df_global
        
        if not df_all.empty:
            invs = df_all[df_all['category'].str.contains("Invest", case=False, na=False)]
            if not invs.empty:
                invs = invs.sort_values('date', ascending=False)
                tot = invs[invs['type']=='Receita']['amount'].sum() - invs[invs['type']=='Despesa']['amount'].sum()
                st.markdown(f'<div class="kpi-card" style="margin-bottom:20px"><div class="kpi-label">Total Acumulado</div><div class="kpi-value" style="color:#4CAF50">{UIManager.format_money(tot)}</div></div>', unsafe_allow_html=True)
                st.markdown("---")
                
                @st.dialog("Excluir Investimento?")
                def modal_del_inv(tid):
                    st.write("Tem certeza que deseja apagar este registro?")
                    c_a, c_b = st.columns(2)
                    if c_a.button("Sim, Excluir", key=f"s_inv_{tid}", type="primary"):
                        service.delete_transaction(tid, user)
                        st.rerun()
                    if c_b.button("Não", key=f"n_inv_{tid}"):
                        st.rerun()

                for _, r in invs.iterrows():
                    c1,c2,c3,c4,c5 = st.columns([1.5, 2, 4, 2, 1])
                    
                    label_acao = "Transação"
                    cor_texto = "white"
                    desc_low = str(r['description']).lower()
                    
                    if r['type'] == 'Despesa':
                        label_acao = "📤 Aporte" # Saiu da conta -> Foi pro investimento
                        cor_texto = "orange"
                    else:
                        if "saldo" in desc_low or "tenho" in desc_low:
                            label_acao = "💰 Saldo Atual"
                            cor_texto = "green"
                        elif "resgate" in desc_low or "retirei" in desc_low or "saque" in desc_low:
                            label_acao = "📥 Resgate"
                            cor_texto = "blue"
                        else:
                            label_acao = "💰 Saldo/Entrada"
                            cor_texto = "green"

                    data_fmt = r['date'].strftime('%d/%m %H:%M') if pd.notnull(r['date']) else "--/--"
                    
                    c1.caption(data_fmt)
                    c2.markdown(f":{cor_texto}[**{label_acao}**]")
                    c3.write(r['description'])
                    c4.write(UIManager.format_money(r['amount']))
                    
                    if c5.button("🗑️", key=f"del_inv_{r['id']}"):
                        modal_del_inv(r['id'])
                        
                    st.markdown("---")
            else: st.info("Nenhum registro em 'Investimentos'.")
        else: st.info("Sem dados.")

    # Aba 5: Metas
    with tabs[4]:
        c_h, c_b = st.columns([4,1])
        c_h.markdown("#### 🎯 Metas de Gastos")
        @st.dialog("Definir Meta")
        def modal_meta():
            ct = st.selectbox("Categoria", user_cats)
            lm = st.number_input("Limite Mensal (R$)", min_value=1.0, step=50.0, value=100.0)
            if st.button("Salvar Meta"): db.set_meta(user, ct, lm); st.rerun()
        
        @st.dialog("Excluir Meta?")
        def delete_meta_dialog(category):
            st.write(f"Excluir meta de **{category}**?"); 
            c1, c2 = st.columns(2)
            if c1.button("Sim, Excluir", type="primary", key=f"sim_m_{category}"):
                db.delete_meta(user, category)
                st.rerun()
            if c2.button("Não", key=f"nao_m_{category}"): st.rerun()

        if c_b.button("➕ Nova Meta"): modal_meta()
        
        metas = db.get_metas(user)
        if not metas.empty and start_date and end_date:
            if not df_global.empty:
                mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
                atual = df_global.loc[mask]
            else:
                atual = pd.DataFrame(columns=df_global.columns)

            gastos = atual[atual['type']=='Despesa'].groupby('category')['amount'].sum()
            cols = st.columns(3) 
            for idx, r in metas.iterrows():
                c, l = r['category'], r['limit_amount']
                s = gastos.get(c, 0.0)
                pct = s / l if l > 0 else 0
                bar_color = "#4CAF50" if pct < 0.75 else "#FFC107" if pct < 1.0 else "#FF5252"

                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = s,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    number = {'prefix': "R$ ", 'font': {'family': "Poppins", 'color': "white", 'size': 26}},
                    title = {'text': f"<span style='font-size:1.8em; color: #4CAF50'><b>{c}</b></span><br><span style='font-size:0.9em;color:#888'>Meta: R$ {l:,.0f}</span>", 'align': "center"},
                    gauge = {
                        'axis': {'range': [None, max(l, s*1.1)], 'visible': False},
                        'bar': {'color': bar_color, 'thickness': 0.25}, 
                        'bgcolor': "rgba(0,0,0,0)", 'borderwidth': 0,
                        'threshold': {'line': {'color': "white", 'width': 2}, 'thickness': 0.25, 'value': l}
                    }
                ))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white", 'family': "Poppins"}, height=250, margin=dict(l=25, r=25, t=50, b=20))
                
                with cols[idx % 3]:
                    c_chart, c_trash = st.columns([0.85, 0.15])
                    with c_trash:
                        if st.button("🗑️", key=f"btn_del_{idx}", help="Excluir Meta"): delete_meta_dialog(c)
                    with c_chart: st.plotly_chart(fig, use_container_width=True)
        else: st.info("Defina metas e selecione um período.")

    # Aba 6: Extrato
    with tabs[5]:
        with st.container(border=True):
            st.markdown("### 🗂️ Central de Arquivos")
            b1, b2 = st.columns(2)
            full = df_global
            if not full.empty:
                exc = DocGenerator.to_excel(full)
                b1.download_button("📥 Baixar Excel", exc.getvalue(), "controle.xlsx")
                if start_date and end_date:
                    mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
                    mes = df_global.loc[mask]
                    
                    if not mes.empty:
                        i, e, _ = service.get_balance_view(user, start_date, end_date)
                        pdf = DocGenerator.to_pdf(user, mes, i, e, i-e, f"Periodo: {start_date} a {end_date}")
                        if pdf: b2.download_button("📄 Baixar PDF", pdf, "relatorio.pdf")
                        else: b2.warning("⚠️ PDF indisponível (instale 'fpdf')")

        st.divider()
        opt = st.selectbox("Ordenar:", ["Recentes", "Antigos", "Maior Valor"])
        
        if start_date and end_date and not df_global.empty:
            mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
            v = df_global.loc[mask]
        elif not df_global.empty:
            v = df_global.head(20)
        else:
            v = pd.DataFrame(columns=df_global.columns)
        
        if not v.empty:
            if opt == "Recentes": v = v.sort_values('date', ascending=False)
            elif opt == "Antigos": v = v.sort_values('date', ascending=True)
            else: v = v.sort_values('amount', ascending=False)

            @st.dialog("Excluir Transação?")
            def confirm_del_row(tid):
                st.write("Tem certeza que deseja apagar este registro permanentemente?")
                c1, c2 = st.columns(2)
                if c1.button("Sim, Apagar", type="primary", key=f"s_row_{tid}"):
                    service.delete_transaction(tid, user)
                    st.rerun()
                if c2.button("Cancelar", key=f"n_row_{tid}"): st.rerun()

            st.markdown("---")
            for _, r in v.iterrows():
                c1,c2,c3,c4,c5,c6 = st.columns([1.5, 1.5, 2, 2, 2, 1])
                data_fmt = r['date'].strftime('%d/%m %H:%M') if pd.notnull(r['date']) else "--/--"
                val = f"R$ {r['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                tipo_display = r['type']
                if str(tipo_display).lower() in ['expense', 'outcome']: tipo_display = 'Despesa'
                elif str(tipo_display).lower() in ['income', 'entry']: tipo_display = 'Receita'
                
                cor = "green" if tipo_display=='Receita' else "red"
                sig = "+" if tipo_display=='Receita' else "-"
                
                c1.caption(data_fmt); c2.write(tipo_display); c3.write(r['category']); c4.write(r['description'])
                with c5:
                    st.markdown(f":{cor}[{sig} {val}]")
                    if r.get('proof_data'):
                        try: st.download_button("📎", bytes(r['proof_data']), file_name=r['proof_name'] or "comprovante", key=f"dl_{r['id']}")
                        except: pass
                with c6:
                    if st.button("🔄", key=f"clone_{r['id']}"):
                        st.session_state.manual_form = {'amount': r['amount'], 'desc': r['description'], 'cat': r['category']}
                        st.toast("Copiado!", icon="📋")
                    if st.button("🗑️", key=f"del_{r['id']}"): 
                        confirm_del_row(r['id'])
                st.markdown("---")
            
            @st.dialog("⚠️ PERIGO: APAGAR TUDO?")
            def confirm_nuke():
                st.error("Isso vai apagar TODAS as suas transações, metas e histórico.")
                st.write("Tem certeza absoluta? Essa ação não pode ser desfeita.")
                c1, c2 = st.columns(2)
                if c1.button("SIM, APAGAR TUDO", type="primary", key="nuke_yes"):
                    db.nuke_data(user)
                    st.rerun()
                if c2.button("CANCELAR", key="nuke_no"): st.rerun()

            if st.button("⚠️ Resetar Conta"): 
                confirm_nuke()
        else: st.info("Vazio.")

    # Aba 7: Coach
    with tabs[6]:
        c_head, c_trash = st.columns([5, 1])
        c_head.markdown("#### 🧠 Coach Financeiro")
        
        @st.dialog("Limpar Chat?")
        def confirm_clear_chat():
            st.write("Deseja apagar todo o histórico da conversa?")
            c1, c2 = st.columns(2)
            if c1.button("Sim", type="primary", key="s_chat"):
                st.session_state.chat_history = []
                st.rerun()
            if c2.button("Não", key="n_chat"): st.rerun()

        if c_trash.button("🗑️ Limpar", help="Apagar histórico do chat", key="btn_clear_chat"):
            confirm_clear_chat()

        if st.button("Analisar minhas finanças", type="primary"):
            with st.spinner("O Coach está analisando seu perfil..."):
                df_coach = df_global.head(50) if not df_global.empty else pd.DataFrame()
                inc_t, _, _ = service.get_balance_view(user, start_date, end_date)
                
                rep = AIManager.coach_financeiro(df_coach, inc_t, mkt)
                
                st.markdown(f'<div style="background:#262730;padding:25px;border-radius:15px;border-left:5px solid #8e44ad;">{rep}</div>', unsafe_allow_html=True)
        
        st.divider()
        st.caption("Ou converse com seu assistente financeiro abaixo:")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
        if p := st.chat_input("Pergunte algo..."):
            st.session_state.chat_history.append({"role":"user", "content":p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("Consultando..."):
                    res = AIManager.chat_with_docs(p, df=df_global)
                    st.markdown(res)
            st.session_state.chat_history.append({"role":"assistant", "content":res})

if __name__ == "__main__":
    main()