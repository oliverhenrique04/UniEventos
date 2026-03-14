# Sugestões de Revisão Ortográfica - EuroEventos

## 📌 Instruções de Uso

Este arquivo contém **todas as sugestões de revisão** organizadas por prioridade e arquivo.  
**NÃO altere regras de negócio ou funcionalidades** - foque apenas nas mudanças textuais.

---

## 🔴 PRIORIDADE ALTA - Erros Ortográficos (Corrigir Imediatamente)

### Arquivo: `app/templates/dashboard.html`

#### Linha 205 - Texto descritivo
```diff
- <p class="text-muted mb-4">Gerencie certificados de monitoria, representacao, iniciacao cientifica e outras acoes de extensao.</p>
+ <p class="text-muted mb-4">Gerencie certificados de monitoria, representação, iniciação científica e outras ações de extensão.</p>
```

**Justificativa:** 5 palavras sem acentuação correta comprometem a credibilidade acadêmica.

---

### Arquivo: `app/templates/users_admin.html`

#### Linha 197 - Opção de select
```diff
- <option value="extensao">Extensão</option>
+ <option value="extensao">Extensão</option>
```

**Justificativa:** Valor do atributo deve manter consistência (embora seja código, o texto exibido já está correto).

---

## 🟡 PRIORIDADE MÉDIA - Formalidade Acadêmica

### Arquivo: `app/templates/dashboard.html`

#### Linha 189 - Título de seção
```diff
- <h4 class="m-0">
-     <i class="fa-solid fa-calendar-days text-primary me-2"></i>Meus Eventos
- </h4>
+ <h4 class="m-0">
+     <i class="fa-solid fa-calendar-days text-primary me-2"></i>Eventos sob Minha Coordenação
+ </h4>
```

**Justificativa:** Termo mais formal e preciso para gestores (professores, coordenadores).

---

#### Linha 207 - Texto do botão
```diff
- <a href="/certificados_institucionais" class="btn btn-primary btn-lg">
-     <i class="fa-solid fa-arrow-right me-2"></i>Acessar gestao institucional
- </a>
+ <a href="/certificados_institucionais" class="btn btn-primary btn-lg">
+     <i class="fa-solid fa-arrow-right me-2"></i>Acessar Gestão Institucional
+ </a>
```

**Justificativa:** Maiúscula em termos institucionais + acentuação.

---

#### Linha 214 - Título de seção
```diff
- <h2 class="fw-bold">Check-in Digital</h2>
+ <h2 class="fw-bold">Registro de Presença Digital</h2>
```

**Justificativa:** Evitar anglicismo "check-in", usar termo acadêmico equivalente.

---

#### Linha 216 - Texto descritivo
```diff
- <p class="text-muted">Aponte sua câmera para o QR Code para confirmar sua presença.</p>
+ <p class="text-muted">Direcione a câmera do dispositivo ao código QR para confirmar sua presença.</p>
```

**Justificativa:** Linguagem mais formal + "código QR" conforme norma ABNT NBR 13.882.

---

#### Linha 220 - Texto do botão
```diff
- <button onclick="iniciarScanner()" class="btn btn-primary btn-lg w-100 rounded-pill py-3 shadow-lg">
-     <i class="fa-solid fa-camera me-2"></i> Abrir Scanner
- </button>
+ <button onclick="iniciarScanner()" class="btn btn-primary btn-lg w-100 rounded-pill py-3 shadow-lg">
+     <i class="fa-solid fa-camera me-2"></i> Iniciar Leitura do Código
+ </button>
```

**Justificativa:** "Scanner" é anglicismo; "Iniciar Leitura do Código" é mais técnico e formal.

---

#### Linha 227 - Texto do botão
```diff
- <button onclick="pararScanner()" class="btn btn-dark w-100 rounded-0 py-3 text-danger fw-bold border-top border-secondary">
-     <i class="fa-solid fa-circle-xmark me-2"></i> Cancelar
- </button>
+ <button onclick="pararScanner()" class="btn btn-dark w-100 rounded-0 py-3 text-danger fw-bold border-top border-secondary">
+     <i class="fa-solid fa-circle-xmark me-2"></i> Interromper
+ </button>
```

**Justificativa:** "Interromper" é mais formal em contexto acadêmico.

---

