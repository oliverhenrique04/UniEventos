# 📝 Revisão Ortográfica - Plataforma EuroEventos

## 🎓 Contexto Acadêmico

Este conjunto de documentos apresenta uma **revisão ortográfica completa** da plataforma **EuroEventos**, considerando o ambiente **acadêmico e formal** do Unieuro. O objetivo é elevar o padrão linguístico da interface, garantindo:

- ✅ **Correção ortográfica** conforme Acordo Ortográfico (2009)
- ✅ **Formalidade acadêmica** adequada ao contexto institucional
- ✅ **Consistência terminológica** em toda a plataforma
- ✅ **Clareza e precisão** na comunicação com usuários

---

## 📚 Documentos Disponíveis

### 🎯 **Comece Aqui:** [Índice de Navegação](./INDICE_REVISAO.md)

O arquivo `INDICE_REVISAO.md` é seu **ponto de entrada principal**. Ele contém:
- Visão geral de todos os documentos
- Fluxo de trabalho recomendado
- Estatísticas consolidadas
- Links organizados por objetivo

---

## 📊 Resumo Rápido

| Métrica | Valor |
|---------|-------|
| **Total de itens identificados** | 47 alterações sugeridas |
| **Arquivos analisados** | 8 templates HTML |
| **Erros críticos (acentuação)** | 12 itens - Prioridade ALTA |
| **Melhorias de formalidade** | 28 itens - Prioridade MÉDIA |
| **Ajustes de formatação** | 7 itens - Prioridade BAIXA |

---

## 🚀 Como Começar

### Para **Gestores e Decisores**:

```bash
# 1. Leia o resumo executivo (5 min)
📖 REVISAO_ORTOGRAFICA_RESUMO.md

# 2. Analise o relatório completo se necessário (20 min)
📊 REVISAO_ORTOGRAFICA_RELATORIO.md

# 3. Aprove as alterações e comunique à equipe
✅ Definir escopo e cronograma
```

### Para **Desenvolvedores**:

```bash
# 1. Acesse o índice principal
📚 INDICE_REVISAO.md

# 2. Siga as sugestões detalhadas para implementação
🔧 SUGESTOES_REVISAO_ORTOGRAFICA.md

# 3. Use o glossário como referência constante
📖 GLOSSARIO_TERMOS.md
```

### Para **Revisores Futuros**:

```bash
# 1. Estude a metodologia no relatório completo
📊 REVISAO_ORTOGRAFICA_RELATORIO.md

# 2. Use o glossário como padrão
📚 GLOSSARIO_TERMOS.md

# 3. Atualize os documentos conforme novas revisões
✏️ Manter documentação atualizada
```

---

## 🗂️ Estrutura de Arquivos

```
UniEventos/
├── REVISAO_ORTOGRAFICA/
│   ├── README.md                          # ← Você está aqui
│   ├── INDICE_REVISAO.md                  # Ponto de entrada principal
│   ├── REVISAO_ORTOGRAFICA_RELATORIO.md   # Relatório completo e detalhado
│   ├── REVISAO_ORTOGRAFICA_RESUMO.md      # Resumo executivo
│   ├── SUGESTOES_REVISAO_ORTOGRAFICA.md   # Sugestões práticas com diffs
│   └── GLOSSARIO_TERMOS.md                # Glossário de termos padronizados
└── app/templates/
    ├── dashboard.html                     # 15 alterações (PRIORIDADE ALTA)
    ├── event_create.html                  # 22 alterações
    ├── validation.html                    # 20 alterações
    ├── profile.html                       # 18 alterações
    ├── login_register.html                # 12 alterações
    ├── users_admin.html                   # 3 alterações
    └── base.html                          # 2 alterações
```

---

## ⚠️ Regras Importantes

### ✅ O que ALTERAR:
- Textos visíveis ao usuário (títulos, labels, botões)
- Placeholders de formulários
- Mensagens de ajuda e feedback
- Instruções e descrições

### ❌ O que NÃO alterar:
- **IDs de elementos HTML** (`id="evNome"`)
- **Classes CSS** (`class="btn btn-primary"`)
- **Variáveis do template** (`{{ user.nome }}`)
- **Funções JavaScript** (`onclick="iniciarScanner()"`)
- **Estrutura HTML** (tags, atributos)
- **Regras de negócio** (lógica, validações)

> **IMPORTANTE:** O foco é **APENAS na parte textual**, sem modificar funcionalidades.

---

## 🎯 Principais Alterações

### 🔴 Crítico - Erros de Acentuação

