import streamlit as st

class UIManager:
    """
    Gerenciador de Interface de Usuário (UI).
    Responsável por injetar CSS global e definir estilos visuais dinâmicos.
    """

    @staticmethod
    def inject_global_css(primary_color="#4CAF50", text_on_primary="#FFFFFF"):
        """
        Injeta CSS personalizado na página com suporte a temas dinâmicos.
        Args:
            primary_color (str): Cor hexadecimal principal do tema.
            text_on_primary (str): Cor do texto sobre a cor principal.
        """
        st.markdown(f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
            
            html, body, [class*="css"] {{
                font-family: 'Poppins', sans-serif;
            }}
            
            /* --- BOTÕES (FORÇA BRUTA) --- */
            div.stButton > button, 
            div.stButton > button:first-child,
            button[kind="primary"],
            div[data-testid="stForm"] button {{
                background-color: {primary_color} !important;
                color: {text_on_primary} !important;
                border: 1px solid {primary_color} !important;
                border-radius: 8px;
                font-weight: 600;
                transition: all 0.3s ease;
            }}

            div.stButton > button:hover, 
            button[kind="primary"]:hover,
            div[data-testid="stForm"] button:hover {{
                opacity: 0.9;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                border-color: {primary_color} !important;
                background-color: {primary_color} !important;
                filter: brightness(110%);
            }}

            div.stButton > button:active, 
            button[kind="primary"]:active {{
                transform: scale(0.98);
            }}

            /* --- INPUTS DE TEXTO (CORREÇÃO DE BORDAS E FOCO) --- */
            /* Remove bordas padrão e aplica estilo dark em inputs e áreas de texto */
            div[data-baseweb="input"] > div,
            div[data-baseweb="textarea"] > div {{
                border-radius: 12px !important;
                background-color: #1E1E1E !important;
                border: 1px solid #333 !important;
                color: white !important;
            }}
            
            /* Quando clica para digitar, a borda e o brilho ficam da COR DO TEMA */
            div[data-baseweb="input"] > div:focus-within,
            div[data-baseweb="textarea"] > div:focus-within {{
                border-color: {primary_color} !important;
                box-shadow: 0 0 0 1px {primary_color} !important;
            }}

            /* Cards de KPI */
            .kpi-card {{
                background-color: #262730;
                padding: 20px;
                border-radius: 10px;
                border-left: 5px solid {primary_color};
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                text-align: center;
                margin-bottom: 10px;
            }}
            .kpi-label {{ font-size: 0.9em; color: #aaa; margin-bottom: 5px; }}
            .kpi-value {{ font-size: 1.6em; font-weight: 600; }}

            /* Cards do Mercado */
            .market-card {{
                background-color: #1E1E1E;
                padding: 10px;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #333;
                transition: transform 0.2s;
            }}
            .market-card:hover {{
                transform: translateY(-3px);
                border-color: {primary_color};
            }}
            .up-trend {{ color: #4CAF50; }} /* Verde lucro (padrão financeiro) */
            .down-trend {{ color: #F44336; }} /* Vermelho prejuízo (padrão financeiro) */
            .label-coin {{ font-size: 0.8em; color: #888; }}
            .value-coin {{ font-size: 1.1em; font-weight: bold; margin-top: 2px; }}

            /* Títulos */
            h1, h2, h3, h4 {{ color: {primary_color} !important; }}
            
            /* Tabs */
            .stTabs [data-baseweb="tab-highlight"] {{ background-color: {primary_color} !important; }}

            /* Ícone de Enviar do Chat */
            div[data-testid="stChatInput"] button {{ color: {primary_color} !important; }}

            /* Spinners e Loaders (Barras de progresso e spinners seguem o tema) */
            div[data-testid="stStatusWidget"] {{ color: {primary_color} !important; }}
            .stProgress > div > div > div {{ background-color: {primary_color} !important; }}
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def format_money(value, hide=False):
        if hide: return "R$ ****"
        try:
            return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "R$ 0,00"

    @staticmethod
    def get_svg_chart(is_up):
        color = "#4CAF50" if is_up else "#F44336"
        path = "M2 20 L10 12 L15 17 L22 5" if is_up else "M2 5 L10 12 L15 8 L22 20"
        return f"""
        <svg width="100%" height="30" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2">
            <path d="{path}" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """