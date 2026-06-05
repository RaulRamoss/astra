# -*- coding: utf-8 -*-
"""
Astra Agent - NL -> SQL -> Explanation using Claude Haiku
"""
import re
import json
import os
from pathlib import Path
import anthropic

# Load .env if present
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

MODEL = "claude-haiku-4-5-20251001"

SCHEMA = (
    "CREATE TABLE produtos (id INTEGER, nome VARCHAR, categoria VARCHAR, preco DECIMAL(10,2));\n"
    "CREATE TABLE clientes (id INTEGER, nome VARCHAR, estado VARCHAR, cidade VARCHAR);\n"
    "CREATE TABLE pedidos (id INTEGER, cliente_id INTEGER, data DATE, status VARCHAR,\n"
    "  canal_venda VARCHAR, forma_pagamento VARCHAR, valor_total DECIMAL(10,2),\n"
    "  estado VARCHAR, cidade VARCHAR);\n"
    "CREATE TABLE itens_pedido (id INTEGER, pedido_id INTEGER, produto_id INTEGER,\n"
    "  quantidade INTEGER, preco_unitario DECIMAL(10,2));\n"
    "-- status: entregue | cancelado | em_transito | processando\n"
    "-- canal_venda: marketplace | site_proprio | app | televendas\n"
    "-- forma_pagamento: pix | cartao_credito | boleto | cartao_debito\n"
    "-- categoria: Eletronicos | Roupas | Casa & Jardim | Beleza | Esportes | Livros | Alimentos | Brinquedos\n"
    "-- datas: 2024-01-01 a 2026-04-29\n"
)

SQL_SYSTEM = (
    "Voce e um especialista em SQL e DuckDB. Converta perguntas em portugues para SQL valido.\n\n"
    + SCHEMA +
    "\nResponda APENAS com JSON valido (sem markdown):\n"
    '{"sql": "SELECT ...", "chart": {"type": "bar|line|pie|horizontal_bar", '
    '"x": "col", "y": "col", "title": "titulo", "x_label": "lx", "y_label": "ly"}}\n\n'
    "Regras:\n"
    "- Use aliases descritivos (AS faturamento, AS total_pedidos)\n"
    "- Top N: ORDER BY col DESC LIMIT N\n"
    "- Meses: STRFTIME('%Y-%m', data) AS mes\n"
    "- line: series temporais; horizontal_bar: rankings/top-N; pie: proporcoes; bar: periodos\n"
)

EXPLAIN_SYSTEM = (
    "Voce e o Astra, analista de dados de IA especializado em e-commerce brasileiro.\n"
    "Responda em portugues do Brasil. Seja objetivo e use dados concretos.\n"
    "Maximo 3 paragrafos. Destaque tendencias, picos ou anomalias.\n"
    "Nao use markdown. Texto puro apenas."
)

CLASSIFY_SYSTEM = (
    "Classifique se a pergunta requer SQL ou nao. Responda APENAS: sql ou chat.\n"
    "sql -> metricas, rankings, faturamento, produtos, pedidos, clientes, datas\n"
    "chat -> saudacoes, quem voce e, o que faz, quais dados tem, como usar\n"
)

CHAT_SYSTEM = (
    "Voce e o Astra, analista de dados de IA para e-commerce brasileiro.\n"
    "Responda em portugues do Brasil de forma amigavel e util.\n"
    "Nao use markdown. Texto puro. Maximo 3 paragrafos.\n"
    "Voce analisa dados de produtos, clientes, pedidos e faturamento de um e-commerce brasileiro."
)

META_KEYWORDS = [
    "quais dados", "que dados", "quais tabelas", "que tabelas",
    "quais bases", "que bases", "tem acesso", "vc tem", "voce tem",
    "o que faz", "como funciona", "quem e voce", "quem e vc",
    "me explica", "como usar", "o que pode", "que analises",
    "quais analises", "suas capacidades", "ola", "tudo bem",
    "bom dia", "boa tarde", "boa noite",
]


class AstraAgent:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def _call(self, system, user, max_tokens=1024):
        msg = self.client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text.strip()

    @staticmethod
    def _strip_markdown(text):
        text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
        text = re.sub(r'_{1,2}(.+?)_{1,2}', r'\1', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
        return text.strip()

    def _is_sql_question(self, question):
        q = question.lower().strip()
        if any(kw in q for kw in META_KEYWORDS):
            return False
        result = self._call(CLASSIFY_SYSTEM, question, max_tokens=5)
        return result.strip().lower().startswith("sql")

    def generate_sql(self, question):
        raw = self._call(SQL_SYSTEM, question)
        raw = re.sub(r"```(?:json)?", "", raw).strip("` \n")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError("JSON invalido: " + raw)

    def generate_explanation(self, question, sql, results_preview):
        prompt = "Pergunta: " + question + "\n\nSQL:\n" + sql + "\n\nResultados:\n" + results_preview
        return self._strip_markdown(self._call(EXPLAIN_SYSTEM, prompt, max_tokens=600))

    def chat(self, question):
        answer = self._strip_markdown(self._call(CHAT_SYSTEM, question, max_tokens=400))
        return {"type": "chat", "explanation": answer}

    def analyze(self, question, conn):
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
                    "explanation": "Erro ao processar. Tente perguntar sobre vendas, produtos, faturamento ou clientes.",
                }
