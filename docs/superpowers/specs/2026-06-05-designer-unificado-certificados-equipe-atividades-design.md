# Designer Unificado e Gestao de Certificados de Equipe por Atividade Design

**Data:** 2026-06-05

**Objetivo**

Reestruturar o fluxo de certificados de participantes e equipe em torno de um contrato comum de designer/bootstrap, eliminando a logica fragil embutida no HTML, corrigindo o comportamento de tela em branco no designer de participantes com fallback seguro, e tornando os certificados de equipe padrao derivados de atividades vinculadas ao evento e responsaveis do evento, mantendo complemento manual.

## Escopo

- Revisar a definicao do template de certificados de participantes e equipe para um formato comum e normalizado.
- Unificar a inicializacao do designer de certificados para `event` e `team_event` com um payload de bootstrap comum vindo do backend.
- Corrigir o fluxo do designer de participantes para que falhas de template/bootstrap/hidratacao nao resultem em tela em branco.
- Reestruturar a gestao de certificados de equipe para que a origem padrao dos destinatarios seja:
  - pessoas vinculadas a atividades do evento
  - responsaveis do evento
  - complementos manuais
- Garantir que, para equipe, uma mesma pessoa vinculada a duas atividades gere um certificado por atividade.

## Fora De Escopo

- Reescrever o designer institucional neste ciclo, exceto se for necessario preservar o contrato compartilhado sem regressao.
- Alterar as regras de permissao ja existentes para visualizar ou gerenciar certificados.
- Remover o cadastro manual de destinatarios de equipe.

## Problemas Atuais

### 1. Designer com estado espalhado e fragil

Hoje o designer de certificados monta parte importante do estado diretamente no template Jinja, com variacoes por `designer_mode`, `event.tipo`, valores persistidos em JSON e regras de fallback no frontend. Isso aumenta o risco de:

- divergencia entre participantes e equipe
- regressao ao abrir templates antigos ou corrompidos
- falhas de inicializacao que deixam a experiencia quebrada sem estado de erro claro

### 2. Gestao de equipe centrada no evento com sincronizacao lateral

Hoje os certificados de equipe existem como destinatarios do evento, com sincronizacao automatica separada e CRUD manual. Isso atende parte do fluxo, mas nao deixa explicito no modelo funcional que a origem padrao do certificado de equipe deve vir das atividades vinculadas ao evento, com um certificado por atividade quando houver multiplos vinculos.

### 3. Falha percebida no designer de participantes

O relato do usuario e que o designer de participantes fica em branco em qualquer evento. A reproducao local atual nao mostrou a falha, entao o design precisa incluir instrumentacao e fallback operacional em vez de assumir uma unica causa. O objetivo desta entrega nao e mascarar o problema, e sim garantir que:

- a causa seja observavel
- o frontend nao morra silenciosamente
- um template salvo invalido ou incompativel nao derrube a tela inteira

## Arquitetura Proposta

### Contrato Unificado De Designer

Participantes e equipe passam a compartilhar um contrato comum de bootstrap para o designer, com estes campos de alto nivel:

- `designer_mode`
- `entity_id`
- `template`
- `background`
- `fixed_validation_elements`
- `preview_data`
- `permissions`
- `recipient_scope`
- `warnings`

O frontend deixa de decidir a regra principal do template e passa a consumir um payload ja normalizado pelo backend.

### Servicos Principais

#### `DesignerBootstrapService`

Responsabilidades:

- receber `event_id` e `designer_mode`
- carregar configuracao persistida
- aplicar defaults corretos para o modo
- gerar preview data inicial
- devolver avisos de fallback ou normalizacao

#### `CertificateTemplateResolver`

Responsabilidades:

- validar schema do template salvo
- normalizar o formato do template
- converter legado quando necessario
- aplicar fallback seguro quando o template salvo for invalido, ausente ou incompativel

#### `TeamRecipientResolver`

Responsabilidades:

- resolver destinatarios padrao de equipe a partir de atividades do evento
- incluir responsaveis do evento
- incorporar complementos manuais
- materializar a lista final usada em preview, envio individual e envio em lote

## Modelo Funcional Do Designer

### Participantes

O designer de participantes continuara ligado ao evento, mas passara a abrir a partir de um bootstrap normalizado pelo backend. O frontend recebera um template consistente e so tratara renderizacao, interacao e persistencia.

Se o template salvo estiver invalido, o backend retornara um fallback seguro e um aviso explicito. A interface devera exibir esse aviso ao usuario em vez de ficar em branco.

### Equipe

O designer de equipe continuara sendo um modo distinto (`team_event`), mas compartilhando o mesmo contrato comum. O texto padrao, as variaveis disponiveis e o conjunto de preview data serao especificos do modo, sem duplicar a logica principal de bootstrap no HTML.

## Modelo Funcional Da Gestao De Equipe

### Origem Padrao Dos Destinatarios

Os destinatarios padrao de equipe serao derivados de:

1. pessoas vinculadas a atividades do evento
2. responsaveis do evento
3. complementos manuais

### Regra De Emissao

