"""
Astra Agent — NL → SQL → Explanation using Claude Haiku
"""
import re
import json
import os
from pathlib import Path
import anthropic

# Load .env if present (no dependency on python-dotenv)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# Load from Streamlit secrets if available (Streamlit Cloud)
try:
    import streamlit as st
    _key = st.secrets.get("ANTHROPIC_API_KEY")
    if _key:
        os.environ["ANTHROPIC_API_KEY"] = _key
except Exception:
    pass

MODEL = "claude-haiku-4-5-20251001"

SCHEMA = """
-- E-commerce brasileiro · DuckDB · 2024-2026

CREATE TABLE produtos (
    id INTEGER,
    nome VARCHAR,          -- Nome do produto
    categoria VARCHAR,     -- Eletrônicos | Roupas | Casa & Jardim | Beleza | Esportes | Livros | Alimentos | Brinquedos
    preco DECIMAL(10,2)    -- Preço unitário em R$
);

CREATE TABLE clientes (
    id INTEGER,
    nome VARCHAR,
    estado VARCHAR,        -- UF (SP, RJ, MG ...)
    cidade VARCHAR
);

CREATE TABLE pedidos (
    id INTEGER,
    cliente_id INTEGER,
    data DATE,             -- 2024-01-01 a 2026-04-29
    status VARCHAR,        -- entregue | cancelado | em_transito | processando
    canal_venda VARCHAR,   -- marketplace | site_proprio | app | televendas
    forma_pagamento VARCHAR, -- pix | cartao_credito | boleto | cartao_debito
    valor_total DECIMAL(10,2),
    estado VARCHAR,        -- UF do cliente
    cidade VARCHAR
);

CREATE TABLE itens_pedido (
    id INTEGER,
    pedido_id INTEGER,
    produto_id INTEGER,    -- FK → produtos.id
    quantidade INTEGER,
    preco_unitario DECIMAL(10,2)
);

-- Dicas DuckDB:
--   STRFTIME('%Y-%m', data)        → período mensal
--   DATE_TRUNC('month', data)      → truncar para mês
--   YEAR(data) = 2024              → filtrar ano
--   SUM(quantidade * preco_unitario) → faturamento pelos itens
"""

SQL_SYSTEM = f"""Você é um especialista em SQL e DuckDB. Converta perguntas em português para SQL válido.

{SCHEMA}

Responda APENAS com JSON válido (sem markdown, sem ```):
{{
    "sql": "SELECT ...",
    "chart": {{
        "type": "bar|line|pie|horizontal_bar",
        "x": "coluna_eixo_x_ou_nome",
        "y": "coluna_eixo_y_ou_valor",
        "title": "Título do Gráfico",
        "x_label": "Label X",
        "y_label": "Label Y"
    }}
}}

Regras SQL:
- Use aliases descritivos (AS faturamento, AS total_pedidos, etc.)
- Para top N: ORDER BY col DESC LIMIT N
- Para meses: STRFTIME('%Y-%m', data) AS mes
- Para % de categorias: calcule proporção com subquery ou window function
- Cancelas: WHERE status = 'cancelado'
- Ticket médio: AVG(valor_total)
- Tipo de gráfico:
  * "line"           → séries temporais, evolução por mês/ano
  * "horizontal_bar" → rankings e top-N (produtos, cidades, estados, categorias) — USE SEMPRE que o eixo for um nome/label
  * "pie"            → proporções e participações percentuais (máx 8 fatias)
  * "bar"            → comparação entre poucos períodos ou grupos numéricos (ex: trimestres)
"""

EXPLAIN_SYSTEM = """Você é o Astra, analista de dados de IA especializado em e-commerce brasileiro.
Responda sempre em português do Brasil. Seja objetivo, perspicaz e use dados concretos quando disponíveis.
Máximo 3 parágrafos. Destaque tendências, picos ou anomalias relevantes.
Comece com uma resposta direta à pergunta, depois adicione contexto e insights.
IMPORTANTE: Não use markdown. Sem asteriscos, sem negrito, sem itálico, sem #, sem listas com - ou *. Texto puro."""

