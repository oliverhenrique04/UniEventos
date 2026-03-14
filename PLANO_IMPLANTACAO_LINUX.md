# Plano de Implantação - EuroEventos

## Visão Geral

Este documento descreve o plano de implantação da plataforma **EuroEventos** no servidor Linux existente, integrando-a ao Nginx configurado em `nuted.unieuro.edu.br` como sub-rota `/euroeventos`.

---

## 1. Arquitetura de Implantação

### 1.1 Estrutura Atual do Servidor

O servidor já possui múltiplos serviços rodando sob o mesmo domínio:
- **Agendamento** (Flask) → `/agendamento/` via socket Unix
- **Selo** (Flask) → `/selo/` via socket Unix  
- **Grades** (Node.js) → `/grades/` via HTTP 127.0.0.1:3000
- **Papel Zero** (Vue.js + Laravel) → `/papelzero/` e `/api-papelzero/`
- **CPA** (Laravel) → `/cpa/`

### 1.2 Nova Implantação - EuroEventos

```
┌─────────────────────────────────────────┐
│   Nginx (nuted.unieuro.edu.br)          │
│   ├─ /euroeventos/ → Unix Socket        │
│   └─ /euroeventos/static/ → Arquivos    │
└─────────────────────────────────────────┘
              ↓
    ┌─────────────────────┐
    │  Gunicorn (Python)  │
    │  Flask App          │
    └─────────────────────┘
              ↓
       ┌──────────────┐
       │ PostgreSQL   │
       └──────────────┘
```

---

## 2. Pré-requisitos do Sistema

### 2.1 Software Necessário

```bash
# Python 3.12+
python3 --version

# Virtualenv
pip3 install virtualenv

# Nginx (já instalado)
nginx -v

# PostgreSQL (verificar versão)
psql --version
```

### 2.2 Verificações de Ambiente

- [ ] Python 3.12+ disponível
- [ ] Permissões de escrita em `/var/www/`
- [ ] Acesso sudo para criar serviços systemd
- [ ] PostgreSQL acessível (local ou remoto)
- [ ] Certificado SSL já configurado para o domínio

---

## 3. Clonagem do Repositório e Estrutura de Diretórios

### 3.1 Clonar Repositório Git

```bash
# Navegar para diretório padrão dos projetos
sudo mkdir -p /var/www
sudo chown $USER:$USER /var/www/euroeventos || true

# Criar diretório para o projeto
sudo mkdir -p /var/www/euroeventos
cd /var/www/euroeventos

# Clonar repositório Git (substituir pelo URL correto)
git clone https://github.com/UNIEURO/EuroEventos.git .

# OU clonar de outro repositório:
# git clone https://github.com/oliverhenrique04/UniEventos.git /var/www/euroeventos

# Verificar branch e commit
git branch -a
git log --oneline -5

# Se necessário, checkout para branch específica
# git checkout main
# git pull origin main
```

### 3.2 Estrutura de Diretórios Esperada

Após o clone, a estrutura deve ser:

```bash
/var/www/euroeventos/
├── app/                    # Código fonte da aplicação Flask
│   ├── api/               # Endpoints REST (auth, events, certificates, etc.)
│   ├── services/          # Lógica de negócio
│   ├── models/            # Modelos SQLAlchemy
│   ├── repositories/      # Repositórios de dados
│   ├── templates/         # Templates HTML/Jinja2
│   ├── static/           # Arquivos estáticos
│   │   ├── css/
│   │   ├── js/
│   │   ├── images/
│   │   ├── certificates/  # Certificados gerados
│   │   └── qrcodes/      # QR Codes temporários
│   ├── __init__.py       # Factory da aplicação
│   ├── bootstrap.py      # Inicialização
│   ├── config.py         # Configurações
│   ├── extensions.py     # Extensões Flask
│   └── models.py         # Definições de modelos
├── migrations/            # Migrations Alembic
│   ├── versions/         # Scripts de versão do banco
│   └── alembic.ini       # Configuração Alembic
├── scripts/              # Scripts utilitários
│   └── migrate_sqlite_to_postgres.py
├── tests/                # Testes pytest
├── venv/                 # Ambiente virtual (a ser criado)
├── logs/                 # Logs da aplicação (a ser criado)
├── certs/                # Certificados PDF (a ser criado)
├── qrcodes/              # QR Codes em tempo de execução (a ser criar)
├── run.py                # Ponto de entrada principal
├── worker.py             # Worker RabbitMQ para emails
├── config.py             # Configurações por ambiente
├── requirements.txt      # Dependências Python
├── .env                  # Variáveis de ambiente (a ser criado)
├── .gitignore           # Git ignore
└── README.md            # Documentação do projeto
```

