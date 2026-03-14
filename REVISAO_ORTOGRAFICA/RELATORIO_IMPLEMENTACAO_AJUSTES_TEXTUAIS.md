# Relatório Completo de Implementação
## Ajustes Textuais - Plataforma EuroEventos

Data: 14/03/2026
Escopo: revisão textual e formalidade acadêmica

## Restrições obrigatórias respeitadas
1. Não alterar CPF: respeitado.
2. Não alterar RA: respeitado.
3. Não alterar Linha 118 - Label de campo: respeitado (`Curso / Departamento` mantido em `event_create.html`).
4. Não alterar Linha 113 - Label de campo: respeitado (`Descrição Detalhada` mantido em `event_create.html`).

## Arquivos alterados
- `app/templates/dashboard.html`
- `app/templates/event_create.html`
- `app/templates/login_register.html`
- `app/templates/profile.html`
- `app/templates/validation.html`

### Rodada complementar (varredura final)
Também foram ajustados pontos remanescentes de padronização textual em:
- `app/templates/base.html`
- `app/templates/checkin_confirm.html`
- `app/templates/my_events.html`
- `app/templates/events_admin.html`
- `app/templates/event_edit.html`
- `app/templates/institutional_certificates.html`

Ajustes aplicados na rodada complementar:
- Padronização de "Check-in" para "Registro de Presença" em textos de interface.
- Padronização de "QR Code" para "código QR"/"Código QR" em textos visíveis.
- Correções ortográficas remanescentes (ex.: "Iniciação científica" em placeholder).

## Detalhamento por arquivo

### 1) app/templates/dashboard.html
Alterações aplicadas:
- "Meus Eventos" -> "Eventos sob Minha Coordenação"
- Correção ortográfica no bloco de certificados:
  - "representacao" -> "representação"
  - "iniciacao" -> "iniciação"
  - "cientifica" -> "científica"
  - "acoes" -> "ações"
  - "extensao" -> "extensão"
- "Acessar gestao institucional" -> "Acessar Gestão Institucional"
- "Check-in Digital" -> "Registro de Presença Digital"
- "Aponte sua câmera para o QR Code..." -> "Direcione a câmera do dispositivo ao código QR..."
- "Abrir Scanner" -> "Iniciar Leitura do Código"
- "Cancelar" (scanner) -> "Interromper"
- "Encontrar Eventos" -> "Localizar Eventos"
- "Eventos Disponíveis" -> "Eventos em Aberto para Inscrição"

### 2) app/templates/event_create.html
Alterações aplicadas:
- "Início" -> "Página Inicial"
- "Novo Evento Institucional" -> "Criação de Novo Evento Institucional"
- "Cancelar" -> "Desistir da Criação"
- "Publicar Evento" -> "Finalizar e Publicar Evento"
- "Informações do Evento" -> "Dados Cadastrais do Evento"
- "Título do Evento" -> "Denominação do Evento"
- "Localização do Check-in" -> "Local de Registro de Presença"
- "Clique no mapa para marcar ou use GPS" -> "Selecione no mapa ou utilize geolocalização"
- "Usar minha localização" -> "Utilizar Minha Localização Atual"
- "Limpar localização" -> "Remover Localização"
- "Nenhuma localização marcada (opcional)." -> "Nenhuma localização registrada (opcional)."
- Texto explicativo de raio:
  - "O check-in considera presença..." -> "O registro de presença é válido apenas quando realizado..."
- "Data de Início" -> "Data de Início do Evento"
- "Data de Término" -> "Data de Encerramento do Evento"
- "Cronograma e Atividades" -> "Programação e Atividades"
- "Evento Padrão" -> "Evento Convencional"
- "Múltiplas oficinas, palestras e minicursos." -> "Múltiplas atividades: oficinas, palestras e minicursos."
- "Evento Rápido" -> "Evento Simplificado"
- "Check-in único. Ideal para aulas ou reuniões." -> "Registro de presença único. Recomendado para aulas ou reuniões."