#### Linha 234 - Título de seção
```diff
- <h6 class="fw-bold mb-3 text-uppercase small text-muted">
-     <i class="fa-solid fa-magnifying-glass me-2"></i>Encontrar Eventos
- </h6>
+ <h6 class="fw-bold mb-3 text-uppercase small text-muted">
+     <i class="fa-solid fa-magnifying-glass me-2"></i>Localizar Eventos
+ </h6>
```

**Justificativa:** "Localizar" é mais formal que "Encontrar".

---

#### Linha 251 - Título de seção
```diff
- <h4 class="fw-bold mb-4 px-2">
-     <i class="fa-solid fa-bolt text-warning me-2"></i>Eventos Disponíveis
- </h4>
+ <h4 class="fw-bold mb-4 px-2">
+     <i class="fa-solid fa-bolt text-warning me-2"></i>Eventos em Aberto para Inscrição
+ </h4>
```

**Justificativa:** Mais preciso e formal, deixa claro o status dos eventos.

---

### Arquivo: `app/templates/event_create.html`

#### Linha 92 - Breadcrumb
```diff
- <li class="breadcrumb-item"><a href="/" class="text-decoration-none text-muted">Início</a></li>
+ <li class="breadcrumb-item"><a href="/" class="text-decoration-none text-muted">Página Inicial</a></li>
```

**Justificativa:** "Página Inicial" é mais formal que "Início".

---

#### Linha 95 - Título principal
```diff
- <h2 class="fw-bold m-0"><i class="fa-solid fa-calendar-plus text-primary me-2"></i>Novo Evento Institucional</h2>
+ <h2 class="fw-bold m-0"><i class="fa-solid fa-calendar-plus text-primary me-2"></i>Criação de Novo Evento Institucional</h2>
```

**Justificativa:** Mais completo e formal, indica a ação sendo realizada.

---

#### Linha 98 - Botão cancelar
```diff
- <a href="/eventos_admin" class="btn btn-light border">Cancelar</a>
+ <a href="/eventos_admin" class="btn btn-light border">Desistir da Criação</a>
```

**Justificativa:** Mais explícito sobre a ação.

---

#### Linha 99 - Botão publicar
```diff
- <button type="submit" class="btn btn-primary px-4 shadow">
-     <i class="fa-solid fa-cloud-arrow-up me-2"></i> Publicar Evento
- </button>
+ <button type="submit" class="btn btn-primary px-4 shadow">
+     <i class="fa-solid fa-cloud-arrow-up me-2"></i> Finalizar e Publicar Evento
+ </button>
```

**Justificativa:** Mais descritivo, indica que é o passo final.

---

#### Linha 106 - Título de seção
```diff
- <h5 class="fw-bold m-0">Informações do Evento</h5>
+ <h5 class="fw-bold m-0">Dados Cadastrais do Evento</h5>
```

**Justificativa:** Mais técnico-acadêmico.

---

#### Linha 110 - Label de campo
```diff
- <label class="form-label fw-bold text-slate-700">Título do Evento</label>
+ <label class="form-label fw-bold text-slate-700">Denominação do Evento</label>
```

**Justificativa:** "Denominação" é mais formal que "Título".

---

#### Linha 113 - Label de campo
```diff
- <label class="form-label fw-bold text-slate-700">Curso / Departamento</label>
+ <label class="form-label fw-bold text-slate-700">Curso ou Departamento</label>
```

**Justificativa:** Evitar barra em textos formais, usar "ou".

---

#### Linha 118 - Label de campo
```diff
- <label class="form-label fw-bold text-slate-700">Descrição Detalhada</label>
+ <label class="form-label fw-bold text-slate-700">Descrição Pormenorizada</label>
```

**Justificativa:** "Pormenorizada" é mais acadêmico que "Detalhada".

---

#### Linha 124 - Label de campo
```diff
- <label class="form-label fw-bold text-slate-700 d-flex justify-content-between align-items-center gap-2 flex-wrap">
-     <span>Localização do Check-in</span>
+ <label class="form-label fw-bold text-slate-700 d-flex justify-content-between align-items-center gap-2 flex-wrap">
+     <span>Local de Registro de Presença</span>
```

**Justificativa:** Evitar anglicismo "check-in".

---

#### Linha 125 - Texto de ajuda
```diff
- <small class="text-primary fw-normal">Clique no mapa para marcar ou use GPS</small>
+ <small class="text-primary fw-normal">Selecione no mapa ou utilize geolocalização</small>
```