### 3.3 Criar Diretórios Adicionais Necessários

```bash
# Navegar para diretório do projeto
cd /var/www/euroeventos

# Criar diretórios de runtime
mkdir -p logs
mkdir -p certs
mkdir -p qrcodes

# Garantir que subdiretórios de static existam
mkdir -p app/static/css
mkdir -p app/static/js
mkdir -p app/static/images
mkdir -p app/static/certificates
mkdir -p app/static/qrcodes

# Verificar estrutura criada
tree -L 2 -d
```

### 3.4 Configurar Permissões de Diretórios

```bash
# Definir proprietário principal (substituir $USER pelo usuário correto)
sudo chown -R $USER:$USER /var/www/euroeventos

# Permissões gerais de leitura/execução
sudo chmod -R 755 /var/www/euroeventos

# Permissões especiais para diretórios sensíveis

# Logs - apenas owner e group podem escrever
sudo chmod 770 /var/www/euroeventos/logs
sudo chown $USER:www-data /var/www/euroeventos/logs

# Certificados gerados - acessível pelo Nginx
sudo chmod 775 /var/www/euroeventos/certs
sudo chown $USER:www-data /var/www/euroeventos/certs

# QR Codes temporários - alta rotatividade
sudo chmod 777 /var/www/euroeventos/qrcodes
sudo chown $USER:www-data /var/www/euroeventos/qrcodes

# Static files - leitura para www-data (Nginx)
sudo chmod -R 755 /var/www/euroeventos/app/static
sudo chown -R $USER:www-data /var/www/euroeventos/app/static

# Templates - apenas leitura necessária
sudo chmod -R 555 /var/www/euroeventos/app/templates

# Proteger arquivo .env (após criar)
# sudo chmod 600 /var/www/euroeventos/.env
# sudo chown $USER:$USER /var/www/euroeventos/.env

# Verificar permissões
ls -la /var/www/euroeventos/
ls -la /var/www/euroeventos/app/
```

### 3.5 Script Completo de Setup Inicial

Salvar como `setup_directories.sh`:

```bash
#!/bin/bash
# Script de setup inicial para EuroEventos

set -e  # Parar em caso de erro

echo "=== Setup EuroEventos - Diretórios e Permissões ==="

# Variáveis
PROJECT_DIR="/var/www/euroeventos"
OWNER_USER="${SUDO_USER:-$USER}"

# Navegar para diretório
cd $PROJECT_DIR

echo "[1/5] Criando diretórios de runtime..."
mkdir -p logs certs qrcodes
mkdir -p app/static/{css,js,images,certificates,qrcodes}

echo "[2/5] Definindo proprietário..."
sudo chown -R $OWNER_USER:$OWNER_USER $PROJECT_DIR

echo "[3/5] Configurando permissões gerais..."
sudo chmod -R 755 $PROJECT_DIR

echo "[4/5] Configurando permissões específicas..."
sudo chmod 770 $PROJECT_DIR/logs
sudo chmod 775 $PROJECT_DIR/certs
sudo chmod 777 $PROJECT_DIR/qrcodes
sudo chown -R $OWNER_USER:www-data $PROJECT_DIR/{logs,certs,qrcodes,app/static}

echo "[5/5] Verificando estrutura..."
ls -la $PROJECT_DIR/

echo ""
echo "✅ Setup de diretórios concluído!"
echo "Próximo passo: Criar ambiente virtual Python"
```

Executar:
```bash
# Dar permissão de execução
chmod +x setup_directories.sh

# Executar como sudo (para criar em /var/www)
sudo bash setup_directories.sh
```

---

## 4. Configuração do Ambiente Python

### 3.1 Layout Proposto

