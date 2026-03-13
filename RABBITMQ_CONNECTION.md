# RabbitMQ Connection Guide for EuroEventos

## 🔌 Connection URL

### For Local Development (Windows):
```bash
RABBITMQ_URL=amqp://guest:guest@localhost:7770/
```

### For Remote Server (nuted-ia.dev):
```bash
RABBITMQ_URL=amqp://guest:guest@nuted-ia.dev:7770/
```

## ⚠️ Important Notes

### Why NOT `https://nuted-ia.dev/rabbitmq` for AMQP?

The RabbitMQ **AMQP protocol** is a binary TCP protocol that:
- ❌ Cannot work through HTTP/HTTPS proxy
- ❌ Nginx doesn't support AMQP in HTTP context
- ✅ Must use direct TCP connection on port 7770

### What Works:

| Purpose | URL | Protocol |
|---------|-----|----------|
| **Application Connection** | `amqp://guest:guest@nuted-ia.dev:7770/` | AMQP (TCP) |
| **Management UI** | `https://nuted-ia.dev/rabbitmq/` | HTTPS |

## 🚀 Quick Setup

1. **Update your `.env` file**:
```bash
RABBITMQ_URL=amqp://guest:guest@nuted-ia.dev:7770/
```

2. **Ensure port 7770 is open in firewall**

3. **Test connection**:
```python
import pika

try:
    connection = pika.BlockingConnection(pika.URLParameters(
        'amqp://guest:guest@nuted-ia.dev:7770/'
    ))
    print("✅ Successfully connected to RabbitMQ!")
    connection.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

## 🔍 Troubleshooting

### Connection Refused?
- Check if RabbitMQ is running: `docker ps | grep rabbitmq`
- Verify port 7770 is open: `telnet nuted-ia.dev 7770`
- Check firewall rules allow port 7770

### Authentication Error?
- Verify credentials in docker-compose.yml
- Default: `guest` / `guest`

## 📊 Architecture

```
EuroEventos App
    │
    │ TCP Connection (Port 7770)
    ▼
nuted-ia.dev:7770
    │
    │ Docker Port Mapping
    ▼
RabbitMQ Container (Port 5672)
    │
    ├─ AMQP Protocol ← Application connects here
    └─ Management UI ← Accessible via https://nuted-ia.dev/rabbitmq/
```
