# Arquivo: main.py
import streamlit as st
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import os

# Importando módulos da estrutura
from src.database import RobustDatabase
from src.ai_engine import AIManager
from src.ui import UIManager
from src.utils import get_market_data, DocGenerator

# Configuração da página
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
    now = datetime.now(FUSO_BR)
    d_str = now.strftime("%A, %d de %B de %Y")
    t_map = {"Monday":"Segunda","Tuesday":"Terça","Wednesday":"Quarta","Thursday":"Quinta","Friday":"Sexta","Saturday":"Sábado","Sunday":"Domingo",
             "January":"Janeiro","February":"Fevereiro","March":"Março","April":"Abril","May":"Maio","June":"Junho","July":"Julho","August":"Agosto","September":"Setembro","October":"Outubro","November":"Novembro","December":"Dezembro"}
    for en, pt in t_map.items(): d_str = d_str.replace(en, pt)
    
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"### {d_str} | {now.strftime('%H:%M:%S')}")
    st_ico = "🟢" if "online" in mkt.get('status', 'offline') else "🔴"
    c2.caption(f"{st_ico} Conexão: {mkt.get('status', 'OFFLINE').upper()}")

def main():
    UIManager.inject_global_css()
    db = RobustDatabase()
    AIManager.configure()
    
    # Inicialização de Variáveis
    if 'audio_key' not in st.session_state: st.session_state.audio_key = 0
    if 'history_mkt' not in st.session_state: st.session_state.history_mkt = {}
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'user' not in st.session_state: st.session_state.user = None
    if 'manual_form' not in st.session_state: st.session_state.manual_form = {}

    # --- TELA DE LOGIN ---
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

    # --- SISTEMA LOGADO ---
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
            if st.button("Excluir"):
                if db.delete_category(user, del_cat): st.success("Excluída!"); time.sleep(1); st.rerun()

        st.divider()
        if st.button("Sair da Conta"): st.session_state.logged_in = False; st.rerun()

    mkt = get_market_data()
    header_relogio(mkt)
    
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

    tabs = st.tabs(["🤖 IA Híbrida", "✍️ Manual", "📊 Dashboard", "💰 Investimentos", "🎯 Metas", "📑 Extrato", "🧠 Coach"])

    with tabs[0]:
        st.markdown("""<div style="margin-bottom: 20px;"><h2 style="font-weight: 600; color: #fff;">💬 Assistente Híbrido</h2><p style="color: #888; font-size: 14px;">Processamento Dual: Regex (Local/Rápido) + LLM (Gemini).</p></div>""", unsafe_allow_html=True)
        
        # Aviso de Privacidade implementado conforme feedback
        st.caption("🔒 **Privacidade:** Transações complexas podem ser processadas pela API do Google Gemini. Dados sensíveis não são armazenados para treino.")
        
        with st.container(border=True):
            st.info("💡 **Dicas:** 'Gastei 50 no Uber' (Processado Localmente) ou envie áudio para análise complexa.")
            c_input, c_mic = st.columns([5, 1], vertical_alignment="bottom")
            with c_input:
                with st.form("ia_text", clear_on_submit=True):
                    txt = st.text_input("O que aconteceu?", placeholder="Digite aqui...", label_visibility="collapsed")
                    submitted_text = st.form_submit_button("Enviar Texto", type="primary", use_container_width=True)
            with c_mic:
                audio_val = st.audio_input("🎙️ Gravar", label_visibility="visible", key=f"audio_{st.session_state.audio_key}")

            if audio_val:
                with st.spinner("🎙️ Processando áudio (Nuvem)..."):
                    res = AIManager.process_audio_nlp(audio_val, mkt, user_cats)
                    if "error" not in res:
                        db.add_transaction(user, datetime.now(FUSO_BR), res['amount'], res['category'], res['description'], res['type'])
                        st.toast(f"{res['type']} de R$ {res['amount']} registrada!", icon="✅"); st.session_state.audio_key += 1; time.sleep(1.0); st.rerun()
                    else: st.error(res['error'])
            elif submitted_text and txt:
                with st.spinner("⚡ Analisando comando..."):
                    res = AIManager.process_nlp(txt, mkt, user_cats)
                    if "error" not in res:
                        db.add_transaction(user, datetime.now(FUSO_BR), res['amount'], res['category'], res['description'], res['type'])
                        
                        # Feedback visual se foi Local ou IA
                        if res.get("source") == "Local/Regex":
                            st.toast(f"⚡ Processado Localmente (Regex): R$ {res['amount']}", icon="🚀")
                        else:
                            st.toast(f"🤖 Processado via Gemini: R$ {res['amount']}", icon="✨")
                            
                        time.sleep(1.5); st.rerun()
                    else: st.error(res['error'])

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
        if st.button("Salvar Registro"):
            now = datetime.now(FUSO_BR)
            db.add_transaction(user, now, vl, ct, ds, tp, uploaded_file, uploaded_file.name if uploaded_file else None)
            if is_rec: db.add_recurring(user, ct, vl, ds, tp, now.day)
            st.toast("Salvo!", icon="💾"); st.session_state.manual_form = {}; time.sleep(1); st.rerun()

    with tabs[2]:
        if start_date and end_date:
            c_tit, c_eye = st.columns([6, 1])
            c_tit.subheader(f"Visão Geral: {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}")
            priv = c_eye.toggle("👁️", value=False)
            inc, exp = db.get_totals(user, start_date, end_date)
            bal = inc - exp
            k1, k2, k3 = st.columns(3)
            with k1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Entrou</div><div class="kpi-value" style="color:#4CAF50">{UIManager.format_money(inc, priv)}</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Saiu</div><div class="kpi-value" style="color:#F44336">{UIManager.format_money(exp, priv)}</div></div>', unsafe_allow_html=True)
            with k3: 
                cor = "#4CAF50" if bal >= 0 else "#F44336"
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">Saldo</div><div class="kpi-value" style="color:{cor}">{UIManager.format_money(bal, priv)}</div></div>', unsafe_allow_html=True)
            st.divider()
            df_dash = db.fetch_all(user, start_date=start_date, end_date=end_date)
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

    with tabs[3]:
        st.subheader("💰 Carteira de Investimentos")
        df_all = db.fetch_all(user, limit=None)
        if not df_all.empty:
            invs = df_all[df_all['category'].str.contains("Invest", case=False, na=False)]
            if not invs.empty:
                invs['date'] = pd.to_datetime(invs['date'], errors='coerce')
                invs = invs.sort_values('date', ascending=False)
                tot = invs['amount'].sum()
                st.markdown(f'<div class="kpi-card" style="margin-bottom:20px"><div class="kpi-label">Total Acumulado</div><div class="kpi-value" style="color:#4CAF50">{UIManager.format_money(tot)}</div></div>', unsafe_allow_html=True)
                st.markdown("---")
                for _, r in invs.iterrows():
                    c1,c2,c3,c4,c5 = st.columns([1.5, 1.5, 5, 2, 1])
                    data_fmt = r['date'].strftime('%d/%m %H:%M') if pd.notnull(r['date']) else "--/--"
                    val = f"R$ {r['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    cor = "green"
                    sig = "+" if r['type'] != 'Despesa' else ""
                    c1.caption(data_fmt); c2.write("Investiu" if r['type'] == 'Despesa' else "Resgate"); c3.write(r['description']); c4.markdown(f":{cor}[{sig} {val}]")
                    @st.dialog(f"Apagar Investimento?")
                    def modal_del_inv(tid):
                        st.write("Confirmar?"); c_a, c_b = st.columns(2)
                        if c_a.button("Sim", key=f"s_inv_{tid}"): db.remove_transaction(tid, user); st.rerun()
                        if c_b.button("Não", key=f"n_inv_{tid}"): st.rerun()
                    if c5.button("🗑️", key=f"del_inv_{r['id']}"): modal_del_inv(r['id'])
                    st.markdown("---")
            else: st.info("Nenhum registro em 'Investimentos'.")
        else: st.info("Sem dados.")

    with tabs[4]:
        c_h, c_b = st.columns([4,1])
        c_h.markdown("#### 🎯 Metas de Gastos")
        @st.dialog("Definir Meta")
        def modal_meta():
            ct = st.selectbox("Categoria", user_cats)
            lm = st.number_input("Limite Mensal (R$)", 100.0, step=50.0)
            if st.button("Salvar Meta"): db.set_meta(user, ct, lm); st.rerun()
        
        @st.dialog("Excluir Meta?")
        def delete_meta_dialog(category):
            st.write(f"Excluir meta de **{category}**?"); 
            if st.button("Sim", type="primary"): db.delete_meta(user, category); st.rerun()

        if c_b.button("➕ Nova Meta"): modal_meta()
        
        metas = db.get_metas(user)
        if not metas.empty and start_date and end_date:
            atual = db.fetch_all(user, start_date=start_date, end_date=end_date)
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

    with tabs[5]:
        with st.container(border=True):
            st.markdown("### 🗂️ Central de Arquivos")
            b1, b2 = st.columns(2)
            full = db.fetch_all(user, limit=None)
            if not full.empty:
                exc = DocGenerator.to_excel(full)
                b1.download_button("📥 Baixar Excel", exc.getvalue(), "controle.xlsx")
                if start_date and end_date:
                    mes = db.fetch_all(user, start_date=start_date, end_date=end_date)
                    if not mes.empty:
                        i, e = db.get_totals(user, start_date, end_date)
                        pdf = DocGenerator.to_pdf(user, mes, i, e, i-e, f"Periodo: {start_date} a {end_date}")
                        if pdf: b2.download_button("📄 Baixar PDF", pdf, "relatorio.pdf")
                        else: b2.warning("⚠️ PDF indisponível (instale 'fpdf')")

        st.divider()
        opt = st.selectbox("Ordenar:", ["Recentes", "Antigos", "Maior Valor"])
        v = db.fetch_all(user, start_date=start_date, end_date=end_date) if start_date else db.fetch_all(user, limit=20)
        
        if not v.empty:
            v['date'] = pd.to_datetime(v['date'], errors='coerce')
            if opt == "Recentes": v = v.sort_values('date', ascending=False)
            elif opt == "Antigos": v = v.sort_values('date', ascending=True)
            else: v = v.sort_values('amount', ascending=False)

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
                    if st.button("🗑️", key=f"del_{r['id']}"): db.remove_transaction(r['id'], user); st.rerun()
                st.markdown("---")
            if st.button("⚠️ Resetar Conta"): db.nuke_data(user); st.rerun()
        else: st.info("Vazio.")

    with tabs[6]:
        st.markdown("#### 🧠 Coach Financeiro")
        if st.button("Analisar minhas finanças", type="primary"):
            with st.spinner("O Coach está pensando..."):
                df_coach = db.fetch_all(user, limit=50)
                inc_t, _ = db.get_totals(user, start_date, end_date)
                rep = AIManager.coach_financeiro(df_coach, inc_t, mkt)
                st.markdown(f'<div style="background:#262730;padding:25px;border-radius:15px;border-left:5px solid #8e44ad;">{rep}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()