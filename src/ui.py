import streamlit as st
from typing import Union

class UIManager:
    """
    Gerenciador de Interface de Usuário (UI).
    Responsável por injetar CSS customizado, criar componentes visuais e formatar dados.
    """
    
    @staticmethod
    def inject_global_css() -> None:
        """Injeta o CSS global da aplicação para customização visual."""
        try:
            st.markdown("""
                <style>
                @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
                
                /* Tipografia Global */
                html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }
                .main { background-color: #0E1117; }
                
                /* Estilo do Container de Login */
                .login-container {
                    background: linear-gradient(145deg, #1E1E1E, #252525);
                    padding: 45px;
                    border-radius: 24px;
                    border: 1px solid #333;
                    box-shadow: 0 20px 50px rgba(0,0,0,0.5);
                    text-align: center;
                    margin-top: 60px;
                }
                
                /* Animações de Tendência de Mercado */
                @keyframes flashGreen {
                    0% { border-color: #4CAF50; box-shadow: 0 0 15px rgba(76, 175, 80, 0.5); }
                    100% { border-color: #2C2F38; box-shadow: none; }
                }
                @keyframes flashRed {
                    0% { border-color: #F44336; box-shadow: 0 0 15px rgba(244, 67, 54, 0.5); }
                    100% { border-color: #2C2F38; box-shadow: none; }
                }

                /* Cards de Cotação (Ticker) */
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
                
                /* Botões e Inputs Customizados */
                div.stButton > button { border-radius: 50px; font-weight: 600; padding: 0.6rem 2rem; border: none; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
                div.stButton > button:hover { transform: translateY(-2px); }
                
                div[data-baseweb="input"] > div { border-radius: 12px !important; background-color: #121318 !important; border: 1px solid #333 !important; color: white !important; }
                div[data-baseweb="input"] > div:focus-within { border-color: #4CAF50 !important; }
                div[data-testid="stToast"] { border-radius: 16px !important; background-color: #262730 !important; border: 1px solid #333 !important; }
                </style>
            """, unsafe_allow_html=True)
        except Exception:
            pass

    @staticmethod
    def get_svg_chart(is_up: bool = True) -> str:
        """
        Gera o código SVG para o gráfico de fundo dos cards de cotação.
        Args:
            is_up (bool): Define a cor (Verde para alta, Vermelho para baixa).
        Returns:
            str: String HTML contendo o SVG.
        """
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
    def format_money(value: Union[float, int], hidden: bool = False) -> str:
        """
        Formata valores numéricos para o padrão monetário BRL (R$ 1.000,00).
        Args:
            value (float): Valor numérico.
            hidden (bool): Se True, oculta o valor ('R$ ****').
        Returns:
            str: String formatada.
        """
        if hidden: 
            return "R$ ****"
            
        try:
            return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (ValueError, TypeError):
            return "R$ 0,00"
    
    @staticmethod
    def fmt_money(value: Union[float, int]) -> str:
        """Alias para format_money."""
        return UIManager.format_money(value, hidden=False)

    @staticmethod
    def render_market_ticker(mkt: dict):
        """Renderiza o ticker de cotações com base nos dados fornecidos."""
        mc1, mc2, mc3, mc4 = st.columns(4)
        assets = [("USD", "Dólar", "$"), ("EUR", "Euro", "€"), ("GBP", "Libra", "£"), ("BTC", "Bitcoin", "₿")]
        
        history = st.session_state.get('history_mkt', {})
        
        for i, (k, n, s) in enumerate(assets):
            val = mkt.get(k, 0.0)
            prev_val = history.get(k, val)
            is_up = val >= prev_val 
            
            if 'history_mkt' in st.session_state:
                st.session_state.history_mkt[k] = val
                
            trend_class = "up-trend" if is_up else "down-trend"
            
            with [mc1, mc2, mc3, mc4][i]:
                svg = UIManager.get_svg_chart(is_up)
                st.markdown(f"""
                <div class="market-card {trend_class}">
                    {svg}
                    <div class="label-coin">{n}</div>
                    <div class="value-coin">{s} {UIManager.format_money(val).replace('R$ ','')}</div>
                </div>
                """, unsafe_allow_html=True)