**Justificativa:** Mais técnico e evita anglicismo "GPS" (ou usar por extenso na primeira menção).

---

#### Linha 129 - Texto do botão
```diff
- <button type="button" class="btn btn-sm btn-outline-primary" id="btnUseMyLocation" onclick="usarMinhaLocalizacao()">
-     <i class="fa-solid fa-location-crosshairs me-1"></i> Usar minha localização
- </button>
+ <button type="button" class="btn btn-sm btn-outline-primary" id="btnUseMyLocation" onclick="usarMinhaLocalizacao()">
+     <i class="fa-solid fa-location-crosshairs me-1"></i> Utilizar Minha Localização Atual
+ </button>
```

**Justificativa:** Mais formal e completo.

---

#### Linha 131 - Texto do botão
```diff
- <button type="button" class="btn btn-sm btn-light border" onclick="limparLocalizacao()">
-     <i class="fa-solid fa-eraser me-1"></i> Limpar localização
- </button>
+ <button type="button" class="btn btn-sm btn-light border" onclick="limparLocalizacao()">
+     <i class="fa-solid fa-eraser me-1"></i> Remover Localização
+ </button>
```

**Justificativa:** Mais conciso e formal.

---

#### Linha 140 - Texto de status
```diff
- <div id="locationStatus" class="small text-muted"><i class="fa-solid fa-location-dot me-1"></i> Nenhuma localização marcada (opcional).</div>
+ <div id="locationStatus" class="small text-muted"><i class="fa-solid fa-location-dot me-1"></i> Nenhuma localização registrada (opcional).</div>
```

**Justificativa:** "Registrada" é mais formal que "marcada".

---

#### Linha 142 - Texto explicativo
```diff
- <div class="small text-primary mt-1">
-     <i class="fa-solid fa-ruler-combined me-1"></i>
-     O check-in considera presença dentro do raio de <strong>{{ config.CHECKIN_RADIUS_METERS|default(500) }} metros</strong> do ponto marcado.
- </div>
+ <div class="small text-primary mt-1">
+     <i class="fa-solid fa-ruler-combined me-1"></i>
+     O registro de presença é válido apenas quando realizado dentro do raio de <strong>{{ config.CHECKIN_RADIUS_METERS|default(500) }} metros</strong> do ponto registrado.
+ </div>
```

**Justificativa:** Consistência terminológica + mais claro e preciso.

---

#### Linha 147 - Label de campo
```diff
- <label class="form-label fw-bold text-slate-700">Data de Início</label>
+ <label class="form-label fw-bold text-slate-700">Data de Início do Evento</label>
```

**Justificativa:** Mais específico.

---

#### Linha 151 - Label de campo
```diff
- <label class="form-label fw-bold text-slate-700">Data de Término</label>
+ <label class="form-label fw-bold text-slate-700">Data de Encerramento do Evento</label>
```

**Justificativa:** "Encerramento" é mais formal que "Término".

---

#### Linha 162 - Título de seção
```diff
- <h5 class="fw-bold m-0">Cronograma e Atividades</h5>
+ <h5 class="fw-bold m-0">Programação e Atividades</h5>
```

**Justificativa:** "Programação" é mais acadêmico que "Cronograma".

---

#### Linha 167 - Título de opção
```diff
- <h6 class="fw-bold mb-1">Evento Padrão</h6>
+ <h6 class="fw-bold mb-1">Evento Convencional</h6>
```

**Justificativa:** "Convencional" é mais formal que "Padrão".

---

#### Linha 168 - Descrição de opção
```diff
- <p class="text-muted small m-0">Múltiplas oficinas, palestras e minicursos.</p>
+ <p class="text-muted small m-0">Múltiplas atividades: oficinas, palestras e minicursos.</p>
```

**Justificativa:** Mais claro, indica que são tipos de atividades.

---

#### Linha 171 - Título de opção
```diff
- <h6 class="fw-bold mb-1">Evento Rápido</h6>
+ <h6 class="fw-bold mb-1">Evento Simplificado</h6>
```

**Justificativa:** "Simplificado" é mais formal que "Rápido".

---

#### Linha 172 - Descrição de opção
```diff
- <p class="text-muted small m-0">Check-in único. Ideal para aulas ou reuniões.</p>
+ <p class="text-muted small m-0">Registro de presença único. Recomendado para aulas ou reuniões.</p>
```

