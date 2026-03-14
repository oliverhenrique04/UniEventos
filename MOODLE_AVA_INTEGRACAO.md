# Integracao AVA (Moodle) com UniEventos via Ferramenta Externa

Este guia cobre a autenticacao integrada no Moodle LMS 2024100708.03 usando CPF como campo principal, considerando LTI 1.0/1.1 e CPF armazenado no `username` do Moodle.

## 1. O que foi implementado no UniEventos

1. Botao na tela de login: **Entrar com o AVA** (apenas quando `MOODLE_LOGIN_ENABLED=true`).
2. Endpoint de redirecionamento para o AVA: `GET /api/ava`.
3. Endpoint de recepcao da Ferramenta Externa: `POST /api/ava/launch`.
4. Login/provisionamento de usuario por CPF:
   - Busca usuario existente por CPF.
   - Se nao existir, cria automaticamente como `participante`.
5. Restricao para comunidade Unieuro por dominio de e-mail (`MOODLE_ALLOWED_EMAIL_DOMAIN`).
6. Validacao de credencial LTI por `oauth_consumer_key` (`MOODLE_TOOL_CONSUMER_KEY`).
7. Validacao opcional de segredo compartilhado legado (`MOODLE_TOOL_SHARED_SECRET`).

## 2. Variaveis de ambiente

Configure no `.env`:

- `MOODLE_LOGIN_ENABLED=true`
- `MOODLE_LOGIN_URL=https://SEU_MOODLE/mod/lti/launch.php?id=ID_DA_ATIVIDADE`
- `MOODLE_TOOL_CONSUMER_KEY=chave-do-consumidor-lti`
- `MOODLE_TOOL_SHARED_SECRET=defina-um-segredo-forte`
- `MOODLE_ALLOWED_EMAIL_DOMAIN=unieuro.edu.br`
- `MOODLE_CPF_FIELD=username`

Observacoes:

1. `MOODLE_LOGIN_URL` deve ser o link da atividade de Ferramenta Externa no Moodle.
2. `MOODLE_TOOL_CONSUMER_KEY` deve ser igual ao `oauth_consumer_key` enviado pelo Moodle.
3. Se quiser desativar o modo legado por parametro customizado, deixe apenas `MOODLE_TOOL_CONSUMER_KEY` configurado.

## 3. Configuracao no Moodle (2024100708.03)

## 3.0. Versao LTI

1. Utilize **LTI 1.0/1.1** para esta integracao.
2. Nao utilize fluxo OIDC/Dynamic Registration (LTI 1.3) neste cenario.

## 3.1. Garantir CPF no username do Moodle

1. Garanta que o campo `username` de cada usuario no Moodle esteja preenchido com CPF (11 digitos).
2. Se houver usuarios legados, normalize para conter apenas digitos.
3. Mantenha esse padrao para toda a comunidade academica Unieuro.

## 3.2. Habilitar Ferramenta Externa

1. Acesse: **Administracao do site > Plugins > Modulos de atividade > Ferramenta externa**.
2. Garanta que o modulo esteja habilitado.
3. Em privacidade, habilite envio de nome e e-mail ao provedor.

## 3.3. Criar atividade Ferramenta Externa

1. Entre no curso/componente em que o acesso AVA sera oferecido.
2. Clique em **Ativar edicao**.
3. Adicione atividade: **Ferramenta externa**.
4. Em **URL da ferramenta**, informe:
   - `https://SEU_UNIEVENTOS/api/ava/launch`
5. Em **Launch container**, selecione "Janela atual" (ou equivalente).
6. Em configuracoes de privacidade da atividade:
   - Compartilhar nome do iniciador: **Sempre**.
   - Compartilhar e-mail do iniciador: **Sempre**.

## 3.4. Parametros customizados (obrigatorio)

Na atividade de Ferramenta Externa, em **Parametros personalizados**, adicione:

- `custom_cpf=$User.username`
- `custom_ava_secret=SEU_MOODLE_TOOL_SHARED_SECRET`

Importante:

1. O valor de `custom_ava_secret` deve ser igual ao `MOODLE_TOOL_SHARED_SECRET` do UniEventos.
2. Como fallback, o UniEventos tambem tenta ler diretamente `username` no payload do launch.
3. Se desejar outro nome de parametro para CPF, altere `MOODLE_CPF_FIELD` no UniEventos.
4. Em LTI 1.0/1.1, caso `custom_ava_secret` nao seja enviado, o UniEventos aceita `oauth_consumer_key` para validacao da credencial compartilhada.

## 3.5. Obter URL para o botao "Entrar com o AVA"

1. Abra a atividade Ferramenta Externa criada.
2. Copie a URL completa de launch da atividade (ex.: `.../mod/lti/launch.php?id=123`).
3. Configure essa URL em `MOODLE_LOGIN_URL` no UniEventos.

## 4. Fluxo final de autenticacao

1. Usuario abre a tela de login do UniEventos.
2. Clica em **Entrar com o AVA**.
3. Sistema redireciona para `MOODLE_LOGIN_URL`.
4. Moodle autentica o usuario e envia launch para `POST /api/ava/launch`.
5. UniEventos recebe CPF + dados do usuario, valida dominio/segredo e cria/login de sessao local.
6. Usuario entra no dashboard do UniEventos.

## 5. Checklist de validacao

1. `MOODLE_LOGIN_ENABLED=true` no ambiente de destino.
2. `MOODLE_LOGIN_URL` aponta para a atividade correta.
3. CPF chega no payload (`username` e/ou `custom_cpf`).
4. Dominio do e-mail do usuario e Unieuro (`@unieuro.edu.br`), se restricao ativa.
5. `oauth_consumer_key` confere com `MOODLE_TOOL_CONSUMER_KEY`.
6. Quando usar modo legado, `custom_ava_secret` confere com `MOODLE_TOOL_SHARED_SECRET`.
7. Usuario entra sem digitar senha no UniEventos via botao AVA.

## 6. Diagnostico rapido

1. Erro 400 "CPF nao recebido do AVA": conferir se o `username` do Moodle contem CPF valido e se o launch envia `username`/`custom_cpf`.
2. Erro 403 "Acesso restrito": conferir dominio do e-mail e envio de e-mail na atividade.
3. Erro 403 "Assinatura invalida": conferir `custom_ava_secret` vs `MOODLE_TOOL_SHARED_SECRET`.
   - Em LTI 1.0/1.1, priorize conferir `oauth_consumer_key` vs `MOODLE_TOOL_CONSUMER_KEY`.
4. Botao nao aparece na tela de login: conferir `MOODLE_LOGIN_ENABLED=true`.
5. Erro/registro com `GET /api/ava/launch?...openid_configuration=...&registration_token=...`:
   - Isso indica tentativa de fluxo LTI 1.3/OIDC dynamic registration.
   - Esta integracao atual do UniEventos foi implementada para **LTI 1.0/1.1** com launch por **POST**.
   - Ajuste a atividade Ferramenta Externa para enviar launch por POST para `https://SEU_UNIEVENTOS/api/ava/launch`.
   - Use o botao do UniEventos (`/api/ava`) como ponto de entrada do usuario final.
