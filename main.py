import streamlit as st
import sys
import os
import logging

# Configuração de Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import locale

# Importações
from src.database import RobustDatabase
from src.ai_engine import AIManager
from src.ui import UIManager
from src.utils import get_market_data, DocGenerator
from src.services.transaction_service import TransactionService

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importação Segura do Módulo OFX
try:
    from src.services.ofx_importer import parse_ofx_file
except ImportError:
    parse_ofx_file = None 

# Configuração de Localização
try: locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try: locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except: pass

st.set_page_config(
    page_title="SmartWallet Personal Pro",
    page_icon="💲", 
    layout="wide",
    initial_sidebar_state="expanded"
)

FUSO_BR = pytz.timezone('America/Sao_Paulo')
CATEGORIAS_BASE = ["Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", "Salário", "Investimentos", "Educação", "Viagem", "Compras", "Assinaturas", "Presentes", "Outros"]

THEMES = {
    "🟢 Verde": "#4CAF50",
    "🔵 Azul": "#2962FF",
    "🟣 Roxo": "#9C27B0",
    "🔴 Vermelho": "#F44336",
    "🟠 Laranja": "#FF6D00",
    "🔘 Cinza": "#607D8B",
    "🟡 Dourado": "#FFD700"
}

def get_contrast_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.5 else "#FFFFFF"

@st.fragment(run_every=10) 
def header_relogio(mkt, theme_color):
    now = datetime.now(FUSO_BR)
    d_str = now.strftime("%A, %d de %B de %Y").title()
    t_map = {"Monday":"Segunda","Tuesday":"Terça","Wednesday":"Quarta","Thursday":"Quinta","Friday":"Sexta","Saturday":"Sábado","Sunday":"Domingo","January":"Janeiro","February":"Fevereiro","March":"Março","April":"Abril","May":"Maio","June":"Junho","July":"Julho","August":"Agosto","September":"Setembro","October":"Outubro","November":"Novembro","December":"Dezembro"}
    for en, pt in t_map.items(): 
        if en in d_str: d_str = d_str.replace(en, pt)
    
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"### <span style='color:{theme_color}'>{d_str}</span> | {now.strftime('%H:%M:%S')}", unsafe_allow_html=True)
    st_ico = "🟢" if "online" in mkt.get('status', 'offline') else "🔴"
    c2.caption(f"{st_ico} Conexão: {mkt.get('status', 'OFFLINE').upper()}")

