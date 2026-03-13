# 📧 Email Templates Documentation

## Visão Geral

O EuroEventos utiliza templates HTML profissionais para envio de e-mails transacionais. Todos os templates seguem um design consistente com a identidade visual da UNIEURO.

## 📁 Estrutura de Arquivos

```
app/templates/emails/
├── base.html                           # Template base (estrutura comum)
├── welcome.html                       # E-mail de boas-vindas
├── enrollment_confirmation.html       # Confirmação de inscrição
├── certificate_ready.html             # Certificado de evento disponível
├── institutional_certificate_ready.html # Certificado institucional disponível
└── password_reset.html                # Recuperação de senha (TODO)
```

## 🎨 Templates Disponíveis

### 1. **Welcome Email** (`welcome.html`)
Enviado quando um novo usuário se cadastra na plataforma.

**Variáveis disponíveis:**
- `user_name`: Nome do usuário
- `email`: E-mail do usuário
- `app_url`: URL da aplicação

**Exemplo de uso:**
```python
from app.services.email_template_service import EmailTemplateService

service = EmailTemplateService()
html = service.render_welcome_email(
    user_name="João Silva",
    email="joao@unieuro.edu.br",
    app_url="https://EuroEventos.local"
)
```

---

### 2. **Enrollment Confirmation** (`enrollment_confirmation.html`)
Enviado quando um usuário se inscreve em um evento.

**Variáveis disponíveis:**
- `user_name`: Nome do usuário
- `event_name`: Nome do evento
- `event_date`: Data do evento (formatada)
- `event_time`: Horário do evento
- `event_location`: Local do evento
- `event_type`: Tipo (Curso, Workshop, Palestra, etc.)
- `event_description`: Descrição do evento (opcional)
- `event_details_url`: URL para ver detalhes
- `my_events_url`: URL para ver meus eventos
- `cancel_url`: URL para cancelar inscrição

**Exemplo de uso:**
```python
html = service.render_enrollment_confirmation(
    user_name="Maria Santos",
    event_name="Workshop de Python",
    event_date="15/04/2026",
    event_time="14:00 - 17:00",
    event_location="Auditório Principal",
    event_type="Workshop",
    event_description="Aprenda Python do básico ao avançado...",
    event_details_url="https://EuroEventos.local/events/123",
    my_events_url="https://EuroEventos.local/my-events",
    cancel_url="https://EuroEventos.local/events/123/cancel"
)
```

---

### 3. **Certificate Ready** (`certificate_ready.html`)
Enviado quando um certificado está disponível para download.

**Variáveis disponíveis:**
- `user_name`: Nome do usuário
- `event_name`: Nome do evento
- `event_date`: Data do evento
- `course_hours`: Carga horária (ex: "8 horas")
- `certificate_number`: Número do certificado
- `certificate_download_url`: URL para download
- `view_certificate_url`: URL para visualizar online
- `my_certificates_url`: URL para ver todos certificados

**Exemplo de uso:**
```python
html = service.render_certificate_ready(
    user_name="Carlos Oliveira",
    event_name="Curso de Gestão de Projetos",
    event_date="10/03/2026",
    course_hours="40 horas",
    certificate_number="CERT-2026-001234",
    certificate_download_url="https://EuroEventos.local/certificates/download/567",
    view_certificate_url="https://EuroEventos.local/certificates/view/567",
    my_certificates_url="https://EuroEventos.local/my-certificates"
)
```

---

## 🔧 Integração com RabbitMQ

Os templates são renderizados no `worker.py` antes de enviar o e-mail:

```python
from app.services.email_template_service import EmailTemplateService

def send_email(to, subject, body, attachment_path=None):
    # body já vem como HTML renderizado
    # O worker envia via SMTP
```

**Fluxo completo:**
1. Aplicação Flask publica mensagem no RabbitMQ
2. Worker consome a mensagem
3. Worker renderiza o template (se necessário)
4. Worker envia e-mail via SMTP

---

## 🎨 Personalização

### Cores da Marca UNIEURO
- **Azul Principal**: `#005A9C`
- **Fundo**: `#f4f4f7`
- **Texto Escuro**: `#1a202c`
- **Texto Médio**: `#4a5568`
- **Texto Claro**: `#718096`

### Logo
URL da logo: `https://unieuro.edu.br/wp-content/uploads/2019/02/unieuro2.png`

---

## 📱 Responsividade

Todos os templates são responsivos e se adaptam a dispositivos móveis:
- Largura máxima: 600px
- Padding ajustado para mobile
- Fontes legíveis em telas pequenas

---

## ✅ Melhores Práticas

1. **Sempre use variáveis de template** - Não hardcode valores
2. **Teste em múltiplos clientes** - Outlook, Gmail, Apple Mail
3. **Inclua texto alternativo** - Para imagens
4. **Mantenha o design consistente** - Use as cores da marca
5. **Adicione links de desinscrição** - Para conformidade legal

---

## 🧪 Testando Templates

Para testar um template localmente:

```python
from app.services.email_template_service import EmailTemplateService

service = EmailTemplateService()

# Renderizar template
html = service.render_welcome_email(
    user_name="Teste User",
    email="teste@unieuro.edu.br",
    app_url="http://localhost:5000"
)

# Salvar em arquivo para visualização
with open('test_email.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Template salvo em test_email.html")
```

Abra `test_email.html` no navegador para visualizar.

---

## 🚀 Próximos Passos (TODO)

- [ ] Template de recuperação de senha
- [ ] Template de lembrete de evento
- [ ] Template de confirmação de check-in
- [ ] Template de newsletter
- [ ] Versões em texto plano (para clientes sem HTML)
- [ ] Suporte a múltiplos idiomas (i18n)

---

## 📞 Suporte

Para dúvidas ou alterações nos templates, contate:
- **Equipe**: NUTED Unieuro
- **E-mail**: automacao.nuted.euro@unieuro.edu.br