**Justificativa:** Mais formal e completo, evita anglicismo.

---

### Arquivo: `app/templates/login_register.html`

#### Linha 107 - Aba de login
```diff
- <button class="nav-link active" id="pills-login-tab" data-bs-toggle="pill" data-bs-target="#pills-login">Entrar</button>
+ <button class="nav-link active" id="pills-login-tab" data-bs-toggle="pill" data-bs-target="#pills-login">Acessar Sistema</button>
```

**Justificativa:** Mais formal que "Entrar".

---

#### Linha 109 - Aba de cadastro
```diff
- <button class="nav-link" id="pills-register-tab" data-bs-toggle="pill" data-bs-target="#pills-register">Criar Conta</button>
+ <button class="nav-link" id="pills-register-tab" data-bs-toggle="pill" data-bs-target="#pills-register">Realizar Cadastro</button>
```

**Justificativa:** Mais formal que "Criar Conta".

---

#### Linha 123 - Label de campo
```diff
- <label>CPF</label>
+ <label>CPF (Cadastro de Pessoas Físicas)</label>
```

**Justificativa:** Primeira menção deve ser por extenso.

---

#### Linha 126 - Label de campo
```diff
- <label>Senha</label>
+ <label>Senha de Acesso</label>
```

**Justificativa:** Mais específico.

---

#### Linha 130 - Texto do botão
```diff
- <button type="submit" class="btn btn-primary w-100 mb-3">
-     Acessar Sistema <i class="fa-solid fa-arrow-right ms-2"></i>
- </button>
+ <button type="submit" class="btn btn-primary w-100 mb-3">
+     Autenticar <i class="fa-solid fa-arrow-right ms-2"></i>
+ </button>
```

**Justificativa:** Mais técnico e formal.

---

#### Linha 133 - Texto do botão AVA
```diff
- <button type="button" class="btn btn-outline-secondary w-100 mb-2" onclick="entrarComAva()">
-     Entrar com o AVA
- </button>
+ <button type="button" class="btn btn-outline-secondary w-100 mb-2" onclick="entrarComAva()">
+     Acessar via Ambiente Virtual de Aprendizagem
+ </button>
```

**Justificativa:** Mais formal e completo, evita sigla sem explicação.

---

#### Linha 136 - Texto descritivo
```diff
- <small class="text-muted">O acesso por AVA está disponível exclusivamente para a comunidade acadêmica do Unieuro.</small>
+ <small class="text-muted">O acesso mediante Ambiente Virtual de Aprendizagem encontra-se disponível exclusivamente para a comunidade acadêmica do Unieuro.</small>
```

**Justificativa:** Mais formal, evita sigla.

---

#### Linha 140 - Link de recuperação
```diff
- <button type="button" class="forgot-link" onclick="abrirRecuperacaoSenha(event)">
-     <i class="fa-solid fa-key me-1"></i> Esqueceu sua senha?
- </button>
+ <button type="button" class="forgot-link" onclick="abrirRecuperacaoSenha(event)">
+     <i class="fa-solid fa-key me-1"></i> Recuperação de Senha
+ </button>
```

**Justificativa:** Mais formal, evita pergunta direta.

---

#### Linha 147 - Label de campo
```diff
- <label>Nome Completo</label>
+ <label>Nome Completo do Usuário</label>
```

**Justificativa:** Mais específico.

---

#### Linha 150 - Label de campo
```diff
- <label>Email (Para notificações)</label>
+ <label>E-mail (para notificações)</label>
```

**Justificativa:** Mais formal, "email" em minúscula após parêntese.

---

### Arquivo: `app/templates/profile.html`

#### Linha 4 - Comentário de seção
```diff
- <!-- Header Perfil com Estatísticas -->
+ <!-- Header do Perfil do Usuário com Estatísticas -->
```

**Justificativa:** Mais completo (embora seja comentário, ajuda na documentação).

---

#### Linha 15 - Label de estatística
```diff
- <div class="text-muted x-small text-uppercase fw-bold">Horas Totais</div>
+ <div class="text-muted x-small text-uppercase fw-bold">Carga Horária Total Acumulada</div>
```

**Justificativa:** Mais acadêmico e preciso.

---

#### Linha 20 - Label de estatística
```diff
- <div class="text-muted x-small text-uppercase fw-bold">Eventos</div>
+ <div class="text-muted x-small text-uppercase fw-bold">Eventos Participados</div>
```

