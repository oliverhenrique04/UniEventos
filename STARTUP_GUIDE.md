# 🚀 Guia de Inicialização - EuroEventos

## Pré-requisitos

1. ✅ Python 3.12+ instalado
2. ✅ Ambiente virtual ativado
3. ✅ RabbitMQ rodando no servidor (nuted-ia.dev)
4. ✅ Porta 7770 liberada no firewall

---

## 📝 Passo a Passo

### 1️⃣ Ativar Ambiente Virtual

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

---

### 2️⃣ Verificar Configuração do .env

Seu arquivo `.env` deve conter:
```bash
RABBITMQ_URL=amqp://guest:guest@nuted-ia.dev:7770/
```

✅ **Já configurado!** Seu `.env` está correto.

---

### 3️⃣ Testar Conexão com RabbitMQ

Execute este comando para verificar se o RabbitMQ está acessível:

**No PowerShell (com venv ativado):**
```powershell
python -c "import pika; conn = pika.BlockingConnection(pika.URLParameters('amqp://guest:guest@nuted-ia.dev:7770/')); print('✅ RabbitMQ conectado!'); conn.close()"
```

**Se funcionar**, você verá:
```
✅ RabbitMQ conectado!
```

**Se falhar**, verifique:
- RabbitMQ está rodando no servidor?
- Porta 7770 está liberada no firewall?
- IP do servidor está correto?

---

### 4️⃣ Rodar a Aplicação Flask

**Terminal 1 - Iniciar o App:**
```powershell
python run.py
```

A aplicação vai iniciar em: `http://localhost:5000`

---

### 5️⃣ Rodar o Worker (Processador de E-mails)

**Terminal 2 - Iniciar o Worker:**
```powershell
python worker.py
```

Você verá:
```
[*] EuroEventos Worker active. Waiting for messages. Press CTRL+C to stop.
```

O worker fica escutando a fila do RabbitMQ e processando notificações de e-mail.

---

## 🔄 Fluxo Completo

```
┌─────────────────────────────────────────────┐
│  Terminal 1                                 │
│  python run.py                              │
│  → Flask App rodando na porta 5000         │
└─────────────────────────────────────────────┘
              │
              │ Recebe requisições HTTP
              ▼
┌─────────────────────────────────────────────┐
│  Navegador                                  │
│  http://localhost:5000                     │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  Terminal 2                                 │
│  python worker.py                           │
│  → Worker escutando RabbitMQ               │
└─────────────────────────────────────────────┘
              │
              │ Consume mensagens da fila
              ▼
┌─────────────────────────────────────────────┐
│  RabbitMQ (nuted-ia.dev:7770)              │
│  → Fila: email_queue                       │
└─────────────────────────────────────────────┘
```

---

## 🧪 Testes Rápidos

### Testar API Flask:
```powershell
curl http://localhost:5000/
```

### Testar Worker:
O worker deve mostrar mensagens quando receber tarefas do RabbitMQ.

### Monitorar RabbitMQ:
Acesse: `https://nuted-ia.dev/rabbitmq/`
- Login: `guest`
- Senha: `guest`

---

## 🐛 Solução de Problemas

### Erro: "Connection refused" no RabbitMQ
```powershell
# Testar conexão TCP
Test-NetConnection nuted-ia.dev -Port 7770

# Se falhar, verifique:
# 1. RabbitMQ está rodando? → docker ps | grep rabbitmq
# 2. Porta 7770 está aberta no firewall?
# 3. IP/hostname está correto?
```

### Erro: "ModuleNotFoundError: No module 'pika'"
```powershell
# Instalar dependências
pip install -r requirements.txt
```

### Erro: ".env não carregado"
```powershell
# Verificar se .env existe
Get-Content .env

# Se estiver vazio, adicione:
Add-Content .env "RABBITMQ_URL=amqp://guest:guest@nuted-ia.dev:7770/"
```

---

## 📞 Acesso Remoto (Opcional)

Se você quiser acessar a aplicação de outro computador:

1. **Alterar `run.py`**:
```python
app.run(host='0.0.0.0', debug=True, port=5000)
```

2. **Acessar via IP**:
```
http://SEU_IP_LOCAL:5000
```

---

## ✅ Checklist Final

- [ ] Ambiente virtual ativado
- [ ] `.env` configurado com RabbitMQ URL
- [ ] RabbitMQ rodando no servidor (porta 7770)
- [ ] Conexão testada com sucesso
- [ ] Flask app iniciada (`python run.py`)
- [ ] Worker iniciado (`python worker.py`)
- [ ] Navegador acessa `http://localhost:5000`

---

## 🎯 Comandos Rápidos (Cheat Sheet)

```powershell
# Ativar venv
.\venv\Scripts\Activate.ps1

# Rodar app
python run.py

# Rodar worker (outro terminal)
python worker.py

# Testar RabbitMQ
python -c "import pika; print('OK' if pika.BlockingConnection(pika.URLParameters('amqp://guest:guest@nuted-ia.dev:7770/')) else 'FAIL')"

# Verificar portas
netstat -an | findstr "5000"
netstat -an | findstr "7770"
```

---

## 📚 Links Úteis

- **RabbitMQ Management**: https://nuted-ia.dev/rabbitmq/
- **Documentação RabbitMQ**: RABBITMQ_SETUP.md
- **Conexão RabbitMQ**: RABBITMQ_CONNECTION.md