- vinculo vindo de atividade gera um certificado por atividade
- responsavel sem atividade vinculada gera um certificado por evento
- o manual continua permitido como complemento

### Regra De Identidade E Duplicidade

A resolucao de destinatarios de equipe deve considerar, no minimo, estes eixos:

- evento
- atividade
- pessoa
- papel
- origem

Isso evita colapsar incorretamente dois vinculos distintos da mesma pessoa em atividades diferentes.

### Materializacao Da Lista Final

A tela de certificados de equipe deixara de depender de uma lista parcialmente manual como fonte principal. Ela exibira uma lista resolvida final, composta por:

- itens automaticos derivados de atividade
- itens automaticos derivados de responsavel
- itens manuais complementares

Os fluxos de preview, download, reenvio e envio em lote devem usar essa mesma lista resolvida como fonte de verdade.

## Fluxos

### Abertura Do Designer

1. usuario abre `/designer_certificado/<event_id>` ou `/designer_certificado_equipe/<event_id>`
2. a pagina carrega a casca visual do editor
3. o frontend requisita o bootstrap comum ao backend
4. o backend devolve template normalizado, elementos fixos, preview data, permissoes e avisos
5. o frontend hidrata o canvas
6. se houver falha de template persistido, usa fallback e mostra aviso visivel

### Salvar Layout

1. frontend exporta layout no formato comum
2. backend valida o schema
3. backend persiste o formato normalizado
4. resposta informa sucesso ou erro explicito

### Listagem De Equipe

1. tela de equipe solicita a lista resolvida
2. backend combina atividade, responsaveis e manuais
3. frontend renderiza a lista final com origem e contexto

### Envio Em Lote De Equipe

1. usuario dispara envio em lote
2. backend resolve a lista final antes do envio
3. certificados sao gerados conforme a regra de um por atividade ou um por evento
4. status de entrega e hashes sao persistidos de forma consistente

## Tratamento De Falhas

### Designer Em Branco

O sistema deve tratar como estados visiveis e observaveis, e nao silenciosos:

- erro ao obter bootstrap
- erro de parse do template salvo
- erro ao converter template legado
- erro na hidratacao do canvas

Comportamento esperado:

- registrar erro no backend quando a causa estiver no payload ou persistencia
- exibir aviso operacional no frontend
- usar fallback seguro quando possivel
- nao deixar a pagina inteira sem resposta visual

### Templates Invalidos

Se um template salvo estiver corrompido ou fora do contrato:

- o backend nao deve reaproveita-lo cegamente
- o resolver deve devolver um template fallback valido
- o usuario deve receber aviso de que o layout salvo precisou ser normalizado/substituido para abertura segura

## UI E UX

- O designer deve continuar visualmente familiar ao fluxo atual.
- A tela de equipe deve explicitar que a origem padrao dos destinatarios vem de atividades e responsaveis.
- O manual deve ser apresentado como complemento, nao como origem principal.
- Mensagens ao usuario permanecem em portugues.

## Impacto Em Dados

- Participantes permanecem persistidos em `Event.cert_template_json` e `Event.cert_bg_path`, mas sob contrato normalizado.
- Equipe permanece persistida em `Event.cert_team_template_json` e `Event.cert_team_bg_path`, mas sob o mesmo contrato estrutural.
- A resolucao de destinatarios de equipe pode continuar materializando registros persistidos, desde que a origem final observavel seja coerente com `atividades + responsaveis + manuais`.

## Testes Necessarios

### Designer

- abrir designer de participantes com template vazio
- abrir designer de participantes com template valido
- abrir designer de participantes com template legado
- abrir designer de participantes com template corrompido
- abrir designer de equipe com o mesmo contrato de bootstrap

### Bootstrap E Persistencia

- validar payload de bootstrap comum para `event`
- validar payload de bootstrap comum para `team_event`
- validar persistencia apenas de template normalizado

### Equipe

- resolver destinatarios com apenas atividades
- resolver destinatarios com apenas responsaveis
- resolver destinatarios com atividades + responsaveis
- resolver a mesma pessoa em duas atividades como dois certificados distintos
- manter complemento manual sem sobrescrever a origem automatica
- garantir que envio individual e lote usem a lista resolvida final

## Riscos E Mitigacoes

- **Risco:** ampliar demais o escopo ao tentar reescrever todos os modos de certificado.
  - **Mitigacao:** manter o foco em `event` e `team_event`, preservando institucional salvo o contrato compartilhado necessario.

- **Risco:** quebrar templates existentes ao endurecer validacao.
  - **Mitigacao:** resolver legado no backend e aplicar fallback seguro com aviso.

- **Risco:** duplicidade incorreta na equipe.
  - **Mitigacao:** chave de resolucao considerando evento, atividade, pessoa, papel e origem.

## Resultado Esperado

Ao final, o sistema deve:

- abrir o designer de participantes com robustez mesmo diante de template invalido
- compartilhar um contrato unico de designer entre participantes e equipe
- tratar certificados de equipe como derivados por padrao de atividades vinculadas ao evento e responsaveis do evento
- manter inclusoes manuais como complemento
- gerar um certificado por atividade quando a mesma pessoa estiver em multiplas atividades
