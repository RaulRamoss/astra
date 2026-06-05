#!/usr/bin/env python3
"""
demo_auto.py — Astra Demo Automator

Inicia o app, digita as perguntas automaticamente e navega pelos resultados.
Grave a tela enquanto este script roda.

Pré-requisito:
    pip install selenium

Uso:
    python demo_auto.py
"""

import subprocess
import sys
import time
from pathlib import Path

# ── Verifica dependência ───────────────────────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
except ImportError:
    print("\n  Erro: selenium não instalado.")
    print("  Execute: pip install selenium\n")
    sys.exit(1)

# ── Configurações ─────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).parent
APP_URL = "http://localhost:8501"

PERGUNTAS = [
    "Quais são os 10 produtos mais vendidos em 2024?",
    "Qual o faturamento mensal de 2025?",
    "Como as vendas se distribuem por estado?",
    "Qual canal de venda tem maior ticket médio?",
    "Quantos pedidos foram cancelados por mês?",
]

TEMPO_LEITURA    = 4     # segundos exibindo resposta antes da próxima pergunta
TEMPO_ABA        = 2.5   # segundos em cada aba (Gráfico, SQL)
DIGITACAO_DELAY  = 0.045 # delay entre caracteres (efeito de digitação)
COUNTDOWN        = 6     # contagem regressiva antes de começar


# ── Streamlit ─────────────────────────────────────────────────────────────────
def iniciar_streamlit() -> subprocess.Popen | None:
    """Tenta iniciar o Streamlit. Se já estiver rodando, segue em frente."""
    import urllib.request
    try:
        urllib.request.urlopen(APP_URL, timeout=2)
        print("  Streamlit já está rodando em", APP_URL)
        return None
    except Exception:
        pass

    print("  Iniciando Astra...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.headless", "true",
         "--server.port", "8501"],
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("  Aguardando o app subir", end="")
    for _ in range(10):
        time.sleep(1)
        print(".", end="", flush=True)
        try:
            urllib.request.urlopen(APP_URL, timeout=1)
            print(" pronto!\n")
            return proc
        except Exception:
            pass
    print()
    return proc


# ── Chrome ────────────────────────────────────────────────────────────────────
def criar_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-infobars")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=opts)


# ── Interações ────────────────────────────────────────────────────────────────
def esperar_chat_input(driver, timeout=15):
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="stChatInput"] textarea')
        )
    )


def contar_mensagens(driver) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, '[data-testid="stChatMessage"]'))


def esperar_nova_mensagem(driver, total_antes: int, timeout=25):
    """Aguarda até uma nova mensagem aparecer no chat."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: contar_mensagens(d) > total_antes
        )
    except Exception:
        pass
    time.sleep(2)  # buffer para gráfico renderizar


def digitar_pergunta(driver, pergunta: str):
    campo = esperar_chat_input(driver)
    campo.click()
    time.sleep(0.4)
    for char in pergunta:
        campo.send_keys(char)
        time.sleep(DIGITACAO_DELAY)
    time.sleep(0.6)
    campo.send_keys(Keys.RETURN)


def clicar_aba(driver, texto: str) -> bool:
    """Clica em uma aba pelo texto (parcial)."""
    try:
        abas = driver.find_elements(By.CSS_SELECTOR, '[data-baseweb="tab"]')
        for aba in abas:
            if texto.lower() in aba.text.lower():
                driver.execute_script("arguments[0].scrollIntoView(true);", aba)
                driver.execute_script("arguments[0].click();", aba)
                time.sleep(TEMPO_ABA)
                return True
    except Exception:
        pass
    return False


def scroll_para_resposta(driver):
    """Rola suavemente até a última mensagem."""
    driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
    time.sleep(1)


# ── Demo ──────────────────────────────────────────────────────────────────────
def rodar_demo():
    streamlit_proc = None
    driver = None

    try:
        print("\n" + "=" * 55)
        print("  ASTRA — DEMO AUTOMATOR")
        print("=" * 55 + "\n")

        # Inicia o app
        streamlit_proc = iniciar_streamlit()

        # Abre o Chrome
        print("  Abrindo o navegador...")
        driver = criar_driver()
        driver.get(APP_URL)
        esperar_chat_input(driver)
        time.sleep(1.5)

        # Contagem regressiva
        print(f"\n  ✅ App carregado!")
        print(f"  ⏺  INICIE A GRAVAÇÃO DA TELA AGORA\n")
        for i in range(COUNTDOWN, 0, -1):
            print(f"     Começa em {i}...", end="\r")
            time.sleep(1)
        print("     🎬 GRAVANDO!              \n")

        # Loop de perguntas
        for i, pergunta in enumerate(PERGUNTAS, 1):
            total_antes = contar_mensagens(driver)

            print(f"  [{i}/{len(PERGUNTAS)}] {pergunta}")
            digitar_pergunta(driver, pergunta)

            print("         ⏳ aguardando resposta...")
            esperar_nova_mensagem(driver, total_antes)
            scroll_para_resposta(driver)

            # Mostra a aba Resposta
            clicar_aba(driver, "Resposta")
            time.sleep(TEMPO_LEITURA)

            # Mostra o gráfico
            if clicar_aba(driver, "Gráfico"):
                print("         📊 gráfico")
                time.sleep(TEMPO_LEITURA)

            # Mostra o SQL
            if clicar_aba(driver, "SQL"):
                print("         🔍 SQL")
                time.sleep(TEMPO_ABA)

            # Volta para resposta antes da próxima
            clicar_aba(driver, "Resposta")
            time.sleep(1.5)

        # Finaliza
        print("\n  ✅ Demo concluída!")
        print("  Pare a gravação quando quiser. Encerrando em 10s...\n")
        time.sleep(10)

    except KeyboardInterrupt:
        print("\n\n  Interrompido.")
    except Exception as e:
        print(f"\n  Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
        if streamlit_proc:
            streamlit_proc.terminate()
            print("  App encerrado.")


if __name__ == "__main__":
    rodar_demo()