def main():
    db = RobustDatabase()
    try:
        service = TransactionService()
    except Exception as e:
        st.error(f"Critical Error: {e}"); return
    
    AIManager.configure()
    
    if 'audio_key' not in st.session_state: st.session_state.audio_key = 0
    if 'history_mkt' not in st.session_state: st.session_state.history_mkt = {}
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'user' not in st.session_state: st.session_state.user = None
    if 'manual_form' not in st.session_state: st.session_state.manual_form = {}
    if 'chat_history' not in st.session_state: st.session_state.chat_history = []
    if 'theme_choice' not in st.session_state: st.session_state.theme_choice = "🟢 Verde"

    # --- LOGIN ---
    if not st.session_state.logged_in:
        UIManager.inject_global_css("#4CAF50", "#FFFFFF")
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
                with st.form("login"):
                    u = st.text_input("Usuário")
                    p = st.text_input("Senha", type="password")
                    if st.form_submit_button("Acessar", use_container_width=True):
                        if db.login(u.strip(), p.strip()):
                            st.session_state.logged_in = True
                            st.session_state.user = u.strip()
                            db.process_recurring_items(u.strip())
                            st.rerun()
                        else: st.error("Credenciais inválidas.")
            with st.expander("Primeiro Acesso"):
                nu, np = st.text_input("Novo Usuário"), st.text_input("Nova Senha", type="password")
                if st.button("Registrar"): 
                    ok, msg = db.register(nu.strip(), np.strip())
                    if ok: st.success(msg) 
                    else: st.error(msg)
        return

    # --- APP ---
    user = st.session_state.user
    user_cats = db.get_categories(user)
    
    with st.sidebar:
        logo_path = None
        for file in ["logo.png", "logo.jpg", "logo.jpeg"]:
            if os.path.exists(file): logo_path = file; break
        if logo_path: st.logo(logo_path, icon_image=logo_path)
        else: st.title("💲 SmartWallet")
        st.info(f"Usuário: **{user}**")
        st.divider()
        st.markdown("### 🎨 Aparência")
        selected_theme_name = st.selectbox("Escolha um Tema", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme_choice))
        if selected_theme_name != st.session_state.theme_choice:
            st.session_state.theme_choice = selected_theme_name
            st.rerun()
        primary_color = THEMES[st.session_state.theme_choice]
        text_contrast = get_contrast_color(primary_color)
        st.divider()
        st.markdown("### 📅 Filtro")
        filter_mode = st.radio("Modo", ["Mês Atual", "Personalizado"], horizontal=True, label_visibility="collapsed")
        start_date, end_date = None, None
        if filter_mode == "Mês Atual":
            today = datetime.now(FUSO_BR).date()
            start_date = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
            st.caption(f"{start_date.strftime('%d/%m')} até {end_date.strftime('%d/%m')}")
        else:
            d_range = st.date_input("Intervalo", [], format="DD/MM/YYYY")
            if len(d_range) == 2: start_date, end_date = d_range
            else: st.warning("Defina início e fim.")
        st.divider()
        with st.expander("⚙️ Categorias"):
            new_cat = st.text_input("Nova Categoria")
            if st.button("Adicionar"):
                if db.add_category(user, new_cat): st.success("OK!"); time.sleep(0.5); st.rerun()
            del_cat = st.selectbox("Remover", [c for c in user_cats if c not in CATEGORIAS_BASE])
            if st.button("Excluir"): db.delete_category(user, del_cat); st.rerun()
        st.divider()
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    UIManager.inject_global_css(primary_color, text_contrast)

    mkt = get_market_data()
    header_relogio(mkt, primary_color)
    
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

    try:
        df_global = service.get_statement(user, limit=None)
    except Exception as e:
        st.error(f"Error: {e}"); df_global = pd.DataFrame()
    
    if not df_global.empty:
        df_global['date'] = pd.to_datetime(df_global['date'], errors='coerce')
        df_global = df_global.sort_values('date', ascending=False)
    
    tabs = st.tabs(["🤖 IA Rápida", "✍️ Manual", "📊 Dashboard", "💰 Investimentos", "🎯 Metas", "📑 Extrato", "🧠 Coach"])

    with tabs[0]:
        st.markdown(f"""<div style="margin-bottom: 20px;"><h2 style="font-weight: 600; color: {primary_color};">Assistente Financeiro</h2><p style="color: #888;">Registro por voz ou texto com Inteligência Artificial.</p></div>""", unsafe_allow_html=True)
        with st.container(border=True):
            c_input, c_mic = st.columns([5, 1], vertical_alignment="bottom")
            with c_input:
                with st.form("ia_text", clear_on_submit=True):
                    txt = st.text_input("Comando", placeholder="Ex: Gastei 50 no Uber...", label_visibility="collapsed")
                    submitted_text = st.form_submit_button("Processar", type="primary", use_container_width=True)
            with c_mic:
                audio_val = st.audio_input("🎙️", label_visibility="collapsed", key=f"audio_{st.session_state.audio_key}")

            if audio_val:
                with st.spinner("Ouvindo..."):
                    res = AIManager.process_audio_nlp(audio_val, mkt, user_cats, history_df=df_global)
                    if "error" not in res:
                        result = service.register_transaction(user, datetime.now(FUSO_BR), res['amount'], res['category'], res['description'], res['type'])
                        if result.is_success:
                            st.toast(f"✅ {res['type']}: R$ {res['amount']}"); st.session_state.audio_key += 1; time.sleep(1); st.rerun()
                        else: st.error(result.error)
                    else: st.error(res['error'])
            elif submitted_text and txt:
                with st.spinner("Processando..."):
                    res = AIManager.process_nlp(txt, mkt, user_cats, history_df=df_global)
                    if "error" not in res:
                        result = service.register_transaction(user, datetime.now(FUSO_BR), res['amount'], res['category'], res['description'], res['type'])
                        if result.is_success:
                            st.toast(f"✨ Registrado: {res['description']}"); time.sleep(1); st.rerun()
                        else: st.error(result.error)
                    else: st.error(res['error'])

    with tabs[1]:
        # --- SEÇÃO DE IMPORTAÇÃO OFX ---
        st.markdown("### 📥 Importação Automática (OFX)")
        with st.expander("📂 Clique para importar Extrato Bancário", expanded=False):
            if parse_ofx_file:
                up_ofx = st.file_uploader("Arquivo .OFX do Banco", type=["ofx"], key="ofx_up")
                if up_ofx:
                    if st.button("Processar Arquivo", type="primary"):
                        with st.spinner("Lendo extrato..."):
                            transacoes = parse_ofx_file(up_ofx)
                            
                            if not transacoes:
                                st.warning("Nenhuma transação encontrada ou erro ao ler arquivo.")
                            else:
                                count = 0
                                for tr in transacoes:
                                    # [CORREÇÃO SÊNIOR] Respeita o tipo definido no importer
                                    tipo_final = tr['type']  
                                    cat_final = "Outros"
                                    
                                    res = service.register_transaction(
                                        user, tr['date'], tr['amount'], cat_final, 
                                        tr['description'], tipo_final
                                    )
                                    if res.is_success: count += 1
                                
                                st.success(f"{count} transações importadas com sucesso!")
                                time.sleep(1.5)
                                st.rerun()
            else:
                st.error("Módulo 'ofx_importer' não carregado ou dependências faltando (instale 'ofxparse').")

        st.divider()
        
        st.markdown("### ✍️ Lançamento Manual")
        c1, c2 = st.columns(2)
        default_val = st.session_state.manual_form.get('amount', 0.0)
        default_desc = st.session_state.manual_form.get('desc', "")
        with c1:
            tp = st.radio("Tipo", ["Despesa", "Receita"], horizontal=True)
            vl = st.number_input("Valor", min_value=0.01, value=max(0.01, float(default_val)))
        with c2:
            ct = st.selectbox("Categoria", user_cats)
            ds = st.text_input("Descrição", value=default_desc)
        uploaded_file = st.file_uploader("Comprovante", type=['png', 'jpg', 'jpeg', 'pdf'])
        is_rec = st.checkbox("Recorrência Mensal")
        l_date = st.date_input("Data", datetime.now(FUSO_BR), format="DD/MM/YYYY")
        if st.button("Confirmar Lançamento"):
            result = service.register_transaction(user, datetime.combine(l_date, datetime.now(FUSO_BR).time()), vl, ct, ds, tp, uploaded_file)
            if result.is_success:
                if is_rec: db.add_recurring(user, ct, vl, ds, tp, l_date.day)
                st.toast("Sucesso!", icon="💾"); st.session_state.manual_form = {}; time.sleep(1); st.rerun()
            else: st.error(result.error)

    with tabs[2]:
        if start_date and end_date:
            c_tit, c_eye = st.columns([6, 1])
            c_tit.subheader("Visão Geral")
            priv = c_eye.toggle("👁️", value=False)
            inc, exp, bal = service.get_balance_view(user, start_date, end_date)
            k1, k2, k3 = st.columns(3)
            with k1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Entradas</div><div class="kpi-value" style="color:#4CAF50">{UIManager.format_money(inc, priv)}</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Saídas</div><div class="kpi-value" style="color:#F44336">{UIManager.format_money(exp, priv)}</div></div>', unsafe_allow_html=True)
            with k3: 
                cor_saldo = primary_color if bal >= 0 else "#F44336"
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">Saldo</div><div class="kpi-value" style="color:{cor_saldo}">{UIManager.format_money(bal, priv)}</div></div>', unsafe_allow_html=True)
            st.divider()
            if not df_global.empty:
                mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
                df_dash = df_global.loc[mask]
            else: df_dash = pd.DataFrame()
            if not df_dash.empty:
                df_exp = df_dash[df_dash['type']=='Despesa']
                if not df_exp.empty:
                    c_ch, c_li = st.columns([1.5, 1])
                    with c_ch:
                        grp = df_exp.groupby('category')['amount'].sum().reset_index()
                        grp['fmt'] = grp['amount'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        fig = px.pie(grp, values='amount', names='category', hole=0.6, 
                                     color_discrete_sequence=px.colors.qualitative.Pastel, custom_data=['fmt'])
                        fig.update_traces(textposition='outside', hovertemplate='<b>%{label}</b><br>%{customdata[0]}<br>(%{percent})')
                        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="white", height=400, margin=dict(t=30, b=80, l=20, r=20), showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
                        st.plotly_chart(fig, use_container_width=True)
                    with c_li:
                        st.markdown("##### 🏆 Maiores Gastos")
                        top = df_exp.groupby('category')['amount'].sum().sort_values(ascending=False).head(5)
                        for c, v in top.items(): 
                            st.write(f"**{c}**")
                            st.progress(min(v/exp, 1.0) if exp>0 else 0, text=f"{UIManager.format_money(v, priv)}")
                    st.divider()
                    st.subheader("📊 Histórico e Evolução")
                    dt_trend_start = end_date - timedelta(days=180)
                    mask_trend = (df_global['date'].dt.date >= dt_trend_start) & (df_global['date'].dt.date <= end_date)
                    df_trend = df_global.loc[mask_trend]
                    df_trend_exp = df_trend[df_trend['type'] == 'Despesa'].copy()
                    if not df_trend_exp.empty:
                        df_trend_exp['mes_ano'] = df_trend_exp['date'].dt.strftime('%Y-%m')
                        df_trend_exp['mes_exibicao'] = df_trend_exp['date'].dt.strftime('%b/%Y').str.title()
                        df_grouped = df_trend_exp.groupby(['mes_ano', 'mes_exibicao', 'category'])['amount'].sum().reset_index().sort_values('mes_ano')
                        fig_bar = px.bar(df_grouped, x='mes_exibicao', y='amount', color='category', barmode='group', text_auto='.2s', color_discrete_sequence=px.colors.qualitative.Pastel)
                        fig_bar.update_traces(hovertemplate='<b>%{x}</b><br>%{data.name}<br><b>R$ %{y:,.2f}</b><extra></extra>')
                        fig_bar.update_layout(xaxis_title=None, yaxis_title=None, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white", legend_title_text="", hovermode="x unified", height=400)
                        fig_bar.update_yaxes(gridcolor='#333')
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else: st.info("Sem histórico suficiente.")
                else: st.info("Sem despesas no período.")
            else: st.warning("Sem dados.")
        else: st.info("Selecione um período.")

    with tabs[3]:
        st.subheader("Carteira de Ativos")
        if not df_global.empty:
            invs = df_global[df_global['category'].str.contains("Invest", case=False, na=False)].sort_values('date', ascending=False)
            if not invs.empty:
                tot = invs[invs['type']=='Receita']['amount'].sum() - invs[invs['type']=='Despesa']['amount'].sum()
                cor_inv = primary_color if tot >= 0 else "#F44336"
                st.markdown(f'<div class="kpi-card" style="margin-bottom:20px"><div class="kpi-label">Posição Estimada</div><div class="kpi-value" style="color:{cor_inv}">{UIManager.format_money(tot)}</div></div>', unsafe_allow_html=True)
                @st.dialog("Remover Ativo")
                def modal_del_inv(tid):
                    st.write("Confirmar exclusão?")
                    c_a, c_b = st.columns(2)
                    if c_a.button("Sim", key=f"s_{tid}", type="primary"): service.delete_transaction(tid, user); st.rerun()
                    if c_b.button("Não", key=f"n_{tid}"): st.rerun()
                for _, r in invs.iterrows():
                    c1,c2,c3,c4,c5 = st.columns([1.5, 2, 4, 2, 1])
                    lbl, cor = ("📤 Aporte", "orange") if r['type'] == 'Despesa' else ("📥 Resgate/Saldo", "green")
                    c1.caption(r['date'].strftime('%d/%m %H:%M'))
                    c2.markdown(f":{cor}[**{lbl}**]")
                    c3.write(r['description'])
                    c4.write(UIManager.format_money(r['amount']))
                    if c5.button("🗑️", key=f"d_inv_{r['id']}"): modal_del_inv(r['id'])
                    st.markdown("---")
            else: st.info("Carteira vazia.")
        else: st.info("Carteira vazia.")

    with tabs[4]:
        c_h, c_b = st.columns([4,1])
        c_h.markdown("#### Monitoramento de Metas")
        @st.dialog("Nova Meta")
        def modal_meta():
            ct = st.selectbox("Categoria", user_cats)
            lm = st.number_input("Limite (R$)", min_value=1.0, step=50.0, value=100.0)
            if st.button("Salvar"): db.set_meta(user, ct, lm); st.rerun()
        @st.dialog("Excluir Meta")
        def delete_meta_dialog(cat):
            st.write(f"Remover meta de **{cat}**?"); 
            if st.button("Confirmar", type="primary"): db.delete_meta(user, cat); st.rerun()
        if c_b.button("➕ Adicionar"): modal_meta()
        metas = db.get_metas(user)
        if not metas.empty and start_date and end_date:
            mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
            atual = df_global.loc[mask] if not df_global.empty else pd.DataFrame()
            gastos = atual[atual['type']=='Despesa'].groupby('category')['amount'].sum()
            cols = st.columns(3) 
            for idx, r in metas.iterrows():
                c, l = r['category'], r['limit_amount']
                s = gastos.get(c, 0.0)
                pct = s / l if l > 0 else 0
                bar_color = primary_color if pct < 0.75 else "#FFC107" if pct < 1.0 else "#FF5252"
                fig = go.Figure(go.Indicator(mode = "gauge+number", value = s, number = {'prefix': "R$ ", 'font': {'family': "Poppins", 'color': "white", 'size': 24}}, title = {'text': f"<span style='color:{primary_color}; font-size:1.4em'><b>{c}</b></span><br><span style='color:#888; font-size:0.8em'>Meta: {l:.0f}</span>"}, gauge = {'axis': {'range': [None, max(l, s*1.1)], 'visible': False}, 'bar': {'color': bar_color, 'thickness': 0.2}, 'bgcolor': "rgba(0,0,0,0)", 'borderwidth': 0, 'threshold': {'line': {'color': "white", 'width': 2}, 'thickness': 0.2, 'value': l}}))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=30, r=30, t=50, b=20), height=220)
                with cols[idx % 3]:
                    st.plotly_chart(fig, use_container_width=True)
                    if st.button("🗑️", key=f"dm_{idx}"): delete_meta_dialog(c)
        else: st.info("Defina metas.")

    with tabs[5]:
        with st.container(border=True):
            b1, b2 = st.columns(2)
            if not df_global.empty:
                b1.download_button("📥 Excel", DocGenerator.to_excel(df_global).getvalue(), "extrato.xlsx")
                if start_date and end_date:
                    mask = (df_global['date'].dt.date >= start_date) & (df_global['date'].dt.date <= end_date)
                    mes = df_global.loc[mask]
                    if not mes.empty:
                        i, e, _ = service.get_balance_view(user, start_date, end_date)
                        
                        # --- GERAÇÃO DE PDF SEGURA ---
                        pdf_data = DocGenerator.to_pdf(user, mes, i, e, i-e, f"{start_date} - {end_date}")
                        if pdf_data: 
                            b2.download_button("📄 PDF", pdf_data, "relatorio.pdf")
                        else:
                            # Se falhar, mostra aviso, mas não quebra
                            b2.warning("PDF indisponível (verifique logs/dados).")
        st.divider()
        if not df_global.empty:
            v = df_global.head(50) 
            @st.dialog("Apagar Registro")
            def confirm_del_row(tid):
                st.write("Irreversível."); 
                if st.button("Apagar", type="primary"): service.delete_transaction(tid, user); st.rerun()
            for _, r in v.iterrows():
                c1,c2,c3,c4,c5,c6 = st.columns([1.5, 1.5, 2, 2, 2, 1])
                val_fmt = f"R$ {r['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                cor = "green" if r['type']=='Receita' else "red"
                c1.caption(r['date'].strftime('%d/%m %H:%M'))
                c2.write(r['type']); c3.write(r['category']); c4.write(r['description'])
                c5.markdown(f":{cor}[{val_fmt}]")
                with c6:
                    if st.button("🗑️", key=f"del_{r['id']}"): confirm_del_row(r['id'])
                st.markdown("---")
            @st.dialog("RESETAR CONTA")
            def confirm_nuke():
                st.error("Apagar TUDO?"); 
                if st.button("CONFIRMAR", type="primary"): db.nuke_data(user); st.rerun()
            if st.button("⚠️ Resetar Dados"): confirm_nuke()
        else: st.info("Vazio.")

    with tabs[6]:
        c_head, c_trash = st.columns([5, 1])
        c_head.markdown("#### 🧠 Coach Financeiro")
        
        @st.dialog("Limpar Conversa")
        def confirm_clear_chat():
            if st.button("Sim", type="primary"): st.session_state.chat_history = []; st.rerun()

        if c_trash.button("🗑️", help="Limpar Chat"): confirm_clear_chat()

        if st.button("Analisar Finanças", type="primary"):
            with st.spinner("Analisando..."):
                inc_t, _, _ = service.get_balance_view(user, start_date, end_date)
                rep = AIManager.coach_financeiro(df_global.head(50), inc_t, mkt)
                st.session_state.chat_history.append({"role": "assistant", "content": rep})
                st.rerun()
        
        st.divider()
        
        chat_container = st.container()
        if p := st.chat_input("Dúvida?"):
            st.session_state.chat_history.append({"role":"user", "content":p})
            with st.spinner("Pensando..."):
                res = AIManager.chat_with_docs(p, df=df_global)
            st.session_state.chat_history.append({"role":"assistant", "content":res})
            st.rerun()
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): 
                    st.markdown(msg["content"])

if __name__ == "__main__":
    main()
