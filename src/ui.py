# Arquivo: src/ui.py
import streamlit as st

class UIManager:
    """Gerencia a interface visual idêntica ao original (v9.43.0)."""
    
    @staticmethod
    def inject_global_css():
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
            html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }
            .main { background-color: #0E1117; }
            
            /* Estilo do Container de Login (Faltava este) */
            .login-container {
                background: linear-gradient(145deg, #1E1E1E, #252525);
                padding: 45px;
                border-radius: 24px;
                border: 1px solid #333;
                box-shadow: 0 20px 50px rgba(0,0,0,0.5);
                text-align: center;
                margin-top: 60px;
            }
            
            /* Animações de Mercado */
            @keyframes flashGreen {
                0% { border-color: #4CAF50; box-shadow: 0 0 15px rgba(76, 175, 80, 0.5); }
                100% { border-color: #2C2F38; box-shadow: none; }
            }
            @keyframes flashRed {
                0% { border-color: #F44336; box-shadow: 0 0 15px rgba(244, 67, 54, 0.5); }
                100% { border-color: #2C2F38; box-shadow: none; }
            }

            .market-card { 
                background-color: #121318; 
                border: 1px solid #2C2F38; 
                border-radius: 24px; 
                padding: 16px; 
                text-align: center;
                position: relative;
                overflow: hidden; 
                height: 100px;
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            }
            .up-trend { animation: flashGreen 2s ease-out; }
            .down-trend { animation: flashRed 2s ease-out; }

            .market-card:hover { transform: translateY(-5px); border-color: #888; }
            
            .label-coin { font-size: 11px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; z-index: 2; position: relative; }
            .value-coin { font-size: 24px; font-weight: 700; color: #fff; z-index: 2; position: relative; }
            
            /* Cards de KPI (Dashboard) */
            .kpi-card {
                background-color: #1F2129;
                padding: 24px;
                border-radius: 24px;
                border-left: 6px solid #4CAF50;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                transition: transform 0.2s;
            }
            .kpi-card:hover { transform: scale(1.01); }
            .kpi-label { font-size: 13px; color: #aaa; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; }
            .kpi-value { font-size: 32px; font-weight: 600; margin-top: 8px; letter-spacing: -0.5px; }
            
            /* Botões e Inputs */
            div.stButton > button { border-radius: 50px; font-weight: 600; padding: 0.6rem 2rem; border: none; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
            div.stButton > button:hover { transform: translateY(-2px); }
            
            div[data-baseweb="input"] > div { border-radius: 12px !important; background-color: #121318 !important; border: 1px solid #333 !important; color: white !important; }
            div[data-baseweb="input"] > div:focus-within { border-color: #4CAF50 !important; }
            div[data-testid="stToast"] { border-radius: 16px !important; background-color: #262730 !important; border: 1px solid #333 !important; }
            </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def get_svg_chart(is_up=True):
        """Gráfico SVG de fundo dos cards (Idêntico ao original)."""
        color = "#4CAF50" if is_up else "#F44336"
        fill_color = "rgba(76, 175, 80, 0.15)" if is_up else "rgba(244, 67, 54, 0.15)"
        
        if is_up:
            pts = "0,80 20,60 40,70 60,30 80,40 100,10"
            area = "0,100 0,80 20,60 40,70 60,30 80,40 100,10 100,100"
        else:
            pts = "0,20 20,40 40,30 60,70 80,60 100,90"
            area = "0,100 0,20 20,40 40,30 60,70 80,60 100,90 100,100"
        
        return f"""
        <svg viewBox="0 0 100 100" style="position:absolute; bottom:-5px; left:0; width:100%; height:60%; opacity:0.3;" preserveAspectRatio="none">
            <polygon points="{area}" fill="{fill_color}" />
            <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
        </svg>
        """

    @staticmethod
    def format_money(value, hidden=False):
        if hidden: return "R$ ****"
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")