# Design: Co-responsaveis em eventos

## Contexto

O sistema hoje modela a autoria de um evento com um unico campo `owner_username` na entidade `Event`. Esse campo e usado ao mesmo tempo como referencia visual do dono, origem de permissoes, filtro de listagens, criterio de notificacao e base da serializacao do evento.

O novo requisito e permitir que um evento tenha varios responsaveis, com um deles marcado como principal. O principal e a referencia visual padrao, mas principal e co-responsaveis devem ter as mesmas permissoes operacionais.

## Objetivo

Permitir a vinculacao de varios responsaveis a um evento, com exatamente um responsavel principal, garantindo:

- permissao equivalente entre principal e co-responsaveis
- exibicao da lista completa de responsaveis na interface
- compatibilidade gradual com fluxos legados que ainda dependem de `owner_username`
- migracao segura dos eventos ja existentes

## Fora de escopo

- remocao imediata do campo `owner_username`
- redefinicao completa do modelo de papeis da aplicacao
- delegacao de responsabilidade para usuarios sem perfil de gestao de eventos
- revisao de layout ampla fora das telas de criacao, edicao, listagem e detalhes do evento

## Abordagem escolhida

Foi escolhida a modelagem relacional unica para responsaveis do evento, com um marcador de principal.

Essa abordagem substitui a logica de autoridade baseada apenas em `owner_username` por uma tabela dedicada, mas mantem `owner_username` temporariamente como espelho do principal para reduzir risco em pontos legados do sistema.

## Modelo de dados

### Nova entidade

Criar uma entidade relacional dedicada, sugerida como `EventResponsible`, com os campos:

- `event_id`: FK para `events.id`
- `user_username`: FK para `users.username`
- `is_primary`: booleano obrigatorio
- `created_at`: opcional, para auditoria

### Regras de integridade

- cada evento deve ter pelo menos um responsavel
- cada evento deve ter exatamente um responsavel principal
- um mesmo usuario nao pode aparecer mais de uma vez como responsavel do mesmo evento
- o usuario marcado como principal deve necessariamente estar presente na lista de responsaveis

### Compatibilidade com legado

O campo `Event.owner_username` permanece em fase de transicao, com as regras:

- a nova tabela passa a ser a fonte de verdade para permissoes e relacao de responsaveis
- `owner_username` passa a espelhar o username do responsavel principal
- gravacoes que alterem o principal devem sincronizar `owner_username`
- leituras legadas que usam `owner_username` continuam funcionando durante a transicao

## Autoridade e permissoes

### Regra principal

Principal e co-responsaveis terao as mesmas permissoes operacionais:

- editar o evento
- gerenciar participantes
- adicionar participantes
- enviar notificacoes
- operar fluxos de certificados em que hoje o dono do evento possui acesso

### Diferenca do principal

O principal existe apenas para:

- ser a referencia visual padrao em listagens resumidas
- alimentar `owner_username` durante a transicao
- servir como fallback para fluxos legados que ainda esperam um unico dono

### Restricao de elegibilidade

So podem ser vinculados como responsaveis usuarios aptos a gestao de eventos no sistema. Isso evita que o vinculo a um evento conceda, por si so, uma elevacao de privilegio para perfis que hoje nao deveriam administrar eventos.

## Fluxo funcional

### Criacao de evento

- o evento nasce com pelo menos um responsavel
- o usuario autenticado entra por padrao como principal
- a interface permite adicionar outros responsaveis antes de salvar
- a interface permite escolher qual deles sera o principal

### Edicao de evento

- qualquer responsavel vinculado ao evento pode editar os responsaveis
- e permitido adicionar novos co-responsaveis
- e permitido remover co-responsaveis
- e permitido trocar o principal
- nao e permitido salvar sem responsaveis
- nao e permitido salvar com dois principais
- nao e permitido remover o principal sem indicar outro principal na mesma operacao

### Exibicao

- a interface sempre mostra todos os responsaveis do evento
- o principal aparece primeiro e com indicacao clara de responsavel principal
- onde hoje a aplicacao exibe apenas um dono, pode continuar mostrando o principal com um indicador de que ha outros vinculados

## Impacto por camada

### Modelos

Atualizar `app/models.py` para:

- declarar a nova entidade de relacao entre evento e usuario
- adicionar relacionamento de responsaveis em `Event`
- manter `owner_username` enquanto o sistema ainda usa compatibilidade gradual

### Servico de eventos

Atualizar `app/services/event_service.py` para:

- criar metodos de sincronizacao dos responsaveis
- substituir verificacoes de autoria por verificacoes baseadas na nova relacao
- garantir exatamente um principal nas operacoes de create e update
- adaptar notificacoes automaticas para todos os responsaveis

Metodos hoje acoplados ao dono unico, como permissao de edicao, listagem, notificacao e visualizacao de evento, devem consultar a nova relacao e nao apenas `owner_username`.

### Serializacao

Atualizar `app/serializers.py` para devolver:

- `responsavel_principal`
- `responsaveis`
- `owner` e `owner_name` de forma derivada do principal, apenas para compatibilidade temporaria

Estrutura sugerida:

- `responsavel_principal`: objeto com username, nome e metadados relevantes
- `responsaveis`: lista completa de objetos de usuarios vinculados, com flag `is_primary`

