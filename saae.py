import asyncio
import os
import logging
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright
from homeassistant import HomeAssistant

ENTITY_SAAE = "input_number.saae_consumo_mensal"
STATISTIC_ID_SAAE = "sensor.saae_consumo_mensal"
FUSO_BR = timezone(timedelta(hours=-3))

# Configuração de Logging para monitoramento
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"  # ,
    # filename="saae.log",
    # filemode="a"
)
logger = logging.getLogger(__name__)


def inicio_do_mes_iso(mes_str: str) -> str:
    dt = datetime.strptime(mes_str, "%m/%Y").replace(
        tzinfo=FUSO_BR,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )
    return dt.isoformat()


class SAAEScraper:
    def __init__(self):
        self.url_login = "https://sorocabaagvrt.consensotec.com.br/gsan/exibirServicosPortalSaaeSorocabaAction.do"
        self.consumo_valor: Optional[float] = None
        self.consumo_data: Optional[str] = None

    def run(self) -> Optional[tuple[str, float] | None]:
        logger.info("=== SAAE Sorocaba - Consulta de Consumo ===")

        with sync_playwright() as p:
            logger.info("\nIniciando navegador...")
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            try:
                logger.info("Acessando a Agência Virtual...")
                # URL da página de login
                page.goto(self.url_login)

                # Preenche o formulário de login
                logger.info("Realizando login...")
                page.fill("#cpfOrCnpj", SAAE_USER)
                page.fill("#senhaAcesso", SAAE_PASS)

                # Clica no botão de login inicial (que abre o aviso)
                page.click("#btnOk")

                # --- Lidar com o pop-up de "Aviso" e EFETIVAR o login ---
                try:
                    # O botão real que faz o submit é o ".confirm" dentro do modal
                    # Aguardamos ele aparecer
                    aviso_ok = page.wait_for_selector(".confirm", timeout=5000)
                    if aviso_ok and aviso_ok.is_visible():
                        logger.info("Confirmando aviso e efetivando login...")
                        # Ao clicar aqui, o formulário é enviado (via JS do site)
                        aviso_ok.click()
                        # Aguardamos a navegação de fato ocorrer
                        page.wait_for_load_state("networkidle")
                except Exception:
                    # Se não houver aviso, talvez já tenha logado direto (raro)
                    pass
                # -------------------------------------------------------

                # Verifica se ainda estamos na página de login (o que indica falha)
                if page.query_selector("#cpfOrCnpj"):
                    # Se os campos de login ainda existem, algo deu errado
                    if page.query_selector(".erro") or page.query_selector("text='Senha inválida'"):
                        logger.info(
                            "Erro: Falha no login. Verifique seu CPF/CNPJ e senha.")
                    else:
                        logger.info(
                            "Erro: Não foi possível avançar após o login. Verifique o print debug_page_v2.png.")
                        page.screenshot(path="debug_page_v2.png")
                    return None

                logger.info("Login realizado com sucesso! Dashboard acessado.")

                # Navega para o histórico de consumo
                logger.info("Acessando histórico de consumo...")

                # Tentamos localizar o link de várias formas para ser mais robusto
                # O sistema GSAN costuma usar links com texto ou IDs específicos
                try:
                    # Tenta pelo texto parcial (case-insensitive) e aguarda até 15s
                    selector = "text=/Histórico de consumo/i"
                    logger.info("Procurando link do histórico...")
                    page.wait_for_selector(selector, timeout=15000)
                    page.click(selector)
                except Exception as e:
                    logger.info(
                        f"Aviso: Não encontrou pelo seletor padrão ({e}). Tentando alternativas...")
                    # Tenta procurar por todos os links e filtrar manualmente
                    links = page.query_selector_all("a")
                    found_link = False
                    for link in links:
                        text = link.inner_text().strip().lower()
                        if "histórico" in text and "consumo" in text:
                            logger.info(
                                f"Link alternativo encontrado: '{link.inner_text()}'")
                            link.click()
                            found_link = True
                            break

                    if not found_link:
                        logger.info(
                            "Erro: Não foi possível encontrar o link 'Histórico de consumo de água'.")
                        logger.info(
                            "Salvando print da página para depuração (debug_page_v2.png)...")
                        page.screenshot(path="debug_page_v2.png")
                        # Salva o HTML para análise técnica se necessário
                        with open("debug_page.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                        return

                page.wait_for_load_state("networkidle")

                # Localiza a tabela de histórico
                logger.info("Extraindo dados de consumo...")

                # Tentativa genérica de pegar a primeira linha da tabela de consumo
                # Ajustado para o padrão comum do GSAN (sistema usado pelo SAAE)
                rows = page.query_selector_all("table tr")

                found = False
                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 3:
                        # Verifica se a primeira célula parece uma data (MM/AAAA)
                        text = cells[0].inner_text().strip()
                        if "/" in text and len(text) <= 10:
                            self.consumo_data = text
                            # Geralmente a 3ª coluna é o consumo em m3
                            self.consumo_valor = float(
                                cells[3].inner_text().strip())
                            found = True
                            break
                if not found:
                    logger.info(
                        "\nNão foi possível localizar os dados de consumo na tabela.")
                    # Tira um print para depuração se necessário (opcional)
                    # page.screenshot(path="debug_consumo.png")

            except Exception as e:
                logger.info(f"\nOcorreu um erro durante a execução: {e}")
                return
            finally:
                browser.close()
                logger.info("\nNavegador encerrado.")

        return self.consumo_data, self.consumo_valor


def main():
    load_dotenv(override=True)

    global SAAE_USER, SAAE_PASS
    SAAE_USER = os.getenv("USER_NAME")
    SAAE_PASS = os.getenv("PASSWORD")
    HA_URL = os.getenv("HA_URL")
    HA_WS_URL = os.getenv("HA_WS_URL")
    TOKEN = os.getenv("HA_TOKEN")

    if not SAAE_USER or not SAAE_PASS or not HA_URL or not HA_WS_URL or not TOKEN:
        raise RuntimeError(
            "Verifique o .env: USER_NAME, PASSWORD_SAAE, HA_URL, HA_WS_URL e HA_TOKEN."
        )

    scraper = SAAEScraper()
    mes, consumo = ('05/2026', 16)  # scraper.run()

    if mes is None or consumo is None:
        logger.warning("O script terminou sem conseguir capturar o consumo.")
        return

    inicio_mes = inicio_do_mes_iso(mes)
    logger.info(
        f"Consumo capturado do SAAE: {mes}, {consumo} m³")

    ha = HomeAssistant(HA_URL, TOKEN, HA_WS_URL)

    # 1) Atualiza o valor atual na interface do home assistant
    # ha.atualizar_input_number(ENTITY_SAAE, consumo)

    asyncio.run(ha.importar_estatistica_mensal(
        statistic_id=STATISTIC_ID_SAAE,
        name="SAAE Consumo Mensal",
        unit="m3",
        start_iso=inicio_mes,
        value=consumo
    ))


if __name__ == "__main__":
    main()
