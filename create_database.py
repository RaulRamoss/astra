"""
Astra - Create Database
Run once to generate the DuckDB database with Brazilian e-commerce data.
"""
import duckdb
import random
from datetime import datetime, timedelta
import os

random.seed(42)

# ── Products ──────────────────────────────────────────────────────────────────
PRODUTOS = [
    # (nome, categoria, preco)
    ("iPhone 15 Pro", "Eletrônicos", 5499), ("Samsung Galaxy S24", "Eletrônicos", 3999),
    ("Notebook Dell Inspiron", "Eletrônicos", 3799), ("Notebook Lenovo IdeaPad", "Eletrônicos", 2999),
    ("Fone JBL Tune 770", "Eletrônicos", 379), ("Fone Sony WH-1000XM5", "Eletrônicos", 1599),
    ("Smartwatch Apple Watch SE", "Eletrônicos", 2199), ("Smart TV LG 55\"", "Eletrônicos", 2799),
    ("Mouse Logitech MX Master", "Eletrônicos", 429), ("Teclado Mecânico Redragon", "Eletrônicos", 349),
    ("Monitor LG 27\" 4K", "Eletrônicos", 1899), ("Tablet Samsung Tab A9", "Eletrônicos", 1499),

    ("Camiseta Básica Premium", "Roupas", 59), ("Calça Jeans Slim Fit", "Roupas", 149),
    ("Vestido Midi Floral", "Roupas", 129), ("Moletom Cropped", "Roupas", 119),
    ("Jaqueta Corta-Vento", "Roupas", 199), ("Tênis Nike Air Force 1", "Roupas", 499),
    ("Tênis Adidas Ultraboost", "Roupas", 649), ("Sandália Arezzo Tressê", "Roupas", 249),
    ("Conjunto Esportivo Feminino", "Roupas", 149), ("Blazer Social Slim", "Roupas", 279),

    ("Sofá 3 Lugares Veludo", "Casa & Jardim", 1899), ("Mesa de Jantar 6 Lugares", "Casa & Jardim", 2499),
    ("Cadeira Gamer ThunderX3", "Casa & Jardim", 899), ("Luminária de Piso Tripé", "Casa & Jardim", 349),
    ("Jogo de Cama Queen 400 Fios", "Casa & Jardim", 299), ("Panela de Pressão Elétrica Instant", "Casa & Jardim", 499),
    ("Aspirador Robô Roborock", "Casa & Jardim", 1799), ("Air Fryer Mondial 4L", "Casa & Jardim", 299),

    ("Perfume 212 Carolina Herrera 100ml", "Beleza", 399), ("Kit Skincare Dermage", "Beleza", 259),
    ("Shampoo Kérastase Nutritive", "Beleza", 189), ("Paleta de Sombras Fenty Beauty", "Beleza", 319),
    ("Protetor Solar FPS 70 La Roche", "Beleza", 89), ("Creme Anti-Idade Olay", "Beleza", 149),

    ("Bicicleta MTB Caloi Explorer", "Esportes", 2199), ("Par de Halteres 10kg", "Esportes", 159),
    ("Esteira Elétrica Speedo", "Esportes", 2899), ("Tênis de Corrida Asics Gel", "Esportes", 549),
    ("Bola de Futebol Adidas", "Esportes", 189), ("Raquete de Tênis Wilson", "Esportes", 399),

    ("Hábitos Atômicos - James Clear", "Livros", 49), ("O Poder do Agora - Tolle", "Livros", 39),
    ("Python para Análise de Dados", "Livros", 89), ("Box Harry Potter Capa Dura", "Livros", 249),
    ("Mangá One Piece Vol. 1-10", "Livros", 199),

    ("Café Especial Blend 500g", "Alimentos", 49), ("Whey Protein Gold Standard 2lb", "Alimentos", 189),
    ("Azeite Extravirgem Espanhol", "Alimentos", 69), ("Chocolate Lindt 70% 500g", "Alimentos", 89),

    ("LEGO Star Wars Millennium Falcon", "Brinquedos", 799),
    ("Barbie Extra Deluxe", "Brinquedos", 149),
]

