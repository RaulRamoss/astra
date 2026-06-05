"""
Astra — Your AI Data Analyst
TCC FIAP · Streamlit + DuckDB + Claude Haiku
"""
import os
import base64
import traceback
from pathlib import Path
import sqlparse

import duckdb
import streamlit as st
from PIL import Image

from agent import AstraAgent
from charts import create_chart

# ── Page config ───────────────────────────────────────────────────────────────
_logo_path = Path(__file__).parent / "assets" / "logo.png"
_page_icon = Image.open(_logo_path) if _logo_path.exists() else "🚀"

st.set_page_config(
    page_title="Astra",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ─── Hide Streamlit chrome (header, toolbar, footer) ─── */
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"]      { display: none !important; }
[data-testid="stDecoration"]   { display: none !important; }
[data-testid="stBottom"] {
    background: transparent !important;
    border-top: none !important;
    box-shadow: none !important;
}
footer { display: none !important; }
.block-container { padding-top: 2rem !important; }

/* ─── Background: black → purple radial gradient ─── */
.stApp {
    background:
        radial-gradient(ellipse at 90% 100%, rgba(109, 40, 217, 0.35) 0%, transparent 55%),
        radial-gradient(ellipse at 10% 0%,   rgba(76,  29, 149, 0.25) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 80%,  rgba(147, 51, 234, 0.12) 0%, transparent 60%),
        #050008;
}

/* ─── Sidebar ─── */
[data-testid="stSidebar"] {
    background: rgba(10, 0, 25, 0.85) !important;
    border-right: 1px solid rgba(139, 92, 246, 0.2) !important;
    backdrop-filter: blur(12px);
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

/* ─── Sidebar suggestion buttons ─── */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(124, 58, 237, 0.08) !important;
    border: 1px solid rgba(139, 92, 246, 0.35) !important;
    border-radius: 12px !important;
    color: #d8b4fe !important;
    font-size: 0.80rem !important;
    line-height: 1.4 !important;
    padding: 0.5rem 0.75rem !important;
    text-align: center !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(124, 58, 237, 0.25) !important;
    border-color: rgba(167, 139, 250, 0.7) !important;
    color: #f3e8ff !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.3) !important;
}

/* ─── Chat input ─── */
[data-testid="stChatInput"] {
    border: 1px solid rgba(139, 92, 246, 0.4) !important;
    border-radius: 16px !important;
    background: rgba(15, 0, 35, 0.8) !important;
    backdrop-filter: blur(10px) !important;
}
[data-testid="stChatInput"] textarea {
    color: #f3e8ff !important;
}

/* ─── Chat messages ─── */
[data-testid="stChatMessage"] {
    background: rgba(20, 0, 45, 0.6) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 16px !important;
    backdrop-filter: blur(8px) !important;
}

/* ─── Response cards ─── */
.astra-card {
    background: rgba(25, 0, 55, 0.55);
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(10px);
}
.astra-card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #c4b5fd;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(139, 92, 246, 0.2);
}
.astra-answer {
    color: #f1e8ff;
    font-size: 0.95rem;
    line-height: 1.7;
}

/* ─── Welcome screen ─── */
.astra-welcome {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    text-align: center;
}
.astra-welcome h1 {
    font-size: 3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #c084fc, #9333ea, #7c3aed);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
}
.astra-welcome p {
    color: #a78bfa;
    font-size: 1.1rem;
    max-width: 500px;
}

/* ─── Tabs ─── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(20, 0, 45, 0.5) !important;
    border-radius: 10px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    color: #a78bfa !important;
    border-radius: 8px !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(124, 58, 237, 0.3) !important;
    color: #f3e8ff !important;
}

/* ─── Dataframe ─── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(139, 92, 246, 0.2) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ─── Code blocks ─── */
.stCodeBlock {
    border: 1px solid rgba(139, 92, 246, 0.25) !important;
    border-radius: 10px !important;
}

