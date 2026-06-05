# Certificados de equipe - bloqueio de exclusao e acesso na pagina de eventos

Data: 2026-06-05

## Objetivo

Ajustar dois pontos do fluxo de certificados de equipe ja implementado:

- impedir exclusao de eventos que ainda possuem destinatarios de certificados de equipe vinculados
- expor um acesso visual separado, na pagina de eventos, para a gestao operacional de certificados de equipe

Tambem faz parte deste trabalho remover o evento local temporario usado apenas para validacao manual do fluxo, sem deixar dados artificiais na base.

## Decisoes aprovadas

- Eventos com destinatarios de certificados de equipe vinculados devem ter a exclusao bloqueada.
- O acesso a certificados de equipe na pagina de eventos deve aparecer como acao separada da acao atual de certificados de participantes.
- A acao separada deve abrir o fluxo operacional de equipe em `/certificados_equipe/<event_id>`.

## Fora do escopo

- Redesenhar o fluxo atual de certificados de participantes.
- Unificar participantes e equipe em uma unica tela.
- Alterar a modelagem central de `EventTeamCertificateRecipient`.
- Reabrir o desenho do designer de equipe ou do designer de participantes.

## Regras de exclusao

`EventService.get_event_delete_block_status()` deve passar a considerar tambem os registros de `EventTeamCertificateRecipient` vinculados ao evento.

Com isso:

- `has_linked_records` deve ficar verdadeiro quando houver destinatarios de certificados de equipe, mesmo sem inscricoes ou matriculas.
- a mensagem de bloqueio deve citar tambem os destinatarios de certificados de equipe, para deixar claro o motivo funcional do bloqueio.
- qualquer fluxo existente que ja dependa desse status deve continuar funcionando, mas agora com a nova protecao incluida.

O sistema nao deve excluir automaticamente os destinatarios de equipe para liberar a remocao do evento. A regra aprovada e de bloqueio, nao de limpeza implicita.

## UI da pagina de eventos

A pagina de eventos deve manter a acao atual de certificados de participantes sem mudar seu comportamento.

Uma segunda acao visivel deve ser adicionada ao mesmo contexto visual da listagem/card de eventos para equipe:

- identificacao clara em portugues, como `Certificados da equipe`
- icone ou botao separado da acao atual de participantes
- destino em `/certificados_equipe/<event_id>`

Essa acao deve respeitar a mesma logica de permissao de visualizacao de certificados do evento, para nao aparecer como atalho inutil para perfis sem acesso.

## Validacao e testes

Cobertura minima esperada:

- teste para provar que destinatarios de equipe entram no bloqueio de exclusao do evento
- teste para provar que a pagina de eventos expoe a nova acao separada para equipe
- teste para garantir que a acao atual de certificados de participantes continua presente e intacta

Verificacao apos implementacao:

- testes focados de servico/UI afetados
- `python -m pytest -q`
- checagem funcional da rota de equipe a partir da pagina de eventos

## Limpeza de dados temporarios

O evento local de validacao `Evento Verificacao Designer Certificados` criado apenas para teste manual deve ser removido ao fim do trabalho, junto com qualquer dado temporario associado criado exclusivamente para essa validacao.

Se a nova regra de bloqueio impedir a remocao direta, a limpeza deve remover primeiro os registros temporarios de equipe ligados a esse evento e depois excluir o evento de validacao.

## Riscos e mitigacoes

- Risco: bloquear exclusao em cenarios onde o usuario esperava cascade silencioso. Mitigacao: alinhar o comportamento com a regra ja existente de registros vinculados e explicitar a causa na mensagem.
- Risco: poluir a pagina de eventos com uma acao ambigua. Mitigacao: manter acao separada e rotulo explicito para equipe.
- Risco: quebrar o fluxo atual de participantes ao tocar na mesma area da UI. Mitigacao: validar a permanencia da acao atual e cobrir com teste especifico.