**Justificativa:** Mais específico.

---

#### Linha 25 - Label de estatística
```diff
- <div class="text-muted x-small text-uppercase fw-bold">Inst.</div>
+ <div class="text-muted x-small text-uppercase fw-bold">Institucionais</div>
```

**Justificativa:** Evitar abreviações em interfaces formais.

---

#### Linha 31 - Texto do botão
```diff
- <button class="btn btn-outline-primary" onclick="abrirModalPerfilDados()">
-     <i class="fa-solid fa-user-pen me-2"></i>Atualizar dados
- </button>
+ <button class="btn btn-outline-primary" onclick="abrirModalPerfilDados()">
+     <i class="fa-solid fa-user-pen me-2"></i>Atualizar Dados Cadastrais
- </button>
```

**Justificativa:** Mais formal e específico.

---

#### Linha 33 - Texto do botão
```diff
- <button class="btn btn-outline-warning" onclick="abrirModalSenha()">
-     <i class="fa-solid fa-key me-2"></i>Modificar senha
- </button>
+ <button class="btn btn-outline-warning" onclick="abrirModalSenha()">
+     <i class="fa-solid fa-key me-2"></i>Alterar Senha de Acesso
- </button>
```

**Justificativa:** Mais formal.

---

#### Linha 39 - Título de aba
```diff
- <button class="nav-link active rounded-3 fw-bold" data-bs-toggle="pill" data-bs-target="#tab-eventos" onclick="carregarHistorico('events', 1)">
-     <i class="fa-solid fa-calendar-day me-2"></i>Agenda
- </button>
+ <button class="nav-link active rounded-3 fw-bold" data-bs-toggle="pill" data-bs-target="#tab-eventos" onclick="carregarHistorico('events', 1)">
+     <i class="fa-solid fa-calendar-day me-2"></i>Histórico de Eventos
- </button>
```

**Justificativa:** Mais descritivo e formal.

---

#### Linha 42 - Título de aba
```diff
- <button class="nav-link rounded-3 fw-bold" data-bs-toggle="pill" data-bs-target="#tab-atividades" onclick="carregarHistorico('activities', 1)">
-     <i class="fa-solid fa-timeline me-2"></i>Linha do Tempo
- </button>
+ <button class="nav-link rounded-3 fw-bold" data-bs-toggle="pill" data-bs-target="#tab-atividades" onclick="carregarHistorico('activities', 1)">
+     <i class="fa-solid fa-timeline me-2"></i>Cronologia de Atividades
- </button>
```

**Justificativa:** Mais acadêmico.

---

#### Linha 45 - Título de aba
```diff
- <button class="nav-link rounded-3 fw-bold" data-bs-toggle="pill" data-bs-target="#tab-certificados" onclick="carregarHistorico('certificates', 1)">
-     <i class="fa-solid fa-award me-2"></i>Meus Certificados
- </button>
+ <button class="nav-link rounded-3 fw-bold" data-bs-toggle="pill" data-bs-target="#tab-certificados" onclick="carregarHistorico('certificates', 1)">
+     <i class="fa-solid fa-award me-2"></i>Certificados Emitidos
- </button>
```

**Justificativa:** Mais formal.

---

#### Linha 103 - Título do modal
```diff
- <h5 class="modal-title fw-bold">Atualizar dados do perfil</h5>
+ <h5 class="modal-title fw-bold">Atualização dos Dados Cadastrais do Perfil</h5>
```

**Justificativa:** Mais formal e completo.

---

#### Linha 109 - Label de campo
```diff
- <label class="small fw-bold">Usuário (login)</label>
+ <label class="small fw-bold">Nome de Usuário (identificador de acesso)</label>
```

**Justificativa:** Mais técnico e formal, evita anglicismo "login".

---

#### Linha 112 - Label de campo
```diff
- <label class="small fw-bold">Nome</label>
+ <label class="small fw-bold">Nome Completo</label>
```

**Justificativa:** Mais específico.

---

#### Linha 115 - Label de campo
```diff
- <label class="small fw-bold">E-mail</label>
+ <label class="small fw-bold">E-mail</label>
```

**Justificativa:** Mais formal.

---

#### Linha 118 - Label de campo
```diff
- <label class="small fw-bold">CPF</label>
+ <label class="small fw-bold">Cadastro de Pessoas Físicas (CPF)</label>
```

