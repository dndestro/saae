import getpass
import time
from playwright.sync_api import sync_playwright

def main():
    print("=== SAAE Sorocaba - Consulta de Consumo ===")
    
    # Solicita credenciais ao usuário
    usuario = input("Digite seu CPF ou CNPJ: ").strip()
    senha = getpass.getpass("Digite sua senha: ")
    
    if not usuario or not senha:
        print("Erro: Usuário e senha são obrigatórios.")
        return

    with sync_playwright() as p:
        print("\nIniciando navegador...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            print("Acessando a Agência Virtual...")
            # URL da página de login
            page.goto("https://sorocabaagvrt.consensotec.com.br/gsan/exibirServicosPortalSaaeSorocabaAction.do")
            
            # Preenche o formulário de login
            print("Realizando login...")
            page.fill("#cpfOrCnpj", usuario)
            page.fill("#senhaAcesso", senha)
            
            # Clica no botão de login inicial (que abre o aviso)
            page.click("#btnOk")
            
            # --- Lidar com o pop-up de "Aviso" e EFETIVAR o login ---
            try:
                # O botão real que faz o submit é o ".confirm" dentro do modal
                # Aguardamos ele aparecer
                aviso_ok = page.wait_for_selector(".confirm", timeout=5000)
                if aviso_ok and aviso_ok.is_visible():
                    print("Confirmando aviso e efetivando login...")
                    # Ao clicar aqui, o formulário é enviado (via JS do site)
                    aviso_ok.click()
                    # Aguardamos a navegação de fato ocorrer
                    page.wait_for_load_state("networkidle")
            except:
                # Se não houver aviso, talvez já tenha logado direto (raro)
                pass
            # -------------------------------------------------------

            # Verifica se ainda estamos na página de login (o que indica falha)
            if page.query_selector("#cpfOrCnpj"):
                # Se os campos de login ainda existem, algo deu errado
                if page.query_selector(".erro") or page.query_selector("text='Senha inválida'"):
                    print("Erro: Falha no login. Verifique seu CPF/CNPJ e senha.")
                else:
                    print("Erro: Não foi possível avançar após o login. Verifique o print debug_page_v2.png.")
                    page.screenshot(path="debug_page_v2.png")
                return

            print("Login realizado com sucesso! Dashboard acessado.")
            
            # Navega para o histórico de consumo
            print("Acessando histórico de consumo...")
            
            # Tentamos localizar o link de várias formas para ser mais robusto
            # O sistema GSAN costuma usar links com texto ou IDs específicos
            try:
                # Tenta pelo texto parcial (case-insensitive) e aguarda até 15s
                selector = "text=/Histórico de consumo/i"
                print("Procurando link do histórico...")
                page.wait_for_selector(selector, timeout=15000)
                page.click(selector)
            except Exception as e:
                print(f"Aviso: Não encontrou pelo seletor padrão ({e}). Tentando alternativas...")
                # Tenta procurar por todos os links e filtrar manualmente
                links = page.query_selector_all("a")
                found_link = False
                for link in links:
                    text = link.inner_text().strip().lower()
                    if "histórico" in text and "consumo" in text:
                        print(f"Link alternativo encontrado: '{link.inner_text()}'")
                        link.click()
                        found_link = True
                        break
                
                if not found_link:
                    print("Erro: Não foi possível encontrar o link 'Histórico de consumo de água'.")
                    print("Salvando print da página para depuração (debug_page_v2.png)...")
                    page.screenshot(path="debug_page_v2.png")
                    # Salva o HTML para análise técnica se necessário
                    with open("debug_page.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                    return
                
            page.wait_for_load_state("networkidle")
            
            # Localiza a tabela de histórico
            print("Extraindo dados de consumo...")
            
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
                        mes_ano = text
                        consumo = cells[3].inner_text().strip() # Geralmente a 3ª coluna é o consumo em m3
                        print(f"\n>>> Último mês disponível: {mes_ano}")
                        print(f">>> Consumo realizado: {consumo} m³")
                        found = True
                        break
            
            if not found:
                print("\nNão foi possível localizar os dados de consumo na tabela.")
                # Tira um print para depuração se necessário (opcional)
                # page.screenshot(path="debug_consumo.png")

        except Exception as e:
            print(f"\nOcorreu um erro durante a execução: {e}")
        finally:
            browser.close()
            print("\nNavegador encerrado.")

if __name__ == "__main__":
    main()
