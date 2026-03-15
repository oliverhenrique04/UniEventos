import argparse
import json
import pathlib
import sys
import time
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Thread
from urllib.parse import urlparse

from werkzeug.serving import make_server


BASE_DIR = pathlib.Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services.auth_service import AuthService
from app.tutorial_setup import (
    TUTORIAL_ACTIVITY_CHECKIN,
    TUTORIAL_EVENT_NAME,
    get_tutorial_runtime_context,
    reset_tutorial_database,
    tutorial_default_settings,
)
from app.utils import gerar_hash_dinamico, normalize_cpf

try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("Playwright e obrigatorio. Instale com: pip install -r requirements.txt")
    sys.exit(1)


CONFIG_PATH = BASE_DIR / "config.json"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
MARKDOWN_PATH = BASE_DIR / "tutorial.md"


@dataclass(frozen=True)
class CaptureMeta:
    filename: str
    title: str
    what_user_sees: str
    what_user_can_do: str


CAPTURE_PLAN = [
    CaptureMeta(
        filename="01_login.png",
        title="Login",
        what_user_sees="Tela inicial com acesso ao sistema por CPF e senha.",
        what_user_can_do="Autenticar-se no sistema, alternar a visualizacao da senha e iniciar o fluxo de recuperacao.",
    ),
    CaptureMeta(
        filename="02_cadastro.png",
        title="Cadastro",
        what_user_sees="Formulario de criacao de conta para novos participantes.",
        what_user_can_do="Informar nome, e-mail, CPF e senha para criar um novo acesso.",
    ),
    CaptureMeta(
        filename="03_recuperacao_senha.png",
        title="Recuperação de Senha",
        what_user_sees="Modal de recuperacao solicitado diretamente pela tela inicial.",
        what_user_can_do="Informar o e-mail cadastrado para receber as instrucoes de redefinicao.",
    ),
    CaptureMeta(
        filename="04_resetar_senha.png",
        title="Redefinição de Senha",
        what_user_sees="Tela segura de redefinicao aberta com token valido.",
        what_user_can_do="Cadastrar uma nova senha e concluir a recuperacao da conta.",
    ),
    CaptureMeta(
        filename="05_dashboard_checkin.png",
        title="Dashboard com Presença Digital",
        what_user_sees="Inicio do painel do participante com destaque para o registro de presenca por QR Code.",
        what_user_can_do="Abrir o leitor da camera, iniciar o check-in e acompanhar o feedback da validacao.",
    ),
    CaptureMeta(
        filename="06_dashboard_eventos.png",
        title="Dashboard com Filtros e Eventos",
        what_user_sees="Area de localizacao de eventos e lista de oportunidades abertas para inscricao.",
        what_user_can_do="Filtrar por nome, curso ou data e iniciar a inscricao nas atividades disponiveis.",
    ),
    CaptureMeta(
        filename="07_evento_detalhes.png",
        title="Detalhes do Evento",
        what_user_sees="Pagina publica do evento com descricao, cronograma e botoes de inscricao por atividade.",
        what_user_can_do="Ler as informacoes do evento, comparar atividades e decidir em quais deseja participar.",
    ),
    CaptureMeta(
        filename="08_evento_pos_inscricao.png",
        title="Evento após Inscrição",
        what_user_sees="Mesma tela de detalhes apos a inscricao do aluno na atividade de demonstracao.",
        what_user_can_do="Confirmar que a inscricao foi registrada e, se necessario, cancelar a participacao antes do evento.",
    ),
    CaptureMeta(
        filename="09_participacoes.png",
        title="Participações",
        what_user_sees="Pagina com os eventos em que a presenca do aluno ja foi confirmada.",
        what_user_can_do="Consultar horas conquistadas, revisar detalhes do evento e abrir a emissao de certificados.",
    ),
    CaptureMeta(
        filename="10_participacoes_certificados.png",
        title="Modal de Certificados da Página Participações",
        what_user_sees="Modal com os certificados ja disponiveis para as atividades concluidas.",
        what_user_can_do="Baixar ou visualizar os certificados emitidos sem sair da pagina de participacoes.",
    ),
    CaptureMeta(
        filename="11_perfil_visao_geral.png",
        title="Perfil com Estatísticas",
        what_user_sees="Resumo do aluno com dados cadastrais, horas acumuladas e navegacao por abas.",
        what_user_can_do="Acompanhar a evolucao academica e acessar rapidamente historico, cronologia e certificados.",
    ),
    CaptureMeta(
        filename="12_perfil_eventos.png",
        title="Perfil - Histórico de Eventos",
        what_user_sees="Aba com os eventos do aluno e atalho para abrir os detalhes de cada um.",
        what_user_can_do="Relembrar inscricoes anteriores e voltar aos detalhes do evento sempre que precisar.",
    ),
    CaptureMeta(
        filename="13_perfil_atividades.png",
        title="Perfil - Cronologia de Atividades",
        what_user_sees="Linha do tempo com atividades inscritas ou confirmadas, incluindo status individual.",
        what_user_can_do="Distinguir rapidamente o que ja teve presenca validada e o que ainda esta pendente.",
    ),
    CaptureMeta(
        filename="14_perfil_certificados.png",
        title="Perfil - Certificados Emitidos",
        what_user_sees="Colecao de certificados disponiveis para download e preview.",
        what_user_can_do="Baixar PDFs, abrir previews e conferir o hash publico de validacao.",
    ),
    CaptureMeta(
        filename="15_modal_atualizar_dados.png",
        title="Modal Atualizar Dados",
        what_user_sees="Janela de edicao dos dados cadastrais permitidos ao participante.",
        what_user_can_do="Atualizar nome e e-mail, mantendo CPF, RA e curso como campos apenas de consulta.",
    ),
    CaptureMeta(
        filename="16_modal_alterar_senha.png",
        title="Modal Alterar Senha",
        what_user_sees="Janela de troca de senha dentro do perfil do aluno.",
        what_user_can_do="Informar a senha atual, definir a nova credencial e confirmar a atualizacao do acesso.",
    ),
    CaptureMeta(
        filename="17_checkin_confirmacao.png",
        title="Confirmação Segura de Presença",
        what_user_sees="Tela segura aberta pelo QR Code dinamico, com dados da atividade e validacao geolocalizada.",
        what_user_can_do="Autorizar a localizacao e concluir o registro oficial de presenca na atividade.",
    ),
    CaptureMeta(
        filename="18_checkin_sucesso.png",
        title="Presença Confirmada",
        what_user_sees="Mensagem de sucesso exibida imediatamente apos a validacao da presenca.",
        what_user_can_do="Seguir para o perfil/certificados ou encerrar a tela com seguranca.",
    ),
]