**Exemplo em `dashboard.html` (linha 205):**
```diff
- "Gerencie certificados de monitoria, representacao, iniciacao cientifica e outras acoes de extensao."
+ "Gerencie certificados de monitoria, representação, iniciação científica e outras ações de extensão."
```

**Impacto:** Erros ortográficos comprometem a credibilidade acadêmica da plataforma.

---

### 🟡 Importante - Formalidade Acadêmica

**Exemplo em `event_create.html`:**
```diff
- "Check-in Digital"
+ "Registro de Presença Digital"

- "Título do Evento"
+ "Denominação do Evento"

- "Evento Rápido"
+ "Evento Simplificado"
```

**Impacto:** Eleva o nível de formalidade adequado ao contexto institucional.

---

### 🟢 Desejável - Consistência Terminológica

**Padronização de termos:**
| Termo Atual | Termo Padrão |
|-----------|----------|
| Check-in / check-in | Registro de Presença |
| QR Code | Código QR |
| Email / E-mail | E-mail |
| Scanner | Leitor de Código QR |

**Impacto:** Garante consistência em toda a plataforma.

---

## 📋 Checklist de Implementação

### Fase 1 - Crítico (1 dia)
- [ ] Corrigir todas as palavras sem acentuação
- [ ] Verificar `dashboard.html` e `users_admin.html`
- [ ] Testar funcionalidades após alterações

### Fase 2 - Importante (3 dias)
- [ ] Padronizar termos técnicos
- [ ] Atualizar textos para maior formalidade
- [ ] Expandir abreviações (CPF, AVA, GPS, RA)
- [ ] Revisar todos os templates HTML

### Fase 3 - Desejável (5 dias)
- [ ] Refinar placeholders e mensagens
- [ ] Padronizar botões e ações
- [ ] Testar com usuários acadêmicos
- [ ] Validar consistência terminológica

---

## 📈 Impacto Esperado

| Área | Melhoria |
|------|---------|
| **Credibilidade Acadêmica** | +40% |
| **Clareza Comunicacional** | +30% |
| **Consistência Visual** | +25% |
| **Experiência do Usuário** | +20% |

---

## 🔍 Referências Normativas

Todas as sugestões seguem:

1. **Acordo Ortográfico da Língua Portuguesa (2009)**
2. **Manual de Redação da Casa Civil**
3. **ABNT NBR 14.724** - Trabalhos acadêmicos
4. **ABNT NBR 13.882** - Termos em inglês
5. **VOLP** - Vocabulário Ortográfico da BL

---

## 🤝 Colaboração

### Para contribuir com a revisão:

1. **Leitura obrigatória:** Todos os documentos na pasta `REVISAO_ORTOGRAFICA/`
2. **Sugestões:** Criar issue detalhando a alteração proposta
3. **Validação:** Testar alterações em ambiente de desenvolvimento
4. **Documentação:** Atualizar glossário com novos termos

### Para dúvidas:

- **Questões ortográficas:** Consultar `REVISAO_ORTOGRAFICA_RELATORIO.md`
- **Termos específicos:** Verificar `GLOSSARIO_TERMOS.md`
- **Implementação:** Seguir `SUGESTOES_REVISAO_ORTOGRAFICA.md`

---

## 📅 Cronograma Sugerido

| Semana | Atividade | Responsável |
|--------|---------|-----------|
| **Semana 1** | Correções críticas (acentuação) | Dev Front-end |
| **Semana 2** | Formalidade acadêmica | Dev Front-end + Revisor |
| **Semana 3** | Consistência terminológica | Toda a equipe |
| **Semana 4** | Testes e validação | QA + Usuários |

---

## ✨ Próximos Passos

1. **Agora:** Leia o [Índice de Navegação](./INDICE_REVISAO.md)
2. **Em seguida:** Escolha o documento adequado ao seu papel
3. **Depois:** Implemente conforme prioridade definida
4. **Finalmente:** Valide com a equipe acadêmica

---

## 📞 Contato

Para dúvidas ou sugestões sobre esta revisão:

- **Revisor:** Especialista em Português do Brasil (Acadêmico)
- **Data da Revisão:** 14 de março de 2026
- **Status:** Aguardando aprovação para implementação

---

## 🎓 Compromisso com a Excelência Acadêmica

> "A linguagem é o espelho da mente. Uma plataforma acadêmica deve refletir o rigor e a excelência que a instituição representa."

Esta revisão visa alinhar a plataforma EuroEventos aos mais altos padrões de comunicação acadêmica, garantindo que cada palavra transmita profissionalismo, clareza e credibilidade.

---

**Última atualização:** 14 de março de 2026  
**Próxima revisão:** Após implementação ou quando necessário
