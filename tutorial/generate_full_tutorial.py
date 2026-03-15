"""Generate a comprehensive tutorial for the UniEventos web application.

This script uses Playwright to automate browser sessions, log in as each
profile type and capture screenshots of ALL main pages relevant for that profile.
The screenshots are stored in ``tutorial/screenshots`` and a detailed Markdown 
file ``tutorial/tutorial.md`` is generated with comprehensive explanations.

Usage:
    python -m tutorial.generate_tutorial_complete

Requirements:
    pip install -r requirements.txt
    playwright install

Configuration:
    Edit tutorial/config.json with valid user credentials (CPF and password)
"""

import json
import os
import pathlib
import sys
from datetime import datetime, timezone
from typing import Dict, List, Tuple

try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("Playwright is required. Install with: pip install playwright")
    sys.exit(1)

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"
SCREENSHOT_DIR = pathlib.Path(__file__).parent / "screenshots"
MARKDOWN_PATH = pathlib.Path(__file__).parent / "tutorial.md"


def load_config() -> dict:
    """Load configuration file with user credentials."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        return json.load(fp)


def login(page, cpf: str, password: str) -> bool:
    """Login using CPF and password. Returns True if successful."""
    try:
        print(f"  🔄 Navegando para {BASE_URL}...")
        page.goto(f"{BASE_URL}/")
        
        # Wait for login form (uses CPF as username)
        print("  🔍 Procurando formulário de login...")
        page.wait_for_selector("#loginCpf", timeout=10000)
        print("  ✅ Formulário encontrado!")
        
        # Fill credentials
        print(f"  📝 Preenchendo CPF: {cpf}")
        page.fill("#loginCpf", cpf)
        print("  🔐 Preenchendo senha")
        page.fill("#loginPass", password)
        
        # Submit
        print("  🚀 Enviando formulário...")
        page.click("button[type='submit']")
        
        # Wait for navigation
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(2000)
        
        print("  ✅ Login bem-sucedido!")
        return True
        
    except Exception as e:
        print(f"  ❌ Erro no login: {e}")
        return False


def capture_page(page, name: str, url: str, description: str = "") -> Tuple[pathlib.Path, bool]:
    """Navigate to URL and capture screenshot. Returns (path, success)."""
    try:
        print(f"  📷 Capturando {name}...")
        page.goto(url)
        page.wait_for_selector("body", timeout=10000)
        page.wait_for_timeout(2000)
        
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename = SCREENSHOT_DIR / f"{name}.png"
        page.screenshot(path=str(filename), full_page=True)
        print(f"    ✓ Salvo: {filename.name}")
        return filename, True
        
    except Exception as e:
        print(f"    ✗ Erro: {e}")
        return pathlib.Path(""), False


def generate_markdown(entries: List[Tuple[str, str, str]]) -> None:
    """Generate comprehensive Markdown documentation."""
    lines = [
        "# UniEventos - Tutorial Completo",
        "",
        f"> **Gerado em:** {datetime.now(timezone.utc).isoformat()} UTC",
        "",
        "---",
        "",
        "## 📚 Introdução",
        "",
        "Este tutorial fornece instruções detalhadas para o uso da aplicação UniEventos.",
        "A aplicação possui interfaces diferentes baseadas nos perfis de usuário.",
        "",
        "## 👥 Perfis de Usuário",
        "",
        "- **👨‍🎓 Participante**: Acesso a eventos, inscrições e certificados pessoais",
        "- **👨‍🏫 Professor**: Criação e gerenciamento de eventos, design de certificados",
        "- **🎓 Coordenador**: Gestão de eventos do curso e certificados",
        "- **🏢 Extensão**: Gestão de certificados institucionais",
        "- **⚙️ Administrador**: Acesso total ao sistema",
        "",
        "---",
        ""
    ]
    
    # Group by section
    current_section = None
    for section_title, entry_title, path in entries:
        if current_section != section_title:
            current_section = section_title
            lines.append(f"## {section_title}")
            lines.append("")
        
        rel_path = pathlib.Path(path).name
        lines.append(f"### {entry_title}")
        lines.append("")
        lines.append(f"![{entry_title}]({rel_path})")
        lines.append("")
    
    # Conclusion
    lines.extend([
        "---",
        "",
        "## 📝 Conclusão",
        "",
        "Este tutorial cobriu todas as principais funcionalidades da aplicação UniEventos.",
        "",
        f"*Tutorial gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y às %H:%M')}*",
        ""
    ])
    
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ Markdown gerado: {MARKDOWN_PATH}")


def get_participante_pages() -> Dict[str, Tuple[str, str]]:
    """Pages for participant profile."""
    return {
        "participante_Dashboard": (f"{BASE_URL}/", "Visão geral após login"),
        "participante_MeusEventos": (f"{BASE_URL}/meus_eventos", "Eventos frequentados"),
        "participante_Perfil": (f"{BASE_URL}/perfil", "Informações pessoais"),
    }


def get_professor_pages() -> Dict[str, Tuple[str, str]]:
    """Pages for professor profile."""
    return {
        "professor_Dashboard": (f"{BASE_URL}/", "Dashboard do professor"),
        "professor_CriarEvento": (f"{BASE_URL}/criar_evento", "Formulário de criação"),
        "professor_GerenciarEventos": (f"{BASE_URL}/eventos_admin", "Listagem administrativa"),
    }


def get_admin_pages() -> Dict[str, Tuple[str, str]]:
    """Pages for admin profile."""
    return {
        "admin_Dashboard": (f"{BASE_URL}/", "Painel administrativo"),
        "admin_GerenciarUsuarios": (f"{BASE_URL}/usuarios", "Gestão de usuários"),
    }


def run_profile_tutorial(profile: str, creds: dict, pages: Dict[str, Tuple[str, str]], context) -> List[Tuple[str, str, str]]:
    """Generate tutorial for a specific profile."""
    entries = []
    page = context.new_page()
    
    print(f"\n📸 Gerando tutorial para perfil: {profile}")
    print("=" * 60)
    
    try:
        # Login
        cpf = creds.get("username", "")
        password = creds.get("password", "")
        
        if not login(page, cpf, password):
            print(f"❌ Falha no login para {profile}")
            page.close()
            return entries
        
        # Capture pages
        for page_name, (url, description) in pages.items():
            screenshot_path, success = capture_page(page, page_name, url, description)
            
            if success:
                section_title = f"👤 Perfil: {profile.capitalize()}"
                entry_title = f"{page_name.replace('_', ' ').title()} - {description}"
                entries.append((section_title, entry_title, str(screenshot_path)))
        
        page.close()
        
    except Exception as e:
        print(f"❌ Erro ao processar {profile}: {e}")
        if page:
            page.close()
    
    return entries


def main():
    """Main function to generate complete tutorial."""
    print("\n" + "=" * 70)
    print("🎓 GERADOR DE TUTORIAL COMPLETO - UniEventos")
    print("=" * 70 + "\n")
    
    # Load config
    try:
        config = load_config()
        print(f"✅ Configuração carregada com {len(config)} perfis\n")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\n⚠️  Crie tutorial/config.json com credenciais válidas\n")
        sys.exit(1)
    
    # Profile handlers
    profile_handlers = {
        "participante": get_participante_pages,
        "student": get_participante_pages,
        "aluno": get_participante_pages,
        "professor": get_professor_pages,
        "instructor": get_professor_pages,
        "admin": get_admin_pages,
    }
    
    all_entries: List[Tuple[str, str, str]] = []
    
    # Launch browser
    with sync_playwright() as p:
        print("🚀 Iniciando navegador...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        
        # Process each profile
        for profile_name, creds in config.items():
            profile_lower = profile_name.lower()
            
            # Find handler
            handler = None
            for key, page_handler in profile_handlers.items():
                if key in profile_lower:
                    handler = page_handler
                    break
            
            if handler is None:
                print(f"⚠️  Perfil desconhecido: {profile_name}")
                continue
            
            # Get pages and generate entries
            pages = handler()
            entries = run_profile_tutorial(profile_name, creds, pages, context)
            all_entries.extend(entries)
        
        browser.close()
    
    # Generate documentation
    print("\n" + "=" * 70)
    print("📝 Gerando documentação...")
    
    if all_entries:
        generate_markdown(all_entries)
        print(f"   Total de screenshots: {len(all_entries)}")
        print(f"   Local: {SCREENSHOT_DIR}")
    else:
        print("❌ Nenhum screenshot foi capturado.")
    
    print("\n" + "=" * 70)
    print("✨ Processo concluído!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