def get_capture_plan():
    return list(CAPTURE_PLAN)


def load_settings(config_path=CONFIG_PATH, base_url=None):
    env_base_url = (base_url or "http://127.0.0.1:5000").rstrip("/")
    settings = tutorial_default_settings(base_url=env_base_url)

    if not pathlib.Path(config_path).exists():
        return settings

    raw = json.loads(pathlib.Path(config_path).read_text(encoding="utf-8"))
    participant = raw.get("participant") or raw.get("participante") or {}

    legacy_participant = raw.get("student") or raw.get("aluno") or {}
    if not participant and legacy_participant:
        participant = legacy_participant

    participant_cpf = participant.get("cpf")
    legacy_login = participant.get("username") or participant.get("login")
    if not participant_cpf and legacy_login:
        normalized_legacy_login = normalize_cpf(legacy_login)
        if normalized_legacy_login and len(normalized_legacy_login) == 11:
            participant_cpf = legacy_login
    participant_password = participant.get("password")

    if raw.get("base_url"):
        settings["base_url"] = str(raw["base_url"]).rstrip("/")
    if participant_cpf:
        settings["participant"]["cpf"] = participant_cpf
    if participant_password:
        settings["participant"]["password"] = participant_password

    return settings


def build_reset_password_token(app, username):
    with app.app_context():
        service = AuthService()
        serializer = service._password_reset_serializer()
        return serializer.dumps({"username": username})


class LocalFlaskServer:
    def __init__(self, app, host, port):
        self.app = app
        self.host = host
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        self._server = make_server(self.host, self.port, self.app)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)


def is_local_base_url(base_url):
    parsed = urlparse(base_url)
    return parsed.hostname in {"127.0.0.1", "localhost"}


def wait_for_server(base_url, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"Servidor indisponivel em {base_url}")


def is_server_available(base_url, timeout=1):
    try:
        wait_for_server(base_url, timeout=timeout)
        return True
    except Exception:
        return False


def ensure_output_dir():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for png_file in SCREENSHOT_DIR.glob("*.png"):
        png_file.unlink()


def save_screenshot(page, filename, full_page=False):
    path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(path), full_page=full_page)
    return path


def capture_viewport(page, filename, scroll_selector=None):
    if scroll_selector:
        page.locator(scroll_selector).scroll_into_view_if_needed()
        page.wait_for_timeout(400)
    return save_screenshot(page, filename, full_page=False)