### API

Atualizar `app/api/events.py` para que criacao e edicao aceitem um payload contendo a lista de responsaveis e qual e o principal.

Validacoes obrigatorias:

- lista nao vazia
- usernames existentes
- usuarios elegiveis para gestao
- sem duplicidade
- exatamente um principal

### Repositorio e consultas

Atualizar listagens e filtros que hoje dependem de `Event.owner_username` para considerar qualquer usuario vinculado como responsavel.

Isso inclui:

- listagens administrativas
- filtros por responsavel no painel
- consultas restritas ao usuario autenticado

Durante a transicao, consultas resumidas ainda podem derivar o principal via `owner_username`, mas regras de acesso devem migrar para a nova relacao.

### Interface

Atualizar `app/templates/event_create.html` e `app/templates/event_edit.html` para incluir:

- componente de selecao multipla de responsaveis
- marcacao visual do responsavel principal
- validacao client-side para impedir estados invalidos obvios

Atualizar telas e componentes de exibicao, como listagens administrativas e detalhes do evento, para mostrar:

- principal em destaque
- lista completa de co-responsaveis

## Migracao de dados

### Passos

1. criar a nova tabela de responsaveis do evento
2. migrar os eventos existentes copiando `owner_username` para a nova tabela com `is_primary = true`
3. manter `owner_username` sincronizado com o principal em todas as gravacoes posteriores
4. alterar leitura de permissoes e filtros para consultar a nova tabela

### Garantias da migracao

- todo evento legado com `owner_username` valido passa a ter um responsavel principal correspondente
- eventos sem `owner_username` exigem estrategia explicita de fallback na migracao

### Estrategia para eventos sem owner

Caso existam eventos legados sem `owner_username`, a migracao nao deve inventar um usuario automaticamente. Esses registros devem ser identificados e tratados de uma das duas formas:

- bloqueio da migracao com mensagem clara para saneamento manual, se houver qualquer evento inconsistente
- atribuicao controlada a um usuario tecnico do sistema, apenas se essa conta ja existir e a equipe aceitar esse comportamento

A recomendacao e bloquear a migracao nesses casos, para nao mascarar dados inconsistentes.

## Notificacoes

As notificacoes automaticas associadas ao ciclo de vida do evento passam a ser enviadas para todos os responsaveis vinculados.

Regras:

- se houver principal e co-responsaveis, todos recebem e-mail
- o conteudo pode manter o principal como referencia nominal, mas nao deve omitir os demais no envio
- duplicidades de destinatario devem ser evitadas

## Compatibilidade e transicao

### Fase 1

- nova tabela introduzida
- `owner_username` mantido como espelho do principal
- serializacao expande resposta com principal e lista completa
- permissao migra para a relacao nova

### Fase 2 futura

- remocao de dependencias residuais de `owner_username`
- eliminacao do campo do modelo e do banco, se nao houver mais consumidores

Essa segunda fase nao faz parte desta entrega.

## Testes

### Testes de comportamento minimo

- criar evento com varios responsaveis e um principal
- editar evento adicionando co-responsavel
- editar evento removendo co-responsavel
- trocar o principal do evento
- impedir salvamento sem principal
- impedir salvamento com mais de um principal
- impedir duplicidade do mesmo usuario como responsavel
- garantir que principal e co-responsavel possam editar e gerenciar o evento
- garantir que usuario fora da lista nao ganhe permissao
- garantir que filtros por responsavel retornem eventos onde o usuario e principal ou co-responsavel
- garantir que a serializacao devolva principal e lista completa
- garantir que `owner_username` continue refletindo o principal durante a transicao

### Testes de migracao

- converter evento legado com `owner_username` em um registro principal na nova tabela
- falhar explicitamente ou sinalizar eventos legados sem responsavel principal valido

## Riscos e mitigacoes

### Risco: dependencia espalhada de owner_username

Mitigacao:

- manter `owner_username` temporariamente
- migrar primeiro a logica de permissao e consulta
- manter respostas legadas derivadas do principal

### Risco: quebra de filtros e dashboards

Mitigacao:

- adaptar consultas que filtram por dono unico para `join` na relacao de responsaveis
- validar explicitamente os filtros existentes no painel administrativo e no dashboard

### Risco: inconsistencias de principal

Mitigacao:

- validar no backend, independentemente da interface
- garantir sincronizacao atomica entre tabela de responsaveis e `owner_username`

## Decisoes tomadas

- o sistema tera uma tabela unica de responsaveis por evento
- havera exatamente um principal por evento
- principal e co-responsaveis terao as mesmas permissoes operacionais
- a interface mostrara todos os responsaveis
- `owner_username` sera mantido temporariamente como espelho do principal
- apenas usuarios elegiveis para gestao de eventos poderao ser vinculados como responsaveis

## Criterios de aceite

- um evento pode ser salvo com varios responsaveis e exatamente um principal
- principal e co-responsaveis conseguem operar o evento com a mesma permissao
- telas de criacao, edicao e administracao exibem todos os responsaveis
- filtros e listagens consideram qualquer responsavel vinculado
- eventos legados sao migrados sem perda de autoria principal
- o sistema continua funcionando nos pontos ainda dependentes de `owner_username` durante a transicao