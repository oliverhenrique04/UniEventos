# Sistema de Tutorial do Participante

Este diretório contém o pipeline oficial de geração do tutorial do participante/aluno. O fluxo suportado é determinístico: ele recria o banco configurado, prepara um cenário mínimo e produz o guia em português com screenshots oficiais.

## Fluxo oficial

### Reset destrutivo da base

```bash
flask --app run.py tutorial-reset --yes
```

### Geração do tutorial

```bash
python tutorial/run_tutorial.py
```

Por padrão, o wrapper faz:

1. Reset e seed do cenário canônico
2. Inicialização local do app, quando necessário
3. Captura das telas do participante com Playwright
4. Geração de `tutorial/tutorial.md`

Para depuração:

```bash
python tutorial/run_tutorial.py --skip-reset
```

## Arquivos principais

- `generate_participant_tutorial.py`: gerador oficial do tutorial
- `run_tutorial.py`: wrapper principal do fluxo suportado
- `config.example.json`: exemplo de configuração opcional
- `test_tutorial_generation.py`: testes dos helpers do gerador
- `test_participante.py`: testes de reset e smoke flow do participante

## Saída gerada

- `tutorial.md`: guia final do participante
- `screenshots/*.png`: capturas oficiais em ordem determinística

## Configuração opcional

Se `tutorial/config.json` não existir, o gerador usa as credenciais fixas do cenário oficial:

```json
{
  "base_url": "http://127.0.0.1:5000",
  "participant": {
    "cpf": "444.555.666-77",
    "password": "1234"
  }
}
```

## Cenário semeado

O reset cria exatamente:

- 6 usuários, um por perfil
- 1 curso: `Ciência da Computação`
- 1 evento: `Evento Tutorial do Participante`
- 2 atividades
- 1 inscrição inicial concluída, com presença e certificado emitido

## Scripts legados

Os arquivos antigos `generate_full_tutorial.py`, `generate_tutorial.py`, `generate_tutorial_complete.py` e `gerar_tutorial_completo.py` foram preservados apenas como legado. Eles não fazem parte do caminho principal do projeto.