Restrições preservadas neste arquivo:
- Label `Curso / Departamento`: mantido sem alteração.
- Label `Descrição Detalhada`: mantido sem alteração.

### 3) app/templates/login_register.html
Alterações aplicadas:
- Aba "Entrar" -> "Acessar Sistema"
- Aba "Criar Conta" -> "Realizar Cadastro"
- Label "Senha" (login) -> "Senha de Acesso"
- Botão "Acessar Sistema" (login) -> "Autenticar"
- "Entrar com o AVA" -> "Acessar via Ambiente Virtual de Aprendizagem"
- Texto de apoio AVA formalizado
- "Esqueceu sua senha?" -> "Recuperação de Senha"
- "Nome Completo" -> "Nome Completo do Usuário"
- "Email (Para notificações)" -> "E-mail (para notificações)"
- Label "Senha" (cadastro) -> "Senha de Acesso"

Restrições preservadas neste arquivo:
- Labels de CPF mantidos sem alteração.

### 4) app/templates/profile.html
Alterações aplicadas:
- Comentário de seção formalizado
- "Horas Totais" -> "Carga Horária Total Acumulada"
- "Eventos" -> "Eventos Participados"
- "Inst." -> "Institucionais"
- "Atualizar dados" -> "Atualizar Dados Cadastrais"
- "Modificar senha" -> "Alterar Senha de Acesso"
- Aba "Agenda" -> "Histórico de Eventos"
- Aba "Linha do Tempo" -> "Cronologia de Atividades"
- Aba "Meus Certificados" -> "Certificados Emitidos"
- Título do modal de dados formalizado
- "Usuário (login)" -> "Nome de Usuário (identificador de acesso)"
- "Nome" -> "Nome Completo"
- "E-mail" -> "E-mail"
- "Curso" -> "Curso de Graduação"
- "Salvar dados" -> "Salvar Alterações Cadastrais"
- Título do modal de senha: "Modificar senha" -> "Alterar Senha de Acesso"

Restrições preservadas neste arquivo:
- Label "CPF" mantido sem alteração.
- Label "RA" mantido sem alteração.

### 5) app/templates/validation.html
Alterações aplicadas:
- "Voltar ao site" -> "Retornar à Página Inicial"
- "EuroEventos • Validação" -> "EuroEventos - Validação de Documentos"
- "Validação de Certificados" -> "Validação de Autenticidade de Certificados"
- "Documento autêntico" -> "Documento Autêntico Verificado"
- "Emitido e assinado digitalmente." -> "Emitido e autenticado digitalmente conforme padrões de segurança."
- "Certificado Institucional" -> "Certificado de Natureza Institucional"
- "Documento não vinculado a evento específico" -> "Documento não vinculado a evento acadêmico específico"
- "Participante" -> "Beneficiário do Certificado"
- "Título" (institucional) -> "Denominação"
- "Evento" (não institucional) -> "Evento Acadêmico"
- "Curso" (não institucional) -> "Curso de Graduação"
- "Carga horária" -> "Carga Horária Total"
- "Data" -> "Data de Emissão"
- "Responsável pelo Envio" -> "Responsável pela Emissão e Envio"
- "HASH" -> "Hash de Autenticação"
- "Validar outro documento" -> "Realizar Nova Validação de Documento"
- "Não foi possível validar" -> "Não Foi Possível Realizar a Validação"
- "Código de autenticação" -> "Código de Autenticação do Documento"

Restrições preservadas neste arquivo:
- Label "CPF" mantido sem alteração.

## Itens não alterados por restrição
- Qualquer texto de CPF: mantido.
- Qualquer texto de RA: mantido.
- Label `Curso / Departamento` em `event_create.html`: mantido.
- Label `Descrição Detalhada` em `event_create.html`: mantido.

## Impacto funcional
- Nenhuma regra de negócio alterada.
- Nenhuma função JavaScript alterada.
- Nenhum endpoint alterado.
- Sem alteração em IDs/classes com impacto de comportamento.

## Conclusão
Os ajustes textuais foram implementados integralmente dentro do escopo aprovado, com preservação explícita das restrições informadas.