```bash
/var/www/euroeventos/
├── app/                    # Código fonte da aplicação
│   ├── api/               # Endpoints REST
│   ├── services/          # Lógica de negócio
│   ├── models/            # Modelos de dados
│   ├── templates/         # Templates HTML
│   └── static/           # Arquivos estáticos (CSS, JS, imagens)
├── venv/                  # Ambiente virtual Python
├── logs/
│   ├── euroeventos.log
│   └── error.log
├── certs/                 # Certificados gerados
├── qrcodes/              # QR Codes temporários
├── .env                   # Variáveis de ambiente (PROTEGIDO)
├── gunicorn.conf.py       # Configuração Gunicorn
└── requirements.txt       # Dependências Python
```

### 3.2 Comandos de Criação

```bash
# Criar diretórios principais
sudo mkdir -p /var/www/euroeventos/{app,venv,logs,certs,qrcodes}
sudo chown -R $USER:$USER /var/www/euroeventos
sudo chmod -R 755 /var/www/euroeventos

# Criar subdiretórios da aplicação
cd /var/www/euroeventos/app
mkdir -p api services models templates static/{css,js,images,certificates,qrcodes}
```

---

## 4. Configuração do Ambiente Python

### 4.1 Criar Virtual Environment

```bash
# Navegar para diretório da aplicação
cd /var/www/euroeventos

# Criar venv
python3 -m venv venv

# Ativar
source venv/bin/activate
```

### 4.2 Instalar Dependências

```bash
# Atualizar pip
pip install --upgrade pip setuptools wheel

# Instalar dependências do projeto
pip install -r requirements.txt

# Verificar instalação
pip list
```

### 4.3 Arquivo requirements.txt (Produção)

```txt
Flask==3.0.0
Flask-Login==0.6.3
Flask-Migrate==4.0.5
Flask-SQLAlchemy==3.1.1
psycopg[binary]==3.1.18
gunicorn==21.2.0
Werkzeug==3.0.1
python-dotenv==1.0.0
reportlab==4.0.7
qrcode==7.4.2
Pillow==10.1.0
pika==1.3.2
openpyxl==3.1.2
email-validator==2.1.0.post1
```

---

## 5. Configuração do Banco de Dados

### 5.1 Criar Usuário e Database PostgreSQL

```bash
# Acessar PostgreSQL como usuário postgres
sudo -u postgres psql

# No prompt do PostgreSQL:
CREATE DATABASE euro_eventos_prod;
CREATE USER euroeventos WITH PASSWORD 'SUA_SENHA_SEGURA_AQUI';
GRANT ALL PRIVILEGES ON DATABASE euro_eventos_prod TO euroeventos;
\q
```

### 5.2 Variáveis de Ambiente (.env)

Criar arquivo `/var/www/euroeventos/.env`:

```env
# Configurações Gerais
FLASK_ENV=production
SECRET_KEY=sua-chego-segura-aqui-minimo-32-caracteres

# Banco de Dados PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=euro_eventos_prod
DB_USER=euroeventos
DB_PASSWORD=SUA_SENHA_SEGURA_AQUI

# URL Base (IMPORTANTE para sub-rota)
BASE_URL=https://nuted.unieuro.edu.br/euroeventos

# Email (SMTP)
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=seu-email@unieuro.edu.br
SMTP_PASSWORD=senha-app-office365
DEFAULT_SENDER=UniEventos <noreply@unieuro.edu.br>

# RabbitMQ (opcional - filas de email)
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Configurações de Check-in
CHECKIN_RADIUS_METERS=500

# Moodle Login (opcional)
MOODLE_LOGIN_ENABLED=false
MOODLE_LOGIN_URL=
MOODLE_TOOL_CONSUMER_KEY=
MOODLE_TOOL_SHARED_SECRET=
MOODLE_ALLOWED_EMAIL_DOMAIN=unieuro.edu.br
```

### 5.3 Permissões do Arquivo .env

```bash
# PROTEGER arquivo de credenciais
sudo chown root:www-data /var/www/euroeventos/.env
sudo chmod 640 /var/www/euroeventos/.env
```

---

## 6. Configuração do Gunicorn

