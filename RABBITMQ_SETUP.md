# 🐰 RabbitMQ Configuration Guide

## 📍 Access Points

### 1. **Management UI (Web Interface)**
- **URL**: `https://nuted-ia.dev/rabbitmq/` (via nginx)
- **Username**: `guest`
- **Password**: `guest`
- **Purpose**: Monitor queues, exchanges, bindings, and publish/consume statistics

### 2. **AMQP Protocol (Application Connection)**
- **Protocol**: AMQP (not HTTP/HTTPS)
- **Port**: `7770` (custom port - standard is 5672)
- **Cannot be proxied via HTTPS** - must use direct TCP connection

---

## 🔧 Configuration Options

### Option A: Local Development (Recommended for Windows)

If you're running EuroEventos on Windows and RabbitMQ in Docker:

1. **Update `.env` file**:
```bash
RABBITMQ_URL=amqp://guest:guest@localhost:7770/
```

2. **Start services**:
```bash
# Terminal 1: Start Docker containers
docker-compose up -d rabbitmq

# Terminal 2: Run EuroEventos
python run.py
```

### Option B: Full Docker Setup (Production)

If you want to containerize the entire EuroEventos app:

1. **Update `docker-compose.yml`** - Add EuroEventos service:
```yaml
unиеventos:
  build: .
  container_name: EuroEventos
  environment:
    - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
  depends_on:
    - rabbitmq
  networks:
    - ai-tools
```

2. **Update `.env`**:
```bash
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
```

---

## 🚀 Quick Start

### 1. Start RabbitMQ
```bash
docker-compose up -d rabbitmq
```

### 2. Verify it's running
```bash
docker ps | grep rabbitmq
```

### 3. Access Management UI
Open browser: `https://nuted-ia.dev/rabbitmq/`

### 4. Configure EuroEventos
Add to your `.env`:
```bash
RABBITMQ_URL=amqp://guest:guest@localhost:7770/
```

### 5. Start Worker
```bash
python worker.py
```

---

## 🔍 Understanding the Architecture

```
┌─────────────────────────────────────────────────────┐
│                    EuroEventos                       │
│  ┌──────────────┐     ┌──────────────┐             │
│  │ Flask App    │────▶│ Notification │             │
│  │ (Producer)   │     │ Service      │             │
│  └──────────────┘     └──────────────┘             │
│                           │                         │
│                           ▼                         │
│                    ┌──────────────┐                │
│                    │ worker.py    │                │
│                    │ (Consumer)   │                │
│                    └──────────────┘                │
└─────────────────────────────────────────────────────┘
                      │
                      │ AMQP Protocol (Port 5672)
                      ▼
┌─────────────────────────────────────────────────────┐
│                  RabbitMQ Container                  │
│                                                     │
│  ┌──────────────────────────────────────────┐      │
│  │  Queue: email_queue                      │      │
│  │  DLQ: email_dlq                         │      │
│  └──────────────────────────────────────────┘      │
│                                                     │
│  📊 Management UI: Port 15672 (via nginx)          │
│     → https://nuted-ia.dev/rabbitmq/               │
└─────────────────────────────────────────────────────┘
```

---

## ⚠️ Important Notes

### Why NOT `https://nuted-ia.dev/rabbitmq` for AMQP?

The RabbitMQ **AMQP protocol** (used by applications) is a binary protocol that:
- ❌ Cannot be proxied via HTTP/HTTPS
- ❌ Doesn't work through nginx reverse proxy
- ✅ Must use direct TCP connection on port 5672

The **Management UI** (web interface):
- ✅ Works via HTTPS through nginx
- ✅ Accessible at `https://nuted-ia.dev/rabbitmq/`

### Security Considerations

For production, consider:
1. Change default credentials (`guest/guest`)
2. Use SSL/TLS for AMQP connections
3. Restrict network access to port 5672
4. Enable RabbitMQ authentication mechanism

---

## 🧪 Testing Connection

### Test from EuroEventos (Python)
```python
import pika

connection = pika.BlockingConnection(pika.URLParameters(
    'amqp://guest:guest@localhost:7770/'
))
print("✅ Connected to RabbitMQ!")
connection.close()
```

### Test Worker
```bash
python worker.py
# Should show: " [*] EuroEventos Worker active. Waiting for messages."
```

---

## 📝 Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `RABBITMQ_URL` | Connection string for RabbitMQ (custom port 7770) | `amqp://guest:guest@localhost:7770/` |
| `RABBITMQ_DEFAULT_USER` | Default username (Docker) | `guest` |
| `RABBITMQ_DEFAULT_PASS` | Default password (Docker) | `guest` |

---

## 🔗 Useful Links

- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [AMQP Protocol](https://www.rabbitmq.com/protocols.html#amqp-overview)
- [Management Plugin](https://www.rabbitmq.com/management.html)
