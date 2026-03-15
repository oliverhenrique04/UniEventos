"""Script principal para geração completa do tutorial UniEventos.

Este script orquestra todo o processo de geração de tutoriais, incluindo:
1. Verificação de pré-requisitos
2. Validação de configuração
3. Geração de screenshots para todos os perfis
4. Criação da documentação Markdown
5. Relatório final

Uso:
    python tutorial/gerar_tutorial_completo.py
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime


def print_header():
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(" " * 20 + "🎓 UNIEVENTOS")
    print(" " * 15 + "GERADOR DE TUTORIAL COMPLETO")
    print("=" * 80 + "\n")


def print_step(step_num: int, message: str):
    """Print formatted step."""
    print(f"📌 Passo {step_num}: {message}")
    print("-" * 80)


def check_prerequisites():
    """Check if all prerequisites are installed."""
    print_step(1, "Verificando pré-requisitos...")
    
    # Check Playwright
    try:
        from playwright.sync_api import sync_playwright
        print("  ✅ Playwright instalado")
    except ImportError:
        print("  ❌ Playwright não encontrado!")
        print("  💡 Execute: pip install playwright")
        return False
    
    # Check config file
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        print("  ❌ Arquivo config.json não encontrado!")
        print("  💡 Copie config.example.json para config.json e edite")
        return False
    
    print("  ✅ Configuração encontrada")
    return True


def validate_config():
    """Validate configuration file."""
    print_step(2, "Validando configuração...")
    
    try:
        import json
        config_path = Path(__file__).parent / "config.json"
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        required_profiles = ["admin", "professor", "participante"]
        found_profiles = list(config.keys())
        
        print(f"  ✅ {len(found_profiles)} perfis encontrados: {', '.join(found_profiles)}")
        
        # Check for required fields
        for profile, creds in config.items():
            if "username" not in creds or "password" not in creds:
                print(f"  ⚠️ Perfil {profile}缺少 credenciais completas")
                return False
        
        print("  ✅ Todos os perfis têm credenciais válidas")
        return True
        
    except Exception as e:
        print(f"  ❌ Erro ao validar config: {e}")
        return False


def check_server():
    """Check if server is running."""
    print_step(3, "Verificando servidor...")
    
    try:
        import urllib.request
        base_url = os.getenv("BASE_URL", "http://localhost:5000")
        
        response = urllib.request.urlopen(f"{base_url}/", timeout=5)
        if response.status == 200:
            print(f"  ✅ Servidor rodando em {base_url}")
            return True
        else:
            print(f"  ⚠️ Servidor retornou status {response.status}")
            return False
            
    except Exception as e:
        print(f"  ❌ Servidor não está acessível!")
        print(f"  💡 Execute: python run.py")
        return False


def generate_tutorial():
    """Run the tutorial generation script."""
    print_step(4, "Gerando screenshots e documentação...")
    
    try:
        script_path = Path(__file__).parent / "generate_full_tutorial.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print("  ✅ Tutorial gerado com sucesso!")
            return True
        else:
            print(f"  ❌ Erro na geração do tutorial")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Erro ao executar script: {e}")
        return False
    except KeyboardInterrupt:
        print("\n  ⚠️ Processo interrompido pelo usuário")
        return False


def show_results():
    """Show generated files and statistics."""
    print_step(5, "Resultados da geração...")
    
    screenshots_dir = Path(__file__).parent / "screenshots"
    tutorial_md = Path(__file__).parent / "tutorial.md"
    
    # Count screenshots
    if screenshots_dir.exists():
        screenshot_files = list(screenshots_dir.glob("*.png"))
        print(f"  📸 Screenshots gerados: {len(screenshot_files)}")
        
        # Group by profile
        profiles = {}
        for file in screenshot_files:
            profile = file.stem.split("_")[0] if "_" in file.stem else "unknown"
            profiles[profile] = profiles.get(profile, 0) + 1
        
        print("\n  Por perfil:")
        for profile, count in sorted(profiles.items()):
            print(f"    • {profile.capitalize()}: {count} screenshots")
    
    # Check Markdown files
    md_files = list(Path(__file__).parent.glob("tutorial*.md"))
    print(f"\n  📄 Arquivos Markdown: {len(md_files)}")
    for md_file in md_files:
        size = md_file.stat().st_size
        print(f"    • {md_file.name} ({size:,} bytes)")
    
    print(f"\n  📁 Localização: {Path(__file__).parent.absolute()}")


def print_footer(success: bool):
    """Print formatted footer."""
    print("\n" + "=" * 80)
    if success:
        print("✨ Processo concluído com sucesso!")
        print("💡 Abra tutorial.md para visualizar o tutorial completo")
    else:
        print("⚠️ Processo concluído com erros")
        print("💡 Verifique os logs acima para detalhes")
    print("=" * 80 + "\n")


def main():
    """Main execution flow."""
    print_header()
    
    # Step 1: Check prerequisites
    if not check_prerequisites():
        print_footer(False)
        sys.exit(1)
    
    # Step 2: Validate config
    if not validate_config():
        print_footer(False)
        sys.exit(1)
    
    # Step 3: Check server (optional warning)
    server_running = check_server()
    if not server_running:
        response = input("\n  ⚠️ Servidor não está rodando. Deseja continuar? (s/n): ")
        if response.lower() != 's':
            print_footer(False)
            sys.exit(1)
    
    # Step 4: Generate tutorial
    success = generate_tutorial()
    
    # Step 5: Show results
    if success:
        show_results()
    
    # Footer
    print_footer(success)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
