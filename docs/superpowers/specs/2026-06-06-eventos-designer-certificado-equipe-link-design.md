# Design: Atalho do Designer de Certificados da Equipe em `/eventos`

## Objetivo

Alterar os atalhos de certificados da equipe nas listagens de eventos para que abram diretamente o designer de certificados da equipe (`/designer_certificado_equipe/:id`) em vez da tela de entregas (`/certificados_equipe/:id`).

## Escopo

Aplicar a mudança em dois pontos da interface:

- `app/templates/dashboard.html`
- `app/templates/events_admin.html`

Fora de escopo:

- remover ou alterar a rota `/certificados_equipe/:id`
- mudar permissões de acesso
- criar novo botão para entregas da equipe
- refatorar helpers compartilhados entre templates

## Estado Atual

- A listagem principal do `dashboard` renderiza dois atalhos de certificados quando `ev.can_view_certificates` é verdadeiro:
  - participantes: `/designer_certificado/${ev.id}`
  - equipe: `/certificados_equipe/${ev.id}`
- A listagem de gestão em `events_admin` repete o mesmo padrão.
- O tooltip atual do botão da equipe comunica `Certificados da Equipe`, que hoje coincide com a tela de entregas, não com o designer.

## Mudança Proposta

### Navegação

Substituir o destino do botão da equipe nos dois templates:

- de: ``/certificados_equipe/${ev.id}``
- para: ``/designer_certificado_equipe/${ev.id}``

### Texto Acessível

Atualizar o `title` do botão da equipe para refletir a nova ação. Texto recomendado:

- `Designer de Certificados da Equipe`

O ícone (`fa-users`), classes CSS e posição no grupo de ações permanecem inalterados para evitar regressão visual desnecessária.

## Fluxo Resultante

1. Usuário abre `/` ou `/eventos_admin`.
2. A listagem renderiza o botão de certificados da equipe quando `ev.can_view_certificates` é verdadeiro.
3. Ao clicar, o usuário é levado para `/designer_certificado_equipe/:id`.
4. A tela de entregas da equipe continua existindo, mas não terá mais atalho visível nessas duas listagens.

## Impacto em Permissões

Nenhuma mudança de permissão é necessária.

- a visibilidade do botão continua condicionada a `ev.can_view_certificates`
- a rota de destino já valida acesso em `main.designer_certificado_equipe`

## Riscos e Mitigações

### Risco: teste existente ficar desatualizado

Há teste que hoje espera `/certificados_equipe/${ev.id}` no HTML de `/` e `/eventos_admin`.

Mitigação:

- atualizar o teste para esperar `/designer_certificado_equipe/${ev.id}`
- validar também o texto do tooltip para a nova intenção do botão

### Risco: perda de acesso rápido à tela de entregas

Esse comportamento é intencional e aprovado para esta mudança.

Mitigação:

- não remover a rota `/certificados_equipe/:id`
- manter o acesso por navegação interna já existente quando necessário

## Testes

Atualizar testes de renderização das páginas de eventos para garantir:

- `events_admin` contém `/designer_certificado_equipe/${ev.id}`
- `dashboard` contém `/designer_certificado_equipe/${ev.id}`
- o atalho antigo `/certificados_equipe/${ev.id}` deixa de ser exigido nesses dois pontos
- o texto acessível do botão da equipe reflete `Designer de Certificados da Equipe`

## Implementação Mínima

1. Ajustar o link e o `title` em `dashboard.html`.
2. Ajustar o link e o `title` em `events_admin.html`.
3. Atualizar o teste de renderização associado em `tests/test_api.py`.
