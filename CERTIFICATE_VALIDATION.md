# ✅ Validação de Certificados - Sistema Completo

## 📋 Visão Geral

O sistema de validação de certificados foi atualizado para suportar **ambos os tipos**:
1. **Certificados de Eventos** (vinculados a cursos/workshops)
2. **Certificados Institucionais** (reconhecimentos, premiações, etc.)

## 🔗 URL de Validação

```
https://EuroEventos.local/validar/{HASH}
```

Onde `{HASH}` é o código de 16 caracteres impresso no certificado.

## 🎯 Diferenças na Validação

| Campo | Certificado de Evento | Certificado Institucional |
|-------|---------------------|-------------------------|
| **Tipo** | `evento` | `institucional` |
| **Título** | Nome do evento | Título do certificado |
| **Categoria/Curso** | Curso vinculado ao evento | Categoria (Reconhecimento, Premiação) |
| **Carga Horária** | ✅ Exibida (ex: 40h) | ❌ Não exibida |
| **Data** | Data do evento | Data de emissão |
| **Signatário** | ❌ Não exibido | ✅ Exibido (autoridade signatária) |
| **CPF** | ✅ Exibido | ✅ Exibido |
| **Badge Visual** | Padrão (verde) | Amarelo com ícone de prêmio |

## 🔍 Fluxo de Validação

```
1. Usuário acessa /validar/{HASH}
   │
   ├─▶ 2. Busca no InstitutionalCertificateRecipient
   │      │
   │      ├─▶ Encontrado? → Renderiza template institucional
   │      │         - Mostra badge amarelo
   │      │         - Exibe signatário
   │      │         - Não exibe carga horária
   │      │
   │      └─▶ Não encontrado
   │
   ├─▶ 3. Busca no Enrollment (eventos)
   │      │
   │      ├─▶ Encontrado? → Renderiza template de evento
   │      │         - Mostra badge padrão
   │      │         - Exibe carga horária
   │      │         - Não exibe signatário
   │      │
   │      └─▶ Não encontrado → Erro "Certificado não encontrado"
   │
   └─▶ 4. Renderiza validation.html com dados apropriados
```

## 📊 Dados Exibidos

### Certificado de Evento:
```
✅ Participante: João Silva
✅ Evento: Workshop de Python
✅ Curso: Ciência da Computação
✅ Carga Horária: 8h
✅ Data: 15/04/2026
✅ CPF: 123.456.789-00
✅ HASH: ABCD-1234-EFGH-5678
```

### Certificado Institucional:
```
⚠️ Badge: "Certificado Institucional"
✅ Participante: Maria Santos
✅ Título: Certificado de Reconhecimento Profissional
✅ Categoria: Reconhecimento
✅ Data: 13/03/2026
✅ Signatário: Prof. Dr. João Santos - Diretor do NUTED
✅ CPF: 987.654.321-00
✅ HASH: XYZW-9876-LKJI-5432
```

## 🎨 Elementos Visuais

### Badge de Certificado Institucional
```html
<div class="alert alert-warning border-0 rounded-4 mb-4">
    <i class="fa-solid fa-award fs-3"></i>
    <div>
        <div class="fw-bold">Certificado Institucional</div>
        <div class="small">Documento não vinculado a evento específico</div>
    </div>
</div>
```

### Signatário (apenas institucional)
```html
<div class="details-row mt-3 pt-3 border-top">
    <div class="details-label text-warning">
        <i class="fa-solid fa-signature me-2"></i>Signatário
    </div>
    <div class="details-value fw-bold">{{ signatario }}</div>
</div>
```

## 🔧 Código Backend (routes.py)

```python
@bp.route('/validar/<cert_hash>')
def validar_hash(cert_hash):
    """Validates both event and institutional certificates."""
    
    # 1. Try institutional certificate first
    institutional_recipient = InstitutionalCertificateRecipient.query.filter_by(
        cert_hash=cert_hash
    ).first()
    
    if institutional_recipient:
        cert = institutional_recipient.certificate
        return render_template('validation.html',
            success=True,
            certificado_tipo='institucional',
            nome=institutional_recipient.nome,
            evento=cert.titulo,
            data=format_date(cert.data_emissao),
            horas=None,
            curso=cert.categoria,
            signatario=cert.signer_name,
            cpf=institutional_recipient.cpf,
            hash=cert_hash
        )
    
    # 2. Try event certificate
    enrollment = Enrollment.query.filter_by(cert_hash=cert_hash).first()
    if not enrollment:
        return render_template('validation.html', 
            erro="Certificado não encontrado ou inválido.")
    
    # Calculate hours, get event details...
    return render_template('validation.html',
        success=True,
        certificado_tipo='evento',
        nome=user.nome,
        evento=event.nome,
        data=event_date,
        horas=total_hours,
        curso=curso,
        signatario=None,
        cpf=enrollment.user_cpf,
        hash=cert_hash
    )
```

## 🧪 Testes

### Testar Validação de Certificado Institucional:

1. **Gerar um certificado institucional** (via interface administrativa)
2. **Obter o HASH** do certificado
3. **Acessar**: `https://EuroEventos.local/validar/{HASH}`
4. **Verificar**:
   - ✅ Badge amarelo aparece
   - ✅ Signatário é exibido
   - ✅ Carga horária NÃO aparece
   - ✅ CPF é exibido
   - ✅ Categoria aparece (não "Curso")

### Testar Validação de Certificado de Evento:

1. **Gerar certificado de evento** (via sistema normal)
2. **Obter o HASH** do certificado
3. **Acessar**: `https://EuroEventos.local/validar/{HASH}`
4. **Verificar**:
   - ✅ Badge padrão (verde)
   - ✅ Signatário NÃO aparece
   - ✅ Carga horária é exibida
   - ✅ CPF é exibido
   - ✅ "Curso" aparece

## 📝 Arquivos Modificados

### Backend:
- ✅ `app/main/routes.py` - Rota `/validar/<cert_hash>` atualizada
  - Suporte a ambos os tipos de certificado
  - Lógica separada para cada tipo
  - Dados específicos por tipo

### Frontend:
- ✅ `app/templates/validation.html` - Template de validação
  - Badge condicional para certificados institucionais
  - Campos condicionais (signatário, carga horária)
  - Labels dinâmicos ("Evento" vs "Título", "Curso" vs "Categoria")

## 🔐 Segurança

- ✅ HASH único por certificado (MD5/SHA)
- ✅ Validação via banco de dados
- ✅ Página pública (não requer login)
- ✅ Dados mínimos exibidos (apenas o necessário para validação)

## 🚀 Integração com E-mails

Os e-mails de certificados incluem link de validação:

### Template Institucional:
```jinja2
<a href="{{ validation_url }}">✓ Validar certificado</a>
```

Onde `validation_url` é gerado como:
```python
validation_url = f"{BASE_URL}/validar/{certificate_number}"
```

## 📞 Suporte

Problemas com validação?
- Verifique se o HASH está correto (16 caracteres)
- Confirme que o certificado foi emitido
- Contate: automacao.nuted.euro@unieuro.edu.br

---

**Data da Implementação:** 13/03/2026  
**Versão:** 1.0.0  
**Status:** ✅ Funcional e Testado