# ── States & Cities ───────────────────────────────────────────────────────────
ESTADOS_CIDADES = {
    "SP": (["São Paulo", "Campinas", "Santos", "Ribeirão Preto", "Sorocaba", "São José dos Campos", "Osasco", "Santo André"], 35),
    "RJ": (["Rio de Janeiro", "Niterói", "São Gonçalo", "Duque de Caxias", "Petrópolis", "Nova Iguaçu"], 14),
    "MG": (["Belo Horizonte", "Uberlândia", "Contagem", "Juiz de Fora", "Montes Claros", "Betim"], 10),
    "RS": (["Porto Alegre", "Caxias do Sul", "Pelotas", "Canoas", "Santa Maria"], 7),
    "PR": (["Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel"], 7),
    "BA": (["Salvador", "Feira de Santana", "Vitória da Conquista", "Camaçari"], 5),
    "GO": (["Goiânia", "Aparecida de Goiânia", "Anápolis", "Rio Verde"], 4),
    "PE": (["Recife", "Caruaru", "Petrolina", "Olinda", "Jaboatão dos Guararapes"], 4),
    "CE": (["Fortaleza", "Caucaia", "Juazeiro do Norte", "Maracanaú"], 4),
    "SC": (["Florianópolis", "Joinville", "Blumenau", "Chapecó", "Itajaí"], 4),
    "DF": (["Brasília", "Ceilândia", "Taguatinga", "Planaltina"], 3),
    "ES": (["Vitória", "Serra", "Vila Velha", "Cariacica"], 2),
    "PA": (["Belém", "Ananindeua", "Santarém", "Marabá"], 2),
    "MT": (["Cuiabá", "Várzea Grande", "Rondonópolis", "Sinop"], 1),
    "AM": (["Manaus", "Parintins", "Itacoatiara"], 1),
}

PAGAMENTOS = ["pix", "cartao_credito", "boleto", "cartao_debito"]
PAG_WEIGHTS = [40, 35, 15, 10]

CANAIS = ["marketplace", "site_proprio", "app", "televendas"]
CANAL_WEIGHTS = [45, 30, 20, 5]

STATUS = ["entregue", "cancelado", "em_transito", "processando"]
STATUS_WEIGHTS = [70, 15, 10, 5]

PRIMEIROS_NOMES = [
    "Ana", "Carlos", "Fernanda", "Lucas", "Mariana", "Pedro", "Juliana", "Rafael",
    "Camila", "Rodrigo", "Gabriela", "Thiago", "Larissa", "Felipe", "Beatriz",
    "Gustavo", "Isabela", "Mateus", "Natália", "Diego", "Amanda", "Vinicius",
    "Patricia", "André", "Leticia", "Bruno", "Aline", "Eduardo", "Carla", "Victor"
]
SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Costa", "Ferreira", "Alves", "Pereira",
    "Lima", "Carvalho", "Martins", "Rodrigues", "Almeida", "Nascimento", "Cardoso",
    "Ribeiro", "Barbosa", "Mendes", "Campos", "Moreira", "Cavalcanti", "Rocha"
]


def seasonal_weight(date: datetime) -> float:
    """Return a multiplier to simulate seasonal e-commerce patterns."""
    m = date.month
    weights = {1: 0.7, 2: 0.75, 3: 0.9, 4: 0.95, 5: 1.0, 6: 0.9,
               7: 0.95, 8: 1.0, 9: 1.05, 10: 1.1, 11: 2.0, 12: 1.8}
    return weights.get(m, 1.0)


