"""Generate a high‑quality tutorial for the UniEventos web application.

This script uses Playwright to automate a browser session, log in as each
profile type defined in ``config.json`` and capture screenshots of ALL main
pages that are relevant for that profile.  The screenshots are stored in
``tutorial/screenshots`` and a comprehensive Markdown file 
``tutorial/tutorial.md`` is generated with detailed explanations.

The script is intentionally lightweight – it does not depend on any
framework‑specific code and can be run from the project root:

    python -m tutorial.generate_tutorial

Before running the script you must install Playwright and its browsers:

    pip install -r requirements.txt
    playwright install

The configuration file ``tutorial/config.json`` contains the credentials
for each profile.  It is intentionally kept out of version control – the
example file ``tutorial/config.example.json`` shows the expected format.
"""

import json
import os
import pathlib
import sys
from datetime import datetime
from typing import Dict, List, Tuple

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover
    print("Playwright is required to generate the tutorial. Install it with:\n\tpip install -r requirements.txt")
    sys.exit(1)

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"
SCREENSHOT_DIR = pathlib.Path(__file__).parent / "screenshots"
MARKDOWN_PATH = pathlib.Path(__file__).parent / "tutorial.md"


def load_config() -> dict:
    """Load the JSON configuration file.

    The configuration file must contain a mapping of profile names to a
    dictionary with ``username`` and ``password`` keys.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        return json.load(fp)


def login(page, username: str, password: str) -> bool:
    """Perform a login on the application.

    The login form is located at ``/`` and expects CPF (username) and
    ``password`` fields.  After a successful login the user is redirected
    to the home page.
    
    Returns True if login was successful, False otherwise.
    """
    try:
        # Navigate to home page (which shows login form if not authenticated)
        page.goto(f"{BASE_URL}/")
        
        # Wait for login form - the app uses CPF as username
        page.wait_for_selector("#loginCpf", timeout=10000)
        
        # Fill in credentials (username is actually CPF in this system)
        page.fill("#loginCpf", username)
        page.fill("#loginPass", password)
        
        # Click submit button
        page.click("button[type='submit']")
        
        # Wait for navigation after login (redirect to dashboard)
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # Additional wait to ensure all content is loaded
        page.wait_for_timeout(2000)
        
        return True
    except Exception as e:
        print(f"  ⚠️ Login failed: {e}")
        return False


def capture_page(page, name: str, url: str, description: str = "") -> Tuple[pathlib.Path, bool]:
    """Navigate to ``url`` and capture a screenshot.

    The screenshot is stored in ``SCREENSHOT_DIR`` with a filename that
    includes the profile name and the page name.
    
    Returns tuple of (path to screenshot, success boolean).
    """
    try:
        page.goto(url)
        # Wait for the main content to load
        page.wait_for_selector("body", timeout=10000)
        # Additional wait for dynamic content
        page.wait_for_timeout(2000)  # Wait for any animations or lazy loading
        
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename = SCREENSHOT_DIR / f"{name}.png"
        page.screenshot(path=str(filename), full_page=True)
        return filename, True
    except Exception as e:
        print(f"  ⚠️ Failed to capture {name}: {e}")
        return pathlib.Path(""), False


def generate_markdown(entries: List[Tuple[str, str, str]]) -> None:
    """Generate a comprehensive Markdown file that references the screenshots.

    ``entries`` is a list of tuples ``(section_title, entry_title, path)``.
    """
    lines = [
        "# UniEventos - Tutorial Completo",
        "",
        f"> **Gerado em:** {datetime.utcnow().isoformat()} UTC",
        "",
        "---",
        "",
        "## 📚 Introdução",
        "",
        "Este tutorial fornece instruções passo a passo detalhadas para o uso da aplicação web UniEventos.",
        "A aplicação possui interfaces diferentes baseadas nos perfis de usuário. Este guia cobre todos os tipos de perfil:",
        "",
        "### 👥 Perfis de Usuário",
        "",
        "- **👨‍🎓 Participante (Aluno)**: Acesso a eventos, cursos e dashboard pessoal",
        "- **👨‍🏫 Professor**: Criação e gerenciamento de eventos, design de certificados",
        "- **🎓 Coordenador**: Gerenciamento de eventos do curso, gestão de certificados",
        "- **🏢 Extensão**: Gestão de certificados institucionais",
        "- **⚙️ Administrador**: Acesso total ao sistema e gerenciamento completo",
        "",
        "---",
        "",
    ]
    
    # Group entries by section
    current_section = None
    for section_title, entry_title, path in entries:
        if current_section != section_title:
            current_section = section_title
            lines.append(f"## {section_title}")
            lines.append("")
        
        rel_path = pathlib.Path(path).relative_to(pathlib.Path(path).parent)
        lines.append(f"### {entry_title}")
        lines.append("")
        lines.append(f"![{entry_title}]({rel_path})")
        lines.append("")
    
    # Add conclusion
    lines.extend([
        "---",
        "",
        "## 📝 Conclusão",
        "",
        "Este tutorial cobriu todas as principais funcionalidades da aplicação UniEventos para cada perfil de usuário.",
        "Para mais informações sobre o sistema, consulte a documentação completa ou entre em contato com a equipe de suporte.",
        "",
        "---",
        "",
        f"*Tutorial gerado automaticamente em {datetime.utcnow().strftime('%d/%m/%Y às %H:%M')}*",
        ""
    ])
    
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def get_participant_pages() -> Dict[str, Tuple[str, str]]:
    """Define the pages to capture for participant profile.
    
    Returns dict mapping page_name -> (url, description)
    """
    return {
        "Login": (f"{BASE_URL}/", "Tela de login do sistema"),
        "Dashboard": (f"{BASE_URL}/", "Dashboard principal após login"),
        "Meus Eventos": (f"{BASE_URL}/meus_eventos", "Lista de eventos que o participante já frequentou"),
        "Perfil": (f"{BASE_URL}/perfil", "Página de perfil do usuário com estatísticas"),
        "Eventos Disponíveis": (f"{BASE_URL}/eventos", "Listagem de todos os eventos públicos disponíveis"),
        "Inscrição em Evento": (f"{BASE_URL}/inscrever/", "Página de visualização e inscrição em evento"),
        "Confirmação de Presença": (f"{BASE_URL}/confirmar_presenca/", "Tela para confirmar presença via QR Code"),
        "Meus Certificados": (f"{BASE_URL}/certificados", "Lista de certificados disponíveis para download"),
        "Histórico de Participação": (f"{BASE_URL}/historico", "Histórico completo de participações e horas acumuladas"),
    }


def get_professor_pages() -> Dict[str, Tuple[str, str]]:
    """Define the pages to capture for professor profile."""
    return {
        "Login": (f"{BASE_URL}/", "Tela de login do sistema"),
        "Dashboard Professor": (f"{BASE_URL}/", "Dashboard principal com acesso a todas as funcionalidades"),
        "Criar Evento": (f"{BASE_URL}/criar_evento", "Formulário para criação de novo evento"),
        "Gerenciar Eventos": (f"{BASE_URL}/eventos_admin", "Listagem administrativa de todos os eventos"),
        "Editar Evento": (f"{BASE_URL}/editar_evento/", "Página de edição de evento existente"),
        "Designer de Certificado": (f"{BASE_URL}/designer_certificado/", "Ferramenta visual para design de certificados"),
        "Gerenciar Entregas": (f"{BASE_URL}/gerenciar_entregas/", "Gestão de entregas de certificados por email"),
        "Participantes do Evento": (f"{BASE_URL}/participantes/", "Listagem de participantes com controle de presença"),
        "Notificações": (f"{BASE_URL}/notificar/", "Envio de notificações em massa para participantes"),
    }


def get_coordenador_pages() -> Dict[str, Tuple[str, str]]:
    """Define the pages to capture for coordenador profile."""
    return {
        "Login": (f"{BASE_URL}/", "Tela de login do sistema"),
        "Dashboard Coordenador": (f"{BASE_URL}/", "Dashboard com foco em gestão de curso"),
        "Eventos do Curso": (f"{BASE_URL}/eventos_curso", "Listagem de eventos do curso sob coordenação"),
        "Gerenciar Certificados": (f"{BASE_URL}/certificados_curso", "Gestão de certificados do curso"),
        "Designer Avançado": (f"{BASE_URL}/designer_certificado/", "Ferramenta avançada de design com templates personalizados"),
        "Relatórios": (f"{BASE_URL}/relatorios", "Relatórios detalhados de participação e desempenho"),
        "Entregas em Lote": (f"{BASE_URL}/entregas_lote", "Envio em massa de certificados"),
    }


def get_extensao_pages() -> Dict[str, Tuple[str, str]]:
    """Define the pages to capture for extensão profile."""
    return {
        "Login": (f"{BASE_URL}/", "Tela de login do sistema"),
        "Dashboard Extensão": (f"{BASE_URL}/", "Dashboard focado em certificados institucionais"),
        "Certificados Institucionais": (f"{BASE_URL}/certificados_institucionais", "Listagem de todos os certificados institucionais"),
        "Criar Certificado Institucional": (f"{BASE_URL}/criar_certificado_institucional", "Formulário para criação de certificado institucional"),
        "Designer Institucional": (f"{BASE_URL}/designer_certificado_institucional/", "Design personalizado para certificados institucionais"),
        "Gerenciar Destinatários": (f"{BASE_URL}/gerenciar_destinatarios", "Gestão de lista de destinatários"),
        "Exportar Certificados": (f"{BASE_URL}/exportar_certificados", "Exportação em lote de certificados"),
    }


def get_admin_pages() -> Dict[str, Tuple[str, str]]:
    """Define the pages to capture for admin profile."""
    return {
        "Login": (f"{BASE_URL}/", "Tela de login do sistema"),
        "Dashboard Admin": (f"{BASE_URL}/admin/dashboard", "Painel administrativo completo"),
        "Gerenciar Usuários": (f"{BASE_URL}/admin/users", "Listagem e gestão de todos os usuários"),
        "Configurações do Sistema": (f"{BASE_URL}/admin/config", "Configurações globais do sistema"),
        "Relatórios Globais": (f"{BASE_URL}/admin/reports", "Relatórios completos de toda a plataforma"),
        "Eventos Administrativos": (f"{BASE_URL}/admin/events", "Gestão administrativa de eventos"),
        "Certificados Administrativos": (f"{BASE_URL}/admin/certificates", "Gestão administrativa de certificados"),
        "Logs do Sistema": (f"{BASE_URL}/admin/logs", "Visualização de logs e auditoria"),
        "Backup e Restauração": (f"{BASE_URL}/admin/backup", "Ferramentas de backup e recuperação"),
    }


def run_profile_tutorial(profile: str, creds: dict, pages: Dict[str, Tuple[str, str]], browser_context) -> List[Tuple[str, str, str]]:
    """Run tutorial generation for a specific profile.
    
    Returns list of (section_title, entry_title, screenshot_path) tuples.
    """
    entries = []
    page = browser_context.new_page()
    
    print(f"\n📸 Gerando tutorial para perfil: {profile}")
    print("=" * 60)
    
    try:
        # Attempt login
        if not login(page, creds["username"], creds["password"]):
            print(f"❌ Falha no login para perfil {profile}")
            page.close()
            return entries
        
        print(f"✅ Login bem-sucedido como {profile}")
        
        # Capture each page
        for page_name, (url, description) in pages.items():
            print(f"  📷 Capturando: {page_name}...")
            
            screenshot_path, success = capture_page(page, f"{profile}_{page_name}", url, description)
            
            if success:
                section_title = f"👤 Perfil: {profile.capitalize()}"
                entry_title = f"{page_name} - {description}"
                entries.append((section_title, entry_title, str(screenshot_path)))
                print(f"    ✓ Capturado: {screenshot_path.name}")
            else:
                print(f"    ✗ Falha ao capturar")
        
        page.close()
        
    except Exception as e:
        print(f"❌ Erro ao processar perfil {profile}: {e}")
        if page:
            page.close()
    
    return entries


def main() -> None:
    """Main function to generate complete tutorial."""
    print("\n" + "=" * 60)
    print("🎓 GERADOR DE TUTORIAL - UniEventos")
    print("=" * 60)
    
    # Load configuration
    try:
        config = load_config()
        print(f"✅ Configuração carregada com {len(config)} perfis")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\n⚠️  Crie o arquivo tutorial/config.json com as credenciais dos usuários")
        sys.exit(1)
    
    # Define profile handlers
    profile_handlers = {
        "student": get_participant_pages,
        "participant": get_participant_pages,
        "aluno": get_participant_pages,
        "professor": get_professor_pages,
        "instructor": get_professor_pages,
        "coordenador": get_coordenador_pages,
        "extensao": get_extensao_pages,
        "admin": get_admin_pages,
    }
    
    all_entries: List[Tuple[str, str, str]] = []
    
    # Launch browser
    with sync_playwright() as p:
        print("\n🚀 Iniciando navegador...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        
        # Process each profile in order (starting with participant/student)
        for profile_name, creds in config.items():
            profile_lower = profile_name.lower()
            
            # Find matching handler
            handler = None
            for key, page_handler in profile_handlers.items():
                if key in profile_lower:
                    handler = page_handler
                    break
            
            if handler is None:
                print(f"⚠️  Perfil desconhecido: {profile_name}, pulando...")
                continue
            
            # Get pages for this profile
            pages = handler()
            
            # Generate tutorial entries
            entries = run_profile_tutorial(profile_name, creds, pages, context)
            all_entries.extend(entries)
        
        browser.close()
    
    # Generate Markdown documentation
    print("\n" + "=" * 60)
    print("📝 Gerando documentação Markdown...")
    
    if all_entries:
        generate_markdown(all_entries)
        print(f"✅ Tutorial gerado com sucesso: {MARKDOWN_PATH}")
        print(f"   Total de screenshots: {len(all_entries)}")
        print(f"   Local dos screenshots: {SCREENSHOT_DIR}")
    else:
        print("❌ Nenhum screenshot foi capturado. Verifique as credenciais e se o servidor está rodando.")
    
    print("\n" + "=" * 60)
    print("✨ Processo concluído!")
    print("=" * 60 + "\n")


if __name__ == "__main__":  # pragma: no cover
    main()