def capture_top(page, filename):
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    return save_screenshot(page, filename, full_page=False)


def login(page, base_url, cpf, password):
    page.goto(f"{base_url}/")
    page.wait_for_selector("#loginCpf", timeout=10000)
    page.fill("#loginCpf", cpf)
    page.fill("#loginPass", password)
    with page.expect_response(lambda res: res.url.endswith("/api/login") and res.request.method == "POST"):
        page.locator("#pills-login button[type='submit']").click()
    page.wait_for_timeout(1200)
    page.wait_for_selector("#checkin-digital", timeout=15000)
    page.wait_for_timeout(1200)


def render_markdown(entries, generated_at, settings):
    lines = [
        "# Tutorial Canônico do Participante - UniEventos",
        "",
        f"> **Gerado em:** {generated_at.isoformat()} UTC",
        "",
        "## Resumo do cenário",
        "",
        "Este material foi gerado automaticamente a partir do cenário oficial e determinístico do participante.",
        f"O reset prepara a base com o evento **{TUTORIAL_EVENT_NAME}** e com a atividade **{TUTORIAL_ACTIVITY_CHECKIN}** pronta para demonstrar inscrição e check-in.",
        "",
        "### Credenciais do participante",
        "",
        f"- CPF: `{settings['participant']['cpf']}`",
        f"- Senha: `{settings['participant']['password']}`",
        "",
        "## Fluxo completo do aluno",
        "",
    ]

    for index, (meta, path) in enumerate(entries, start=1):
        relative_path = path.relative_to(BASE_DIR).as_posix()
        lines.extend(
            [
                f"### {index}. {meta.title}",
                "",
                f"![{meta.title}]({relative_path})",
                "",
                f"**O que o aluno vê:** {meta.what_user_sees}",
                "",
                f"**O que ele pode fazer:** {meta.what_user_can_do}",
                "",
            ]
        )

        if meta.filename == "10_participacoes_certificados.png":
            lines.append(
                "Os downloads e previews dos certificados podem ser feitos diretamente pelos cards e botoes do sistema; o visualizador nativo de PDF nao faz parte do conjunto oficial de telas."
            )
            lines.append("")

    lines.extend(
        [
            "## Encerramento",
            "",
            "Com essas telas, o participante entende como entrar no sistema, localizar eventos, se inscrever, confirmar presença, acompanhar o histórico e emitir certificados.",
            "",
        ]
    )
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def generate_tutorial(skip_reset=False, config_path=CONFIG_PATH):
    settings = load_settings(config_path=config_path)
    app = create_app()

    with app.app_context():
        if not skip_reset:
            reset_tutorial_database()
        runtime = get_tutorial_runtime_context()
        if not runtime["event_id"] or not runtime["activity_checkin_id"] or not runtime["event_token"]:
            raise RuntimeError("Cenario do tutorial nao encontrado. Execute o reset antes de capturar.")
        reset_token = build_reset_password_token(app, runtime["participant_username"])
        checkin_hash = gerar_hash_dinamico(runtime["activity_checkin_id"])

    local_server = None
    if is_local_base_url(settings["base_url"]) and not is_server_available(settings["base_url"], timeout=1):
        parsed = urlparse(settings["base_url"])
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        local_server = LocalFlaskServer(app, host, port)
        local_server.start()

    try:
        wait_for_server(settings["base_url"])
        ensure_output_dir()
        entries = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1600, "height": 1100},
                geolocation=runtime["coordinates"],
                permissions=["geolocation"],
                locale="pt-BR",
            )
            page = context.new_page()

            page.goto(f"{settings['base_url']}/")
            page.wait_for_selector("#loginCpf", timeout=10000)
            entries.append((CAPTURE_PLAN[0], capture_top(page, CAPTURE_PLAN[0].filename)))

            page.click("#pills-register-tab")
            page.wait_for_timeout(300)
            entries.append((CAPTURE_PLAN[1], capture_top(page, CAPTURE_PLAN[1].filename)))

            page.click("#pills-login-tab")
            page.click("button.forgot-link")
            page.wait_for_selector(".swal2-popup", timeout=10000)
            entries.append((CAPTURE_PLAN[2], capture_top(page, CAPTURE_PLAN[2].filename)))
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

            page.goto(f"{settings['base_url']}/resetar-senha/{reset_token}")
            page.wait_for_selector("#newPassword", timeout=10000)
            entries.append((CAPTURE_PLAN[3], capture_top(page, CAPTURE_PLAN[3].filename)))

            login(page, settings["base_url"], settings["participant"]["cpf"], settings["participant"]["password"])
            page.wait_for_selector("#checkin-digital", timeout=10000)
            entries.append((CAPTURE_PLAN[4], capture_top(page, CAPTURE_PLAN[4].filename)))

            page.wait_for_selector("#listaEventosAluno .col", timeout=10000)
            entries.append((CAPTURE_PLAN[5], capture_viewport(page, CAPTURE_PLAN[5].filename, "#filtPartNome")))

            page.goto(f"{settings['base_url']}/inscrever/{runtime['event_token']}")
            page.wait_for_selector("#lista-atividades-desktop", timeout=10000)
            page.wait_for_timeout(600)
            entries.append((CAPTURE_PLAN[6], capture_top(page, CAPTURE_PLAN[6].filename)))

            enroll_button = page.locator(f"button[data-atv-id='{runtime['activity_checkin_id']}']:visible").first
            with page.expect_response(
                lambda res: res.url.endswith("/api/toggle_inscricao") and res.request.method == "POST"
            ):
                enroll_button.click()
            page.wait_for_timeout(1200)
            entries.append((CAPTURE_PLAN[7], capture_top(page, CAPTURE_PLAN[7].filename)))

            page.goto(f"{settings['base_url']}/meus_eventos")
            page.wait_for_selector("#lista-participados .col", timeout=10000)
            entries.append((CAPTURE_PLAN[8], capture_top(page, CAPTURE_PLAN[8].filename)))

            page.locator("button[title='Emitir certificados']").first.click()
            page.wait_for_selector("#modalCertificadosEvento.show", timeout=10000)
            page.wait_for_selector("#corpo-certificados-evento a", timeout=10000)
            entries.append((CAPTURE_PLAN[9], capture_top(page, CAPTURE_PLAN[9].filename)))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            page.goto(f"{settings['base_url']}/perfil")
            page.wait_for_selector("#stat-hours", timeout=10000)
            page.wait_for_timeout(800)
            entries.append((CAPTURE_PLAN[10], capture_top(page, CAPTURE_PLAN[10].filename)))

            entries.append((CAPTURE_PLAN[11], capture_viewport(page, CAPTURE_PLAN[11].filename, "#lista-eventos")))

            page.locator("button[data-bs-target='#tab-atividades']").click()
            page.wait_for_selector("#tab-atividades.show.active", timeout=10000)
            page.wait_for_timeout(600)
            entries.append((CAPTURE_PLAN[12], capture_top(page, CAPTURE_PLAN[12].filename)))

            page.locator("button[data-bs-target='#tab-certificados']").click()
            page.wait_for_selector("#tab-certificados.show.active", timeout=10000)
            page.wait_for_timeout(600)
            entries.append((CAPTURE_PLAN[13], capture_top(page, CAPTURE_PLAN[13].filename)))

            page.click("button[onclick='abrirModalPerfilDados()']")
            page.wait_for_selector("#modalPerfilDados.show", timeout=10000)
            entries.append((CAPTURE_PLAN[14], capture_top(page, CAPTURE_PLAN[14].filename)))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            page.click("button[onclick='abrirModalSenha()']")
            page.wait_for_selector("#modalPerfilSenha.show", timeout=10000)
            entries.append((CAPTURE_PLAN[15], capture_top(page, CAPTURE_PLAN[15].filename)))
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)

            page.goto(
                f"{settings['base_url']}/confirmar_presenca/"
                f"{runtime['activity_checkin_id']}/{checkin_hash}"
            )
            page.wait_for_selector("#btn-confirmar", timeout=10000)
            entries.append((CAPTURE_PLAN[16], capture_top(page, CAPTURE_PLAN[16].filename)))

            with page.expect_response(lambda res: res.url.endswith("/api/validar_presenca") and res.request.method == "POST"):
                page.click("#btn-confirmar")
            page.wait_for_selector("text=Registro de Presença Realizado!", timeout=10000)
            page.wait_for_timeout(400)
            entries.append((CAPTURE_PLAN[17], capture_top(page, CAPTURE_PLAN[17].filename)))

            browser.close()

        generated_at = datetime.now(timezone.utc)
        render_markdown(entries, generated_at, settings)
        return entries
    finally:
        if local_server is not None:
            with suppress(Exception):
                local_server.stop()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Gera o tutorial oficial do participante.")
    parser.add_argument("--skip-reset", action="store_true", help="Nao recria a base antes das capturas.")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Arquivo JSON opcional com base_url e credenciais.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    entries = generate_tutorial(skip_reset=args.skip_reset, config_path=args.config)
    print(f"Tutorial gerado com {len(entries)} capturas em {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