def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def create_database():
    db_path = os.path.join(os.path.dirname(__file__), "data", "astra.duckdb")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = duckdb.connect(db_path)

    # ── Schema ────────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE produtos (
            id INTEGER PRIMARY KEY,
            nome VARCHAR,
            categoria VARCHAR,
            preco DECIMAL(10,2)
        )
    """)

    conn.execute("""
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            nome VARCHAR,
            estado VARCHAR,
            cidade VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE pedidos (
            id INTEGER PRIMARY KEY,
            cliente_id INTEGER,
            data DATE,
            status VARCHAR,
            canal_venda VARCHAR,
            forma_pagamento VARCHAR,
            valor_total DECIMAL(10,2),
            estado VARCHAR,
            cidade VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE itens_pedido (
            id INTEGER PRIMARY KEY,
            pedido_id INTEGER,
            produto_id INTEGER,
            quantidade INTEGER,
            preco_unitario DECIMAL(10,2)
        )
    """)

    # ── Products ──────────────────────────────────────────────────────────────
    produto_rows = [(i + 1, nome, cat, preco) for i, (nome, cat, preco) in enumerate(PRODUTOS)]
    conn.executemany("INSERT INTO produtos VALUES (?, ?, ?, ?)", produto_rows)
    print(f"[OK] {len(produto_rows)} produtos inseridos")

    # ── Customers ─────────────────────────────────────────────────────────────
    N_CLIENTES = 4000
    estados = list(ESTADOS_CIDADES.keys())
    estado_weights = [ESTADOS_CIDADES[e][1] for e in estados]
    cliente_rows = []
    for i in range(N_CLIENTES):
        nome = f"{random.choice(PRIMEIROS_NOMES)} {random.choice(SOBRENOMES)}"
        estado = random.choices(estados, weights=estado_weights)[0]
        cidade = random.choice(ESTADOS_CIDADES[estado][0])
        cliente_rows.append((i + 1, nome, estado, cidade))
    conn.executemany("INSERT INTO clientes VALUES (?, ?, ?, ?)", cliente_rows)
    print(f"[OK] {len(cliente_rows)} clientes inseridos")

    # ── Orders & Items ────────────────────────────────────────────────────────
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 4, 29)
    N_PEDIDOS = 20000

    pedido_rows = []
    item_rows = []
    item_id = 1

    # Generate orders with seasonal bias
    all_dates = []
    for _ in range(N_PEDIDOS * 3):  # oversample then filter
        d = random_date(start_date, end_date)
        if random.random() < seasonal_weight(d) / 2.0:
            all_dates.append(d)
        if len(all_dates) >= N_PEDIDOS:
            break
    all_dates = sorted(all_dates[:N_PEDIDOS])

    for pedido_id, data in enumerate(all_dates, start=1):
        cliente = random.choice(cliente_rows)
        estado = cliente[2]
        cidade = cliente[3]
        pagamento = random.choices(PAGAMENTOS, weights=PAG_WEIGHTS)[0]
        canal = random.choices(CANAIS, weights=CANAL_WEIGHTS)[0]
        status = random.choices(STATUS, weights=STATUS_WEIGHTS)[0]

        n_itens = random.choices([1, 2, 3, 4], weights=[55, 28, 12, 5])[0]
        produtos_escolhidos = random.sample(range(len(PRODUTOS)), min(n_itens, len(PRODUTOS)))

        valor_total = 0.0
        for prod_idx in produtos_escolhidos:
            prod = PRODUTOS[prod_idx]
            preco_base = prod[2]
            variacao = random.uniform(0.95, 1.05)
            preco_unit = round(preco_base * variacao, 2)
            qtd = random.choices([1, 2, 3], weights=[75, 20, 5])[0]
            item_rows.append((item_id, pedido_id, prod_idx + 1, qtd, preco_unit))
            valor_total += preco_unit * qtd
            item_id += 1

        pedido_rows.append((
            pedido_id, cliente[0], data.strftime("%Y-%m-%d"),
            status, canal, pagamento, round(valor_total, 2),
            estado, cidade
        ))

    conn.executemany("INSERT INTO pedidos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", pedido_rows)
    conn.executemany("INSERT INTO itens_pedido VALUES (?, ?, ?, ?, ?)", item_rows)
    print(f"[OK] {len(pedido_rows)} pedidos inseridos")
    print(f"[OK] {len(item_rows)} itens de pedido inseridos")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_rev = conn.execute("SELECT SUM(valor_total) FROM pedidos").fetchone()[0]
    print(f"\n[OK] Banco criado em: {db_path}")
    print(f"     Faturamento total: R$ {total_rev:,.2f}")
    conn.close()


if __name__ == "__main__":
    create_database()
