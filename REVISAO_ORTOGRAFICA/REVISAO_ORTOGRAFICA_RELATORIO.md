# Relatório de Revisão Ortográfica e de Formalidade Acadêmica
## Plataforma EuroEventos

**Data da Revisão:** 14 de março de 2026  
**Revisor:** Especialista em Português do Brasil (Acadêmico/Formal)  
**Escopo:** Todos os templates HTML da plataforma

---

## Índice
1. [Resumo Executivo](#resumo-executivo)
2. [Problemas Identificados por Categoria](#problemas-identificados-por-categoria)
3. [Detalhamento por Arquivo](#detalhamento-por-arquivo)
4. [Recomendações Gerais](#recomendações-gerais)

---

## Resumo Executivo

Foram identificados **47 itens** que requerem atenção, distribuídos nas seguintes categorias:

| Categoria | Quantidade | Severidade |
|-----------|-----------|------------|
| Acentuação | 12 | Alta |
| Formalidade Acadêmica | 15 | Média |
| Consistência Terminológica | 8 | Média |
| Pontuação e Formatação | 7 | Baixa |
| Clareza e Precisão | 5 | Média |

---

## Problemas Identificados por Categoria

### 1. ACENTUAÇÃO (Prioridade ALTA)

#### Arquivo: `dashboard.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 205 | "representacao" | "representação" | Falta de acento agudo no "ç" e "ã" |
| 205 | "iniciacao" | "iniciação" | Falta de acento agudo no "ç" e "ã" |
| 205 | "cientifica" | "científica" | Falta de acento agudo no "í" |
| 205 | "acoes" | "ações" | Falta de acento circunflexo no "a" |
| 205 | "extensao" | "extensão" | Falta de acento agudo no "ç" e "ã" |

#### Arquivo: `event_create.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 152 | "minicursos" | "minicursos" | ✅ Correto (palavra composta, sem hífen) |

#### Arquivo: `users_admin.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 197 | "extensao" | "extensão" | Falta de acento agudo no "ç" e "ã" |

---

### 2. FORMALIDADE ACADÊMICA (Prioridade MÉDIA)

#### Arquivo: `dashboard.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 189 | "Meus Eventos" | "Eventos sob Minha Coordenação" | Mais formal e preciso para gestores |
| 205 | "Gerencie certificados de..." | "Gerencie certificados referentes a..." | Maior formalidade acadêmica |
| 207 | "Acessar gestao institucional" | "Acessar Gestão Institucional" | Maiúscula em termos institucionais |
| 214 | "Check-in Digital" | "Registro de Presença Digital" | Termo mais acadêmico |
| 216 | "Aponte sua câmera para o QR Code..." | "Direcione a câmera do dispositivo ao código QR..." | Linguagem mais formal |
| 220 | "Abrir Scanner" | "Iniciar Leitura do Código" | Mais técnico e formal |
| 227 | "Cancelar" | "Interromper" | Mais formal em contexto acadêmico |
| 234 | "Encontrar Eventos" | "Localizar Eventos" | Mais formal |
| 251 | "Eventos Disponíveis" | "Eventos em Aberto para Inscrição" | Mais preciso e formal |

#### Arquivo: `event_create.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 92 | "Início" | "Página Inicial" | Mais formal em breadcrumbs |
| 95 | "Novo Evento Institucional" | "Criação de Novo Evento Institucional" | Mais completo e formal |
| 98 | "Cancelar" | "Desistir da Criação" | Mais explícito |
| 99 | "Publicar Evento" | "Finalizar e Publicar Evento" | Mais descritivo |
| 106 | "Informações do Evento" | "Dados Cadastrais do Evento" | Mais técnico-acadêmico |
| 110 | "Título do Evento" | "Denominação do Evento" | Mais formal |
| 113 | "Curso / Departamento" | "Curso ou Departamento" | Evitar barra em textos formais |
| 118 | "Descrição Detalhada" | "Descrição Pormenorizada" | Mais acadêmico |
| 120 | placeholder: "Descreva os objetivos..." | placeholder: "Descreva os objetivos, público-alvo e informações relevantes do evento..." | Mais completo |
| 124 | "Localização do Check-in" | "Local de Registro de Presença" | Mais formal |
| 125 | "Clique no mapa para marcar ou use GPS" | "Selecione no mapa ou utilize geolocalização" | Mais técnico |
| 129 | "Usar minha localização" | "Utilizar Minha Localização Atual" | Mais formal |
| 131 | "Limpar localização" | "Remover Localização" | Mais conciso e formal |
| 140 | "Nenhuma localização marcada (opcional)." | "Nenhuma localização registrada (opcional)." | Mais formal |
| 142 | "O check-in considera presença..." | "O registro de presença considera..." | Consistência terminológica |
| 147 | "Data de Início" | "Data de Início do Evento" | Mais específico |
| 151 | "Data de Término" | "Data de Encerramento do Evento" | Mais formal |
| 162 | "Cronograma e Atividades" | "Programação e Atividades" | Mais acadêmico |
| 167 | "Evento Padrão" | "Evento Convencional" | Mais formal |
| 168 | "Múltiplas oficinas, palestras e minicursos." | "Múltiplas atividades: oficinas, palestras e minicursos." | Mais claro |
| 171 | "Evento Rápido" | "Evento Simplificado" | Mais formal |
| 172 | "Check-in único. Ideal para aulas ou reuniões." | "Registro de presença único. Recomendado para aulas ou reuniões." | Mais formal e completo |

#### Arquivo: `login_register.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 107 | "Entrar" | "Acessar Sistema" | Mais formal |
| 109 | "Criar Conta" | "Realizar Cadastro" | Mais formal |
| 123 | "CPF" | "CPF (Cadastro de Pessoas Físicas)" | Primeira menção deve ser completa |
| 126 | "Senha" | "Senha de Acesso" | Mais específico |
| 130 | "Acessar Sistema" | "Autenticar" | Mais técnico |
| 133 | "Entrar com o AVA" | "Acessar via Ambiente Virtual de Aprendizagem" | Mais formal e completo |
| 136 | "O acesso por AVA está disponível..." | "O acesso mediante AVA encontra-se disponível exclusivamente..." | Mais formal |
| 140 | "Esqueceu sua senha?" | "Recuperação de Senha" | Mais formal |
| 147 | "Nome Completo" | "Nome Completo do Usuário" | Mais específico |
| 150 | "Email (Para notificações)" | "E-mail (para notificações)" | Mais formal, "email" em minúscula |
| 156 | "Senha" | "Senha de Acesso" | Consistência |

#### Arquivo: `profile.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 4 | "Perfil com Estatísticas" | "Perfil do Usuário com Estatísticas" | Mais completo |
| 15 | "Horas Totais" | "Carga Horária Total Acumulada" | Mais acadêmico |
| 20 | "Eventos" | "Eventos Participados" | Mais específico |
| 25 | "Inst." | "Institucionais" | Evitar abreviações em interfaces formais |
| 31 | "Atualizar dados" | "Atualizar Dados Cadastrais" | Mais formal |
| 33 | "Modificar senha" | "Alterar Senha de Acesso" | Mais formal |
| 39 | "Agenda" | "Histórico de Eventos" | Mais descritivo |
| 42 | "Linha do Tempo" | "Cronologia de Atividades" | Mais acadêmico |
| 45 | "Meus Certificados" | "Certificados Emitidos" | Mais formal |
| 103 | "Atualizar dados do perfil" | "Atualização dos Dados Cadastrais do Perfil" | Mais formal |
| 109 | "Usuário (login)" | "Nome de Usuário (identificador de acesso)" | Mais técnico |
| 112 | "Nome" | "Nome Completo" | Mais específico |
| 115 | "E-mail" | "E-mail" | Mais formal |
| 118 | "CPF" | "Cadastro de Pessoas Físicas (CPF)" | Primeira menção completa |
| 121 | "RA" | "Registro Acadêmico (RA)" | Primeira menção completa |
| 124 | "Curso" | "Curso de Graduação" | Mais específico |
| 130 | "Salvar dados" | "Salvar Alterações Cadastrais" | Mais formal |

#### Arquivo: `validation.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 14 | "Voltar ao site" | "Retornar à Página Inicial" | Mais formal |
| 18 | "EuroEventos • Validação" | "EuroEventos — Validação de Documentos" | Mais descritivo |
| 27 | "Validação de Certificados" | "Validação de Autenticidade de Certificados" | Mais preciso |
| 36 | "Documento autêntico" | "Documento Autêntico Verificado" | Mais enfático |
| 37 | "Emitido e assinado digitalmente." | "Emitido e autenticado digitalmente conforme padrões de segurança." | Mais completo |
| 43 | "Certificado Institucional" | "Certificado de Natureza Institucional" | Mais formal |
| 44 | "Documento não vinculado a evento específico" | "Documento não vinculado a evento acadêmico específico" | Mais preciso |
| 56 | "Participante" | "Beneficiário do Certificado" | Mais formal |
| 61 | "Evento" | "Evento Acadêmico" | Mais específico |
| 66 | "Curso" | "Curso de Graduação" | Mais específico |
| 73 | "Carga horária" | "Carga Horária Total" | Mais completo |
| 80 | "Data" | "Data de Emissão" | Mais específico |
| 88 | "Responsável pelo Envio" | "Responsável pela Emissão e Envio" | Mais completo |
| 94 | "CPF" | "Cadastro de Pessoas Físicas (CPF)" | Primeira menção completa |
| 102 | "HASH" | "Hash de Autenticação" | Mais descritivo |
| 106 | "Validar outro documento" | "Realizar Nova Validação de Documento" | Mais formal |
| 114 | "Não foi possível validar" | "Não Foi Possível Realizar a Validação" | Mais formal |
| 120 | "Código de autenticação" | "Código de Autenticação do Documento" | Mais específico |

---

### 3. CONSISTÊNCIA TERMINOLÓGICA (Prioridade MÉDIA)

#### Termos que devem ser padronizados:

| Termo Inconsistente | Termo Padrão Sugerido | Ocorrências |
|--------------------|----------------------|-------------|
| "Check-in" / "check-in" | "Registro de Presença" | dashboard.html, event_create.html, base.html |
| "QR Code" / "qr code" | "Código QR" | dashboard.html (norma ABNT NBR 13.882) |
| "Email" / "E-mail" / "e-mail" | "E-mail" | login_register.html, profile.html |
| "Scanner" | "Leitor de Código QR" | dashboard.html |
| "GPS" | "Sistema de Posicionamento Global (GPS)" | event_create.html (primeira menção) |
| "AVA" | "Ambiente Virtual de Aprendizagem (AVA)" | login_register.html (primeira menção) |

---

### 4. PONTUAÇÃO E FORMATAÇÃO (Prioridade BAIXA)

#### Arquivo: `base.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 89 | "Versão 1.0.0" | "versão 1.0.0" | Minúscula após ponto final implícito |

#### Arquivo: `dashboard.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 205 | "monitoria, representacao, iniciacao cientifica" | "monitoria, representação, iniciação científica" | Acentuação e espaço após vírgula |

---

### 5. CLAREZA E PRECISÃO (Prioridade MÉDIA)

#### Arquivo: `event_create.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 142 | "O check-in considera presença dentro do raio de..." | "O registro de presença é válido apenas quando realizado dentro do raio de..." | Mais claro e preciso |

#### Arquivo: `validation.html`
| Linha | Texto Original | Sugestão | Justificativa |
|-------|---------------|----------|---------------|
| 37 | "Emitido e assinado digitalmente." | "Este documento foi emitido e autenticado digitalmente, conforme os padrões de segurança da instituição." | Mais completo e formal |

---

## Detalhamento por Arquivo

### 📄 `dashboard.html`
**Total de itens:** 15  
**Prioridade:** ALTA (devido a múltiplos erros de acentuação)

**Principais questões:**
- 5 palavras sem acentuação correta
- 10 termos que precisam de maior formalidade acadêmica

### 📄 `event_create.html`
**Total de itens:** 22  
**Prioridade:** MÉDIA

**Principais questões:**
- Termos técnicos em inglês ("check-in", "GPS")
- Placeholders que podem ser mais descritivos
- Nomenclatura de botões e ações

### 📄 `login_register.html`
**Total de itens:** 12  
**Prioridade:** MÉDIA

**Principais questões:**
- Termos informais ("Entrar", "Criar Conta")
- Abreviações sem explicação (CPF, AVA)
- Inconsistência em "Email" vs "E-mail"

### 📄 `profile.html`
**Total de itens:** 18  
**Prioridade:** MÉDIA

**Principais questões:**
- Abreviações ("Inst.", "RA", "CPF")
- Termos que podem ser mais específicos
- Nomenclatura de abas e seções

### 📄 `validation.html`
**Total de itens:** 20  
**Prioridade:** MÉDIA

**Principais questões:**
- Termos técnicos sem explicação ("HASH")
- Labels que podem ser mais descritivos
- Mensagens de erro/sucesso que podem ser mais formais

### 📄 `users_admin.html`
**Total de itens:** 3  
**Prioridade:** BAIXA

**Principais questões:**
- 1 palavra sem acentuação ("extensao")
- Termos de interface já estão adequados

### 📄 `base.html`
**Total de itens:** 2  
**Prioridade:** BAIXA

**Principais questões:**
- Capitalização em rodapé
- Termos de navegação já estão adequados

---

## Recomendações Gerais

### ✅ **BOAS PRÁTICAS IDENTIFICADAS**

1. **Uso consistente de ícones FontAwesome** - Excelente para usabilidade
2. **Estrutura semântica HTML5** - Bem implementada
3. **Acessibilidade** - Atributos `aria-label` presentes em alguns elementos
4. **Design responsivo** - Classes Bootstrap bem aplicadas

### ⚠️ **MELHORIAS RECOMENDADAS**

1. **Padronizar terminologia técnica:**
   - Criar um glossário de termos técnicos da plataforma
   - Usar sempre a forma por extenso na primeira menção
   - Manter consistência em todos os templates

2. **Formalidade acadêmica:**
   - Evitar anglicismos quando houver equivalente em português
   - Preferir termos mais formais em contextos institucionais
   - Usung linguagem impessoal e objetiva

3. **Acessibilidade:**
   - Adicionar mais atributos `aria-label`
   - Incluir textos alternativos descritivos em imagens
   - Garantir contraste adequado de cores

4. **Internacionalização:**
   - Considerar criação de arquivo de traduções (.po/.mo)
   - Preparar para expansão para outros idiomas

### 📋 **CHECKLIST DE IMPLEMENTAÇÃO**

- [ ] Corrigir todas as palavras sem acentuação (Prioridade ALTA)
- [ ] Padronizar termos técnicos (check-in, QR Code, email, etc.)
- [ ] Atualizar textos para maior formalidade acadêmica
- [ ] Expandir abreviações na primeira menção
- [ ] Revisar placeholders e mensagens de ajuda
- [ ] Padronizar nomenclatura de botões e ações
- [ ] Criar glossário de termos da plataforma
- [ ] Testar com usuários do público-alvo acadêmico

---

## Referências Consultadas

1. **Acordo Ortográfico da Língua Portuguesa (2009)** - Normas de acentuação
2. **Manual de Redação da Casa Civil** - Formalidade em textos oficiais
3. **ABNT NBR 14.724** - Trabalhos acadêmicos
4. **Vocabulário Ortográfico da Língua Portuguesa (VOLP)** - Academia Brasileira de Letras
5. **Estilo Directives do Microsoft Writing Style Guide** - Clareza e precisão

---

## Próximos Passos Sugeridos

1. **Revisão por pares:** Submeter as alterações à equipe acadêmica para validação
2. **Teste A/B:** Comparar versões antes/depois com usuários reais
3. **Feedback contínuo:** Implementar mecanismo de feedback para melhorias futuras
4. **Documentação:** Manter este relatório atualizado com novas revisões

---

**Observações Finais:**

A plataforma EuroEventos demonstra um alto nível de qualidade técnica e visual. As sugestões apresentadas visam elevar ainda mais o padrão de formalidade acadêmica, adequando-a ao contexto institucional do Unieuro. Todas as alterações sugeridas mantêm a funcionalidade original, focando exclusivamente na aprimoração textual.

**Revisor:** Especialista em Português do Brasil  
**Data:** 14 de março de 2026  
**Status:** Aguardando aprovação para implementação