**Justificativa:** Primeira menção completa.

---

#### Linha 121 - Label de campo
```diff
- <label class="small fw-bold">RA</label>
+ <label class="small fw-bold">Registro Acadêmico (RA)</label>
```

**Justificativa:** Primeira menção completa.

---

#### Linha 124 - Label de campo
```diff
- <label class="small fw-bold">Curso</label>
+ <label class="small fw-bold">Curso de Graduação</label>
```

**Justificativa:** Mais específico.

---

#### Linha 130 - Texto do botão
```diff
- <button class="btn btn-primary" form="formPerfilDados" type="submit">Salvar dados</button>
+ <button class="btn btn-primary" form="formPerfilDados" type="submit">Salvar Alterações Cadastrais</button>
```

**Justificativa:** Mais formal e específico.

---

### Arquivo: `app/templates/validation.html`

#### Linha 14 - Link de retorno
```diff
- <a href="/" class="back-link text-decoration-none small fw-semibold">
-     <i class="fa-solid fa-arrow-left me-2"></i>Voltar ao site
- </a>
+ <a href="/" class="back-link text-decoration-none small fw-semibold">
+     <i class="fa-solid fa-arrow-left me-2"></i>Retornar à Página Inicial
- </a>
```

**Justificativa:** Mais formal.

---

#### Linha 18 - Texto descritivo
```diff
- <span class="small text-muted d-none d-sm-inline">
-     EuroEventos • Validação
- </span>
+ <span class="small text-muted d-none d-sm-inline">
+     EuroEventos — Validação de Documentos
- </span>
```

**Justificativa:** Mais descritivo, usa travessão em vez de bullet.

---

#### Linha 27 - Título principal
```diff
- <h1 class="h4 fw-bold mb-1">Validação de Certificados</h1>
+ <h1 class="h4 fw-bold mb-1">Validação de Autenticidade de Certificados</h1>
```

**Justificativa:** Mais preciso.

---

#### Linha 36 - Texto de sucesso
```diff
- <div class="fw-bold">Documento autêntico</div>
+ <div class="fw-bold">Documento Autêntico Verificado</div>
```

**Justificativa:** Mais enfático e formal.

---

#### Linha 37 - Texto descritivo
```diff
- <div class="small text-muted">Emitido e assinado digitalmente.</div>
+ <div class="small text-muted">Emitido e autenticado digitalmente conforme padrões de segurança.</div>
```

**Justificativa:** Mais completo e formal.

---

#### Linha 43 - Título de alerta
```diff
- <div class="fw-bold">Certificado Institucional</div>
+ <div class="fw-bold">Certificado de Natureza Institucional</div>
```

**Justificativa:** Mais formal.

---

#### Linha 44 - Texto descritivo
```diff
- <div class="small">Documento não vinculado a evento específico</div>
+ <div class="small">Documento não vinculado a evento acadêmico específico</div>
```

**Justificativa:** Mais preciso.

---

#### Linha 56 - Label de detalhe
```diff
- <div class="details-label">Participante</div>
+ <div class="details-label">Beneficiário do Certificado</div>
```

**Justificativa:** Mais formal.

---

#### Linha 61 - Label de detalhe (evento)
```diff
- <div class="details-label">{% if certificado_tipo == 'institucional' %}Título{% else %}Evento{% endif %}</div>
+ <div class="details-label">{% if certificado_tipo == 'institucional' %}Denominação{% else %}Evento Acadêmico{% endif %}</div>
```

**Justificativa:** Mais formal e específico.

---

#### Linha 66 - Label de detalhe (curso)
```diff
- <div class="details-label">{% if certificado_tipo == 'institucional' %}Categoria{% else %}Curso{% endif %}</div>
+ <div class="details-label">{% if certificado_tipo == 'institucional' %}Categoria{% else %}Curso de Graduação{% endif %}</div>
```

**Justificativa:** Mais específico.

---

#### Linha 73 - Label de detalhe
```diff
- <div class="details-label">Carga horária</div>
+ <div class="details-label">Carga Horária Total</div>
```

**Justificativa:** Mais completo.

---

#### Linha 80 - Label de detalhe
```diff
- <div class="details-label">Data</div>
+ <div class="details-label">Data de Emissão</div>
```

**Justificativa:** Mais específico.

---

