"""
Astra Agent -- NL -> SQL -> Explanation using Claude Haiku
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


MODEL = "claude-haiku-4-5-20251001"

SCHEMA = """
-- E-commerce brasileiro - DuckDB - 2024-2026

CREATE TABLE produtos (
    id INTEGER,
    nome VARCHAR,
    categoria VARCHAR,
    preco DECIMAL(10,2)
);

CREATE TABLE clientes (
    id INTEGER,
    nome VARCHAR,
    estado VARCHAR,
    cidade VARCHAR
);

CREATE TABLE pedidos (
    id INTEGER,
    cliente_id INTEGER,
    data DATE,
    status VARCHAR,
    canal_venda VARCHAR,
    forma_pagamento VARCHAR,
    valor_total DECIMAL(10,2),
    estado VARCHAR,
    cidade VARCHAR
);

CREATE TABLE itens_pedido (
    id INTEGER,
    pedido_id INTEGER,
    produto_id INTEGER,
    quantidade INTEGER,
    preco_unitario DECIMAL(10,2)
);
"""

SQL_SYSTEM = f"""Voce e um especialista em SQL e DuckDB. Converta perguntas em portugues para SQL valido.

{SCHEMA}

Responda APENAS com JSON valido (sem markdown, sem ```):
{{
    "sql": "SELECT ...",
    "chart": {{
        "type": "bar|line|pie|horizontal_bar",
        "x": "coluna_eixo_x_ou_nome",
        "y": "coluna_eixo_y_ou_valor",
        "title": "Titulo do Grafico",
        "x_label": "Label X",
        "y_label": "Label Y"
    }}
}}

Regras SQL:
- Use aliases descritivos (AS faturamento, AS total_pedidos, etc.)
- Para top N: ORDER BY col DESC LIMIT N
- Para meses: STRFTIME('%Y-%m', data) AS mes
- Para % de categorias: calcule proporcao com subquery ou window function
- Cancelados: WHERE status = 'cancelado'
- Ticket medio: AVG(valor_total)
- Tipo de grafico:
  * "line"           -> series temporais, evolucao por mes/ano
  * "horizontal_bar" -> rankings e top-N (produtos, cidades, estados, categorias)
  * "pie"            -> proporcoes e participacoes percentuais (max 8 fatias)
  * "bar"            -> comparacao entre poucos periodos ou grupos numericos
"""

EXPLAIN_SYSTEM = """Voce e o Astra, analista de dados de IA especializado em e-commerce brasileiro.
Responda sempre em portugues do Brasil. Seja objetivo, perspicaz e use dados concretos quando disponiveis.
Maximo 3 paragrafos. Destaque tendencias, picos ou anomalias relevantes.
Comece com uma resposta direta a pergunta, depois adicione contexto e insights.
IMPORTANTE: Nao use markdown. Sem asteriscos, sem negrito, sem italico, sem #, sem listas com - ou *. Texto puro."""

CLASSIFY_SYSTEM = """Classifique se a pergunta requer consulta SQL ao banco de dados ou nao.
Responda APENAS com uma palavra: "sql" ou "chat".

"sql"  -> metricas, rankings, faturamento, produtos, pedidos, clientes, categorias, estados, datas, comparacoes, totais
"chat" -> saudacoes, quem voce e, o que voce faz, quais dados/tabelas/bases voce tem, como usar, ajuda

Exemplos sql:
"quais produtos mais vendidos?" -> sql
"faturamento mensal de 2024" -> sql
"top 5 cidades" -> sql

Exemplos chat:
"quais dados voce tem?" -> chat
"o que voce faz?" -> chat
"quem e voce?" -> chat
"ola" -> chat"""

CHAT_SYSTEM = f"""Voce e o Astra, um analista de dados de IA para e-commerce brasileiro.
Responda de forma amigavel e util em portugues do Brasil.
IMPORTANTE: Nao use markdown. Sem asteriscos, sem negrito, sem italico, sem #. Texto puro.

Voce tem acesso a um banco de dados DuckDB com dados de e-commerce: produtos, clientes, pedidos e itens_pedido.
Diga ao usuario o que voce pode fazer e incentive-o a fazer perguntas sobre os dados.
Seja conciso (max 3 paragrafos)."""


class AstraAgent:
    def __init__(self):
        # Load API key from Streamlit secrets if available (Streamlit Cloud)
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
        except Exception:
            pass
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
        q = question.lower().strip()
        meta_keywords = [
            "quais dados", "que dados", "quais tabelas", "que tabelas",
            "quais bases", "que bases", "tem acesso", "vc tem", "voce tem",
            "o que faz", "o que vc faz", "o que voce faz", "como funciona",
            "quem e voce", "quem e vc", "me explica", "como usar",
            "o que pode", "oque pode", "o que consegue", "que analises",
            "quais analises", "me conta", "suas capacidades", "sua funcao",
            "ola", "oi ", "tudo bem", "bom dia", "boa tarde", "boa noite",
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
            raise ValueError(f"Claude nao retornou JSON valido:\n{raw}")

    def generate_explanation(self, question: str, sql: str, results_preview: str) -> str:
        prompt = (
            f"Pergunta: {question}\n\n"
            f"SQL executado:\n{sql}\n\n"
            f"Amostra dos resultados:\n{results_preview}"
        )
        return self._strip_markdown(self._call(EXPLAIN_SYSTEM, prompt, max_tokens=600))

    def chat(self, question: str) -> dict:
        answer = self._strip_markdown(self._call(CHAT_SYSTEM, question, max_tokens=400))
        return {"type": "chat", "explanation": answer}

    def analyze(self, question: str, conn) -> dict:
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
                    "explanation": "Nao consegui processar essa pergunta. Tente perguntar sobre vendas, produtos, faturamento, pedidos ou clientes.",
                }
