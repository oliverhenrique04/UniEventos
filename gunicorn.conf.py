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
request_body_max_size = 20 * 1024 * 1024  # 20MB

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
threads = 4

# Conectar workers
connect_timeout = 5