# Tutorial Canônico do Participante

## Visão geral

O fluxo oficial do projeto agora gera apenas o tutorial do participante/aluno. Ele é determinístico: por padrão, o comando limpa a base configurada, recria o schema, semeia um cenário fixo e produz um `tutorial/tutorial.md` humano, com screenshots e explicações de cada tela.

## Pré-requisitos

1. Dependências instaladas com `pip install -r requirements.txt`
2. Navegador do Playwright instalado com `playwright install`
3. Banco configurado no `.env`

## Reset oficial da base

O reset canônico é destrutivo e atua sobre o banco configurado no ambiente atual:

```bash
flask --app run.py tutorial-reset --yes
```

Depois do reset, o sistema fica com:

- 6 usuários fixos, um por perfil
- 1 curso: `Ciência da Computação`
- 1 evento: `Evento Tutorial do Participante`
- 2 atividades
- 1 inscrição inicial com presença confirmada e certificado emitido

## Geração oficial

Para gerar o tutorial completo:

```bash
python tutorial/run_tutorial.py
```

Esse comando executa automaticamente:

1. Reset e seed do cenário oficial
2. Captura das 18 telas canônicas do participante
3. Geração de `tutorial/tutorial.md`
4. Atualização de `tutorial/screenshots/*.png`

Durante depuração, se você já tiver preparado a base e quiser apenas repetir as capturas:

```bash
python tutorial/run_tutorial.py --skip-reset
```

## Configuração opcional

O arquivo `tutorial/config.json` é opcional. Se ele não existir, o gerador usa as credenciais fixas do seed oficial.

Exemplo:

```json
{
  "base_url": "http://127.0.0.1:5000",
  "participant": {
    "cpf": "444.555.666-77",
    "password": "1234"
  }
}
```

## Artefatos gerados

- `tutorial/tutorial.md`: guia em português com explicação do que o aluno vê e do que ele pode fazer em cada tela
- `tutorial/screenshots/*.png`: capturas oficiais em ordem determinística

## Telas canônicas

O conjunto oficial inclui:

1. Login
2. Cadastro
3. Recuperação de senha
4. Redefinição de senha
5. Dashboard com presença digital
6. Dashboard com filtros e eventos
7. Detalhes do evento
8. Evento após inscrição
9. Participações
10. Modal de certificados
11. Perfil com estatísticas
12. Histórico de eventos
13. Cronologia de atividades
14. Certificados emitidos
15. Modal de atualização cadastral
16. Modal de alteração de senha
17. Confirmação segura de presença
18. Presença confirmada

O visualizador nativo de PDF não faz parte do conjunto oficial de capturas; download e preview são explicados a partir da interface do próprio sistema.

## Scripts legados

Os scripts antigos multi-perfil em `tutorial/` foram preservados apenas como referência histórica. O pipeline suportado pelo projeto é `tutorial/run_tutorial.py` -> `tutorial/generate_participant_tutorial.py`.

## Solução de problemas

### `ModuleNotFoundError` ou falha ao iniciar o script

Use o wrapper oficial:

```bash
python tutorial/run_tutorial.py
```

### Erro do Playwright

Instale ou reinstale o Chromium:

```bash
playwright install chromium
```

### Falha de login no tutorial

Recrie a base do cenário oficial:

```bash
flask --app run.py tutorial-reset --yes
```