CLASSIFY_SYSTEM = """Classifique se a pergunta requer consulta SQL ao banco de dados ou não.
Responda APENAS com uma palavra: "sql" ou "chat".

"sql"  → métricas, rankings, faturamento, produtos, pedidos, clientes, categorias, estados, datas, comparações, totais
"chat" → saudações, quem você é, o que você faz, quais dados/tabelas/bases você tem, como usar, ajuda, explicações sobre o sistema

Exemplos sql:
"quais produtos mais vendidos?" → sql
"faturamento mensal de 2024" → sql
"top 5 cidades" → sql
"cancelamentos por mês" → sql

Exemplos chat:
"quais dados você tem?" → chat
"quais bases de dados você tem?" → chat
"o que você pode analisar?" → chat
"o que você faz?" → chat
"me explica as tabelas" → chat
"quais tabelas existem?" → chat
"quem é você?" → chat
"olá" → chat
"como funciona?" → chat"""

CHAT_SYSTEM = f"""Você é o Astra, um analista de dados de IA para e-commerce brasileiro.
Responda de forma amigável e útil em português do Brasil.
IMPORTANTE: Não use markdown. Sem asteriscos, sem negrito, sem itálico, sem #, sem listas com - ou *. Texto puro.

Você tem acesso a um banco de dados DuckDB local com os seguintes dados de uma empresa de e-commerce:
{SCHEMA}

Diga ao usuário o que você pode fazer, quais análises são possíveis, e incentive-o a fazer perguntas sobre os dados.
Seja conciso (máx 3 parágrafos). Não invente dados — apenas explique as capacidades e o schema disponível."""


class AstraAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def _call(self, system: str, user: str, max_tokens: int = 1024) -> str:
        msg = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()

    @staticmethod
    def _strip_markdown(text: str) -> str:
        text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
        text = re.sub(r'_{1,2}(.+?)_{1,2}', r'\1', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
        return text.strip()

    @staticmethod
    def _is_meta_question(question: str) -> bool:
        """Fast keyword check — avoids LLM call for obvious conversational questions."""
        q = question.lower().strip()
        meta_keywords = [
            "quais dados", "que dados", "quais tabelas", "que tabelas",
            "quais bases", "que bases", "tem acesso", "vc tem", "você tem",
            "o que faz", "o que vc faz", "o que você faz", "como funciona",
            "quem é você", "quem é vc", "me explica", "como usar",
            "o que pode", "oque pode", "o que consegue", "que análises",
            "quais análises", "me conta", "suas capacidades", "sua função",
            "olá", "oi ", "^oi$", "tudo bem", "bom dia", "boa tarde", "boa noite",
        ]
        return any(kw in q for kw in meta_keywords)

    def _is_sql_question(self, question: str) -> bool:
        if self._is_meta_question(question):
            return False
        result = self._call(CLASSIFY_SYSTEM, question, max_tokens=5)
        return result.strip().lower().startswith("sql")

    def generate_sql(self, question: str) -> dict:
        raw = self._call(SQL_SYSTEM, question)
        raw = re.sub(r"```(?:json)?", "", raw).strip("` \n")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Claude não retornou JSON válido:\n{raw}")

    def generate_explanation(self, question: str, sql: str, results_preview: str) -> str:
        prompt = (
            f"Pergunta: {question}\n\n"
            f"SQL executado:\n{sql}\n\n"
            f"Amostra dos resultados:\n{results_preview}"
        )
        return self._strip_markdown(self._call(EXPLAIN_SYSTEM, prompt, max_tokens=600))

    def chat(self, question: str) -> dict:
        """Respond to conversational questions without querying the database."""
        answer = self._strip_markdown(self._call(CHAT_SYSTEM, question, max_tokens=400))
        return {"type": "chat", "explanation": answer}

    def analyze(self, question: str, conn) -> dict:
        """Full data analysis: classify → SQL → execute → explain."""
        try:
            if not self._is_sql_question(question):
                return self.chat(question)

            config = self.generate_sql(question)
            if "sql" not in config:
                return self.chat(question)

            sql = config["sql"]
            chart_cfg = config.get("chart", {})
            df = conn.execute(sql).df()
            preview = df.head(15).to_string(index=False)
            explanation = self.generate_explanation(question, sql, preview)

            return {
                "type": "data",
                "explanation": explanation,
                "sql": sql,
                "chart_config": chart_cfg,
                "dataframe": df,
            }
        except Exception:
            try:
                return self.chat(question)
            except Exception:
                return {
                    "type": "chat",
                    "explanation": "Não consegui processar essa pergunta. Tente perguntar sobre vendas, produtos, faturamento, pedidos ou clientes.",
                }