### 6.1 Arquivo gunicorn.conf.py

Criar `/var/www/euroeventos/gunicorn.conf.py`:

```python
import multiprocessing
import os

# Bind ao socket Unix (melhor performance que TCP)
bind = "unix:/var/www/euroeventos/euroeventos.sock"

# Número de workers (recomendado: 2-4x núcleos CPU)
workers = multiprocessing.cpu_count() * 2 + 1

# Tipo de worker (sync para Flask padrão)
worker_class = "sync"

# Timeout para workers
timeout = 120

# Limitar tamanho de requisição
request_body_max_size = 10 * 1024 * 1024  # 10MB

# Logs
accesslog = "/var/www/euroeventos/logs/access.log"
errorlog = "/var/www/euroeventos/logs/error.log"
loglevel = "info"

# Daemonizar (opcional - systemd gerencia)
daemon = False

# PID file
pidfile = "/var/www/euroeventos/gunicorn.pid"

# Usuário e grupo
user = "www-data"
group = "www-data"

# Diretório de trabalho
chdir = "/var/www/euroeventos"

# Threads por worker (opcional)
threads = 2

# Conectar workers
connect_timeout = 5
```

---

## 7. Configuração do Systemd

### 7.1 Criar Serviço Gunicorn

Criar arquivo `/etc/systemd/system/euroeventos.service`:

```ini
[Unit]
Description=Gunicorn para EuroEventos Flask App
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=notify

# Usuário e grupo
User=www-data
Group=www-data

# Ambiente
Environment="PATH=/var/www/euroeventos/venv/bin:/usr/local/bin:/usr/bin:/bin"
WorkingDirectory=/var/www/euroeventos

# Executar Gunicorn
ExecStart=/var/www/euroeventos/venv/bin/gunicorn \
    --config /var/www/euroeventos/gunicorn.conf.py \
    run:app

# Reinicialização
Restart=always
RestartSec=10s

# Limites
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

### 7.2 Comandos de Gerenciamento

```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar serviço (iniciar no boot)
sudo systemctl enable euroeventos

# Iniciar serviço
sudo systemctl start euroeventos

# Verificar status
sudo systemctl status euroeventos

# Ver logs
sudo journalctl -u euroeventos -f

# Reiniciar após atualizações
sudo systemctl restart euroeventos
```

---

## 8. Configuração do Nginx

### 8.1 Bloco de Upstream

Adicionar em `/etc/nginx/sites-available/nuted.unieuro.edu.br` (ou arquivo equivalente):

```nginx
# === EUROEVENTOS - Upstream ===
upstream euroeventos_app {
    server unix:/var/www/euroeventos/euroeventos.sock;
}
```

### 8.2 Configurações de Location

Adicionar dentro do bloco `server` (antes de `location /`):

```nginx
# ==========================================================================
# EUROEVENTOS - Plataforma de Gestão Acadêmica
# Acessível em: nuted.unieuro.edu.br/euroeventos
# ==========================================================================

# Redirecionar sem trailing slash para com trailing slash
location = /euroeventos {
    return 301 /euroeventos/;
}

# Arquivos estáticos (performance - Nginx serve diretamente)
location /euroeventos/static/ {
    alias /var/www/euroeventos/app/static/;
    expires 30d;
    add_header Cache-Control "public, no-transform";
    access_log off;
    try_files $uri $uri/ =404;
}

# Aplicação Flask (via Gunicorn + Unix Socket)
location /euroeventos/ {
    # Headers para sub-rota correta
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /euroeventos;
    
    # SCRIPT_NAME para Flask entender a sub-rota
    proxy_set_header SCRIPT_NAME /euroeventos;
    proxy_set_header X-Script-Name /euroeventos;
    
    # Configuração do proxy
    proxy_http_version 1.1;
    proxy_read_timeout 120;
    proxy_connect_timeout 60;
    proxy_send_timeout 120;
    
    # Redirecionamento
    proxy_redirect off;
    
    # Passar para o upstream (Gunicorn)
    proxy_pass http://euroeventos_app;
}

# Certificados gerados (acesso direto opcional)
location /euroeventos/certs/ {
    alias /var/www/euroeventos/certs/;
    expires 7d;
    add_header Cache-Control "public, must-revalidate";
}

