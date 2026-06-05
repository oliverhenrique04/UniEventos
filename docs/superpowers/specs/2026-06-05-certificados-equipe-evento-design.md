# Certificados da equipe do evento - design

Data: 2026-06-05

## Objetivo

Adicionar certificados por evento para pessoas que atuam no evento sem depender de inscricao como participante, incluindo palestrantes, facilitadores, responsaveis e equipe organizadora.

O fluxo deve permitir cadastrar destinatarios automaticamente e manualmente, gerar PDF, visualizar, baixar e enviar por e-mail, sem alterar o comportamento atual dos certificados de participantes nem dos certificados institucionais.

## Decisoes aprovadas

- Escopo por evento.
- Destinatarios com sincronizacao automatica e cadastro manual.
- Modelo visual separado do certificado de participantes.
- Acoes do primeiro corte: gerar, visualizar, baixar, enviar individualmente e enviar em lote.

## Fora do escopo

- Substituir o fluxo atual de certificados de participantes.
- Migrar certificados institucionais para o novo fluxo.
- Remover ou alterar certificados ja emitidos.
- Criar multiplos modelos de equipe por evento no primeiro corte.

## Arquitetura

O evento passa a ter uma configuracao propria para certificado de equipe, independente do certificado de participantes:

- `Event.cert_team_bg_path`: imagem de fundo do modelo de equipe, com default `file/fundo_padrao.png`.
- `Event.cert_team_template_json`: JSON do designer para equipe.

Uma nova entidade armazena os destinatarios de equipe do evento:

- `EventTeamCertificateRecipient.event_id`
- `nome`
- `email`
- `cpf`
- `role_label`, por exemplo `Palestrante`, `Facilitador`, `Equipe organizadora`
- `activity_id`, opcional, para vinculo com atividade especifica
- `workload_hours`, opcional
- `source`, com valores `automatico` ou `manual`
- `source_key`, obrigatorio para origem `automatico` e nulo para origem `manual`, para evitar duplicidade ao sincronizar dados existentes
- `cert_hash`
- `cert_entregue`
- `cert_data_envio`
- timestamps de criacao e atualizacao

O PDF sera gerado reaproveitando `CertificateService.generate_pdf`, como o modulo institucional ja faz. Um servico dedicado de equipe montara um objeto de evento compativel com o designer em modo `event`, um destinatario como usuario simplificado e um objeto de validacao com `cert_hash`. As tags extras de equipe entram por `tag_overrides`, sem alterar o comportamento padrao de participantes.

## Tags do modelo

O modelo de equipe deve aceitar estas tags:

- `{{NOME}}`: nome do destinatario em caixa alta, seguindo o comportamento atual.
- `{{EVENTO}}`: nome do evento.
- `{{PAPEL}}`: papel no evento.
- `{{ATIVIDADE}}`: atividade vinculada, quando houver.
- `{{HORAS}}`: carga horaria do destinatario ou da atividade vinculada.
- `{{DATA}}` e `{{EMISSION_DATE}}`: data de emissao atual, preservada pelo servico.
- `{{DATA_REALIZACAO}}`: data da atividade vinculada ou data inicial do evento.
- `{{CPF}}`: CPF do destinatario, quando informado.
- `{{HASH}}`: codigo de validacao.

O template padrao de equipe sera separado do template de participantes e tera texto apropriado para atuacao no evento, por exemplo certificando que a pessoa participou como `{{PAPEL}}` no evento `{{EVENTO}}`.

## Sincronizacao automatica

A sincronizacao automatica cria destinatarios a partir de:

- Palestrantes cadastrados nas atividades, incluindo multiplos palestrantes por atividade.
- Responsaveis do evento, com papel padrao `Equipe organizadora` ou `Responsavel pelo evento`.

Regras:

- Nao apagar destinatarios manuais.
- Nao duplicar destinatarios automaticos quando a sincronizacao for executada novamente.
- Atualizar campos automaticos basicos quando a origem mudar, sem sobrescrever destinatarios manuais.
- Usar e-mail e nome dos palestrantes quando disponiveis.
- Usar usuario vinculado para responsaveis do evento quando disponivel.

## UI

Adicionar uma area de "Equipe do Evento" acessivel a partir do fluxo de certificados do evento. A pagina principal sera `/certificados_equipe/<event_id>`, e a edicao visual separada usara `/designer_certificado_equipe/<event_id>` reaproveitando o template de designer com endpoints de equipe.

A tela tera:

- Atalho para editar o modelo visual separado da equipe.
- Botao para sincronizar palestrantes e responsaveis.
- Formulario de inclusao manual com nome, e-mail, CPF opcional, papel, atividade opcional e carga horaria opcional.
- Tabela com status de entrega, origem, papel, atividade, e-mail e hash.
- Acoes por destinatario: visualizar, baixar, enviar/reenviar, editar e remover quando permitido.
- Envio em lote em segundo plano, seguindo o padrao existente de jobs em memoria para certificados.

Labels e mensagens de tela devem permanecer em portugues.

## APIs

Novos endpoints ficarao sob `/api/certificates/team`:

- `GET /event/<event_id>/recipients`: lista destinatarios de equipe.
- `POST /event/<event_id>/sync`: sincroniza palestrantes e responsaveis.
- `POST /event/<event_id>/recipients`: adiciona destinatario manual.
- `PUT /recipients/<recipient_id>`: atualiza destinatario.
- `DELETE /recipients/<recipient_id>`: remove destinatario.
- `GET /recipients/<recipient_id>/preview`: visualiza PDF.
- `GET /recipients/<recipient_id>/download`: baixa PDF.
- `POST /recipients/<recipient_id>/resend`: envia ou reenvia por e-mail.
- `POST /event/<event_id>/send_batch`: inicia envio em lote.
- `GET /send_batch/status/<job_id>`: consulta status do lote.
- `POST /event/<event_id>/setup`: salva background e template separado da equipe.
- `POST /event/<event_id>/preview_layout`: preview do modelo de equipe.
- `POST /event/<event_id>/upload_asset`: upload de asset do designer de equipe.

Os endpoints podem viver no blueprint existente de certificados para compartilhar validacao de imagem, preview PDF e padrao de jobs.

## Permissoes

- Visualizacao, preview e download autenticados usam `EventService.can_view_event_certificates`.
- Configuracao, sincronizacao, cadastro, edicao, remocao e envio usam `EventService.can_manage_event_certificates`.
- Gestor continua podendo visualizar certificados de eventos, mas sem mutacoes, como no fluxo atual.
- Acesso publico por hash nao exige login.

## Validacao publica

A rota `/validar/<cert_hash>` passa a procurar tambem certificados de equipe do evento.

Ordem de busca:

1. Certificado institucional.
2. Certificado de equipe do evento.
3. Certificado de participante.

A pagina de validacao exibira tipo `equipe_evento`, beneficiario, evento, papel, atividade quando houver, carga horaria quando houver, CPF quando houver e hash.

## Envio por e-mail

O envio usa `NotificationService.send_email_task`, sem redeclarar filas.

Criar um template especifico simples para equipe, por exemplo `team_certificate_ready.html`, para mensagem mais clara sobre papel no evento. O template deve manter links absolutos construidos com `build_absolute_app_url` para download, preview e validacao.

## Migracoes

Adicionar migracao Alembic para:

- Novas colunas em `events`: `cert_team_bg_path`, `cert_team_template_json`.
- Nova tabela de destinatarios de certificados de equipe.
- Indices por `event_id`, `activity_id`, `cert_hash`, entrega e origem.
- Restricoes para hash unico e controle basico de valores de origem.

## Testes

Cobertura minima:

- Servico sincroniza palestrantes e responsaveis sem duplicar.
- Destinatario manual pode ser criado, editado e removido por perfil com permissao.
- Gestor pode visualizar, preview/download, mas nao pode mutar nem enviar.
- PDF de equipe recebe tags `{{PAPEL}}`, `{{ATIVIDADE}}`, `{{HORAS}}` e `{{HASH}}`.
- Preview e download autenticados retornam PDF.
- Envio individual e lote marcam entrega quando o e-mail e enfileirado.
- Validacao publica reconhece hash de equipe do evento.
- Fluxos atuais de participantes e institucionais continuam passando.

## Riscos e mitigacoes

- Risco: sobrescrever modelo de participante. Mitigacao: colunas e endpoints separados para modelo de equipe.
- Risco: duplicar destinatarios automaticos. Mitigacao: `source_key` deterministico por origem.
- Risco: permissao de gestor virar mutacao acidental. Mitigacao: testes especificos com `can_manage_event_certificates`.
- Risco: hashes colidirem com outros tipos. Mitigacao: hash unico na tabela de equipe e busca ordenada na validacao publica.
- Risco: mudancas no designer afetarem institucional/participante. Mitigacao: reutilizar normalizacao existente em modo `event` com tags adicionais via `tag_overrides`, sem alterar elementos fixos nem endpoints existentes.
