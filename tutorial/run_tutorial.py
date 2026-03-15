"""Wrapper oficial para gerar o tutorial canônico do participante."""

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).parent


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    command = [sys.executable, str(BASE_DIR / "generate_participant_tutorial.py"), *args]

    print("\n" + "=" * 80)
    print("TUTORIAL CANONICO DO PARTICIPANTE - UNIEVENTOS")
    print("=" * 80 + "\n")

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"\nFalha ao gerar o tutorial: {exc}\n")
        sys.exit(exc.returncode or 1)
    except KeyboardInterrupt:
        print("\nProcesso interrompido pelo usuario.\n")
        sys.exit(130)

    print("Arquivos gerados:")
    print(f"- Markdown: {BASE_DIR / 'tutorial.md'}")
    print(f"- Screenshots: {BASE_DIR / 'screenshots'}")
    print("\nUse --skip-reset para reutilizar a base atual durante depuracao.\n")


if __name__ == "__main__":
    main()