# QR Codes temporários
location /euroeventos/qrcodes/ {
    alias /var/www/euroeventos/qrcodes/;
    expires 1h;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

### 8.3 Testar e Recarregar Nginx

```bash
# Testar configuração do Nginx
sudo nginx -t

# Se ok, recarregar Nginx
sudo systemctl reload nginx

# Verificar status
sudo systemctl status nginx
```

---

## 9. Migração de Dados (Opcional)

### 9.1 Se Existir Banco SQLite Legado

```bash
# Navegar para diretório da aplicação
cd /var/www/euroeventos

# Ativar venv
source venv/bin/activate

# Executar script de migração
python scripts/migrate_sqlite_to_postgres.py
```

### 9.2 Aplicar Migrations no PostgreSQL

```bash
# Instalar Flask-CLI
pip install flask-cli

# Configurar variáveis de ambiente
export FLASK_APP=run.py
export FLASK_ENV=production

# Aplicar migrations
flask db upgrade

# Se necessário, criar primeira migration
# flask db init
# flask db migrate -m "Initial migration"
# flask db upgrade
```

---

## 10. Certificado SSL (Let's Encrypt)

### 10.1 Atualizar Certificado Existente

Como o domínio já possui SSL configurado:

```bash
# Verificar certificado atual
sudo ls -la /etc/letsencrypt/live/nuted.unieuro.edu.br/

# O certificado já cobre todo o domínio, não precisa alterar
# Apenas garantir que as configurações do Nginx estejam corretas
```

### 10.2 Se Precisar Renovar

```bash
# Renovar certificados
sudo certbot renew

# Testar renovação automática
sudo certbot renew --dry-run
```

---

## 11. Firewall e Segurança

### 11.1 Configurar UFW (se ativo)

```bash
# Permitir HTTPS (já deve estar permitido)
sudo ufw allow 'Nginx Full'

# Se PostgreSQL for remoto, permitir porta específica
# sudo ufw allow from 192.168.x.x to any port 5432

# Verificar status
sudo ufw status
```

### 11.2 Proteger Arquivos Sensíveis

No Nginx (já existente na configuração):

```nginx
# Proteger arquivos sensíveis
location ~ /\.(git|env|md)$ {
    deny all;
    access_log off;
    log_not_found off;
}
```

### 11.3 Permissões de Diretórios

```bash
# Definir permissões corretas
sudo chown -R www-data:www-data /var/www/euroeventos/
sudo chmod -R 755 /var/www/euroeventos/
sudo chmod -R 770 /var/www/euroeventos/{logs,certs,qrcodes}

# Proteger .env
sudo chmod 640 /var/www/euroeventos/.env
sudo chown root:www-data /var/www/euroeventos/.env
```

---

## 12. Checklist de Implantação

### Pré-Implantação

- [ ] Python 3.12+ instalado e verificado
- [ ] PostgreSQL disponível e acessível
- [ ] Diretórios criados com permissões corretas
- [ ] Virtual environment configurado
- [ ] Dependências instaladas sem erros

### Configuração

- [ ] Arquivo `.env` criado com valores de produção
- [ ] Database PostgreSQL criado com usuário dedicado
- [ ] Gunicorn configurado e testado manualmente
- [ ] Serviço systemd criado e ativo
- [ ] Nginx configurado com upstream e locations
- [ ] Certificado SSL válido para o domínio

### Migração de Dados

- [ ] Migrations aplicadas no banco de dados
- [ ] Dados migrados (se aplicável)
- [ ] Backup do banco antigo realizado

### Testes

- [ ] Serviço Gunicorn iniciado e estável
- [ ] Nginx sem erros de configuração
- [ ] URL `https://nuted.unieuro.edu.br/euroeventos` acessível
- [ ] Login funcional
- [ ] Criação de eventos testada
- [ ] Upload de arquivos funcionando
- [ ] Geração de certificados operante
- [ ] Check-in com QR Code validado

### Monitoramento

- [ ] Logs de acesso sendo escritos
- [ ] Logs de erro monitorados
- [ ] Reinicialização automática configurada
- [ ] Alertas configurados (opcional)

---

## 13. Comandos Úteis para Manutenção

### Verificar Status dos Serviços

```bash
# Gunicorn
sudo systemctl status euroeventos

# Nginx
sudo systemctl status nginx

# PostgreSQL
sudo systemctl status postgresql
```

### Ver Logs em Tempo Real

```bash
# Logs da aplicação
sudo journalctl -u euroeventos -f

# Logs do Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Logs diretos da aplicação
tail -f /var/www/euroeventos/logs/*.log
```

### Reiniciar Serviços Após Atualizações

```bash
# Parar usuários conectados (opcional)
sudo systemctl stop euroeventos

# Fazer deploy do novo código
# ... copiar arquivos, instalar dependências, etc.

# Aplicar migrations se necessário
cd /var/www/euroeventos
source venv/bin/activate
flask db upgrade

# Reiniciar serviço
sudo systemctl restart euroeventos
```

### Backup do Banco de Dados

```bash
# Backup completo
sudo -u postgres pg_dump euro_eventos_prod > /backups/euroeventos_$(date +%Y%m%d).sql

# Restaurar backup
sudo -u postgres psql euro_eventos_prod < /backups/euroeventos_YYYYMMDD.sql
```

---

## 14. Solução de Problemas Comuns

### 14.1 Nginx Retorna 502 Bad Gateway

**Causa:** Gunicorn não está rodando ou socket inacessível

**Solução:**
```bash
# Verificar se Gunicorn está rodando
sudo systemctl status euroeventos

# Verificar permissões do socket
ls -la /var/www/euroeventos/euroeventos.sock

# Reiniciar serviços
sudo systemctl restart euroeventos
sudo systemctl reload nginx
```

### 14.2 Rotas Não Funcionam em Sub-rota

**Causa:** `BASE_URL` ou `SCRIPT_NAME` incorretos

**Solução:**
- Verificar `.env`: `BASE_URL=https://nuted.unieuro.edu.br/euroeventos`
- Verificar headers do Nginx: `proxy_set_header SCRIPT_NAME /euroeventos;`
- No código Flask, usar `url_for()` em vez de URLs hardcoded

### 14.3 Arquivos Estáticos Não Carregam

**Causa:** Permissões ou path incorreto no Nginx

**Solução:**
```bash
# Verificar permissões
ls -la /var/www/euroeventos/app/static/

# Testar acesso direto
curl https://nuted.unieuro.edu.br/euroeventos/static/css/style.css

# Ver logs do Nginx
sudo tail -f /var/log/nginx/error.log
```

### 14.4 Erros de Importação Python

**Causa:** Dependências faltando ou venv incorreto

**Solução:**
```bash
# Ativar venv correto
source /var/www/euroeventos/venv/bin/activate

# Verificar pacotes instalados
pip list

# Reinstalar dependências
pip install -r requirements.txt --force-reinstall
```

---

## 15. Monitoramento e Alertas (Opcional)

### 15.1 Configurar Logrotate

Criar `/etc/logrotate.d/euroeventos`:

```bash
/var/www/euroeventos/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload euroeventos > /dev/null 2>&1 || true
    endscript
}
```

### 15.2 Monitorar Saúde da Aplicação

Criar endpoint de health check em `app/api/health.py`:

```python
from flask import Blueprint, jsonify
import psutil

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'memory': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
        'cpu_percent': psutil.cpu_percent()
    })
```

---

## 16. Referências

- **Documentação Flask:** https://flask.palletsprojects.com/
- **Gunicorn:** https://docs.gunicorn.org/
- **Nginx Python Proxy:** http://nginx.org/en/docs/http/ngx_http_proxy_module.html
- **Systemd Services:** https://www.freedesktop.org/software/systemd/man/systemd.service.html

---

## 17. Contatos e Suporte

Para dúvidas ou problemas durante a implantação:

- **Documentação Interna:** Verificar arquivos `*.md` no repositório
- **Logs:** `/var/www/euroeventos/logs/`
- **Systemd Logs:** `journalctl -u euroeventos`

---

**Versão do Plano:** 1.0  
**Data de Criação:** 14 de Março de 2026  
**Ambiente:** Produção (Linux + Nginx + PostgreSQL)