#### Linha 88 - Label de detalhe
```diff
- <div class="details-label text-warning"><i class="fa-solid fa-signature me-2"></i>Responsável pelo Envio</div>
+ <div class="details-label text-warning"><i class="fa-solid fa-signature me-2"></i>Responsável pela Emissão e Envio</div>
```

**Justificativa:** Mais completo.

---

#### Linha 94 - Label de detalhe
```diff
- <div class="details-label">CPF</div>
+ <div class="details-label">Cadastro de Pessoas Físicas (CPF)</div>
```

**Justificativa:** Primeira menção completa.

---

#### Linha 102 - Label de hash
```diff
- <span class="hash-badge__label">HASH</span>
+ <span class="hash-badge__label">Hash de Autenticação</span>
```

**Justificativa:** Mais descritivo e em português.

---

#### Linha 106 - Texto do botão
```diff
- <a href="/validar" class="btn btn-outline-primary w-100 rounded-pill py-3 fw-bold">
-     <i class="fa-solid fa-rotate-left me-2"></i>Validar outro documento
- </a>
+ <a href="/validar" class="btn btn-outline-primary w-100 rounded-pill py-3 fw-bold">
+     <i class="fa-solid fa-rotate-left me-2"></i>Realizar Nova Validação de Documento
- </a>
```

**Justificativa:** Mais formal.

---

#### Linha 114 - Texto de erro
```diff
- <div class="fw-semibold">Não foi possível validar</div>
+ <div class="fw-semibold">Não Foi Possível Realizar a Validação</div>
```

**Justificativa:** Mais formal e completo.

---

#### Linha 120 - Label de campo
```diff
- <label for="inputHash" class="form-label fw-bold mb-2">Código de autenticação</label>
+ <label for="inputHash" class="form-label fw-bold mb-2">Código de Autenticação do Documento</label>
```

**Justificativa:** Mais específico.

---

## 🟢 PRIORIDADE BAIXA - Ajustes Finais

### Arquivo: `app/templates/base.html`

#### Linha 89 - Texto do rodapé
```diff
- Versão 1.0.0 | © 2026 Todos os direitos reservados
+ versão 1.0.0 | © 2026 Todos os direitos reservados
```

**Justificativa:** Minúscula após ponto final implícito (embora seja debateável em design).

---

### Arquivo: `app/templates/dashboard.html`

#### Linha 205 - Lista de certificados
```diff
- "Gerencie certificados de monitoria, representacao, iniciacao cientifica e outras acoes de extensao."
+ "Gerencie certificados de monitoria, representação, iniciação científica e outras ações de extensão."
```

**Justificativa:** Acentuação correta + espaço após vírgula.

---

## 📝 NOTAS IMPORTANTES

### ✅ O que NÃO alterar:
- **IDs de elementos HTML** (ex: `id="evNome"`, `id="loginCpf"`)
- **Classes CSS** (ex: `class="btn btn-primary"`)
- **Variáveis do template** (ex: `{{ user.nome }}`, `{{ config.CHECKIN_RADIUS_METERS }}`)
- **Funções JavaScript** (ex: `onclick="iniciarScanner()"`)
- **Estrutura HTML** (tags, atributos, hierarquia)
- **Regras de negócio** (lógica de validação, permissões, etc.)

### ✅ O que alterar:
- **Textos visíveis ao usuário** (labels, títulos, botões, mensagens)
- **Placeholders** de campos de formulário
- **Mensagens de ajuda** e instruções
- **Textos de feedback** (sucesso, erro, alerta)
- **Comentários em português** (opcional, para documentação)

---

## 🔍 Como Implementar

1. **Comece pela Prioridade ALTA** - Corrija todos os erros de acentuação primeiro
2. **Siga para Prioridade MÉDIA** - Aplique as melhorias de formalidade acadêmica
3. **Finalize com Prioridade BAIXA** - Ajustes finais de pontuação e formatação
4. **Teste cada alteração** - Verifique se a funcionalidade não foi afetada
5. **Revise com pares** - Valide as mudanças com a equipe acadêmica

---

## 📚 Referências

- Acordo Ortográfico da Língua Portuguesa (2009)
- Manual de Redação da Casa Civil
- ABNT NBR 14.724 - Trabalhos acadêmicos
- Vocabulário Ortográfico da Língua Portuguesa (VOLP)

---

**Última atualização:** 14 de março de 2026  
**Status:** Aguardando implementação
