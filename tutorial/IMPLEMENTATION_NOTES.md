# Notas Técnicas do Tutorial Canônico

## Objetivo

O pipeline oficial foi reduzido para um único tutorial em português, focado exclusivamente no participante/aluno. A meta é produzir sempre o mesmo cenário e a mesma ordem de capturas, facilitando manutenção, testes e documentação.

## Componentes principais

### `app/tutorial_setup.py`

Responsável por:

- recriar o schema da base atual com `db.drop_all()` + `db.create_all()`
- semear o cenário canônico
- disponibilizar constantes reutilizáveis do tutorial
- fornecer o contexto dinâmico usado pelo gerador

### `flask tutorial-reset --yes`

Comando destrutivo exposto em `app/cli.py`. Ele:

1. limpa a base configurada no ambiente
2. recria o schema
3. cria 6 usuários fixos
4. cria 1 curso, 1 evento padrão e 2 atividades
5. deixa 1 inscrição inicial com presença e certificado emitido

### `tutorial/generate_participant_tutorial.py`

Gerador oficial baseado em Playwright. Ele:

- carrega `tutorial/config.json` apenas se existir
- usa credenciais default do seed oficial como fallback
- executa o reset por padrão
- sobe um servidor Flask local quando a `base_url` é local e ainda não existe servidor ativo
- captura as 18 telas canônicas do participante
- monta o `tutorial/tutorial.md` com descrição do que o aluno vê e do que ele pode fazer

## Testes automatizados

### `tutorial/test_tutorial_generation.py`

Valida:

- fallback de configuração
- formato aceito do `config.json`
- ordem e estabilidade do plano de capturas
- geração do token de reset
- estrutura do Markdown final

### `tutorial/test_participante.py`

Valida:

- proteção do comando `tutorial-reset`
- contagens exatas após recriação da base
- fluxo de login, inscrição, check-in, histórico e certificados do participante

## Compatibilidade

O wrapper suportado pelo projeto é `python tutorial/run_tutorial.py`. Scripts antigos multi-perfil foram mantidos apenas para referência histórica e não devem ser usados como ponto de entrada principal.