/* ─── Spinner / progress ─── */
.stSpinner > div { border-top-color: #9333ea !important; }

/* ─── Global text ─── */
.stMarkdown p, .stMarkdown li { color: #e2e8f0; }
h1, h2, h3 { color: #f3e8ff; }

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: rgba(20, 0, 45, 0.3); }
::-webkit-scrollbar-thumb { background: rgba(124, 58, 237, 0.5); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    db_path = Path(__file__).parent / "data" / "astra.duckdb"
    if not db_path.exists():
        db_path.parent.mkdir(exist_ok=True)
        with st.spinner("Gerando banco de dados... (só na primeira vez)"):
            from create_database import create_database
            create_database()
    return duckdb.connect(str(db_path), read_only=True)


@st.cache_resource
def get_agent():
    return AstraAgent()


def load_logo() -> str | None:
    logo_path = Path(__file__).parent / "assets" / "logo.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def render_response(data: dict):
    """Render response — chat (text only) or data (4 tabs)."""
    if data.get("type") == "chat":
        (tab1,) = st.tabs(["💬 Resposta"])
        with tab1:
            st.markdown(
                f'<div class="astra-card">'
                f'<div class="astra-card-header">💬 Astra</div>'
                f'<div class="astra-answer">{data["explanation"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
        return

    tab1, tab2, tab3, tab4 = st.tabs(["💬 Resposta", "📊 Gráfico", "🔍 SQL", "📋 Dados"])

    with tab1:
        st.markdown(
            f'<div class="astra-card">'
            f'<div class="astra-card-header">💬 Análise</div>'
            f'<div class="astra-answer">{data["explanation"]}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    with tab2:
        fig = create_chart(data["dataframe"], data["chart_config"])
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with tab3:
        formatted_sql = sqlparse.format(
            data["sql"],
            reindent=True,
            keyword_case="upper",
            indent_width=4,
            wrap_after=80,
        )
        st.code(formatted_sql, language="sql")

    with tab4:
        st.dataframe(data["dataframe"], use_container_width=True, hide_index=True)


def process_question(question: str, conn, agent: AstraAgent):
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="🚀"):
        with st.spinner("Analisando..."):
            try:
                result = agent.analyze(question, conn)
                render_response(result)
                st.session_state.messages.append({"role": "assistant", "content": result})
            except Exception as e:
                fallback = {
                    "type": "chat",
                    "explanation": (
                        "Não consegui processar essa consulta. "
                        "Tente reformular a pergunta ou pergunte sobre vendas, "
                        "produtos, faturamento, pedidos ou clientes."
                    ),
                }
                render_response(fallback)
                st.session_state.messages.append({"role": "assistant", "content": fallback})
                if os.getenv("ASTRA_DEBUG"):
                    st.code(f"{e}\n\n{traceback.format_exc()}")


# ── Constants ─────────────────────────────────────────────────────────────────
SUGGESTIONS = [
    "Quais são os 10 produtos mais vendidos em 2024?",
    "Qual o faturamento mensal de 2025?",
    "Qual categoria gerou mais receita?",
    "Como as vendas se distribuem por estado?",
    "Qual canal de venda tem maior ticket médio?",
    "Quantos pedidos foram cancelados por mês?",
    "Compare o faturamento por forma de pagamento.",
    "Top 5 cidades com mais pedidos.",
]

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Resources ─────────────────────────────────────────────────────────────────
conn = get_connection()
agent = get_agent()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    logo_b64 = load_logo()
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        'style="width:130px;height:130px;object-fit:contain;'
        'filter:drop-shadow(0 0 18px rgba(147,51,234,0.55));">'
        if logo_b64 else '<div style="font-size:4rem;">🚀</div>'
    )
    st.markdown(
        f'''
        <div style="
            display:flex;flex-direction:column;align-items:center;
            text-align:center;padding:1.5rem 0.5rem 1.2rem;gap:0.6rem;
        ">
            {logo_html}
            <div>
                <div style="
                    font-size:1.6rem;font-weight:800;letter-spacing:-0.02em;
                    background:linear-gradient(135deg,#e9d5ff,#a855f7,#7c3aed);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                    background-clip:text;line-height:1.1;
                ">Astra</div>
                <div style="color:#7c3aed;font-size:0.72rem;font-weight:500;
                    letter-spacing:0.05em;margin-top:0.2rem;">
                    Your AI Data Analyst
                </div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(
        '<p style="color:#a78bfa;font-size:0.75rem;font-weight:600;'
        'letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.6rem;">Sugestões</p>',
        unsafe_allow_html=True,
    )

    for suggestion in SUGGESTIONS:
        if st.button(suggestion, key=f"sug_{suggestion[:20]}", use_container_width=True):
            st.session_state.pending_question = suggestion

    st.divider()

    if st.button("🗑️  Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown(
        '<p style="color:#6d28d9;font-size:0.7rem;text-align:center;margin-top:0.5rem;">'
        "Banco: DuckDB local · LLM: Claude Haiku</p>",
        unsafe_allow_html=True,
    )

# ── Main area ─────────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="astra-welcome">
        <h1>Astra</h1>
        <p>O que deseja saber sobre seus dados hoje?</p>
    </div>
    """, unsafe_allow_html=True)

# Replay chat history (text only for user; re-render tabs for assistant)
for msg in st.session_state.messages:
    avatar = "🧑" if msg["role"] == "user" else "🚀"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_response(msg["content"])

# Handle suggestion button clicks
if st.session_state.pending_question:
    q = st.session_state.pending_question
    st.session_state.pending_question = None
    process_question(q, conn, agent)

# Chat input
if prompt := st.chat_input("Faça uma pergunta sobre seus dados..."):
    process_question(prompt, conn, agent)
